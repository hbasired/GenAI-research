"""A local stand-in for wss://stream.aisstream.io/v0/stream, for tests only.

It follows the documented protocol: the client must send a JSON subscription
within 3 seconds, a wrong key gets {"error": ...} and a close, and AIS
messages are sent as binary frames. Each connection can be scripted to send
some messages and then close, drop, stall or stay open.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

from websockets.asyncio.server import serve

VALID_KEY = "0123456789abcdef0123456789abcdef01234567"


def time_utc(second: int = 0) -> str:
    return f"2026-10-12 03:50:{second:02d}.123456789 +0000 UTC"


def position_report(mmsi: int = 470123456, lat: float = 25.27, lon: float = 55.30, second: int = 0) -> dict:
    return {
        "MessageType": "PositionReport",
        "MetaData": {
            "MMSI": mmsi,
            "MMSI_String": mmsi,
            "ShipName": "TEST VESSEL@@@@     ",
            "latitude": lat,
            "longitude": lon,
            "time_utc": time_utc(second),
        },
        "Message": {
            "PositionReport": {
                "MessageID": 1,
                "RepeatIndicator": 0,
                "UserID": mmsi,
                "Valid": True,
                "NavigationalStatus": 0,
                "RateOfTurn": 0,
                "Sog": 12.3,
                "PositionAccuracy": True,
                "Longitude": lon,
                "Latitude": lat,
                "Cog": 180.5,
                "TrueHeading": 181,
                "Timestamp": second,
                "SpecialManoeuvreIndicator": 0,
                "Spare": 0,
                "Raim": False,
                "CommunicationState": 2249,
            }
        },
    }


def ship_static(mmsi: int = 470123456) -> dict:
    return {
        "MessageType": "ShipStaticData",
        "MetaData": {"MMSI": mmsi, "ShipName": "TEST VESSEL", "latitude": 25.27, "longitude": 55.30,
                     "time_utc": time_utc(5)},
        "Message": {
            "ShipStaticData": {
                "MessageID": 5,
                "RepeatIndicator": 0,
                "UserID": mmsi,
                "Valid": True,
                "AisVersion": 2,
                "ImoNumber": 9876543,
                "CallSign": "A6XY2  ",
                "Name": "TEST VESSEL@@@@@@@@@",
                "Type": 70,
                "Dimension": {"A": 150, "B": 30, "C": 12, "D": 12},
                "FixType": 1,
                "Eta": {"Month": 10, "Day": 14, "Hour": 6, "Minute": 30},
                "MaximumStaticDraught": 9.5,
                "Destination": "AEJEA@@@@",
                "Dte": False,
                "Spare": False,
            }
        },
    }


def base_station(mmsi: int = 4701234, lat: float = 25.0, lon: float = 55.0) -> dict:
    return {
        "MessageType": "BaseStationReport",
        "MetaData": {"MMSI": mmsi, "ShipName": "", "latitude": lat, "longitude": lon, "time_utc": time_utc(7)},
        "Message": {
            "BaseStationReport": {
                "MessageID": 4, "RepeatIndicator": 0, "UserID": mmsi, "Valid": True,
                "UtcYear": 2026, "UtcMonth": 10, "UtcDay": 12, "UtcHour": 3, "UtcMinute": 50, "UtcSecond": 7,
                "PositionAccuracy": True, "Longitude": lon, "Latitude": lat, "FixType": 7,
                "LongRangeEnable": False, "Spare": 0, "Raim": False, "CommunicationState": 0,
            }
        },
    }


def aid_to_navigation(mmsi: int = 992471000, lat: float = 26.5, lon: float = 56.2) -> dict:
    return {
        "MessageType": "AidsToNavigationReport",
        "MetaData": {"MMSI": mmsi, "ShipName": "BUOY", "latitude": lat, "longitude": lon, "time_utc": time_utc(9)},
        "Message": {
            "AidsToNavigationReport": {
                "MessageID": 21, "RepeatIndicator": 0, "UserID": mmsi, "Valid": True, "Type": 1,
                "Name": "HORMUZ BUOY@@@", "PositionAccuracy": False, "Longitude": lon, "Latitude": lat,
                "Dimension": {"A": 0, "B": 0, "C": 0, "D": 0}, "Fixtype": 1, "Timestamp": 9,
                "OffPosition": False, "AtoN": 0, "Raim": False, "VirtualAtoN": True, "AssignedMode": False,
                "Spare": False, "NameExtension": " NORTH",
            }
        },
    }


def static_data_report(mmsi: int = 470999999) -> dict:
    return {
        "MessageType": "StaticDataReport",
        "MetaData": {"MMSI": mmsi, "ShipName": "SMALL BOAT", "latitude": 25.1, "longitude": 55.1,
                     "time_utc": time_utc(11)},
        "Message": {
            "StaticDataReport": {
                "MessageID": 24, "RepeatIndicator": 0, "UserID": mmsi, "Valid": True, "Reserved": 0,
                "PartNumber": True,
                "ReportA": {"Valid": False, "Name": ""},
                "ReportB": {"Valid": True, "ShipType": 37, "VendorIDName": "ABC", "VenderIDModel": 1,
                            "VenderIDSerial": 2, "CallSign": "A6ZZ", "Dimension": {"A": 5, "B": 5, "C": 2, "D": 2},
                            "FixType": 1, "Spare": 0},
            }
        },
    }


@dataclass
class Script:
    """What the server does on one connection after a valid subscription."""

    messages: list = field(default_factory=list)
    then: str = "close"  # "close", "abort", "stall", "open", "error"
    interval: float = 0.0
    error_text: str = "Service temporarily unavailable"


class MockAisStream:
    def __init__(self, valid_key: str = VALID_KEY, scripts: list[Script] | None = None,
                 default: Script | None = None, send_text_frames: bool = False) -> None:
        self.valid_key = valid_key
        self.scripts = list(scripts or [])
        self.default = default or Script(messages=[position_report()], then="open")
        self.send_text_frames = send_text_frames
        self.subscriptions: list[dict] = []
        self.connections = 0
        self._server = None
        self.port = None

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}"

    async def _send(self, ws, obj) -> None:
        data = json.dumps(obj) if isinstance(obj, (dict, list)) else obj
        if isinstance(data, str) and not self.send_text_frames:
            data = data.encode()
        await ws.send(data)

    async def handler(self, ws) -> None:
        self.connections += 1
        index = self.connections - 1
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=3)
        except asyncio.TimeoutError:
            await ws.close(1008, "subscription not received within 3 seconds")
            return
        sub = json.loads(raw)
        self.subscriptions.append(sub)
        if sub.get("APIKey") != self.valid_key:
            await self._send(ws, {"error": "Api Key Is Not Valid"})
            await ws.close()
            return
        script = self.scripts[index] if index < len(self.scripts) else self.default
        for message in script.messages:
            await self._send(ws, message)
            if script.interval:
                await asyncio.sleep(script.interval)
        if script.then == "close":
            await ws.close()
        elif script.then == "abort":
            ws.transport.abort()
        elif script.then == "error":
            await self._send(ws, {"error": script.error_text})
            await ws.close()
        elif script.then in ("stall", "open"):
            await ws.wait_closed()

    async def __aenter__(self) -> MockAisStream:
        self._server = await serve(self.handler, "127.0.0.1", 0, compression="deflate")
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *exc) -> None:
        self._server.close()
        await self._server.wait_closed()
