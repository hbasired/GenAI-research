"""Daily coverage summary of a recorded feed.

Answers the questions that decide whether the recording is usable: how many
messages and vessels arrived, from which regions, which hours had data, where
the gaps are, whether the gaps were the recorder's fault (disconnected) or the
feed's (connected but silent), and how stale the messages were on arrival.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from tracktrust.normalize import POSITION_CLASSES, RegionFn, parse_rx, parse_server_time
from tracktrust.storage.events import iter_events
from tracktrust.storage.layout import FeedLayout
from tracktrust.storage.rawlog import iter_raw_records

GAP_MINUTES = 5
DELAY_SAMPLE_EVERY = 10
# The recorder writes an event at least every 10 minutes while running
# (recorder.HEARTBEAT_S), so two events of one session at most this far apart
# mean it ran in between.
MAX_EVENT_SPACING_MIN = 11


def _percentile(sorted_values: list[float], q: float) -> float | None:
    if not sorted_values:
        return None
    index = min(len(sorted_values) - 1, max(0, round(q * (len(sorted_values) - 1))))
    return round(sorted_values[index], 3)


def _minute_runs(minutes: set[int], start: int, end: int, min_len: int) -> list[tuple[int, int]]:
    """Runs of at least `min_len` minutes in [start, end) that are not in `minutes`."""
    runs = []
    run_start = None
    for minute in range(start, end):
        if minute in minutes:
            if run_start is not None and minute - run_start >= min_len:
                runs.append((run_start, minute))
            run_start = None
        elif run_start is None:
            run_start = minute
    if run_start is not None and end - run_start >= min_len:
        runs.append((run_start, end))
    return runs


def _recording_minutes(points_by_session: dict[str, list[tuple[float, str]]], end_minute: int) -> set[int]:
    """Minutes of the day in which a recorder session was running, from its events."""
    running: set[int] = set()
    for points in points_by_session.values():
        points = sorted(points)
        times = [m for m, _ in points]
        if points[0][1] != "session_start" and times[0] <= MAX_EVENT_SPACING_MIN:
            times.insert(0, 0.0)  # the session was already running at midnight
        for a, b in zip(times, times[1:]):
            if b - a <= MAX_EVENT_SPACING_MIN:
                running.update(range(int(a), int(b) + 1))
        if points[-1][1] != "session_stop" and times[-1] >= end_minute - MAX_EVENT_SPACING_MIN:
            running.update(range(int(times[-1]), end_minute))  # still running at the end
    return {m for m in running if 0 <= m < end_minute}


def _hhmm(minute: int) -> str:
    return "24:00" if minute >= 1440 else f"{minute // 60:02d}:{minute % 60:02d}"


def summarize_day(layout: FeedLayout, day: str, region_for: RegionFn | None = None,
                  now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    day_start = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    files = layout.raw_files(day, include_parts=True)

    kinds: Counter[str] = Counter()
    types: Counter[str] = Counter()
    per_hour: Counter[int] = Counter()
    region_msgs: Counter[str] = Counter()
    region_vessels: dict[str, set[int]] = {}
    vessels: set[int] = set()
    position_vessels: set[int] = set()
    minutes: set[int] = set()
    delays: list[float] = []
    first_rx = last_rx = None
    bad_lines: list[str] = []
    ais_count = 0

    for path in files:
        for record in iter_raw_records(path, bad_lines):
            rx = parse_rx(record.get("rx"))
            if rx is None:
                continue
            kinds[record.get("kind", "?")] += 1
            first_rx = rx if first_rx is None or rx < first_rx else first_rx
            last_rx = rx if last_rx is None or rx > last_rx else last_rx
            minute = int((rx - day_start).total_seconds() // 60)
            if 0 <= minute < 1440:
                minutes.add(minute)
                per_hour[minute // 60] += 1
            msg = record.get("msg")
            if record.get("kind") != "ais" or not isinstance(msg, dict):
                continue
            ais_count += 1
            mtype = msg.get("MessageType")
            types[mtype] += 1
            meta = msg.get("MetaData") if isinstance(msg.get("MetaData"), dict) else {}
            mmsi = meta.get("MMSI")
            if isinstance(mmsi, int):
                vessels.add(mmsi)
            if ais_count % DELAY_SAMPLE_EVERY == 0:
                server = parse_server_time(meta.get("time_utc"))
                if server is not None:
                    delays.append((rx - server).total_seconds())
            if mtype in POSITION_CLASSES:
                body = (msg.get("Message") or {}).get(mtype) or {}
                lat, lon = body.get("Latitude"), body.get("Longitude")
                if isinstance(mmsi, int):
                    position_vessels.add(mmsi)
                name = region_for(lat, lon) if region_for and isinstance(lat, (int, float)) and isinstance(lon, (int, float)) else None
                key = name or "outside_regions"
                region_msgs[key] += 1
                if isinstance(mmsi, int):
                    region_vessels.setdefault(key, set()).add(mmsi)

    events = Counter()
    disconnect_reasons: Counter[str] = Counter()
    sessions = set()
    server_errors = []
    points_by_session: dict[str, list[tuple[float, str]]] = {}
    for path in layout.event_files(day):
        for event in iter_events(path):
            name = event.get("event", "?")
            events[name] += 1
            session = str(event.get("session"))
            sessions.add(session)
            t = parse_rx(event.get("t"))
            if t is not None:
                points_by_session.setdefault(session, []).append(((t - day_start).total_seconds() / 60, name))
            if name == "disconnected" and event.get("reason") != "stopped":
                disconnect_reasons[str(event.get("reason", "?")).split(":")[0]] += 1
            elif name == "server_error":
                server_errors.append(str(event.get("error")))

    day_end = day_start + timedelta(days=1)
    end_minute = 1440 if now >= day_end else max(0, int((now - day_start).total_seconds() // 60))
    recording = _recording_minutes(points_by_session, end_minute) | {m for m in minutes if m < end_minute}
    off_minutes = set(range(end_minute)) - recording
    silent = _minute_runs(minutes | off_minutes, 0, end_minute, GAP_MINUTES)
    off = _minute_runs(recording, 0, end_minute, 1)
    delays.sort()
    raw_bytes = sum(p.stat().st_size for p in files)

    return {
        "day": day,
        "complete_day": now >= day_end,
        "generated": now.isoformat(),
        "raw_files": len(files),
        "raw_bytes": raw_bytes,
        "messages": sum(kinds.values()),
        "messages_by_kind": dict(kinds),
        "ais_messages": ais_count,
        "messages_by_type": dict(types.most_common()),
        "unique_vessels": len(vessels),
        "vessels_with_positions": len(position_vessels),
        "regions": {
            key: {"position_messages": region_msgs[key], "vessels": len(region_vessels.get(key, ()))}
            for key in sorted(region_msgs)
        },
        "first_message": first_rx.isoformat() if first_rx else None,
        "last_message": last_rx.isoformat() if last_rx else None,
        "minutes_elapsed": end_minute,
        "minutes_recording": len(recording),
        "minutes_with_data": len(minutes),
        "coverage_pct": round(100.0 * len(minutes) / len(recording), 1) if recording else None,
        "silent_gaps_over_5_min": [{"from": _hhmm(a), "to": _hhmm(b), "minutes": b - a} for a, b in silent],
        "recorder_off": [{"from": _hhmm(a), "to": _hhmm(b), "minutes": b - a} for a, b in off],
        "messages_per_hour": {f"{h:02d}": per_hour[h] for h in range(24) if per_hour[h]},
        "arrival_delay_s": {
            "p50": _percentile(delays, 0.5),
            "p95": _percentile(delays, 0.95),
            "max": round(delays[-1], 3) if delays else None,
            "sampled": len(delays),
            "note": "receive time on this machine minus aisstream.io time_utc; includes clock offset",
        },
        "connection_events": dict(events),
        "disconnect_reasons": dict(disconnect_reasons),
        "server_errors": server_errors[:20],
        "sessions": len(sessions),
        "unreadable_lines": len(bad_lines),
    }


def write_summary(layout: FeedLayout, summary: dict[str, Any]) -> Path:
    path = layout.summary_path(summary["day"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def _size(n: int) -> str:
    if n >= 1e9:
        return f"{n / 1e9:.2f} GB"
    if n >= 1e6:
        return f"{n / 1e6:.1f} MB"
    return f"{n / 1e3:.0f} kB"


def _periods(runs: list[dict[str, Any]], limit: int = 8) -> str:
    shown = ", ".join(f"{g['from']}-{g['to']}" for g in runs[:limit])
    return shown + (f" and {len(runs) - limit} more" if len(runs) > limit else "")


def format_summary(s: dict[str, Any]) -> str:
    lines = [
        f"AIS recording summary for {s['day']} (UTC){'' if s['complete_day'] else ' - day in progress'}",
        f"  Messages:        {s['messages']:,} ({s['ais_messages']:,} AIS) in {s['raw_files']} file(s), {_size(s['raw_bytes'])}",
        f"  Vessels:         {s['unique_vessels']:,} unique MMSI, {s['vessels_with_positions']:,} with positions",
    ]
    hours = s["minutes_recording"] / 60
    if s["coverage_pct"] is not None:
        lines.append(
            f"  Recording time:  {hours:.1f} h; data in {s['minutes_with_data']:,} of "
            f"{s['minutes_recording']:,} recorded minutes ({s['coverage_pct']}%)"
        )
    else:
        lines.append("  Recording time:  none")
    if s["first_message"]:
        lines.append(f"  First / last:    {s['first_message'][11:19]} / {s['last_message'][11:19]} UTC")
    if s["regions"]:
        lines.append("  By region (position reports):")
        for name, r in s["regions"].items():
            lines.append(f"    {name:<20} {r['position_messages']:>10,} reports  {r['vessels']:>6,} vessels")
    if s["messages_by_type"]:
        lines.append("  Top message types:")
        for name, count in list(s["messages_by_type"].items())[:6]:
            lines.append(f"    {name:<38} {count:>10,}")
    silent = s["silent_gaps_over_5_min"]
    if silent:
        lines.append(f"  Silent while recording (5+ min): {len(silent)}: {_periods(silent)}")
    elif s["minutes_recording"]:
        lines.append("  Silent while recording (5+ min): none")
    if s["recorder_off"]:
        lines.append(f"  Recorder not running: {_periods(s['recorder_off'])}")
    d = s["arrival_delay_s"]
    if d["p50"] is not None:
        lines.append(f"  Arrival delay:   median {d['p50']} s, p95 {d['p95']} s (sampled)")
    if s["disconnect_reasons"]:
        reasons = ", ".join(f"{k} x{v}" for k, v in s["disconnect_reasons"].items())
        lines.append(f"  Disconnects:     {reasons}")
    if s["server_errors"]:
        lines.append(f"  Server errors:   {'; '.join(s['server_errors'][:3])}")
    if s["unreadable_lines"]:
        lines.append(f"  Unreadable lines: {s['unreadable_lines']}")
    return "\n".join(lines)
