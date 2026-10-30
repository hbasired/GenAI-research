from datetime import datetime, timezone

import pytest
from aisstream_mock import aid_to_navigation, base_station, position_report, ship_static, static_data_report

from tracktrust.normalize import extract_rows, parse_rx, parse_server_time


def record(msg, kind="ais"):
    return {"rx": "2026-10-12T03:50:01.500000Z", "seq": 3, "conn": 1, "kind": kind, "msg": msg}


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2026-07-12 12:00:00.123456789 +0000 UTC", datetime(2026, 7, 12, 12, 0, 0, 123456, tzinfo=timezone.utc)),
        ("2026-07-12 12:00:00 +0000 UTC", datetime(2026, 7, 12, 12, tzinfo=timezone.utc)),
        ("2026-07-12 16:00:00.5 +0400 +04", datetime(2026, 7, 12, 12, 0, 0, 500000, tzinfo=timezone.utc)),
        ("2026-07-12T12:00:00Z", datetime(2026, 7, 12, 12, tzinfo=timezone.utc)),
        ("garbage", None),
        (None, None),
    ],
)
def test_parse_server_time(text, expected):
    assert parse_server_time(text) == expected


def test_parse_rx():
    assert parse_rx("2026-10-12T03:50:01.500000Z") == datetime(2026, 10, 12, 3, 50, 1, 500000, tzinfo=timezone.utc)
    assert parse_rx("2026-10-12T03:50:01") is None


def test_position_row():
    rows = extract_rows(record(position_report(lat=25.27, lon=55.30, second=4)), "S1",
                        lambda lat, lon: "gulf" if lat > 20 else None)
    assert len(rows) == 1
    table, row = rows[0]
    assert table == "positions"
    assert row["mmsi"] == 470123456 and row["ais_class"] == "A"
    assert (row["lat"], row["lon"], row["sog"], row["heading"], row["ais_second"]) == (25.27, 55.30, 12.3, 181, 4)
    assert row["server_time"] == datetime(2026, 10, 12, 3, 50, 4, 123456, tzinfo=timezone.utc)
    assert row["rx_time"] == datetime(2026, 10, 12, 3, 50, 1, 500000, tzinfo=timezone.utc)
    assert row["ship_name_meta"] == "TEST VESSEL"
    assert row["region"] == "gulf" and row["session"] == "S1" and row["seq"] == 3


def test_static_row_strips_ais_padding():
    (table, row), = extract_rows(record(ship_static()))
    assert table == "static"
    assert row["name"] == "TEST VESSEL" and row["call_sign"] == "A6XY2" and row["destination"] == "AEJEA"
    assert row["imo"] == 9876543 and row["ship_type"] == 70 and row["draught"] == 9.5
    assert (row["dim_a"], row["dim_b"], row["eta_month"], row["eta_minute"]) == (150, 30, 10, 30)


def test_static_data_report_part_b():
    (table, row), = extract_rows(record(static_data_report()))
    assert table == "static" and row["part"] == "B" and row["ship_type"] == 37 and row["call_sign"] == "A6ZZ"


def test_base_station_row_has_reported_clock():
    (table, row), = extract_rows(record(base_station()))
    assert table == "base_stations"
    assert row["reported_utc"] == datetime(2026, 10, 12, 3, 50, 7, tzinfo=timezone.utc)
    assert row["fix_type"] == 7


def test_aid_to_navigation_row():
    (table, row), = extract_rows(record(aid_to_navigation()))
    assert table == "aids_to_navigation"
    assert row["virtual"] is True and row["name"] == "HORMUZ BUOYNORTH"


def test_extended_class_b_gives_position_and_static():
    msg = {
        "MessageType": "ExtendedClassBPositionReport",
        "MetaData": {"MMSI": 470000001, "time_utc": "2026-10-12 03:50:00 +0000 UTC"},
        "Message": {"ExtendedClassBPositionReport": {
            "MessageID": 19, "UserID": 470000001, "Latitude": 25.0, "Longitude": 55.0, "Sog": 1.0, "Cog": 2.0,
            "TrueHeading": 511, "Timestamp": 60, "Name": "DHOW@@", "Type": 30,
            "Dimension": {"A": 10, "B": 5, "C": 2, "D": 2}, "FixType": 1, "Raim": False, "Dte": True}},
    }
    tables = sorted(t for t, _ in extract_rows(record(msg)))
    assert tables == ["positions", "static"]


def test_non_ais_and_malformed_records_give_no_rows():
    assert extract_rows(record({"error": "x"}, kind="error")) == []
    assert extract_rows({"rx": "x", "kind": "invalid", "invalid": "garbage"}) == []
    assert extract_rows(record({"MessageType": "PositionReport", "Message": {}})) == []
    assert extract_rows(record({"MessageType": "PositionReport", "Message": {"PositionReport": "bad"}})) == []


def test_unexpected_value_types_become_null():
    msg = position_report()
    msg["Message"]["PositionReport"]["Sog"] = "fast"
    msg["Message"]["PositionReport"]["TrueHeading"] = 181.5
    (_, row), = extract_rows(record(msg))
    assert row["sog"] is None and row["heading"] is None
