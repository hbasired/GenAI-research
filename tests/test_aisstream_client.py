import asyncio
import json
import socket

import pytest
from aisstream_mock import VALID_KEY, MockAisStream, Script, position_report, ship_static

from tracktrust.ingest.aisstream import (
    AisStreamClient,
    AuthError,
    build_subscription,
    check_key,
    classify,
    describe_subscription,
    looks_like_key_error,
)

BOX = [[22.0, 47.5], [30.5, 62.5]]


def test_build_subscription_shape():
    sub = build_subscription("k", [BOX], mmsi=["470123456"], message_types=["PositionReport"])
    assert sub == {
        "APIKey": "k",
        "BoundingBoxes": [[[22.0, 47.5], [30.5, 62.5]]],
        "FiltersShipMMSI": ["470123456"],
        "FilterMessageTypes": ["PositionReport"],
    }
    assert "APIKey" not in describe_subscription(sub)


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"boxes": []}, "At least one"),
        ({"boxes": [[[95, 0], [96, 1]]]}, "outside"),
        ({"boxes": [[[1, 2, 3], [4, 5]]]}, "must be"),
        ({"boxes": [BOX], "mmsi": ["123"]}, "9-digit"),
        ({"boxes": [BOX], "message_types": ["Nope"]}, "Unknown"),
    ],
)
def test_build_subscription_validation(kwargs, message):
    with pytest.raises(ValueError, match=message):
        build_subscription("k", **kwargs)


def test_classify():
    assert classify(b'{"MessageType":"PositionReport"}')[2] == "ais"
    assert classify('{"error":"Api Key Is Not Valid"}')[2] == "error"
    assert classify('{"Type":"SubscriptionConfirmation"}')[2] == "control"
    assert classify("not json")[2] == "invalid"
    assert classify("[1,2]")[2] == "invalid"
    text, obj, kind = classify(b"\xff\xfe{")
    assert kind == "invalid" and obj is None


def test_key_error_detection():
    assert looks_like_key_error("Api Key Is Not Valid")
    assert looks_like_key_error("invalid api key")
    assert not looks_like_key_error("Service temporarily unavailable")
    assert not looks_like_key_error("bounding box invalid")


async def _collect(client, stop, n, timeout=10):
    frames = []

    async def run():
        async for frame in client.stream(stop):
            frames.append(frame)
            if len(frames) >= n:
                stop.set()

    await asyncio.wait_for(run(), timeout)
    return frames


async def test_stream_sends_subscription_and_yields_frames():
    async with MockAisStream(default=Script(messages=[position_report(), ship_static()], then="open")) as server:
        events = []
        client = AisStreamClient(VALID_KEY, [BOX], url=server.url, on_event=lambda e, **f: events.append((e, f)))
        frames = await _collect(client, asyncio.Event(), 2)
    assert [f.message_type for f in frames] == ["PositionReport", "ShipStaticData"]
    assert all(f.kind == "ais" and f.conn == 1 for f in frames)
    assert server.subscriptions[0] == {"APIKey": VALID_KEY, "BoundingBoxes": [BOX]}
    names = [e for e, _ in events]
    assert names[:3] == ["connecting", "subscribed", "first_message"]
    assert all(VALID_KEY not in json.dumps(f) for _, f in events)


async def test_text_frames_are_accepted_too():
    async with MockAisStream(send_text_frames=True) as server:
        client = AisStreamClient(VALID_KEY, [BOX], url=server.url)
        frames = await _collect(client, asyncio.Event(), 1)
    assert frames[0].kind == "ais"


async def test_reconnects_after_server_closes(monkeypatch):
    monkeypatch.setattr(AisStreamClient, "_backoff", lambda self, failures: 0.05)
    scripts = [Script(messages=[position_report(second=1)], then="close"),
               Script(messages=[position_report(second=2)], then="abort")]
    async with MockAisStream(scripts=scripts) as server:
        events = []
        client = AisStreamClient(VALID_KEY, [BOX], url=server.url, on_event=lambda e, **f: events.append((e, f)))
        frames = await _collect(client, asyncio.Event(), 3)
    assert [f.conn for f in frames] == [1, 2, 3]
    assert server.connections == 3
    drops = [f["reason"] for e, f in events if e == "disconnected"]
    assert len(drops) == 3 and drops[-1] == "stopped"
    assert all(r.startswith("connection closed") for r in drops[:2])
    assert len(server.subscriptions) == 3


