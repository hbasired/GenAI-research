"""Record the aisstream.io live feed to disk until stopped.

One recorder per data directory (a lock file enforces it). On start it
finalizes files left by a crashed run and processes finished days that were
never compacted. While running it writes every message to hourly raw files,
logs connection events, and after each UTC midnight converts the finished day
to Parquet and writes its summary in a background thread.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

from tracktrust import __version__
from tracktrust.ingest.aisstream import AISSTREAM_URL, AisStreamClient, AuthError, Frame, utcnow
from tracktrust.settings import Settings, mask_key
from tracktrust.storage.compact import DayNotReady, compact_day, pending_days
from tracktrust.storage.events import EventLog
from tracktrust.storage.layout import FeedLayout
from tracktrust.storage.lock import RecorderLock
from tracktrust.storage.rawlog import RawLogWriter, finalize_part, recover_orphans
from tracktrust.summary import format_summary, summarize_day, write_summary

log = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_REJECTED = 2
EXIT_ALREADY_RUNNING = 3
EXIT_DISK_ERROR = 4
EXIT_FORCED = 130
# A heartbeat event at least this often lets the daily summary tell "recorder
# running but the feed was silent" from "recorder not running".
HEARTBEAT_S = 600.0


def make_session_id(now: datetime) -> str:
    return now.strftime("%Y%m%dT%H%M%SZ") + "-" + os.urandom(2).hex()


class SessionStats:
    def __init__(self) -> None:
        self.started = time.monotonic()
        self.frames = 0
        self.ais = 0
        self.types: Counter[str] = Counter()
        self.vessels: set[int] = set()
        self.last_frames = 0

    def add(self, frame: Frame) -> None:
        self.frames += 1
        if frame.kind != "ais" or frame.obj is None:
            return
        self.ais += 1
        self.types[frame.message_type or "?"] += 1
        meta = frame.obj.get("MetaData")
        if isinstance(meta, dict) and isinstance(meta.get("MMSI"), int):
            self.vessels.add(meta["MMSI"])


class Recorder:
    def __init__(
        self,
        settings: Settings,
        api_key: str,
        *,
        url: str = AISSTREAM_URL,
        duration_s: float | None = None,
        auto_compact: bool | None = None,
        clock: Callable[[], datetime] = utcnow,
        install_signal_handlers: bool = True,
    ) -> None:
        if not settings.enabled_regions:
            raise ValueError("No regions are enabled; enable at least one region in the config file")
        self.settings = settings
        self.api_key = api_key
        self.url = url
        self.duration_s = duration_s
        self.auto_compact = settings.recorder.auto_compact if auto_compact is None else auto_compact
        self.clock = clock
        self.install_signal_handlers = install_signal_handlers
        self.layout = FeedLayout(settings.aisstream_dir)
        self.stop = asyncio.Event()
        self.stats = SessionStats()
        self.session = ""
        self._executor: ThreadPoolExecutor | None = None
        self._jobs: list[Future] = []
        self._events: EventLog | None = None
        self._signals = 0
        self._pyarrow_warned = False
        self._disk_error: OSError | None = None

    # ----- background jobs (run one at a time, in submission order) -----

    def _submit(self, fn: Callable[..., Any], *args: Any) -> None:
        assert self._executor is not None
        self._jobs = [j for j in self._jobs if not j.done()]
        self._jobs.append(self._executor.submit(self._guarded, fn, *args))

    @staticmethod
    def _guarded(fn: Callable[..., Any], *args: Any) -> Any:
        try:
            return fn(*args)
        except Exception:
            log.exception("Background job %s%r failed; raw data is kept and the job will be retried on the next start",
                          getattr(fn, "__name__", fn), args)
            return None

    def _finalize_job(self, part: Path) -> None:
        result = finalize_part(part)
        if result.gz is not None:
            log.info("Saved %s (%d messages)", result.gz.name, result.kept)

    def _day_job(self, day: str) -> None:
        if self.auto_compact:
            try:
                import pyarrow  # noqa: F401
            except ImportError:
                if not self._pyarrow_warned:
                    log.warning("pyarrow is not installed, so days are not converted to Parquet (raw files are kept)")
                    self._pyarrow_warned = True
            else:
                try:
                    result = compact_day(
                        self.layout, day, self.settings.region_for,
                        regions_label=[r.name for r in self.settings.enabled_regions],
                    )
                    log.info("Parquet for %s: %s %s", day, result.status, result.rows or "")
                except DayNotReady as exc:
                    log.warning("%s", exc)
        summary = summarize_day(self.layout, day, self.settings.region_for, now=self.clock())
        path = write_summary(self.layout, summary)
        log.info("Summary written to %s\n%s", path, format_summary(summary))

    # ----- events and status -----

    def _event(self, name: str, **fields: Any) -> None:
        if self._events is not None:
            self._events.write(name, **fields)
        if name == "disconnected" and fields.get("reason") == "stopped":
            log.info("%s %s", name, fields)
        elif name in ("disconnected", "stalled", "server_error"):
            log.warning("%s %s", name, fields)
        elif name in ("subscribed", "first_message", "backoff"):
            log.info("%s %s", name, {k: v for k, v in fields.items() if k != "BoundingBoxes"})

    async def _ticker(self, client: AisStreamClient, writer: RawLogWriter) -> None:
        interval = self.settings.recorder.status_interval_s
        next_status = time.monotonic() + interval
        next_heartbeat = time.monotonic() + HEARTBEAT_S
        while not self.stop.is_set():
            try:
                await asyncio.wait_for(self.stop.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
            try:
                writer.flush_if_due()
            except OSError as exc:
                self._disk_error = exc
                self.stop.set()
                return
            if time.monotonic() >= next_heartbeat:
                next_heartbeat += HEARTBEAT_S
                self._event("heartbeat", connected=client.connected, frames=self.stats.frames,
                            vessels=len(self.stats.vessels))
            if time.monotonic() >= next_status:
                next_status += interval
                s = self.stats
                recent = s.frames - s.last_frames
                s.last_frames = s.frames
                state = "connected" if client.connected else "reconnecting"
                current = writer.current_path.name if writer.current_path else "-"
                log.info(
                    "%s | %s messages this session (+%s in last %.0f s) | %s vessels | %s",
                    state, f"{s.frames:,}", f"{recent:,}", interval, f"{len(s.vessels):,}", current,
                )

    def _on_signal(self) -> None:
        self._signals += 1
        if self._signals == 1:
            log.info("Stopping: finishing the current file. Press Ctrl+C again to quit immediately.")
            self.stop.set()
        else:
            log.warning("Quitting immediately; unfinished files are recovered on the next start.")
            logging.shutdown()
            os._exit(EXIT_FORCED)

    def _install_signals(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, getattr(signal, "SIGTERM", None)):
            if sig is None:
                continue
            try:
                loop.add_signal_handler(sig, self._on_signal)
            except (NotImplementedError, RuntimeError):  # Windows, or not the main thread
                try:
                    signal.signal(sig, lambda *_: loop.call_soon_threadsafe(self._on_signal))
                except ValueError:
                    log.debug("Cannot install signal handlers outside the main thread")

    # ----- main loop -----

    async def run(self) -> int:
        self.layout.root.mkdir(parents=True, exist_ok=True)
        lock = RecorderLock(self.layout.lock_path)
        lock.acquire()
        try:
            return await self._run_locked()
        finally:
            lock.release()

    async def _run_locked(self) -> int:
        self.session = make_session_id(self.clock())
        self._events = EventLog(self.layout, self.session, self.clock)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tracktrust-post")
        regions = [{"name": r.name, "box": r.as_subscription_box()} for r in self.settings.enabled_regions]
        self._event("session_start", version=__version__, key_hint=mask_key(self.api_key), regions=regions,
                    data_dir=str(self.layout.root))

        recovered = recover_orphans(self.layout, self.session)
        for result in recovered:
            self._event("recovered_file", part=result.part.name, kept=result.kept, dropped=result.dropped)
        if recovered:
            log.info("Recovered %d unfinished file(s) from an earlier run", len(recovered))
        today = self.clock().strftime("%Y-%m-%d")
        backlog = pending_days(self.layout, today) if self.auto_compact else []
        for day in self.layout.raw_days():
            if day < today and (day in backlog or not self.layout.summary_path(day).is_file()):
                self._submit(self._day_job, day)

        writer = RawLogWriter(
            self.layout,
            self.session,
            on_file_closed=lambda p: self._submit(self._finalize_job, p),
            on_day_closed=lambda d: self._submit(self._day_job, d),
        )
        client = AisStreamClient(
            self.api_key,
            [r.as_subscription_box() for r in self.settings.enabled_regions],
            url=self.url,
            stall_timeout=self.settings.recorder.stall_timeout_s,
            max_backoff=self.settings.recorder.max_backoff_s,
            on_event=self._event,
            clock=self.clock,
        )
        if self.install_signal_handlers:
            self._install_signals()
        loop = asyncio.get_running_loop()
        timer = None
        if self.duration_s:
            timer = loop.call_later(self.duration_s, self._duration_reached)
        ticker = asyncio.create_task(self._ticker(client, writer))

        exit_code = EXIT_OK
        try:
            async for frame in client.stream(self.stop):
                writer.write(frame)
                self.stats.add(frame)
                if frame.kind == "control":
                    self._event("server_message", text=frame.text[:500])
        except AuthError as exc:
            log.error("aisstream.io rejected the API key: %s. Check the key in your .env file.", exc)
            exit_code = EXIT_REJECTED
        except OSError as exc:  # the stream handles network errors itself; this is the disk
            self._disk_error = exc
        finally:
            self.stop.set()
            if timer is not None:
                timer.cancel()
            await ticker
            try:
                writer.close()
            except OSError as exc:
                self._disk_error = self._disk_error or exc
            if self._disk_error is not None:
                log.error("Could not write to %s: %s. Free some disk space and start again; "
                          "everything saved so far is kept.", self.layout.root, self._disk_error)
                exit_code = EXIT_DISK_ERROR
            s = self.stats
            self._event("session_stop", frames=s.frames, ais=s.ais, vessels=len(s.vessels),
                        connections=client.connections, exit_code=exit_code)
            log.info(
                "Session %s finished: %s messages, %s vessels, %d connection(s), %.0f s",
                self.session, f"{s.frames:,}", f"{len(s.vessels):,}", client.connections,
                time.monotonic() - s.started,
            )
            if any(not j.done() for j in self._jobs):
                log.info("Waiting for background jobs (compressing and summarizing)...")
            await asyncio.to_thread(self._executor.shutdown, True)
            self._events.close()
        return exit_code

    def _duration_reached(self) -> None:
        log.info("Requested recording time reached; stopping.")
        self.stop.set()
