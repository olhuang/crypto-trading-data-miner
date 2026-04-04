from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from storage.db import transaction_scope


UTC = timezone.utc


@dataclass(frozen=True, slots=True)
class CleanupTarget:
    name: str
    table_name: str
    time_column: str


TARGETS = [
    CleanupTarget("bars_1m", "md.bars_1m", "bar_time"),
    CleanupTarget("funding_rates", "md.funding_rates", "funding_time"),
    CleanupTarget("open_interest", "md.open_interest", "ts"),
    CleanupTarget("mark_prices", "md.mark_prices", "ts"),
    CleanupTarget("index_prices", "md.index_prices", "ts"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Delete future-dated Binance market-data rows from the local DB. "
            "By default this targets BTCUSDT_SPOT and BTCUSDT_PERP."
        )
    )
    parser.add_argument(
        "--cutoff",
        default=None,
        help="UTC cutoff timestamp in ISO-8601 format. Rows later than this are deleted. Defaults to current UTC time.",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["BTCUSDT_SPOT", "BTCUSDT_PERP"],
        help="Unified symbols to clean. Default: BTCUSDT_SPOT BTCUSDT_PERP",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without modifying the database.",
    )
    return parser.parse_args()


def parse_cutoff(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def preview_future_rows(connection, *, target: CleanupTarget, cutoff: datetime, symbols: list[str]) -> list[dict]:
    return list(
        connection.execute(
            text(
                f"""
                select
                    i.unified_symbol,
                    count(*) as row_count,
                    min(t.{target.time_column}) as min_ts,
                    max(t.{target.time_column}) as max_ts
                from {target.table_name} t
                join ref.instruments i on i.instrument_id = t.instrument_id
                join ref.exchanges e on e.exchange_id = i.exchange_id
                where e.exchange_code = 'binance'
                  and i.unified_symbol = any(:symbols)
                  and t.{target.time_column} > :cutoff
                group by i.unified_symbol
                order by i.unified_symbol
                """
            ),
            {"cutoff": cutoff, "symbols": symbols},
        ).mappings()
    )


def delete_future_rows(connection, *, target: CleanupTarget, cutoff: datetime, symbols: list[str]) -> int:
    return int(
        connection.execute(
            text(
                f"""
                delete from {target.table_name} t
                using ref.instruments i, ref.exchanges e
                where i.instrument_id = t.instrument_id
                  and e.exchange_id = i.exchange_id
                  and e.exchange_code = 'binance'
                  and i.unified_symbol = any(:symbols)
                  and t.{target.time_column} > :cutoff
                """
            ),
            {"cutoff": cutoff, "symbols": symbols},
        ).rowcount
    )


def main() -> int:
    args = parse_args()
    cutoff = parse_cutoff(args.cutoff)

    print(f"Cutoff: {cutoff.isoformat()}")
    print(f"Symbols: {', '.join(args.symbols)}")
    print(f"Mode: {'dry-run' if args.dry_run else 'delete'}")

    with transaction_scope() as connection:
        total_deleted = 0
        for target in TARGETS:
            preview = preview_future_rows(connection, target=target, cutoff=cutoff, symbols=args.symbols)
            print("")
            print(f"[{target.name}]")
            if not preview:
                print("No future-dated rows found.")
                continue
            for row in preview:
                print(
                    f"- {row['unified_symbol']}: row_count={row['row_count']}, "
                    f"min_ts={row['min_ts']}, max_ts={row['max_ts']}"
                )

            if args.dry_run:
                continue

            deleted = delete_future_rows(connection, target=target, cutoff=cutoff, symbols=args.symbols)
            total_deleted += deleted
            print(f"Deleted rows: {deleted}")

    if args.dry_run:
        print("")
        print("Dry run finished. No rows were deleted.")
    else:
        print("")
        print(f"Cleanup finished. Total rows deleted: {total_deleted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