async def test_stall_triggers_reconnect(monkeypatch):
    monkeypatch.setattr(AisStreamClient, "_backoff", lambda self, failures: 0.05)
    scripts = [Script(messages=[position_report()], then="stall")]
    async with MockAisStream(scripts=scripts) as server:
        events = []
        client = AisStreamClient(VALID_KEY, [BOX], url=server.url, stall_timeout=0.5,
                                 on_event=lambda e, **f: events.append((e, f)))
        frames = await _collect(client, asyncio.Event(), 2)
    assert [f.conn for f in frames] == [1, 2]
    assert "stalled" in [e for e, _ in events]


async def test_rejected_key_raises_auth_error():
    async with MockAisStream() as server:
        client = AisStreamClient("wrong-key", [BOX], url=server.url)
        with pytest.raises(AuthError, match="Not Valid"):
            await _collect(client, asyncio.Event(), 1)
    assert server.connections == 1


async def test_temporary_server_errors_never_end_the_stream(monkeypatch):
    """An outage answered with errors must not stop a long recording; only a rejected key does."""
    monkeypatch.setattr(AisStreamClient, "_backoff", lambda self, failures: 0.01)
    scripts = [Script(messages=[], then="error")] * 8
    async with MockAisStream(scripts=scripts, default=Script(messages=[position_report()], then="open")) as server:
        client = AisStreamClient(VALID_KEY, [BOX], url=server.url)
        frames = await _collect(client, asyncio.Event(), 9)
    assert [f.kind for f in frames] == ["error"] * 8 + ["ais"]
    assert server.connections == 9


async def test_server_error_after_data_reconnects(monkeypatch):
    monkeypatch.setattr(AisStreamClient, "_backoff", lambda self, failures: 0.05)
    scripts = [Script(messages=[position_report()], then="error")]
    async with MockAisStream(scripts=scripts) as server:
        client = AisStreamClient(VALID_KEY, [BOX], url=server.url)
        frames = await _collect(client, asyncio.Event(), 3)
    assert frames[0].kind == "ais" and frames[1].kind == "error" and frames[2].conn == 2


async def test_stop_during_backoff_returns_promptly(monkeypatch):
    monkeypatch.setattr(AisStreamClient, "_backoff", lambda self, failures: 30.0)
    async with MockAisStream(default=Script(messages=[position_report()], then="close")) as server:
        stop = asyncio.Event()
        client = AisStreamClient(VALID_KEY, [BOX], url=server.url)

        async def consume():
            async for _ in client.stream(stop):
                asyncio.get_running_loop().call_later(0.2, stop.set)

        await asyncio.wait_for(consume(), timeout=5)


def test_backoff_grows_and_is_capped():
    client = AisStreamClient(VALID_KEY, [BOX], max_backoff=60)
    assert all(1.0 <= client._backoff(1) <= 2.0 for _ in range(100))
    assert all(16.0 <= client._backoff(5) <= 32.0 for _ in range(100))
    assert all(30.0 <= client._backoff(50) <= 60.0 for _ in range(100))


async def test_check_key_ok():
    async with MockAisStream(default=Script(messages=[position_report(), ship_static()], then="open")) as server:
        result = await check_key(VALID_KEY, [BOX], url=server.url, timeout=2, max_messages=2)
    assert result.ok and result.status == "ok"
    assert result.messages == 2 and result.vessels == 1
    assert result.sample["MMSI"] == 470123456


async def test_check_key_rejected():
    async with MockAisStream() as server:
        result = await check_key("bad", [BOX], url=server.url, timeout=2)
    assert result.status == "rejected" and "Not Valid" in result.detail


async def test_check_key_no_data():
    async with MockAisStream(default=Script(messages=[], then="open")) as server:
        result = await check_key(VALID_KEY, [BOX], url=server.url, timeout=0.5)
    assert result.status == "no_data"


async def test_check_key_network_error():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    result = await check_key(VALID_KEY, [BOX], url=f"ws://127.0.0.1:{port}", timeout=2)
    assert result.status == "network_error"
