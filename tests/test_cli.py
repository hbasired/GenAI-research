import argparse
import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from aisstream_mock import VALID_KEY, MockAisStream, Script, position_report

from tracktrust import cli

REPO_CONFIG = str(Path(__file__).resolve().parent.parent / "config" / "aisstream.toml")


@pytest.mark.parametrize("text, seconds", [("90", 90), ("90s", 90), ("45m", 2700), ("2h", 7200), ("1d", 86400),
                                           ("1.5h", 5400)])
def test_parse_duration(text, seconds):
    assert cli.parse_duration(text) == seconds


@pytest.mark.parametrize("text", ["", "abc", "5w", "0", "-1h"])
def test_parse_duration_rejects(text):
    with pytest.raises(argparse.ArgumentTypeError):
        cli.parse_duration(text)


def test_resolve_day():
    today = datetime.now(timezone.utc).date()
    assert cli.resolve_day("today") == today.isoformat()
    assert cli.resolve_day("yesterday") == (today - timedelta(days=1)).isoformat()
    assert cli.resolve_day("2026-10-12") == "2026-10-12"
    with pytest.raises(argparse.ArgumentTypeError):
        cli.resolve_day("12/10/2026")


def test_regions_command(capsys):
    assert cli.main(["regions", "--config", REPO_CONFIG]) == 0
    out = capsys.readouterr().out
    assert "[on ] gulf_hormuz" in out and "[off] red_sea_aden" in out


def test_missing_key_gives_clear_error(capsys):
    assert cli.main(["check-key", "--config", REPO_CONFIG]) == 1
    assert "No aisstream.io API key found" in capsys.readouterr().err


def _run_cli_in_thread(argv):
    return asyncio.to_thread(cli.main, argv)


async def test_check_key_command_ok(tmp_path, capsys):
    (tmp_path / ".env").write_text(f"AISSTREAM_API_KEY={VALID_KEY}\n")
    async with MockAisStream(default=Script(messages=[position_report()] * 3, then="open")) as server:
        code = await _run_cli_in_thread(["check-key", "--config", REPO_CONFIG, "--url", server.url, "--timeout", "2"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "OK: Key accepted" in out and VALID_KEY not in out and "****" in out


async def test_check_key_command_rejected(tmp_path, capsys):
    (tmp_path / ".env").write_text("AISSTREAM_API_KEY=wrongkey\n")
    async with MockAisStream() as server:
        code = await _run_cli_in_thread(["check-key", "--config", REPO_CONFIG, "--url", server.url, "--json"])
    assert code == 2
    assert json.loads(capsys.readouterr().out)["status"] == "rejected"


async def test_record_then_summary_and_compact(tmp_path, capsys):
    (tmp_path / ".env").write_text(f"AISSTREAM_API_KEY={VALID_KEY}\n")
    async with MockAisStream(default=Script(messages=[position_report()] * 5, then="open")) as server:
        code = await _run_cli_in_thread(["record", "--config", REPO_CONFIG, "--url", server.url, "--duration", "1"])
    assert code == 0
    assert (tmp_path / "data" / "aisstream" / "logs" / "recorder.log").is_file()
    assert cli.main(["summary", "--config", REPO_CONFIG]) == 0
    assert "Messages:        5 (5 AIS)" in capsys.readouterr().out
    assert cli.main(["compact", "--config", REPO_CONFIG]) == 0  # today is never compacted automatically
    assert "Nothing to compact" in capsys.readouterr().out
    assert cli.main(["recover", "--config", REPO_CONFIG]) == 0


def test_summary_of_empty_day_returns_1(capsys):
    assert cli.main(["summary", "--config", REPO_CONFIG, "--date", "2026-01-01"]) == 1
