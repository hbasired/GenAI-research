"""Append-only log of recorder events, one JSON line per event.

Events say when the feed was and was not being received (connects,
disconnects, stalls, backoff waits, file rotations). Research use: a gap in a
vessel's track only means the vessel went dark if the recorder was connected
at the time.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import IO, Any

from tracktrust.storage.layout import FeedLayout

log = logging.getLogger(__name__)


class EventLog:
    def __init__(self, layout: FeedLayout, session: str, clock: Callable[[], datetime]) -> None:
        self.layout = layout
        self.session = session
        self._clock = clock
        self._day: str | None = None
        self._fh: IO[str] | None = None

    def write(self, event: str, **fields: Any) -> None:
        now = self._clock()
        day = now.strftime("%Y-%m-%d")
        if day != self._day:
            self._reopen(day)
        record = {"t": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "session": self.session, "event": event, **fields}
        assert self._fh is not None
        self._fh.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")
        self._fh.flush()

    def _reopen(self, day: str) -> None:
        self.close()
        path = self.layout.events_path(day, self.session)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(path, "a", encoding="utf-8", newline="\n")
        self._day = day

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None


def iter_events(path: Path) -> Iterator[dict]:
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.endswith("\n"):
                break
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict):
                yield record
