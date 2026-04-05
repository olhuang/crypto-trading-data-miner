from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from jobs.backfill_bars import run_bar_backfill


UTC = timezone.utc
DEFAULT_WINDOWS = [
    {
        "label": "corrupt_bar_minute",
        "start_time": "2026-04-02T12:34:00+00:00",
        "end_time": "2026-04-02T12:34:59+00:00",
    },
    {
        "label": "late_gap_block_a",
        "start_time": "2026-04-05T01:55:00+00:00",
        "end_time": "2026-04-05T01:57:59+00:00",
    },
    {
        "label": "late_gap_block_b",
        "start_time": "2026-04-05T02:10:00+00:00",
        "end_time": "2026-04-05T02:22:59+00:00",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Repair known BTCUSDT_PERP bar integrity windows by re-fetching bounded 1m kline "
            "history from Binance."
        )
    )
    parser.add_argument("--symbol", default="BTCUSDT", help="Venue symbol. Default: BTCUSDT")
    parser.add_argument(
        "--unified-symbol",
        default="BTCUSDT_PERP",
        help="Unified symbol. Default: BTCUSDT_PERP",
    )
    parser.add_argument(
        "--interval",
        default="1m",
        help="Bar interval. Default: 1m",
    )
    parser.add_argument(
        "--requested-by",
        default="repair_bars_integrity_windows_script",
        help="requested_by value stored on the resulting ingestion job(s).",
    )
    parser.add_argument(
        "--start-time",
        default=None,
        help="Optional UTC ISO timestamp. When supplied with --end-time, repairs only one custom window.",
    )
    parser.add_argument(
        "--end-time",
        default=None,
        help="Optional UTC ISO timestamp. When supplied with --start-time, repairs only one custom window.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the intended repair windows without executing any backfill.",
    )
    return parser.parse_args()


def parse_utc_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def build_windows(args: argparse.Namespace) -> list[dict[str, str]]:
    if bool(args.start_time) ^ bool(args.end_time):
        raise ValueError("start_time and end_time must be supplied together")
    if args.start_time and args.end_time:
        return [
            {
                "label": "custom_window",
                "start_time": args.start_time,
                "end_time": args.end_time,
            }
        ]
    return DEFAULT_WINDOWS


def main() -> int:
    args = parse_args()
    windows = build_windows(args)
    print("Binance bars integrity repair")
    print(json.dumps(
        {
            "symbol": args.symbol,
            "unified_symbol": args.unified_symbol,
            "interval": args.interval,
            "requested_by": args.requested_by,
            "dry_run": args.dry_run,
            "windows": windows,
        },
        indent=2,
    ))

    if args.dry_run:
        print("Dry run only. No backfill executed.")
        return 0

    results = []
    for window in windows:
        start_time = parse_utc_timestamp(window["start_time"])
        end_time = parse_utc_timestamp(window["end_time"])
        result = run_bar_backfill(
            symbol=args.symbol,
            unified_symbol=args.unified_symbol,
            interval=args.interval,
            start_time=start_time,
            end_time=end_time,
            requested_by=args.requested_by,
            exchange_code="binance",
        )
        payload = asdict(result)
        payload["label"] = window["label"]
        payload["start_time"] = start_time.isoformat()
        payload["end_time"] = end_time.isoformat()
        results.append(payload)

    print("")
    print("Repair results:")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
