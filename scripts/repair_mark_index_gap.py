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

from jobs.refresh_market_snapshots import run_market_snapshot_refresh


UTC = timezone.utc
DEFAULT_START_TIME = "2026-04-03T08:39:00+00:00"
DEFAULT_END_TIME = "2026-04-04T13:27:59+00:00"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Repair a known internal Binance BTC perp mark/index history gap by re-fetching "
            "markPriceKlines and indexPriceKlines for a bounded UTC window."
        )
    )
    parser.add_argument("--symbol", default="BTCUSDT", help="Venue symbol. Default: BTCUSDT")
    parser.add_argument(
        "--unified-symbol",
        default="BTCUSDT_PERP",
        help="Unified symbol. Default: BTCUSDT_PERP",
    )
    parser.add_argument(
        "--start-time",
        default=DEFAULT_START_TIME,
        help=f"UTC ISO timestamp. Default: {DEFAULT_START_TIME}",
    )
    parser.add_argument(
        "--end-time",
        default=DEFAULT_END_TIME,
        help=f"UTC ISO timestamp. Default: {DEFAULT_END_TIME}",
    )
    parser.add_argument(
        "--requested-by",
        default="repair_mark_index_gap_script",
        help="requested_by value stored on the resulting ingestion job.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the intended repair window without executing the refresh.",
    )
    return parser.parse_args()


def parse_utc_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def main() -> int:
    args = parse_args()
    start_time = parse_utc_timestamp(args.start_time)
    end_time = parse_utc_timestamp(args.end_time)
    if end_time < start_time:
        raise ValueError("end_time must be greater than or equal to start_time")

    print("Binance mark/index gap repair")
    print(json.dumps(
        {
            "symbol": args.symbol,
            "unified_symbol": args.unified_symbol,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "requested_by": args.requested_by,
            "dry_run": args.dry_run,
        },
        indent=2,
    ))

    if args.dry_run:
        print("Dry run only. No refresh executed.")
        return 0

    result = run_market_snapshot_refresh(
        symbol=args.symbol,
        unified_symbol=args.unified_symbol,
        requested_by=args.requested_by,
        exchange_code="binance",
        history_start_time=start_time,
        history_end_time=end_time,
        include_funding=False,
        include_open_interest=False,
        include_mark_price=True,
        include_index_price=True,
    )
    print("")
    print("Repair result:")
    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
