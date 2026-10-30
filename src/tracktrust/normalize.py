"""Turn raw aisstream.io messages into rows for four research tables.

- positions: vessel and aircraft position reports (AIS types 1-3, 9, 18, 19, 27)
- static: identity and voyage data (types 5 and 24, and the static part of 19)
- base_stations: shore base-station reports (type 4). Their positions are fixed,
  so a jump in a base station's reported position or clock is a direct sign of
  GNSS interference.
- aids_to_navigation: type 21 reports, including virtual aids, which can be spoofed.

Values are kept as transmitted (91/181 still mean "not available"); cleaning
belongs to the later fidelity stages. Each row carries three times:
`rx_time` (this machine received it), `server_time` (aisstream.io's
`MetaData.time_utc`) and, where present, `ais_second` (the UTC second the
transponder stamped, 0-59, with 60-63 meaning not available).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

POSITION_CLASSES = {
    "PositionReport": "A",
    "StandardClassBPositionReport": "B",
    "ExtendedClassBPositionReport": "B",
    "LongRangeAisBroadcastMessage": "LR",
    "StandardSearchAndRescueAircraftReport": "SAR",
}
STATIC_TYPES = {"ShipStaticData", "StaticDataReport", "ExtendedClassBPositionReport"}

RegionFn = Callable[[float | None, float | None], str | None]

_SERVER_TIME = re.compile(
    r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.(\d+))?\s*(?:([+-])(\d{2}):?(\d{2})|Z)?"
)


def parse_server_time(value: Any) -> datetime | None:
    """Parse aisstream.io's time_utc, e.g. '2026-07-12 12:00:00.123456789 +0000 UTC'."""
    if not isinstance(value, str):
        return None
    match = _SERVER_TIME.match(value.strip())
    if not match:
        return None
    day, clock, frac, sign, hh, mm = match.groups()
    micros = (frac or "0")[:6].ljust(6, "0")
    try:
        ts = datetime.fromisoformat(f"{day}T{clock}.{micros}")
    except ValueError:
        return None
    offset_min = 0
    if sign:
        offset_min = int(hh) * 60 + int(mm)
        if sign == "-":
            offset_min = -offset_min
    return (ts - timedelta(minutes=offset_min)).replace(tzinfo=timezone.utc)


