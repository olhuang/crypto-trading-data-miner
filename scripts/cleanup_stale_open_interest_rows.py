from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from storage.db import transaction_scope


UTC = timezone.utc
OPEN_INTEREST_RETENTION_DAYS = 30


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "One-time cleanup for local Binance open-interest rows that fall outside the current "
            "recent-history retention policy. This is intended to remove obvious stale fixture/"
            "legacy rows that predate the rolling retention window."
        )
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["BTCUSDT_PERP"],
        help="Unified symbols to clean. Default: BTCUSDT_PERP",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=OPEN_INTEREST_RETENTION_DAYS,
        help="Rolling retention window in days. Default: 30",
    )
    parser.add_argument(
        "--observed-at",
        default=None,
        help="UTC cutoff anchor in ISO-8601 format. Defaults to current UTC time.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without modifying the database.",
    )
    return parser.parse_args()


def parse_observed_at(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def retention_floor(*, observed_at: datetime, retention_days: int) -> datetime:
    floor = observed_at - timedelta(days=retention_days)
    return floor.replace(hour=0, minute=0, second=0, microsecond=0)


def preview_rows(connection, *, floor: datetime, symbols: list[str]) -> list[dict]:
    return list(
        connection.execute(
            text(
                """
                select
                    i.unified_symbol,
                    count(*) as row_count,
                    min(oi.ts) as min_ts,
                    max(oi.ts) as max_ts
                from md.open_interest oi
                join ref.instruments i on i.instrument_id = oi.instrument_id
                join ref.exchanges e on e.exchange_id = i.exchange_id
                where e.exchange_code = 'binance'
                  and i.unified_symbol = any(:symbols)
                  and oi.ts < :floor
                group by i.unified_symbol
                order by i.unified_symbol
                """
            ),
            {"symbols": symbols, "floor": floor},
        ).mappings()
    )


def sample_rows(connection, *, floor: datetime, symbols: list[str]) -> list[dict]:
    return list(
        connection.execute(
            text(
                """
                select
                    i.unified_symbol,
                    oi.ts,
                    oi.open_interest
                from md.open_interest oi
                join ref.instruments i on i.instrument_id = oi.instrument_id
                join ref.exchanges e on e.exchange_id = i.exchange_id
                where e.exchange_code = 'binance'
                  and i.unified_symbol = any(:symbols)
                  and oi.ts < :floor
                order by i.unified_symbol, oi.ts asc
                limit 20
                """
            ),
            {"symbols": symbols, "floor": floor},
        ).mappings()
    )


def delete_rows(connection, *, floor: datetime, symbols: list[str]) -> int:
    return int(
        connection.execute(
            text(
                """
                delete from md.open_interest oi
                using ref.instruments i, ref.exchanges e
                where i.instrument_id = oi.instrument_id
                  and e.exchange_id = i.exchange_id
                  and e.exchange_code = 'binance'
                  and i.unified_symbol = any(:symbols)
                  and oi.ts < :floor
                """
            ),
            {"symbols": symbols, "floor": floor},
        ).rowcount
    )


def main() -> int:
    args = parse_args()
    observed_at = parse_observed_at(args.observed_at)
    floor = retention_floor(observed_at=observed_at, retention_days=args.retention_days)

    print(f"Observed At: {observed_at.isoformat()}")
    print(f"Retention Days: {args.retention_days}")
    print(f"Retention Floor: {floor.isoformat()}")
    print(f"Symbols: {', '.join(args.symbols)}")
    print(f"Mode: {'dry-run' if args.dry_run else 'delete'}")

    with transaction_scope() as connection:
        preview = preview_rows(connection, floor=floor, symbols=args.symbols)
        if not preview:
            print("")
            print("No stale open-interest rows found outside the retention window.")
            return 0

        print("")
        print("Summary:")
        for row in preview:
            print(
                f"- {row['unified_symbol']}: row_count={row['row_count']}, "
                f"min_ts={row['min_ts']}, max_ts={row['max_ts']}"
            )

        examples = sample_rows(connection, floor=floor, symbols=args.symbols)
        if examples:
            print("")
            print("Sample rows:")
            for row in examples:
                print(
                    f"- {row['unified_symbol']}: ts={row['ts']}, "
                    f"open_interest={row['open_interest']}"
                )

        if args.dry_run:
            print("")
            print("Dry run finished. No rows were deleted.")
            return 0

        deleted = delete_rows(connection, floor=floor, symbols=args.symbols)

    print("")
    print(f"Cleanup finished. Total rows deleted: {deleted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
