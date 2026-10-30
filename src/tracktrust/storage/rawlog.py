"""Crash-safe raw message log, rotated every UTC hour.

Each received message becomes one line:

    {"rx":"2026-10-12T03:50:01.123456Z","seq":1,"conn":1,"kind":"ais","msg":{...}}

`rx` is this machine's UTC receive time, `seq` counts messages within the
recording session, `conn` counts connections within the session and `msg` is
the server's JSON exactly as received. A frame that is not a JSON object is
kept as a string under "invalid" instead of "msg".

The current hour is written to a plain `.jsonl.part` file and flushed every
second. When the hour ends, a background job compresses it to `.jsonl.gz`
(written to a temporary file, then renamed) and deletes the `.part`. If the
recorder is killed, the next start finalizes leftover `.part` files, dropping
only an incomplete last line.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import time
import zlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from tracktrust.ingest.aisstream import Frame
from tracktrust.storage.layout import GZ_SUFFIX, PART_SUFFIX, FeedLayout, hour_key, hour_key_to_day, session_of

log = logging.getLogger(__name__)


def format_rx(frame: Frame) -> str:
    return frame.rx_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def make_line(frame: Frame, seq: int) -> str:
    """Serialize a frame as one raw-log line, keeping the server's JSON verbatim."""
    head = f'{{"rx":"{format_rx(frame)}","seq":{seq},"conn":{frame.conn},"kind":"{frame.kind}",'
    if frame.obj is not None:
        text = frame.text.strip()
        if "\n" in text or "\r" in text:
            text = json.dumps(frame.obj, separators=(",", ":"), ensure_ascii=False)
        return head + '"msg":' + text + "}"
    return head + '"invalid":' + json.dumps(frame.text, ensure_ascii=False) + "}"


def _fsync_dir(path: Path) -> None:
    if os.name != "posix":
        return
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


@dataclass
class FinalizeResult:
    part: Path
    gz: Path | None
    kept: int
    dropped: int


def gz_path_for(part: Path) -> Path:
    return part.with_name(part.name[: -len(PART_SUFFIX)] + GZ_SUFFIX)


def _gz_readable(path: Path) -> bool:
    try:
        with gzip.open(path, "rb") as fh:
            while fh.read(1 << 20):
                pass
        return True
    except (OSError, EOFError, zlib.error):
        return False


def finalize_part(part: Path) -> FinalizeResult:
    """Compress a `.jsonl.part` file into `.jsonl.gz` and delete the part.

    Lines that are not complete JSON-object lines (a write cut off by a crash)
    are dropped and counted.
    """
    gz = gz_path_for(part)
    if gz.exists():
        # A previous finalize renamed the .gz into place but stopped before
        # deleting the .part. Keep the .gz if it reads cleanly.
        if _gz_readable(gz):
            part.unlink(missing_ok=True)
            return FinalizeResult(part, gz, 0, 0)
        gz.unlink()

    tmp = gz.with_name(gz.name + ".tmp")
    kept = dropped = 0
    with open(part, "rb") as src, gzip.open(tmp, "wb", compresslevel=6) as dst:
        for line in src:
            if line.endswith(b"\n") and line.startswith(b"{") and line.rstrip(b"\r\n").endswith(b"}"):
                dst.write(line)
                kept += 1
            elif line.strip():
                dropped += 1
    if kept == 0:
        tmp.unlink(missing_ok=True)
        part.unlink(missing_ok=True)
        return FinalizeResult(part, None, 0, dropped)
    with open(tmp, "rb") as fh:
        os.fsync(fh.fileno())
    os.replace(tmp, gz)
    _fsync_dir(gz.parent)
    part.unlink()
    if dropped:
        log.warning("Dropped %d incomplete line(s) while finalizing %s", dropped, part.name)
    return FinalizeResult(part, gz, kept, dropped)


def recover_orphans(layout: FeedLayout, current_session: str | None = None) -> list[FinalizeResult]:
    """Finalize `.part` files left by earlier sessions and remove stale temp files."""
    results = []
    raw_dir = layout.raw_dir
    if raw_dir.is_dir():
        for tmp in sorted(raw_dir.glob("date=*/*.gz.tmp")):
            if current_session and current_session in tmp.name:
                continue
            tmp.unlink(missing_ok=True)
    for part in layout.part_files():
        if current_session and session_of(part) == current_session:
            continue
        try:
            results.append(finalize_part(part))
        except OSError:
            log.exception("Could not finalize %s; it will be retried on the next start", part)
    return results