def parse_rx(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        return datetime.fromisoformat(value[:-1]).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    return None


def clean_text(value: Any) -> str | None:
    """AIS text is padded with spaces and '@'; strip both."""
    if not isinstance(value, str):
        return None
    text = value.replace("@", " ").strip()
    return text or None


def _dims(dim: Any) -> dict[str, int | None]:
    dim = dim if isinstance(dim, dict) else {}
    return {f"dim_{k.lower()}": _int(dim.get(k)) for k in ("A", "B", "C", "D")}


def _base_station_utc(body: dict) -> datetime | None:
    try:
        year, month, day = body["UtcYear"], body["UtcMonth"], body["UtcDay"]
        hour, minute, second = body["UtcHour"], body["UtcMinute"], body["UtcSecond"]
    except KeyError:
        return None
    if not all(isinstance(v, int) for v in (year, month, day, hour, minute, second)):
        return None
    if year == 0 or month == 0 or day == 0 or hour >= 24 or minute >= 60 or second >= 60:
        return None
    try:
        return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    except ValueError:
        return None


def extract_rows(
    record: dict[str, Any], session: str | None = None, region_for: RegionFn | None = None
) -> list[tuple[str, dict[str, Any]]]:
    """Rows (table name, row) for one raw-log record. Non-AIS records give none."""
    msg = record.get("msg")
    if record.get("kind") != "ais" or not isinstance(msg, dict):
        return []
    mtype = msg.get("MessageType")
    message = msg.get("Message")
    body = message.get(mtype) if isinstance(message, dict) and isinstance(mtype, str) else None
    if not isinstance(body, dict):
        return []
    meta = msg.get("MetaData") if isinstance(msg.get("MetaData"), dict) else {}

    base = {
        "rx_time": parse_rx(record.get("rx")),
        "server_time": parse_server_time(meta.get("time_utc")),
        "mmsi": _int(body.get("UserID")) if _int(body.get("UserID")) is not None else _int(meta.get("MMSI")),
        "msg_type": mtype,
        "msg_id": _int(body.get("MessageID")),
        "repeat": _int(body.get("RepeatIndicator")),
        "valid": _bool(body.get("Valid")),
        "session": session,
        "conn": _int(record.get("conn")),
        "seq": _int(record.get("seq")),
    }
    rows: list[tuple[str, dict[str, Any]]] = []

    def region(lat: float | None, lon: float | None) -> str | None:
        return region_for(lat, lon) if region_for else None

    if mtype in POSITION_CLASSES:
        lat, lon = _float(body.get("Latitude")), _float(body.get("Longitude"))
        rows.append(
            (
                "positions",
                {
                    **base,
                    "ais_class": POSITION_CLASSES[mtype],
                    "lat": lat,
                    "lon": lon,
                    "sog": _float(body.get("Sog")),
                    "cog": _float(body.get("Cog")),
                    "heading": _int(body.get("TrueHeading")),
                    "nav_status": _int(body.get("NavigationalStatus")),
                    "rot": _int(body.get("RateOfTurn")),
                    "pos_accuracy": _bool(body.get("PositionAccuracy")),
                    "raim": _bool(body.get("Raim")),
                    "ais_second": _int(body.get("Timestamp")),
                    "special_manoeuvre": _int(body.get("SpecialManoeuvreIndicator")),
                    "assigned_mode": _bool(body.get("AssignedMode")),
                    "altitude": _int(body.get("Altitude")),
                    "position_latency": _bool(body.get("PositionLatency")),
                    "ship_name_meta": clean_text(meta.get("ShipName")),
                    "region": region(lat, lon),
                },
            )
        )

    if mtype in STATIC_TYPES:
        meta_lat, meta_lon = _float(meta.get("latitude")), _float(meta.get("longitude"))
        common = {
            **base,
            "part": None,
            "imo": None,
            "call_sign": None,
            "name": None,
            "ship_type": None,
            "dim_a": None,
            "dim_b": None,
            "dim_c": None,
            "dim_d": None,
            "draught": None,
            "destination": None,
            "eta_month": None,
            "eta_day": None,
            "eta_hour": None,
            "eta_minute": None,
            "fix_type": None,
            "ais_version": None,
            "dte": None,
            "meta_lat": meta_lat,
            "meta_lon": meta_lon,
            "region": region(meta_lat, meta_lon),
        }
        if mtype == "ShipStaticData":
            eta = body.get("Eta") if isinstance(body.get("Eta"), dict) else {}
            rows.append(
                (
                    "static",
                    {
                        **common,
                        "imo": _int(body.get("ImoNumber")),
                        "call_sign": clean_text(body.get("CallSign")),
                        "name": clean_text(body.get("Name")),
                        "ship_type": _int(body.get("Type")),
                        **_dims(body.get("Dimension")),
                        "draught": _float(body.get("MaximumStaticDraught")),
                        "destination": clean_text(body.get("Destination")),
                        "eta_month": _int(eta.get("Month")),
                        "eta_day": _int(eta.get("Day")),
                        "eta_hour": _int(eta.get("Hour")),
                        "eta_minute": _int(eta.get("Minute")),
                        "fix_type": _int(body.get("FixType")),
                        "ais_version": _int(body.get("AisVersion")),
                        "dte": _bool(body.get("Dte")),
                    },
                )
            )
        elif mtype == "StaticDataReport":
            report_a = body.get("ReportA") if isinstance(body.get("ReportA"), dict) else {}
            report_b = body.get("ReportB") if isinstance(body.get("ReportB"), dict) else {}
            if report_a.get("Valid"):
                rows.append(("static", {**common, "part": "A", "name": clean_text(report_a.get("Name"))}))
            if report_b.get("Valid"):
                rows.append(
                    (
                        "static",
                        {
                            **common,
                            "part": "B",
                            "call_sign": clean_text(report_b.get("CallSign")),
                            "ship_type": _int(report_b.get("ShipType")),
                            **_dims(report_b.get("Dimension")),
                            "fix_type": _int(report_b.get("FixType")),
                        },
                    )
                )
        else:  # ExtendedClassBPositionReport carries static fields too
            rows.append(
                (
                    "static",
                    {
                        **common,
                        "name": clean_text(body.get("Name")),
                        "ship_type": _int(body.get("Type")),
                        **_dims(body.get("Dimension")),
                        "fix_type": _int(body.get("FixType")),
                        "dte": _bool(body.get("Dte")),
                    },
                )
            )

    if mtype == "BaseStationReport":
        lat, lon = _float(body.get("Latitude")), _float(body.get("Longitude"))
        rows.append(
            (
                "base_stations",
                {
                    **base,
                    "lat": lat,
                    "lon": lon,
                    "pos_accuracy": _bool(body.get("PositionAccuracy")),
                    "raim": _bool(body.get("Raim")),
                    "fix_type": _int(body.get("FixType")),
                    "reported_utc": _base_station_utc(body),
                    "region": region(lat, lon),
                },
            )
        )

    if mtype == "AidsToNavigationReport":
        lat, lon = _float(body.get("Latitude")), _float(body.get("Longitude"))
        name = (clean_text(body.get("Name")) or "") + (clean_text(body.get("NameExtension")) or "")
        rows.append(
            (
                "aids_to_navigation",
                {
                    **base,
                    "name": name or None,
                    "aton_type": _int(body.get("Type")),
                    "lat": lat,
                    "lon": lon,
                    "virtual": _bool(body.get("VirtualAtoN")),
                    "off_position": _bool(body.get("OffPosition")),
                    "pos_accuracy": _bool(body.get("PositionAccuracy")),
                    "raim": _bool(body.get("Raim")),
                    "ais_second": _int(body.get("Timestamp")),
                    **_dims(body.get("Dimension")),
                    "region": region(lat, lon),
                },
            )
        )
    return rows
