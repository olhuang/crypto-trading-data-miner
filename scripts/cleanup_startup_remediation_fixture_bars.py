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
class FixtureBarSignature:
    open: str
    high: str
    low: str
    close: str
    volume: str
    quote_volume: str
    trade_count: int


FIXTURE_SIGNATURES = [
    FixtureBarSignature("84000.000000000000", "84020.000000000000", "83980.000000000000", "84010.000000000000", "10.000000000000", "840100.000000000000", 100),
    FixtureBarSignature("84010.000000000000", "84040.000000000000", "84005.000000000000", "84030.000000000000", "12.000000000000", "1008360.000000000000", 120),
    FixtureBarSignature("84210.100000000000", "84255.000000000000", "84190.500000000000", "84250.120000000000", "152.230100000000", "12824611.910000000000", 1289),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Delete known startup-remediation test fixture bars from local Binance perp market data. "
            "This is intended to clean local DB contamination from test-only bars."
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
        help="Show matching rows without deleting them.",
    )
    return parser.parse_args()


def signature_cte_sql() -> str:
    rows = []
    for item in FIXTURE_SIGNATURES:
        rows.append(
            "select "
            f"'{item.open}'::numeric as open, "
            f"'{item.high}'::numeric as high, "
            f"'{item.low}'::numeric as low, "
            f"'{item.close}'::numeric as close, "
            f"'{item.volume}'::numeric as volume, "
            f"'{item.quote_volume}'::numeric as quote_volume, "
            f"{item.trade_count}::bigint as trade_count"
        )
    return " union all ".join(rows)


def preview_rows(connection, *, symbols: list[str]) -> list[dict]:
    return list(
        connection.execute(
            text(
                f"""
                with fixture_signatures as (
                    {signature_cte_sql()}
                )
                select
                    i.unified_symbol,
                    count(*) as row_count,
                    min(b.bar_time) as min_bar_time,
                    max(b.bar_time) as max_bar_time
                from md.bars_1m b
                join ref.instruments i on i.instrument_id = b.instrument_id
                join ref.exchanges e on e.exchange_id = i.exchange_id
                join fixture_signatures s
                  on s.open = b.open
                 and s.high = b.high
                 and s.low = b.low
                 and s.close = b.close
                 and s.volume = b.volume
                 and s.quote_volume = b.quote_volume
                 and s.trade_count = b.trade_count
                where e.exchange_code = 'binance'
                  and i.unified_symbol = any(:symbols)
                group by i.unified_symbol
                order by i.unified_symbol
                """
            ),
            {"symbols": symbols},
        ).mappings()
    )


def delete_rows(connection, *, symbols: list[str]) -> int:
    return int(
        connection.execute(
            text(
                f"""
                with fixture_signatures as (
                    {signature_cte_sql()}
                )
                delete from md.bars_1m b
                using ref.instruments i, ref.exchanges e, fixture_signatures s
                where i.instrument_id = b.instrument_id
                  and e.exchange_id = i.exchange_id
                  and e.exchange_code = 'binance'
                  and i.unified_symbol = any(:symbols)
                  and s.open = b.open
                  and s.high = b.high
                  and s.low = b.low
                  and s.close = b.close
                  and s.volume = b.volume
                  and s.quote_volume = b.quote_volume
                  and s.trade_count = b.trade_count
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
        preview = preview_rows(connection, symbols=args.symbols)
        if not preview:
            print("No startup-remediation fixture bars found.")
            return 0

        for row in preview:
            print(
                f"- {row['unified_symbol']}: row_count={row['row_count']}, "
                f"min_bar_time={row['min_bar_time']}, max_bar_time={row['max_bar_time']}"
            )

        if args.dry_run:
            print("Dry run finished. No rows were deleted.")
            return 0

        deleted = delete_rows(connection, symbols=args.symbols)

    print(f"Cleanup finished. Total rows deleted: {deleted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
