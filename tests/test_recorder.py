import asyncio
import gzip
import json
import logging
from datetime import datetime, timedelta, timezone

import pytest
from aisstream_mock import VALID_KEY, MockAisStream, Script, position_report, ship_static

from tracktrust.ingest.aisstream import AisStreamClient
from tracktrust.recorder import EXIT_OK, EXIT_REJECTED, Recorder
from tracktrust.storage.layout import FeedLayout
from tracktrust.storage.lock import AlreadyRunning, RecorderLock


def all_text_under(path):
    chunks = []
    for f in path.rglob("*"):
        if f.is_file():
            data = f.read_bytes()
            if f.name.endswith(".gz"):
                data = gzip.decompress(data)
            chunks.append(data.decode("utf-8", errors="replace"))
    return "\n".join(chunks)


async def test_records_messages_and_never_writes_the_key(settings, caplog):
    caplog.set_level(logging.DEBUG)
    messages = [position_report(mmsi=470000000 + i, second=i) for i in range(20)] + [ship_static()]
    async with MockAisStream(default=Script(messages=messages, then="open")) as server:
        recorder = Recorder(settings, VALID_KEY, url=server.url, duration_s=1.0, install_signal_handlers=False)
        code = await asyncio.wait_for(recorder.run(), timeout=20)
    assert code == EXIT_OK
    layout = FeedLayout(settings.aisstream_dir)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    files = layout.raw_files(today)
    assert len(files) >= 1 and not layout.part_files()
    lines = [json.loads(line) for f in files for line in gzip.decompress(f.read_bytes()).splitlines()]
    assert len(lines) == 21
    assert [line["seq"] for line in lines] == list(range(1, 22))
    assert lines[0]["msg"]["MetaData"]["MMSI"] == 470000000
    events = [json.loads(line)["event"] for f in layout.event_files(today) for line in f.read_text().splitlines()]
    assert events[0] == "session_start" and events[-1] == "session_stop"
    assert {"subscribed", "first_message", "disconnected"} <= set(events)
    assert server.subscriptions[0]["BoundingBoxes"] == [[[22.0, 47.5], [30.5, 62.5]]]
    assert VALID_KEY not in all_text_under(settings.data_dir)
    assert VALID_KEY not in caplog.text
    start = json.loads(layout.event_files(today)[0].read_text().splitlines()[0])
    assert start["key_hint"] == "****" + VALID_KEY[-4:]


async def test_rejected_key_exits_with_code_2(settings):
    async with MockAisStream() as server:
        recorder = Recorder(settings, "wrong-key", url=server.url, install_signal_handlers=False)
        code = await asyncio.wait_for(recorder.run(), timeout=10)
    assert code == EXIT_REJECTED
    assert not FeedLayout(settings.aisstream_dir).part_files()


async def test_second_recorder_on_same_folder_is_refused(settings):
    layout = FeedLayout(settings.aisstream_dir)
    with RecorderLock(layout.lock_path):
        recorder = Recorder(settings, VALID_KEY, url="ws://127.0.0.1:9", install_signal_handlers=False)
        with pytest.raises(AlreadyRunning):
            await recorder.run()


class SteppingClock:
    """Starts at 23:59:40 UTC and moves 2 seconds per call, so a run crosses midnight."""

    def __init__(self):
        self.now = datetime(2026, 10, 11, 23, 59, 40, tzinfo=timezone.utc)

    def __call__(self):
        self.now += timedelta(seconds=2)
        return self.now


async def test_midnight_rollover_compacts_and_summarizes_previous_day(settings, monkeypatch):
    monkeypatch.setattr(AisStreamClient, "_backoff", lambda self, failures: 0.05)
    messages = [position_report(mmsi=470000000 + i) for i in range(12)]
    async with MockAisStream(default=Script(messages=messages, then="open")) as server:
        recorder = Recorder(settings, VALID_KEY, url=server.url, duration_s=1.0, clock=SteppingClock(),
                            install_signal_handlers=False)
        await asyncio.wait_for(recorder.run(), timeout=20)
    layout = FeedLayout(settings.aisstream_dir)
    assert layout.raw_days() == ["2026-10-11", "2026-10-12"]
    assert layout.table_path("positions", "2026-10-11").is_file()
    summary = json.loads(layout.summary_path("2026-10-11").read_text())
    assert summary["complete_day"] is True and summary["messages"] >= 1
    assert not layout.table_path("positions", "2026-10-12").exists()  # day not finished yet


async def test_restart_recovers_crashed_files_and_catches_up_old_days(settings):
    layout = FeedLayout(settings.aisstream_dir)
    crashed = layout.raw_part_path("20261001T10", "20261001T100000Z-dead")
    crashed.parent.mkdir(parents=True)
    line = json.dumps({"rx": "2026-10-01T10:00:00.000000Z", "seq": 1, "conn": 1, "kind": "ais",
                       "msg": position_report()})
    crashed.write_text(line + "\n" + line[:40])
    async with MockAisStream() as server:
        recorder = Recorder(settings, VALID_KEY, url=server.url, duration_s=0.5, install_signal_handlers=False)
        await asyncio.wait_for(recorder.run(), timeout=20)
    assert not crashed.exists()
    assert layout.raw_files("2026-10-01")
    assert layout.table_path("positions", "2026-10-01").is_file()
    assert layout.summary_path("2026-10-01").is_file()


async def test_no_regions_enabled_is_rejected(settings):
    from tracktrust.settings import Settings

    empty = Settings(settings.data_dir, tuple(r.__class__(r.name, r.box, r.description, False)
                                               for r in settings.regions), settings.recorder)
    with pytest.raises(ValueError, match="No regions"):
        Recorder(empty, VALID_KEY)


async def test_disk_full_stops_with_clear_error(settings, monkeypatch, caplog):
    from tracktrust.recorder import EXIT_DISK_ERROR
    from tracktrust.storage.rawlog import RawLogWriter

    original = RawLogWriter.write
    calls = {"n": 0}

    def failing_write(self, frame):
        calls["n"] += 1
        if calls["n"] > 3:
            raise OSError(28, "No space left on device")
        original(self, frame)

    monkeypatch.setattr(RawLogWriter, "write", failing_write)
    async with MockAisStream(default=Script(messages=[position_report()] * 10, then="open")) as server:
        recorder = Recorder(settings, VALID_KEY, url=server.url, install_signal_handlers=False)
        code = await asyncio.wait_for(recorder.run(), timeout=20)
    assert code == EXIT_DISK_ERROR
    assert "No space left on device" in caplog.text and "Free some disk space" in caplog.text
    layout = FeedLayout(settings.aisstream_dir)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    saved = [line for f in layout.raw_files(today) for line in gzip.decompress(f.read_bytes()).splitlines()]
    assert len(saved) == 3  # what was written before the failure is kept
