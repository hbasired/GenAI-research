"""A lock file so that only one recorder writes to a data directory.

aisstream.io serves one connection per key at a time, and two recorders
writing the same folder would duplicate data. The operating system releases
the lock automatically if the process dies.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import IO


class AlreadyRunning(RuntimeError):
    pass


class RecorderLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh: IO[str] | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+", encoding="utf-8")
        try:
            _lock(fh)
        except OSError:
            fh.seek(0)
            holder = fh.read().strip() or "unknown"
            fh.close()
            raise AlreadyRunning(
                f"Another recorder is already using {self.path.parent} ({holder}). "
                "Stop it first, or use a different --data-dir."
            ) from None
        fh.seek(0)
        fh.truncate()
        fh.write(f"pid {os.getpid()}\n")
        fh.flush()
        self._fh = fh

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            _unlock(self._fh)
        finally:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> RecorderLock:
        self.acquire()
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()


if os.name == "nt":  # pragma: no cover - Windows only
    import msvcrt

    def _lock(fh: IO[str]) -> None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock(fh: IO[str]) -> None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock(fh: IO[str]) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(fh: IO[str]) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