class RawLogWriter:
    """Append frames to hourly `.part` files and hand finished files to `on_file_closed`.

    `on_day_closed(day)` is called after the last file of a UTC day has been
    handed over, so day-level jobs can be queued behind its finalization.
    Hours never move backwards: if the system clock steps back, messages keep
    going to the current file.
    """

    def __init__(
        self,
        layout: FeedLayout,
        session: str,
        *,
        on_file_closed: Callable[[Path], None],
        on_day_closed: Callable[[str], None] | None = None,
        flush_interval: float = 1.0,
        fsync_interval: float = 30.0,
    ) -> None:
        self.layout = layout
        self.session = session
        self._on_file_closed = on_file_closed
        self._on_day_closed = on_day_closed
        self.flush_interval = flush_interval
        self.fsync_interval = fsync_interval
        self._fh: IO[str] | None = None
        self._key: str | None = None
        self._path: Path | None = None
        self._last_flush = time.monotonic()
        self._last_fsync = time.monotonic()
        self.seq = 0
        self.lines_in_file = 0

    @property
    def current_path(self) -> Path | None:
        return self._path

    @property
    def current_day(self) -> str | None:
        return hour_key_to_day(self._key) if self._key else None

    def write(self, frame: Frame) -> None:
        key = hour_key(frame.rx_time)
        if self._key is None or key > self._key:
            self._rotate(key)
        assert self._fh is not None
        self.seq += 1
        self._fh.write(make_line(frame, self.seq))
        self._fh.write("\n")
        self.lines_in_file += 1
        self.flush_if_due()

    def flush_if_due(self) -> None:
        if self._fh is None:
            return
        now = time.monotonic()
        if now - self._last_flush >= self.flush_interval:
            self._fh.flush()
            self._last_flush = now
        if now - self._last_fsync >= self.fsync_interval:
            self._fh.flush()
            os.fsync(self._fh.fileno())
            self._last_fsync = now

    def _open(self, key: str) -> None:
        path = self.layout.raw_part_path(key, self.session)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(path, "a", encoding="utf-8", newline="\n")
        self._key = key
        self._path = path
        self.lines_in_file = 0

    def _close_current(self) -> None:
        if self._fh is None or self._path is None:
            return
        self._fh.flush()
        os.fsync(self._fh.fileno())
        self._fh.close()
        self._fh = None
        self._on_file_closed(self._path)

    def _rotate(self, key: str) -> None:
        previous_day = self.current_day
        self._close_current()
        if previous_day is not None and previous_day != hour_key_to_day(key) and self._on_day_closed:
            self._on_day_closed(previous_day)
        self._open(key)

    def close(self) -> None:
        """Close the current file and hand it over for finalization."""
        self._close_current()
        self._path = None


def iter_raw_lines(path: Path) -> Iterator[bytes]:
    """Yield complete lines from a raw `.jsonl.gz` or `.jsonl.part` file.

    A truncated gzip stream or an unfinished last line ends the iteration
    quietly instead of raising.
    """
    if path.name.endswith(".gz"):
        try:
            with gzip.open(path, "rb") as fh:
                for line in fh:
                    if line.endswith(b"\n"):
                        yield line
        except (OSError, EOFError, zlib.error) as exc:
            log.warning("Stopped reading %s early: %s", path.name, exc)
    else:
        with open(path, "rb") as fh:
            for line in fh:
                if line.endswith(b"\n"):
                    yield line


def iter_raw_records(path: Path, errors: list[str] | None = None) -> Iterator[dict]:
    """Yield parsed raw-log records, skipping lines that are not valid JSON."""
    for number, line in enumerate(iter_raw_lines(path), start=1):
        try:
            record = json.loads(line)
        except ValueError:
            if errors is not None:
                errors.append(f"{path.name}:{number}")
            continue
        if isinstance(record, dict):
            yield record
