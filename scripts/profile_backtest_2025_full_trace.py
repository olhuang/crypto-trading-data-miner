from __future__ import annotations

import argparse
import cProfile
from datetime import datetime, timezone
from decimal import Decimal
from io import StringIO
from pathlib import Path
import pstats
import sys
import time

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from backtest.runner import BacktestRunnerSkeleton
from models.backtest import BacktestRunConfig
from storage.db import get_engine


DEFAULT_START = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
DEFAULT_END = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)
DEFAULT_STATS_PATH = PROJECT_ROOT / "tmp" / "backtest_2025_full_trace.prof"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "tmp" / "backtest_2025_full_trace_report.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Profile one full 2025 backtest run using the real DB-backed minute bars and persisted full debug traces."
        )
    )
    parser.add_argument("--start-time", default=DEFAULT_START.isoformat())
    parser.add_argument("--end-time", default=DEFAULT_END.isoformat())
    parser.add_argument("--exchange-code", default="binance")
    parser.add_argument("--unified-symbol", default="BTCUSDT_PERP")
    parser.add_argument("--strategy-code", default="btc_4h_breakout_perp")
    parser.add_argument("--strategy-version", default="v0.1.0")
    parser.add_argument("--assumption-bundle-code", default="breakout_perp_research")
    parser.add_argument("--assumption-bundle-version", default="v1")
    parser.add_argument("--risk-policy-code", default="perp_medium_v1")
    parser.add_argument("--account-code", default="paper_main")
    parser.add_argument("--run-name", default="profile_btc_2025_full_trace")
    parser.add_argument("--initial-cash", default="100000")
    parser.add_argument("--persist-signals", action="store_true", default=True)
    parser.add_argument("--no-persist-signals", dest="persist_signals", action="store_false")
    parser.add_argument("--commit", action="store_true", help="Commit the profiled run instead of rolling it back.")
    parser.add_argument("--stats-path", default=str(DEFAULT_STATS_PATH))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--top-n", type=int, default=40)
    return parser.parse_args()


def _parse_ts(raw: str) -> datetime:
    normalized = raw.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _query_dataset_coverage(connection, *, exchange_code: str, unified_symbol: str, start_time: datetime, end_time: datetime) -> list[dict]:
    rows = connection.execute(
        text(
            """
            select dataset, min_ts, max_ts, row_count
            from (
                select 'bars_1m' as dataset, min(b.bar_time) as min_ts, max(b.bar_time) as max_ts, count(*) as row_count
                from md.bars_1m b
                join ref.instruments i on i.instrument_id = b.instrument_id
                join ref.exchanges e on e.exchange_id = i.exchange_id
                where e.exchange_code = :exchange_code
                  and i.unified_symbol = :unified_symbol
                  and b.bar_time >= :start_time
                  and b.bar_time <= :end_time
                union all
                select 'funding_rates', min(f.funding_time), max(f.funding_time), count(*)
                from md.funding_rates f
                join ref.instruments i on i.instrument_id = f.instrument_id
                join ref.exchanges e on e.exchange_id = i.exchange_id
                where e.exchange_code = :exchange_code
                  and i.unified_symbol = :unified_symbol
                  and f.funding_time >= :start_time
                  and f.funding_time <= :end_time
                union all
                select 'open_interest', min(o.ts), max(o.ts), count(*)
                from md.open_interest o
                join ref.instruments i on i.instrument_id = o.instrument_id
                join ref.exchanges e on e.exchange_id = i.exchange_id
                where e.exchange_code = :exchange_code
                  and i.unified_symbol = :unified_symbol
                  and o.ts >= :start_time
                  and o.ts <= :end_time
                union all
                select 'mark_prices', min(m.ts), max(m.ts), count(*)
                from md.mark_prices m
                join ref.instruments i on i.instrument_id = m.instrument_id
                join ref.exchanges e on e.exchange_id = i.exchange_id
                where e.exchange_code = :exchange_code
                  and i.unified_symbol = :unified_symbol
                  and m.ts >= :start_time
                  and m.ts <= :end_time
                union all
                select 'index_prices', min(x.ts), max(x.ts), count(*)
                from md.index_prices x
                join ref.instruments i on i.instrument_id = x.instrument_id
                join ref.exchanges e on e.exchange_id = i.exchange_id
                where e.exchange_code = :exchange_code
                  and i.unified_symbol = :unified_symbol
                  and x.ts >= :start_time
                  and x.ts <= :end_time
            ) q
            order by dataset
            """
        ),
        {
            "exchange_code": exchange_code,
            "unified_symbol": unified_symbol,
            "start_time": start_time,
            "end_time": end_time,
        },
    ).mappings().all()
    return [dict(row) for row in rows]


