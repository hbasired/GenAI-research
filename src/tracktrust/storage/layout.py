"""Directory layout of one recorded feed.

    <root>/                      for example data/aisstream/
      raw/date=YYYY-MM-DD/       every message exactly as received, one JSON line each
        aisstream_YYYYMMDDTHH_<session>.jsonl.part   the hour being written now
        aisstream_YYYYMMDDTHH_<session>.jsonl.gz     a finished hour
      events/date=YYYY-MM-DD/    connection events (connects, drops, stalls)
        events_<session>.jsonl
      parquet/<table>/date=YYYY-MM-DD/data.parquet   normalized tables per UTC day
      parquet/_manifests/date=YYYY-MM-DD.json        which raw files went into a day
      summaries/date=YYYY-MM-DD.json                 daily coverage summary
      logs/recorder.log
      .recorder.lock

Dates and hours are UTC and come from the time each message was received.
The `date=` folders let DuckDB, pandas and pyarrow read the files as one
partitioned dataset.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

RAW_PREFIX = "aisstream"
PART_SUFFIX = ".jsonl.part"
GZ_SUFFIX = ".jsonl.gz"
_RAW_NAME = re.compile(r"^(?P<prefix>[a-z0-9]+)_(?P<hour>\d{8}T\d{2})_(?P<session>[0-9TZ]+-[0-9a-f]+)\.jsonl\.(?:part|gz)$")
_DATE_DIR = re.compile(r"^date=(\d{4}-\d{2}-\d{2})$")


@dataclass(frozen=True)
class FeedLayout:
    root: Path
    prefix: str = RAW_PREFIX

    @property
    def raw_dir(self) -> Path:
        return self.root / "raw"

    @property
    def events_dir(self) -> Path:
        return self.root / "events"

    @property
    def parquet_dir(self) -> Path:
        return self.root / "parquet"

    @property
    def manifests_dir(self) -> Path:
        return self.parquet_dir / "_manifests"

    @property
    def summaries_dir(self) -> Path:
        return self.root / "summaries"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def lock_path(self) -> Path:
        return self.root / ".recorder.lock"

    def raw_day_dir(self, day: str) -> Path:
        return self.raw_dir / f"date={day}"

    def raw_part_path(self, hour_key: str, session: str) -> Path:
        day = hour_key_to_day(hour_key)
        return self.raw_day_dir(day) / f"{self.prefix}_{hour_key}_{session}{PART_SUFFIX}"

    def events_path(self, day: str, session: str) -> Path:
        return self.events_dir / f"date={day}" / f"events_{session}.jsonl"

    def table_path(self, table: str, day: str) -> Path:
        return self.parquet_dir / table / f"date={day}" / "data.parquet"

    def manifest_path(self, day: str) -> Path:
        return self.manifests_dir / f"date={day}.json"

    def summary_path(self, day: str) -> Path:
        return self.summaries_dir / f"date={day}.json"

    def raw_files(self, day: str, include_parts: bool = False) -> list[Path]:
        folder = self.raw_day_dir(day)
        if not folder.is_dir():
            return []
        suffixes = (GZ_SUFFIX, PART_SUFFIX) if include_parts else (GZ_SUFFIX,)
        return sorted(p for p in folder.iterdir() if p.name.endswith(suffixes) and _RAW_NAME.match(p.name))

    def part_files(self, day: str | None = None) -> list[Path]:
        folders = [self.raw_day_dir(day)] if day else self._day_dirs(self.raw_dir)
        found = []
        for folder in folders:
            if folder.is_dir():
                found.extend(p for p in folder.iterdir() if p.name.endswith(PART_SUFFIX))
        return sorted(found)

    def raw_days(self) -> list[str]:
        return sorted(_DATE_DIR.match(p.name).group(1) for p in self._day_dirs(self.raw_dir))

    def event_files(self, day: str) -> list[Path]:
        folder = self.events_dir / f"date={day}"
        if not folder.is_dir():
            return []
        return sorted(folder.glob("events_*.jsonl"))

    @staticmethod
    def _day_dirs(parent: Path) -> list[Path]:
        if not parent.is_dir():
            return []
        return sorted(p for p in parent.iterdir() if p.is_dir() and _DATE_DIR.match(p.name))


def hour_key(ts: datetime) -> str:
    """UTC hour bucket used in raw file names, for example 20261012T03."""
    return ts.strftime("%Y%m%dT%H")


def hour_key_to_day(key: str) -> str:
    return f"{key[0:4]}-{key[4:6]}-{key[6:8]}"


def session_of(path: Path) -> str | None:
    match = _RAW_NAME.match(path.name)
    return match.group("session") if match else None


def parse_day(value: str) -> str:
    """Validate a YYYY-MM-DD string and return it unchanged."""
    return date.fromisoformat(value).isoformat()
