"""Convert one UTC day of raw aisstream.io logs into Parquet tables.

Output: parquet/<table>/date=YYYY-MM-DD/data.parquet for the tables defined in
`tracktrust.normalize`, plus a manifest listing the raw files used. Re-running
is safe: a day is rebuilt only when its raw files changed (or with force=True),
and every file is written to a temporary name first and then renamed.

Read the result with DuckDB, for example:

    SELECT * FROM read_parquet('data/aisstream/parquet/positions/*/*.parquet', hive_partitioning = true)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tracktrust import __version__
from tracktrust.normalize import RegionFn, extract_rows
from tracktrust.storage.layout import FeedLayout, session_of
from tracktrust.storage.rawlog import iter_raw_records

log = logging.getLogger(__name__)

BATCH_ROWS = 50_000

_COMMON = [
    ("rx_time", "ts"),
    ("server_time", "ts"),
    ("mmsi", "int64"),
    ("msg_type", "str"),
    ("msg_id", "int16"),
    ("repeat", "int16"),
    ("valid", "bool"),
    ("session", "str"),
    ("conn", "int32"),
    ("seq", "int64"),
]
_DIMS = [("dim_a", "int32"), ("dim_b", "int32"), ("dim_c", "int32"), ("dim_d", "int32")]

TABLE_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "positions": _COMMON
    + [
        ("ais_class", "str"),
        ("lat", "float64"),
        ("lon", "float64"),
        ("sog", "float64"),
        ("cog", "float64"),
        ("heading", "int32"),
        ("nav_status", "int16"),
        ("rot", "int32"),
        ("pos_accuracy", "bool"),
        ("raim", "bool"),
        ("ais_second", "int16"),
        ("special_manoeuvre", "int16"),
        ("assigned_mode", "bool"),
        ("altitude", "int32"),
        ("position_latency", "bool"),
        ("ship_name_meta", "str"),
        ("region", "str"),
    ],
    "static": _COMMON
    + [
        ("part", "str"),
        ("imo", "int64"),
        ("call_sign", "str"),
        ("name", "str"),
        ("ship_type", "int32"),
    ]
    + _DIMS
    + [
        ("draught", "float64"),
        ("destination", "str"),
        ("eta_month", "int16"),
        ("eta_day", "int16"),
        ("eta_hour", "int16"),
        ("eta_minute", "int16"),
        ("fix_type", "int16"),
        ("ais_version", "int16"),
        ("dte", "bool"),
        ("meta_lat", "float64"),
        ("meta_lon", "float64"),
        ("region", "str"),
    ],
    "base_stations": _COMMON
    + [
        ("lat", "float64"),
        ("lon", "float64"),
        ("pos_accuracy", "bool"),
        ("raim", "bool"),
        ("fix_type", "int16"),
        ("reported_utc", "ts"),
        ("region", "str"),
    ],
    "aids_to_navigation": _COMMON
    + [
        ("name", "str"),
        ("aton_type", "int16"),
        ("lat", "float64"),
        ("lon", "float64"),
        ("virtual", "bool"),
        ("off_position", "bool"),
        ("pos_accuracy", "bool"),
        ("raim", "bool"),
        ("ais_second", "int16"),
    ]
    + _DIMS
    + [("region", "str")],
}


def _arrow_schema(table: str):
    import pyarrow as pa

    types = {
        "ts": pa.timestamp("us", tz="UTC"),
        "int16": pa.int16(),
        "int32": pa.int32(),
        "int64": pa.int64(),
        "float64": pa.float64(),
        "bool": pa.bool_(),
        "str": pa.string(),
    }
    return pa.schema([(name, types[kind]) for name, kind in TABLE_COLUMNS[table]])


class DayNotReady(RuntimeError):
    """The day still has unfinished `.part` files."""


@dataclass
class CompactResult:
    day: str
    status: str  # "written", "up_to_date", "no_data"
    rows: dict[str, int] = field(default_factory=dict)
    raw_files: int = 0
    bad_lines: int = 0


def _file_list(files: list[Path]) -> list[dict[str, Any]]:
    return [{"name": p.name, "bytes": p.stat().st_size} for p in files]


def _write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _clamp(row: dict[str, Any], table: str) -> dict[str, Any]:
    """Null out integers that do not fit their column instead of failing the day."""
    limits = {"int16": 2**15, "int32": 2**31, "int64": 2**63}
    for name, kind in TABLE_COLUMNS[table]:
        bound = limits.get(kind)
        value = row.get(name)
        if bound is not None and isinstance(value, int) and not -bound <= value < bound:
            row[name] = None
    return row


def compact_day(layout: FeedLayout, day: str, region_for: RegionFn | None = None, *, force: bool = False,
                regions_label: list[str] | None = None) -> CompactResult:
    """Build the Parquet tables for one UTC day. Requires pyarrow."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    if layout.part_files(day):
        raise DayNotReady(
            f"{day} still has unfinished .part files. If no recorder is running, run `tracktrust recover` first."
        )
    files = layout.raw_files(day)
    if not files:
        return CompactResult(day, "no_data")

    inputs = _file_list(files)
    manifest_path = layout.manifest_path(day)
    if not force and manifest_path.is_file():
        try:
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        except ValueError:
            previous = {}
        if previous.get("inputs") == inputs and all(
            layout.table_path(t, day).is_file() for t, n in previous.get("rows", {}).items() if n
        ):
            return CompactResult(day, "up_to_date", previous.get("rows", {}), len(files))

    schemas = {t: _arrow_schema(t) for t in TABLE_COLUMNS}
    buffers: dict[str, list[dict[str, Any]]] = {t: [] for t in TABLE_COLUMNS}
    writers: dict[str, Any] = {}
    tmp_paths: dict[str, Path] = {}
    rows = {t: 0 for t in TABLE_COLUMNS}
    errors: list[str] = []

    def flush(table: str) -> None:
        batch = buffers[table]
        if not batch:
            return
        if table not in writers:
            final = layout.table_path(table, day)
            final.parent.mkdir(parents=True, exist_ok=True)
            tmp_paths[table] = final.with_name(f"{final.name}.{os.getpid()}.tmp")
            writers[table] = pq.ParquetWriter(tmp_paths[table], schemas[table], compression="zstd")
        columns = {name: [r.get(name) for r in batch] for name, _ in TABLE_COLUMNS[table]}
        writers[table].write_table(pa.Table.from_pydict(columns, schema=schemas[table]))
        rows[table] += len(batch)
        buffers[table] = []

    try:
        for path in files:
            session = session_of(path)
            for record in iter_raw_records(path, errors):
                for table, row in extract_rows(record, session, region_for):
                    buffers[table].append(_clamp(row, table))
                    if len(buffers[table]) >= BATCH_ROWS:
                        flush(table)
        for table in TABLE_COLUMNS:
            flush(table)
    except BaseException:
        for writer in writers.values():
            writer.close()
        for tmp in tmp_paths.values():
            tmp.unlink(missing_ok=True)
        raise

    for table, writer in writers.items():
        writer.close()
        os.replace(tmp_paths[table], layout.table_path(table, day))
    for table in TABLE_COLUMNS:
        if rows[table] == 0:
            layout.table_path(table, day).unlink(missing_ok=True)

    _write_json_atomic(
        manifest_path,
        {
            "day": day,
            "created": datetime.now(timezone.utc).isoformat(),
            "tool_version": __version__,
            "regions": regions_label or [],
            "inputs": inputs,
            "rows": rows,
            "bad_lines": len(errors),
        },
    )
    if errors:
        log.warning("%s: skipped %d unreadable line(s)", day, len(errors))
    return CompactResult(day, "written", rows, len(files), len(errors))


def pending_days(layout: FeedLayout, before_day: str) -> list[str]:
    """Days before `before_day` whose Parquet output is missing or out of date."""
    days = []
    for day in layout.raw_days():
        if day >= before_day or layout.part_files(day):
            continue
        files = layout.raw_files(day)
        if not files:
            continue
        manifest = layout.manifest_path(day)
        if not manifest.is_file():
            days.append(day)
            continue
        try:
            previous = json.loads(manifest.read_text(encoding="utf-8"))
        except ValueError:
            days.append(day)
            continue
        if previous.get("inputs") != _file_list(files):
            days.append(day)
    return days
