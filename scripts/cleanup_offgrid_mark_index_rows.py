from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from storage.db import transaction_scope


@dataclass(frozen=True, slots=True)
class CleanupTarget:
    name: str
    table_name: str


TARGETS = [
    CleanupTarget("mark_prices", "md.mark_prices"),
    CleanupTarget("index_prices", "md.index_prices"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Delete off-grid Binance mark/index rows whose timestamps are not aligned to "
            "whole-minute boundaries. This is intended for local cleanup of legacy snapshot "
            "rows that polluted minute-series integrity checks."
        )
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["BTCUSDT_PERP"],
        help="Unified symbols to clean. Default: BTCUSDT_PERP",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without modifying the database.",
    )
    return parser.parse_args()


def preview_offgrid_rows(connection, *, target: CleanupTarget, symbols: list[str]) -> list[dict]:
    return list(
        connection.execute(
            text(
                f"""
                select
                    i.unified_symbol,
                    count(*) as row_count,
                    min(t.ts) as min_ts,
                    max(t.ts) as max_ts
                from {target.table_name} t
                join ref.instruments i on i.instrument_id = t.instrument_id
                join ref.exchanges e on e.exchange_id = i.exchange_id
                where e.exchange_code = 'binance'
                  and i.unified_symbol = any(:symbols)
                  and (
                    date_part('second', t.ts) <> 0
                    or date_part('microseconds', t.ts) <> 0
                  )
                group by i.unified_symbol
                order by i.unified_symbol
                """
            ),
            {"symbols": symbols},
        ).mappings()
    )


def delete_offgrid_rows(connection, *, target: CleanupTarget, symbols: list[str]) -> int:
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
                  and (
                    date_part('second', t.ts) <> 0
                    or date_part('microseconds', t.ts) <> 0
                  )
                """
            ),
            {"symbols": symbols},
        ).rowcount
    )


def main() -> int:
    args = parse_args()
    print(f"Symbols: {', '.join(args.symbols)}")
    print(f"Mode: {'dry-run' if args.dry_run else 'delete'}")

    with transaction_scope() as connection:
        total_deleted = 0
        for target in TARGETS:
            preview = preview_offgrid_rows(connection, target=target, symbols=args.symbols)
            print("")
            print(f"[{target.name}]")
            if not preview:
                print("No off-grid rows found.")
                continue
            for row in preview:
                print(
                    f"- {row['unified_symbol']}: row_count={row['row_count']}, "
                    f"min_ts={row['min_ts']}, max_ts={row['max_ts']}"
                )
            if args.dry_run:
                continue
            deleted = delete_offgrid_rows(connection, target=target, symbols=args.symbols)
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
