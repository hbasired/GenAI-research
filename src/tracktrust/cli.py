"""Command line: `tracktrust <command>` or `python -m tracktrust <command>`.

    tracktrust check-key           test the aisstream.io API key
    tracktrust record              record the live feed until Ctrl+C (the daily command)
    tracktrust summary             coverage summary for a day
    tracktrust compact             convert finished days to Parquet
    tracktrust recover             finalize files left by a crashed recorder
    tracktrust regions             list the configured regions
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import logging.handlers
import re
import sys
from datetime import datetime, timedelta, timezone

from tracktrust import __version__
from tracktrust.ingest.aisstream import AISSTREAM_URL, check_key
from tracktrust.settings import Settings, SettingsError, load_api_key, load_settings, mask_key
from tracktrust.storage.layout import FeedLayout, parse_day

log = logging.getLogger("tracktrust")

WORLD_BOX = [[-90.0, -180.0], [90.0, 180.0]]


def parse_duration(text: str) -> float:
    """'90s', '45m', '2h', '1d' or plain seconds."""
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([smhd]?)\s*", text.lower())
    if not match:
        raise argparse.ArgumentTypeError(f"invalid duration {text!r}; use for example 30m, 2h or 1d")
    value = float(match.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}[match.group(2)]
    if value <= 0:
        raise argparse.ArgumentTypeError("duration must be positive")
    return value


def resolve_day(text: str) -> str:
    today = datetime.now(timezone.utc).date()
    if text == "today":
        return today.isoformat()
    if text == "yesterday":
        return (today - timedelta(days=1)).isoformat()
    try:
        return parse_day(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid date {text!r}; use YYYY-MM-DD, today or yesterday") from None


def _setup_logging(verbose: bool, log_file=None) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))
    root.addHandler(console)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=10_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s %(message)s"))
        root.addHandler(handler)
    logging.getLogger("websockets").setLevel(logging.WARNING)


def _settings(args: argparse.Namespace) -> Settings:
    settings = load_settings(args.config, args.data_dir)
    regions = getattr(args, "region", None)
    return settings.select_regions(regions) if regions else settings


def _boxes(settings: Settings) -> list[list[list[float]]]:
    return [r.as_subscription_box() for r in settings.enabled_regions]


def cmd_regions(args: argparse.Namespace) -> int:
    settings = _settings(args)
    print(f"Config: {settings.config_path or 'built-in defaults'}")
    print(f"Data directory: {settings.aisstream_dir}")
    for r in settings.regions:
        flag = "on " if r.enabled else "off"
        print(f"  [{flag}] {r.name:<18} lat {r.lat_min:g}..{r.lat_max:g}, lon {r.lon_min:g}..{r.lon_max:g}  {r.description}")
    return 0


def cmd_check_key(args: argparse.Namespace) -> int:
    settings = _settings(args)
    key = load_api_key(args.env_file)
    boxes = [WORLD_BOX] if args.world else _boxes(settings)
    where = "the whole world" if args.world else ", ".join(r.name for r in settings.enabled_regions)
    print(f"Testing aisstream.io key {mask_key(key)} on {where} (up to {args.timeout:.0f} s)...",
          file=sys.stderr if args.json else sys.stdout)
    result = asyncio.run(check_key(key, boxes, url=args.url, timeout=args.timeout))
    if args.json:
        print(json.dumps(result.__dict__, indent=2, default=str))
    else:
        print(("OK: " if result.ok else "PROBLEM: ") + result.detail)
        if result.first_message_after_s is not None:
            print(f"  First message after {result.first_message_after_s} s")
        if result.message_types:
            print("  Message types: " + ", ".join(f"{k} {v}" for k, v in result.message_types.items()))
        if result.sample:
            print(f"  Example: {result.sample}")
        if result.status == "no_data" and not args.world:
            print("  Next step: run `tracktrust check-key --world` to test the key without the region limit.")
    return {"ok": 0, "rejected": 2, "no_data": 3, "network_error": 4}[result.status]


def cmd_record(args: argparse.Namespace) -> int:
    from tracktrust.recorder import EXIT_ALREADY_RUNNING, Recorder
    from tracktrust.storage.lock import AlreadyRunning

    settings = _settings(args)
    key = load_api_key(args.env_file)
    layout = FeedLayout(settings.aisstream_dir)
    _setup_logging(args.verbose, layout.logs_dir / "recorder.log")
    log.info("Recording aisstream.io live AIS (tracktrust %s)", __version__)
    log.info("  Key:      %s", mask_key(key))
    for r in settings.enabled_regions:
        log.info("  Region:   %s  lat %g..%g, lon %g..%g", r.name, r.lat_min, r.lat_max, r.lon_min, r.lon_max)
    log.info("  Saving to %s", layout.root)
    if args.duration:
        log.info("  Stops after %s", timedelta(seconds=round(args.duration)))
    log.info("  Stop with Ctrl+C. Restarting later is safe: files are never overwritten.")
    recorder = Recorder(
        settings,
        key,
        url=args.url,
        duration_s=args.duration,
        auto_compact=False if args.no_compact else None,
    )
    try:
        return asyncio.run(recorder.run())
    except AlreadyRunning as exc:
        log.error("%s", exc)
        return EXIT_ALREADY_RUNNING


def cmd_summary(args: argparse.Namespace) -> int:
    from tracktrust.summary import format_summary, summarize_day, write_summary

    settings = _settings(args)
    layout = FeedLayout(settings.aisstream_dir)
    summary = summarize_day(layout, args.date, settings.region_for)
    if args.save:
        write_summary(layout, summary)
    print(json.dumps(summary, indent=2) if args.json else format_summary(summary))
    return 0 if summary["messages"] else 1


def cmd_compact(args: argparse.Namespace) -> int:
    from tracktrust.storage.compact import DayNotReady, compact_day, pending_days
    from tracktrust.summary import summarize_day, write_summary

    settings = _settings(args)
    layout = FeedLayout(settings.aisstream_dir)
    today = datetime.now(timezone.utc).date().isoformat()
    if args.date:
        days = args.date
    elif args.force:
        days = [d for d in layout.raw_days() if d < today]
    else:
        days = pending_days(layout, today)
    if not days:
        print("Nothing to compact: every finished day is already up to date.")
        return 0
    failures = 0
    for day in days:
        try:
            result = compact_day(layout, day, settings.region_for, force=args.force,
                                 regions_label=[r.name for r in settings.enabled_regions])
        except DayNotReady as exc:
            print(f"{day}: skipped. {exc}")
            failures += 1
            continue
        print(f"{day}: {result.status} {result.rows if result.rows else ''}".rstrip())
        if result.status == "written":
            write_summary(layout, summarize_day(layout, day, settings.region_for))
    return 1 if failures else 0


def cmd_recover(args: argparse.Namespace) -> int:
    from tracktrust.storage.lock import AlreadyRunning, RecorderLock
    from tracktrust.storage.rawlog import recover_orphans

    settings = _settings(args)
    layout = FeedLayout(settings.aisstream_dir)
    lock = RecorderLock(layout.lock_path)
    try:
        lock.acquire()
    except AlreadyRunning as exc:
        print(f"Not recovering: {exc}")
        return 3
    try:
        results = recover_orphans(layout)
    finally:
        lock.release()
    if not results:
        print("No unfinished files found.")
    for r in results:
        print(f"{r.part.name}: kept {r.kept} lines, dropped {r.dropped}" + ("" if r.gz else " (empty, removed)"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", help="config file (default: config/aisstream.toml)")
    common.add_argument("--data-dir", help="where recordings are stored (default: data_dir from the config)")
    common.add_argument("-v", "--verbose", action="store_true", help="more detailed logging")

    keyed = argparse.ArgumentParser(add_help=False)
    keyed.add_argument("--env-file", help="file holding AISSTREAM_API_KEY (default: .env)")
    keyed.add_argument("--url", default=AISSTREAM_URL, help=argparse.SUPPRESS)

    parser = argparse.ArgumentParser(prog="tracktrust", description="Record and check live AIS data from aisstream.io.")
    parser.add_argument("--version", action="version", version=f"tracktrust {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check-key", parents=[common, keyed], help="test the aisstream.io API key")
    p.add_argument("--timeout", type=float, default=30.0, help="seconds to wait for data (default 30)")
    p.add_argument("--world", action="store_true", help="subscribe to the whole world instead of the regions")
    p.add_argument("--region", action="append", help="test only this region (repeatable)")
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    p.set_defaults(func=cmd_check_key)

    p = sub.add_parser("record", parents=[common, keyed], help="record the live feed until Ctrl+C")
    p.add_argument("--region", action="append", help="record only this region (repeatable; default: enabled regions)")
    p.add_argument("--duration", type=parse_duration, help="stop after this long, e.g. 30m, 8h, 1d")
    p.add_argument("--no-compact", action="store_true", help="do not convert finished days to Parquet")
    p.set_defaults(func=cmd_record)

    p = sub.add_parser("summary", parents=[common], help="coverage summary for one UTC day")
    p.add_argument("--date", type=resolve_day, default=resolve_day("today"),
                   help="YYYY-MM-DD, today (default) or yesterday")
    p.add_argument("--json", action="store_true", help="print the full summary as JSON")
    p.add_argument("--save", action="store_true", help="also save it under summaries/")
    p.set_defaults(func=cmd_summary)

    p = sub.add_parser("compact", parents=[common], help="convert finished days to Parquet")
    p.add_argument("--date", type=resolve_day, action="append", help="only this day (repeatable)")
    p.add_argument("--force", action="store_true", help="rebuild even if up to date")
    p.set_defaults(func=cmd_compact)

    p = sub.add_parser("recover", parents=[common], help="finalize files left by a crashed recorder")
    p.set_defaults(func=cmd_recover)

    p = sub.add_parser("regions", parents=[common], help="list the configured regions")
    p.set_defaults(func=cmd_regions)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "record":
        _setup_logging(getattr(args, "verbose", False))
    try:
        return args.func(args)
    except SettingsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
