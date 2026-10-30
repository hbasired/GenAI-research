import json
from datetime import datetime, timezone

import pyarrow.parquet as pq
import pytest
from aisstream_mock import aid_to_navigation, base_station, position_report, ship_static, static_data_report

from tracktrust.ingest.aisstream import Frame, classify
from tracktrust.storage.compact import DayNotReady, compact_day, pending_days
from tracktrust.storage.layout import FeedLayout
from tracktrust.storage.rawlog import RawLogWriter, finalize_part
from tracktrust.summary import format_summary, summarize_day

SESSION = "20261012T000000Z-abcd"


def write_day(layout, entries, session=SESSION, finalize=True):
    """entries: list of (datetime, message dict or raw text)."""
    closed = []
    writer = RawLogWriter(layout, session, on_file_closed=closed.append)
    for ts, msg in entries:
        text, obj, kind = classify(json.dumps(msg) if isinstance(msg, dict) else msg)
        writer.write(Frame(ts, 1, text, obj, kind))
    writer.close()
    if finalize:
        for part in closed:
            finalize_part(part)
    return closed


def ts(hour, minute=0, second=0, day=12):
    return datetime(2026, 10, day, hour, minute, second, tzinfo=timezone.utc)


def region_for(lat, lon):
    return "gulf_hormuz" if lat is not None and 22 <= lat <= 30.5 and 47.5 <= lon <= 62.5 else None


@pytest.fixture
def layout(tmp_path):
    return FeedLayout(tmp_path / "aisstream")


def sample_day(layout):
    write_day(layout, [
        (ts(0, 0), position_report(mmsi=470000001, lat=25.2, lon=55.2)),
        (ts(0, 1), position_report(mmsi=470000002, lat=21.0, lon=39.0)),
        (ts(0, 2), ship_static(mmsi=470000001)),
        (ts(1, 30), base_station()),
        (ts(1, 31), aid_to_navigation()),
        (ts(1, 32), static_data_report()),
        (ts(1, 33), {"error": "Service temporarily unavailable"}),
        (ts(1, 34), "not json"),
        (ts(23, 59), position_report(mmsi=470000003, lat=26.0, lon=56.0)),
    ])


def test_compact_day_writes_all_tables(layout):
    sample_day(layout)
    result = compact_day(layout, "2026-10-12", region_for, regions_label=["gulf_hormuz"])
    assert result.status == "written" and result.raw_files == 3
    assert result.rows == {"positions": 3, "static": 2, "base_stations": 1, "aids_to_navigation": 1}
    positions = pq.read_table(layout.table_path("positions", "2026-10-12")).to_pylist()
    assert [p["mmsi"] for p in positions] == [470000001, 470000002, 470000003]
    assert [p["region"] for p in positions] == ["gulf_hormuz", None, "gulf_hormuz"]
    assert positions[0]["rx_time"] == ts(0, 0)
    assert positions[0]["session"] == SESSION
    manifest = json.loads(layout.manifest_path("2026-10-12").read_text())
    assert manifest["regions"] == ["gulf_hormuz"] and len(manifest["inputs"]) == 3


def test_compact_is_idempotent_and_detects_new_files(layout):
    sample_day(layout)
    assert compact_day(layout, "2026-10-12", region_for).status == "written"
    assert compact_day(layout, "2026-10-12", region_for).status == "up_to_date"
    assert pending_days(layout, "2026-10-13") == []
    write_day(layout, [(ts(5), position_report(mmsi=470000009))], session="20261012T050000Z-ffff")
    assert pending_days(layout, "2026-10-13") == ["2026-10-12"]
    result = compact_day(layout, "2026-10-12", region_for)
    assert result.status == "written" and result.rows["positions"] == 4
    assert compact_day(layout, "2026-10-12", region_for, force=True).status == "written"


def test_compact_refuses_day_with_unfinished_files(layout):
    write_day(layout, [(ts(3), position_report())], finalize=False)
    with pytest.raises(DayNotReady):
        compact_day(layout, "2026-10-12", region_for)
    assert pending_days(layout, "2026-10-13") == []


def test_compact_no_data(layout):
    assert compact_day(layout, "2026-10-12", region_for).status == "no_data"


def test_compact_removes_stale_table_when_rebuilt_without_rows(layout):
    sample_day(layout)
    compact_day(layout, "2026-10-12", region_for)
    stale = layout.table_path("base_stations", "2026-10-12")
    assert stale.exists()
    for f in layout.raw_files("2026-10-12"):
        f.unlink()
    write_day(layout, [(ts(4), position_report())])
    compact_day(layout, "2026-10-12", region_for)
    assert not stale.exists()