def build_run_config(args: argparse.Namespace, *, start_time: datetime, end_time: datetime) -> BacktestRunConfig:
    return BacktestRunConfig.model_validate(
        {
            "run_name": args.run_name,
            "session": {
                "session_code": f"{args.run_name}_session",
                "environment": "backtest",
                "account_code": args.account_code,
                "strategy_code": args.strategy_code,
                "strategy_version": args.strategy_version,
                "exchange_code": args.exchange_code,
                "universe": [args.unified_symbol],
                "risk_policy": {
                    "policy_code": args.risk_policy_code,
                    "max_position_qty": "25",
                    "max_order_qty": "25",
                },
            },
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "initial_cash": args.initial_cash,
            "assumption_bundle_code": args.assumption_bundle_code,
            "assumption_bundle_version": args.assumption_bundle_version,
            "debug_trace_level": "full",
            "strategy_params": {
                "trend_fast_ema": 20,
                "trend_slow_ema": 50,
                "breakout_lookback_bars": 20,
                "atr_window": 14,
                "initial_stop_atr": "2",
                "trailing_stop_atr": "1.5",
                "exit_on_ema20_cross": True,
                "risk_per_trade_pct": "0.005",
                "volatility_floor_atr_pct": "0.008",
                "volatility_ceiling_atr_pct": "0.08",
                "max_funding_rate_long": "0.0005",
                "oi_change_pct_window": "0.05",
                "min_price_change_pct_for_oi_confirmation": "0.01",
                "skip_entries_within_minutes_of_funding": 30,
                "max_consecutive_losses": 3,
                "max_daily_r_multiple_loss": "2",
            },
            "metadata": {
                "profile_case": "2025_full_year_full_trace",
                "rollback": not args.commit,
            },
        }
    )


def render_profile_report(stats_path: Path, report_path: Path, *, top_n: int) -> str:
    stream = StringIO()
    stats = pstats.Stats(str(stats_path), stream=stream)
    stats.sort_stats("tottime")
    stream.write("\n=== TOP BY TOTAL TIME ===\n")
    stats.print_stats(top_n)
    stats.sort_stats("cumulative")
    stream.write("\n=== TOP BY CUMULATIVE TIME ===\n")
    stats.print_stats(top_n)
    report = stream.getvalue()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    return report


def main() -> None:
    args = parse_args()
    start_time = _parse_ts(args.start_time)
    end_time = _parse_ts(args.end_time)
    stats_path = Path(args.stats_path)
    report_path = Path(args.report_path)
    stats_path.parent.mkdir(parents=True, exist_ok=True)

    engine = get_engine()
    connection = engine.connect()
    transaction = connection.begin()
    try:
        coverage = _query_dataset_coverage(
            connection,
            exchange_code=args.exchange_code,
            unified_symbol=args.unified_symbol,
            start_time=start_time,
            end_time=end_time,
        )
        print("Dataset coverage for profile window:")
        for row in coverage:
            print(row)

        run_config = build_run_config(args, start_time=start_time, end_time=end_time)
        runner = BacktestRunnerSkeleton(run_config)

        profile = cProfile.Profile()
        print(
            "Starting profiled run:",
            {
                "strategy": f"{args.strategy_code}@{args.strategy_version}",
                "window": [start_time.isoformat(), end_time.isoformat()],
                "symbol": args.unified_symbol,
                "persist_signals": args.persist_signals,
                "persist_debug_traces": True,
                "debug_trace_level": "full",
                "commit": args.commit,
            },
        )
        t0 = time.perf_counter()
        profile.enable()
        persisted = runner.load_run_and_persist(
            connection,
            persist_signals=args.persist_signals,
            persist_debug_traces=True,
        )
        profile.disable()
        elapsed = time.perf_counter() - t0
        profile.dump_stats(str(stats_path))

        trace_count = runner.run_repository.count_debug_traces(connection, run_id=persisted.run_id)
        summary = runner.run_repository.get_performance_summary(connection, run_id=persisted.run_id)
        report = render_profile_report(stats_path, report_path, top_n=args.top_n)

        print(
            "Profiled run summary:",
            {
                "run_id": persisted.run_id,
                "elapsed_seconds": round(elapsed, 3),
                "debug_trace_count": trace_count,
                "total_return": None if summary is None else str(summary.get("total_return")),
                "max_drawdown": None if summary is None else str(summary.get("max_drawdown")),
                "stats_path": str(stats_path),
                "report_path": str(report_path),
            },
        )
        print(report)

        if args.commit:
            transaction.commit()
            print("Committed profiled run to DB.")
        else:
            transaction.rollback()
            print("Rolled back profiled run so the benchmark does not pollute local DB state.")
    finally:
        if transaction.is_active:
            transaction.rollback()
        connection.close()


if __name__ == "__main__":
    main()
