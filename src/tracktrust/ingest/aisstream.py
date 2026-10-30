"""Client for the aisstream.io live AIS WebSocket feed.

Protocol (from aisstream.io's official examples and message models):

- Connect to wss://stream.aisstream.io/v0/stream with permessage-deflate
  compression, which aisstream.io needs to serve the full message rate.
- Within 3 seconds, send one JSON subscription: the API key, a list of bounding
  boxes as [[lat1, lon1], [lat2, lon2]], and optional MMSI and message-type
  filters.
- The server then pushes JSON messages (as binary or text frames) with
  `MessageType`, `MetaData` and `Message` keys. A rejected subscription comes
  back as {"error": "..."}. Other JSON without `MessageType` (for example a
  subscription confirmation) is passed on as a control message.

`AisStreamClient.stream()` reconnects with exponential backoff and jitter,
reconnects when the feed goes silent, and stops for good only when the server
rejects the API key. Any other server error is treated as temporary, so an
aisstream.io outage does not end a long recording.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import websockets
from websockets.asyncio.client import connect

log = logging.getLogger(__name__)

AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"

MESSAGE_TYPES = frozenset(
    {
        "PositionReport",
        "UnknownMessage",
        "AddressedSafetyMessage",
        "AddressedBinaryMessage",
        "AidsToNavigationReport",
        "AssignedModeCommand",
        "BaseStationReport",
        "BinaryAcknowledge",
        "BinaryBroadcastMessage",
        "ChannelManagement",
        "CoordinatedUTCInquiry",
        "DataLinkManagementMessage",
        "DataLinkManagementMessageData",
        "ExtendedClassBPositionReport",
        "GroupAssignmentCommand",
        "GnssBroadcastBinaryMessage",
        "Interrogation",
        "LongRangeAisBroadcastMessage",
        "MultiSlotBinaryMessage",
        "SafetyBroadcastMessage",
        "ShipStaticData",
        "SingleSlotBinaryMessage",
        "StandardClassBPositionReport",
        "StandardSearchAndRescueAircraftReport",
        "StaticDataReport",
    }
)

# A connection that delivered data for at least this long counts as healthy, so
# the next reconnect starts again from the shortest delay.
HEALTHY_CONNECTION_S = 60.0


class AuthError(RuntimeError):
    """aisstream.io rejected the API key."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Frame:
    """One message received from the server.

    kind is "ais" (an AIS message envelope), "error" (a server error object),
    "control" (any other JSON object) or "invalid" (not a JSON object).
    `text` is the message exactly as received, decoded as UTF-8.
    """

    rx_time: datetime
    conn: int
    text: str
    obj: dict[str, Any] | None
    kind: str

    @property
    def message_type(self) -> str | None:
        if self.obj is None:
            return None
        value = self.obj.get("MessageType")
        return value if isinstance(value, str) else None


def classify(raw: str | bytes) -> tuple[str, dict[str, Any] | None, str]:
    """Decode one WebSocket message and say what kind it is."""
    if isinstance(raw, (bytes, bytearray, memoryview)):
        text = bytes(raw).decode("utf-8", errors="replace")
    else:
        text = raw
    try:
        obj = json.loads(text)
    except ValueError:
        return text, None, "invalid"
    if not isinstance(obj, dict):
        return text, None, "invalid"
    if "MessageType" in obj:
        return text, obj, "ais"
    if "error" in obj:
        return text, obj, "error"
    return text, obj, "control"


def looks_like_key_error(message: str) -> bool:
    lowered = message.lower().replace(" ", "")
    return ("apikey" in lowered or "key" in lowered) and any(
        word in lowered for word in ("invalid", "notvalid", "unauthor", "denied", "expired", "unknown")
    )