def test_compact_out_of_range_integers_become_null(layout):
    msg = position_report()
    msg["Message"]["PositionReport"]["NavigationalStatus"] = 10**9
    write_day(layout, [(ts(3), msg)])
    compact_day(layout, "2026-10-12", region_for)
    row = pq.read_table(layout.table_path("positions", "2026-10-12")).to_pylist()[0]
    assert row["nav_status"] is None


def write_events(layout, session, entries):
    """entries: list of (datetime, event name)."""
    for when, name in entries:
        path = layout.events_path(when.strftime("%Y-%m-%d"), session)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as fh:
            fh.write(json.dumps({"t": when.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "session": session,
                                 "event": name}) + "\n")


def heartbeats(first, last, every_min=10):
    out, t = [], first
    while t <= last:
        out.append((t, "heartbeat"))
        t = t + (ts(0, every_min) - ts(0, 0))
    return out


def test_summary_counts_regions_and_errors(layout):
    sample_day(layout)
    s = summarize_day(layout, "2026-10-12", region_for, now=ts(12, day=13))
    assert s["complete_day"] is True
    assert s["messages"] == 9 and s["ais_messages"] == 7
    assert s["messages_by_kind"] == {"ais": 7, "error": 1, "invalid": 1}
    assert s["unique_vessels"] == 6 and s["vessels_with_positions"] == 3
    assert s["regions"] == {"gulf_hormuz": {"position_messages": 2, "vessels": 2},
                            "outside_regions": {"position_messages": 1, "vessels": 1}}
    assert s["messages_per_hour"] == {"00": 3, "01": 5, "23": 1}
    # With no event log, only minutes that have data count as recorded.
    assert s["minutes_with_data"] == s["minutes_recording"] == 9 and s["coverage_pct"] == 100.0
    assert s["silent_gaps_over_5_min"] == []
    assert s["recorder_off"][0] == {"from": "00:03", "to": "01:30", "minutes": 87}
    assert "gulf_hormuz" in format_summary(s)


def test_summary_separates_silence_from_recorder_off(layout):
    sample_day(layout)
    write_events(layout, "S1", [(ts(0, 0), "session_start")] + heartbeats(ts(0, 10), ts(1, 50))
                 + [(ts(2, 0), "session_stop")])
    write_events(layout, "S2", [(ts(23, 55), "session_start")])  # still running at midnight
    s = summarize_day(layout, "2026-10-12", region_for, now=ts(12, day=13))
    assert s["silent_gaps_over_5_min"] == [{"from": "00:03", "to": "01:30", "minutes": 87},
                                           {"from": "01:35", "to": "02:01", "minutes": 26}]
    assert s["recorder_off"] == [{"from": "02:01", "to": "23:55", "minutes": 1314}]
    assert s["minutes_recording"] == 121 + 5
    text = format_summary(s)
    assert "Silent while recording (5+ min): 2: 00:03-01:30, 01:35-02:01" in text
    assert "Recorder not running: 02:01-23:55" in text


def test_session_running_since_previous_day_counts_from_midnight(layout):
    write_events(layout, "S1", heartbeats(ts(0, 4), ts(0, 54)) + [(ts(1, 0), "session_stop")])
    s = summarize_day(layout, "2026-10-12", region_for, now=ts(12, day=13))
    assert s["minutes_recording"] == 61 and s["recorder_off"][0]["from"] == "01:01"
    assert s["silent_gaps_over_5_min"] == [{"from": "00:00", "to": "01:01", "minutes": 61}]


def test_crashed_session_counts_until_its_last_event(layout):
    write_events(layout, "S1", [(ts(5, 0), "session_start")] + heartbeats(ts(5, 10), ts(5, 30)))
    s = summarize_day(layout, "2026-10-12", region_for, now=ts(12, day=13))
    assert s["minutes_recording"] == 31
    assert s["recorder_off"] == [{"from": "00:00", "to": "05:00", "minutes": 300},
                                 {"from": "05:31", "to": "24:00", "minutes": 1109}]


def test_summary_of_day_in_progress_counts_parts(layout):
    write_day(layout, [(ts(3, 0), position_report()), (ts(3, 1), position_report())], finalize=False)
    write_events(layout, "S1", [(ts(3, 0), "session_start")])
    s = summarize_day(layout, "2026-10-12", region_for, now=ts(3, 10))
    assert s["complete_day"] is False and s["messages"] == 2
    assert s["minutes_elapsed"] == 190 and s["minutes_recording"] == 10
    assert s["silent_gaps_over_5_min"] == [{"from": "03:02", "to": "03:10", "minutes": 8}]
    assert s["recorder_off"] == [{"from": "00:00", "to": "03:00", "minutes": 180}]


def test_summary_empty_day(layout):
    s = summarize_day(layout, "2026-10-12", region_for, now=ts(12, day=13))
    assert s["messages"] == 0 and s["coverage_pct"] is None and s["minutes_recording"] == 0
    text = format_summary(s)
    assert "0 (0 AIS)" in text and "Recording time:  none" in text
