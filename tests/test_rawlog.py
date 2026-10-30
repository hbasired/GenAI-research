import gzip
import json
from datetime import datetime, timedelta, timezone

from tracktrust.ingest.aisstream import Frame, classify
from tracktrust.storage.layout import FeedLayout, session_of
from tracktrust.storage.rawlog import (
    RawLogWriter,
    finalize_part,
    gz_path_for,
    iter_raw_lines,
    iter_raw_records,
    make_line,
    recover_orphans,
)

SESSION = "20261012T035000Z-abcd"


def frame(ts, text='{"MessageType":"PositionReport","MetaData":{"MMSI":1}}', conn=1):
    t, obj, kind = classify(text)
    return Frame(ts, conn, t, obj, kind)


def t(hour, minute=0, day=12):
    return datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)


def test_make_line_keeps_server_json_verbatim():
    text = '{"MessageType":"PositionReport","MetaData":{"MMSI":1,"latitude":25.123456789012}}'
    line = make_line(frame(t(3), text), 7)
    assert line.endswith(text + "}")
    record = json.loads(line)
    assert record == {"rx": "2026-10-12T03:00:00.000000Z", "seq": 7, "conn": 1, "kind": "ais",
                      "msg": json.loads(text)}


def test_make_line_reserializes_multiline_json_and_keeps_invalid_text():
    pretty = '{\n  "MessageType": "PositionReport"\n}'
    assert "\n" not in make_line(frame(t(3), pretty), 1)
    record = json.loads(make_line(frame(t(3), "garbage\nline"), 2))
    assert record["kind"] == "invalid" and record["invalid"] == "garbage\nline"


def test_writer_rotates_hourly_and_reports_day_end(tmp_path):
    layout = FeedLayout(tmp_path)
    closed, days = [], []
    writer = RawLogWriter(layout, SESSION, on_file_closed=closed.append, on_day_closed=days.append)
    for ts in [t(22, 10), t(22, 50), t(23, 5), t(0, 1, day=13), t(0, 30, day=13)]:
        writer.write(frame(ts))
    writer.close()
    assert [p.name for p in closed] == [
        f"aisstream_20261012T22_{SESSION}.jsonl.part",
        f"aisstream_20261012T23_{SESSION}.jsonl.part",
        f"aisstream_20261013T00_{SESSION}.jsonl.part",
    ]
    assert days == ["2026-10-12"]
    assert closed[2].parent.name == "date=2026-10-13"
    assert session_of(closed[0]) == SESSION
    seqs = [json.loads(line)["seq"] for p in closed for line in p.read_text().splitlines()]
    assert seqs == [1, 2, 3, 4, 5]


def test_clock_stepping_back_keeps_current_file(tmp_path):
    layout = FeedLayout(tmp_path)
    closed = []
    writer = RawLogWriter(layout, SESSION, on_file_closed=closed.append)
    writer.write(frame(t(5, 0)))
    writer.write(frame(t(4, 59)))  # clock stepped back across the hour
    writer.write(frame(t(5, 1)))
    writer.close()
    assert len(closed) == 1 and len(closed[0].read_text().splitlines()) == 3


def test_finalize_drops_only_the_cut_off_tail(tmp_path):
    part = tmp_path / f"aisstream_20261012T03_{SESSION}.jsonl.part"
    part.write_bytes(b'{"a":1}\n{"a":2}\n\x00\x00\x00\n{"a":3')
    result = finalize_part(part)
    assert (result.kept, result.dropped) == (2, 2)
    assert not part.exists()
    assert gzip.decompress(result.gz.read_bytes()) == b'{"a":1}\n{"a":2}\n'


def test_finalize_after_interrupted_previous_finalize(tmp_path):
    part = tmp_path / f"aisstream_20261012T03_{SESSION}.jsonl.part"
    part.write_bytes(b'{"a":1}\n')
    gz = gz_path_for(part)
    gz.write_bytes(gzip.compress(b'{"a":1}\n'))
    result = finalize_part(part)
    assert result.gz == gz and not part.exists()
    gz.write_bytes(b"corrupt")
    part.write_bytes(b'{"a":1}\n')
    result = finalize_part(part)
    assert gzip.decompress(gz.read_bytes()) == b'{"a":1}\n' and result.kept == 1


def test_finalize_empty_part_removes_it(tmp_path):
    part = tmp_path / f"aisstream_20261012T03_{SESSION}.jsonl.part"
    part.write_bytes(b"")
    result = finalize_part(part)
    assert result.gz is None and not part.exists()


def test_recover_orphans_skips_current_session(tmp_path):
    layout = FeedLayout(tmp_path)
    old = layout.raw_part_path("20261012T02", "20261012T020000Z-1111")
    mine = layout.raw_part_path("20261012T03", SESSION)
    old.parent.mkdir(parents=True)
    old.write_text('{"a":1}\n')
    mine.write_text('{"a":2}\n')
    stray = old.parent / "aisstream_20261012T01_20261012T010000Z-2222.jsonl.gz.tmp"
    stray.write_bytes(b"junk")
    results = recover_orphans(layout, SESSION)
    assert [r.part for r in results] == [old]
    assert mine.exists() and not old.exists() and not stray.exists()
    assert layout.raw_files("2026-10-12") == [gz_path_for(old)]


def test_readers_tolerate_truncated_gzip(tmp_path):
    path = tmp_path / "x.jsonl.gz"
    full = gzip.compress(b"".join(b'{"n":%d}\n' % i for i in range(1000)))
    path.write_bytes(full[: len(full) // 2])
    lines = list(iter_raw_lines(path))
    assert 0 < len(lines) < 1000
    bad = []
    part = tmp_path / "y.jsonl.part"
    part.write_bytes(b'{"n":1}\nnot json\n{"n":2}\n{"n":')
    assert [r["n"] for r in iter_raw_records(part, bad)] == [1, 2]
    assert bad == ["y.jsonl.part:2"]


def test_flush_makes_data_visible_on_disk(tmp_path):
    layout = FeedLayout(tmp_path)
    writer = RawLogWriter(layout, SESSION, on_file_closed=lambda p: None, flush_interval=0.0)
    writer.write(frame(t(3)))
    assert writer.current_path.read_text().count("\n") == 1
    writer.close()


def test_day_boundary_uses_utc_receive_time(tmp_path):
    layout = FeedLayout(tmp_path)
    closed = []
    writer = RawLogWriter(layout, SESSION, on_file_closed=closed.append)
    dubai = timezone(timedelta(hours=4))
    writer.write(frame(datetime(2026, 10, 13, 2, 0, tzinfo=dubai).astimezone(timezone.utc)))
    writer.close()
    assert closed[0].parent.name == "date=2026-10-12"