def build_subscription(
    api_key: str,
    boxes: Sequence[Sequence[Sequence[float]]],
    mmsi: Sequence[str] | None = None,
    message_types: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build and validate an aisstream.io subscription message."""
    if not api_key:
        raise ValueError("api_key is empty")
    if not boxes:
        raise ValueError("At least one bounding box is required")
    clean_boxes = []
    for box in boxes:
        if len(box) != 2 or any(len(corner) != 2 for corner in box):
            raise ValueError(f"Bounding box must be [[lat1, lon1], [lat2, lon2]], got {box!r}")
        corners = [[float(corner[0]), float(corner[1])] for corner in box]
        for lat, lon in corners:
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                raise ValueError(f"Corner {lat}, {lon} is outside the valid latitude/longitude range")
        clean_boxes.append(corners)
    message: dict[str, Any] = {"APIKey": api_key, "BoundingBoxes": clean_boxes}
    if mmsi:
        bad = [m for m in mmsi if not (isinstance(m, str) and len(m) == 9 and m.isdigit())]
        if bad:
            raise ValueError(f"MMSI filters must be 9-digit strings, got {bad!r}")
        message["FiltersShipMMSI"] = list(mmsi)
    if message_types:
        unknown = sorted(set(message_types) - MESSAGE_TYPES)
        if unknown:
            raise ValueError(f"Unknown aisstream message types: {unknown}")
        message["FilterMessageTypes"] = list(message_types)
    return message


def describe_subscription(subscription: dict[str, Any]) -> dict[str, Any]:
    """Copy of a subscription that is safe to log (the key is removed)."""
    return {k: v for k, v in subscription.items() if k != "APIKey"}


EventCallback = Callable[..., None]


def _no_event(_event: str, **_fields: Any) -> None:
    return None


def _retrieve(task: asyncio.Future) -> None:
    if not task.cancelled():
        task.exception()


class AisStreamClient:
    """Reconnecting aisstream.io client.

    `on_event(name, **fields)` is called for connection events so the recorder
    can log when the feed was and was not being received. Field values never
    include the API key.
    """

    def __init__(
        self,
        api_key: str,
        boxes: Sequence[Sequence[Sequence[float]]],
        *,
        url: str = AISSTREAM_URL,
        mmsi: Sequence[str] | None = None,
        message_types: Sequence[str] | None = None,
        stall_timeout: float = 300.0,
        open_timeout: float = 20.0,
        max_backoff: float = 300.0,
        on_event: EventCallback | None = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._subscription = build_subscription(api_key, boxes, mmsi, message_types)
        self.url = url
        self.stall_timeout = stall_timeout
        self.open_timeout = open_timeout
        self.max_backoff = max_backoff
        self._on_event = on_event or _no_event
        self._clock = clock
        self.connections = 0
        self.connected = False

    @property
    def subscription_summary(self) -> dict[str, Any]:
        return describe_subscription(self._subscription)

    def _emit(self, event: str, **fields: Any) -> None:
        try:
            self._on_event(event, **fields)
        except Exception:  # an event sink must never stop the feed
            log.exception("Event callback failed for %s", event)

    def _backoff(self, failures: int) -> float:
        ceiling = min(self.max_backoff, 2.0 ** min(failures, 16))
        return max(1.0, random.uniform(ceiling / 2, ceiling))

    async def stream(self, stop: asyncio.Event) -> AsyncIterator[Frame]:
        """Yield frames until `stop` is set, reconnecting as needed.

        Raises AuthError if the server rejects the API key.
        """
        failures = 0
        while not stop.is_set():
            self.connections += 1
            conn = self.connections
            started = time.monotonic()
            frames = 0
            reason = "closed"
            self._emit("connecting", conn=conn, url=self.url)
            try:
                async with connect(
                    self.url,
                    compression="deflate",
                    open_timeout=self.open_timeout,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                    max_size=8 * 2**20,
                    max_queue=4096,
                ) as ws:
                    await ws.send(json.dumps(self._subscription))
                    self.connected = True
                    self._emit("subscribed", conn=conn, **self.subscription_summary)
                    while True:
                        if stop.is_set():
                            reason = "stopped"
                            break
                        raw = await self._recv(ws, stop)
                        if raw is None:
                            if stop.is_set():
                                reason = "stopped"
                            else:
                                reason = "stalled"
                                self._emit("stalled", conn=conn, silent_s=self.stall_timeout)
                            break
                        text, obj, kind = classify(raw)
                        frame = Frame(self._clock(), conn, text, obj, kind)
                        if kind == "error":
                            message = str(obj.get("error")) if obj else text
                            self._emit("server_error", conn=conn, error=message, frames=frames)
                            yield frame  # recorded like any other message
                            if frames == 0 and looks_like_key_error(message):
                                raise AuthError(message)
                            reason = f"server error: {message}"
                            break
                        if kind == "ais":
                            if frames == 0:
                                self._emit("first_message", conn=conn, after_s=round(time.monotonic() - started, 3))
                            frames += 1
                        yield frame
            except AuthError:
                self.connected = False
                raise
            except websockets.exceptions.InvalidURI:
                self.connected = False
                raise
            except websockets.exceptions.InvalidStatus as exc:
                reason = f"handshake rejected: HTTP {exc.response.status_code}"
            except websockets.exceptions.ConnectionClosed as exc:
                reason = f"connection closed: {exc}"
            except (OSError, asyncio.TimeoutError, websockets.exceptions.WebSocketException) as exc:
                reason = f"{type(exc).__name__}: {exc}"
            finally:
                self.connected = False

            lasted = time.monotonic() - started
            self._emit("disconnected", conn=conn, reason=reason, frames=frames, lasted_s=round(lasted, 3))
            if stop.is_set():
                break
            if frames > 0 and lasted >= HEALTHY_CONNECTION_S:
                failures = 0
            failures += 1
            delay = self._backoff(failures)
            if frames == 0 and failures >= 3:
                log.warning(
                    "No data on %d connection attempts in a row. If this continues, run "
                    "`tracktrust check-key` to test the API key.",
                    failures,
                )
            self._emit("backoff", conn=conn, delay_s=round(delay, 2), failures=failures)
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass

    async def _recv(self, ws: Any, stop: asyncio.Event) -> str | bytes | None:
        """Next message, or None on stall timeout or stop."""
        recv_task = asyncio.ensure_future(ws.recv())
        stop_task = asyncio.ensure_future(stop.wait())
        done: set = set()
        try:
            done, _ = await asyncio.wait(
                {recv_task, stop_task}, timeout=self.stall_timeout, return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            stop_task.cancel()
            if recv_task not in done:
                # Also reached when the consumer closes the stream mid-wait; the
                # callback retrieves the outcome so asyncio does not warn about it.
                recv_task.cancel()
                recv_task.add_done_callback(_retrieve)
        if recv_task in done:
            return recv_task.result()
        return None


@dataclass
class KeyCheckResult:
    ok: bool
    status: str  # "ok", "rejected", "no_data", "network_error"
    detail: str
    messages: int = 0
    vessels: int = 0
    message_types: dict[str, int] | None = None
    first_message_after_s: float | None = None
    sample: dict[str, Any] | None = None


async def check_key(
    api_key: str,
    boxes: Sequence[Sequence[Sequence[float]]],
    *,
    url: str = AISSTREAM_URL,
    timeout: float = 30.0,
    max_messages: int = 200,
) -> KeyCheckResult:
    """Connect once, subscribe and report whether data arrives.

    A rejected key gives status "rejected". Data within `timeout` seconds gives
    "ok". A connection that stays silent gives "no_data", which usually means
    the key works but the boxes have no coverage right now.
    """
    subscription = build_subscription(api_key, boxes)
    counts: dict[str, int] = {}
    vessels: set[int] = set()
    sample = None
    first_after = None
    started = time.monotonic()
    try:
        async with connect(
            url, compression="deflate", open_timeout=min(timeout, 20.0), close_timeout=5, max_size=8 * 2**20
        ) as ws:
            await ws.send(json.dumps(subscription))
            deadline = started + timeout
            while sum(counts.values()) < max_messages:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                _text, obj, kind = classify(raw)
                if kind == "error":
                    message = str(obj.get("error")) if obj else _text
                    return KeyCheckResult(False, "rejected", f"aisstream.io replied: {message}")
                if kind != "ais" or obj is None:
                    continue
                if first_after is None:
                    first_after = time.monotonic() - started
                mtype = obj.get("MessageType", "?")
                counts[mtype] = counts.get(mtype, 0) + 1
                meta = obj.get("MetaData") or {}
                mmsi = meta.get("MMSI")
                if isinstance(mmsi, int):
                    vessels.add(mmsi)
                if sample is None and isinstance(meta, dict):
                    sample = {
                        k: meta.get(k)
                        for k in ("MMSI", "ShipName", "latitude", "longitude", "time_utc")
                        if k in meta
                    }
                    sample["MessageType"] = mtype
    except websockets.exceptions.ConnectionClosed as exc:
        if not counts:
            return KeyCheckResult(
                False,
                "rejected",
                f"The server closed the connection before sending any data ({exc}). "
                "This usually means the key was not accepted.",
            )
    except websockets.exceptions.InvalidStatus as exc:
        return KeyCheckResult(False, "network_error", f"Handshake rejected: HTTP {exc.response.status_code}")
    except (OSError, asyncio.TimeoutError, websockets.exceptions.WebSocketException) as exc:
        return KeyCheckResult(False, "network_error", f"Could not connect to {url}: {type(exc).__name__}: {exc}")

    total = sum(counts.values())
    if total == 0:
        return KeyCheckResult(
            False,
            "no_data",
            f"Connected and subscribed, but no AIS messages arrived within {timeout:.0f} s. The key was not "
            "rejected; the area may have no coverage right now. Try again with --world.",
        )
    return KeyCheckResult(
        True,
        "ok",
        f"Key accepted: {total} messages from {len(vessels)} vessels in {time.monotonic() - started:.1f} s.",
        messages=total,
        vessels=len(vessels),
        message_types=dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        first_message_after_s=round(first_after, 2) if first_after is not None else None,
        sample=sample,
    )
