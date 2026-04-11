from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys
import time
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from backtest.compare import BacktestCompareProjector
from backtest.compare_review import CompareReviewService
from backtest.runner import BacktestRunnerSkeleton
from models.backtest import BacktestRunConfig
from storage.db import get_engine
from storage.repositories.backtest import BacktestRunRepository


DEFAULT_START = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
DEFAULT_END = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)
DEFAULT_REPORT_PATH = PROJECT_ROOT / "tmp" / "backtest_ablation_report.json"


@dataclass(slots=True)
class AblationVariant:
    variant_id: str
    label: str
    strategy_params: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a batch of backtest ablation variants and emit a comparable summary report."
    )
    parser.add_argument("--preset", default="breakout_exit_tightness")
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
    parser.add_argument("--initial-cash", default="100000")
    parser.add_argument("--run-name-prefix", default="ablation_breakout_exit")
    parser.add_argument("--debug-trace-level", default="compact")
    parser.add_argument("--persist-debug-traces", action="store_true")
    parser.add_argument("--persist-signals", action="store_true", default=True)
    parser.add_argument("--no-persist-signals", dest="persist_signals", action="store_false")
    parser.add_argument("--commit", action="store_true", help="Persist runs and create a compare set.")
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--actor-name", default="codex")
    return parser.parse_args()


def _parse_ts(raw: str) -> datetime:
    normalized = raw.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _base_strategy_params() -> dict[str, Any]:
    return {
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
    }


def _build_variants(preset: str) -> list[AblationVariant]:
    if preset != "breakout_exit_tightness":
        raise ValueError(f"unsupported ablation preset: {preset}")

    base = _base_strategy_params()
    variants: list[AblationVariant] = []
    for trailing_stop_atr in ("1.5", "2.0", "2.5", "3.0"):
        for exit_on_ema20_cross in (True, False):
            params = dict(base)
            params["trailing_stop_atr"] = trailing_stop_atr
            params["exit_on_ema20_cross"] = exit_on_ema20_cross
            variant_id = f"ts{trailing_stop_atr.replace('.', '_')}_{'ema_on' if exit_on_ema20_cross else 'ema_off'}"
            label = f"trailing_stop_atr={trailing_stop_atr}, exit_on_ema20_cross={str(exit_on_ema20_cross).lower()}"
            variants.append(
                AblationVariant(
                    variant_id=variant_id,
                    label=label,
                    strategy_params=params,
                )
            )
    return variants


def _build_run_config(
    args: argparse.Namespace,
    *,
    start_time: datetime,
    end_time: datetime,
    variant: AblationVariant,
) -> BacktestRunConfig:
    return BacktestRunConfig.model_validate(
        {
            "run_name": f"{args.run_name_prefix}_{variant.variant_id}",
            "session": {
                "session_code": f"{args.run_name_prefix}_{variant.variant_id}_{int(time.time() * 1000)}",
                "environment": "backtest",
                "account_code": args.account_code,
                "strategy_code": args.strategy_code,
                "strategy_version": args.strategy_version,
                "exchange_code": args.exchange_code,
                "trading_timezone": "UTC",
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
            "debug_trace_level": args.debug_trace_level,
            "strategy_params": variant.strategy_params,
            "metadata": {
                "ablation_preset": args.preset,
                "variant_id": variant.variant_id,
                "variant_label": variant.label,
                "rollback": not args.commit,
            },
        }
    )


def _normalize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _normalize(entry) for key, entry in value.items()}
    if isinstance(value, list):
        return [_normalize(entry) for entry in value]
    return value


def _build_run_result(
    run_repository: BacktestRunRepository,
    connection,
    *,
    run_id: int,
    variant: AblationVariant,
    elapsed_seconds: float,
) -> dict[str, Any]:
    summary = run_repository.get_performance_summary(connection, run_id=run_id) or {}
    run_row = run_repository.get_run(connection, run_id)
    return {
        "variant_id": variant.variant_id,
        "label": variant.label,
        "run_id": run_id,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "status": None if run_row is None else run_row.get("status"),
        "total_return": summary.get("total_return"),
        "annualized_return": summary.get("annualized_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "turnover": summary.get("turnover"),
        "win_rate": summary.get("win_rate"),
        "avg_holding_seconds": summary.get("avg_holding_seconds"),
        "fee_cost": summary.get("fee_cost"),
        "slippage_cost": summary.get("slippage_cost"),
        "debug_trace_count": run_repository.count_debug_traces(connection, run_id=run_id),
        "strategy_params": variant.strategy_params,
    }


def _build_in_memory_result(
    persisted,
    *,
    variant: AblationVariant,
    elapsed_seconds: float,
) -> dict[str, Any]:
    summary = persisted.loop_result.performance_summary
    return {
        "variant_id": variant.variant_id,
        "label": variant.label,
        "run_id": None,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "status": "finished",
        "total_return": summary.total_return,
        "annualized_return": summary.annualized_return,
        "max_drawdown": summary.max_drawdown,
        "turnover": summary.turnover,
        "win_rate": summary.win_rate,
        "avg_holding_seconds": getattr(summary, "avg_holding_seconds", None),
        "fee_cost": summary.fee_cost,
        "slippage_cost": summary.slippage_cost,
        "debug_trace_count": persisted.loop_result.debug_trace_count,
        "strategy_params": variant.strategy_params,
    }


def _sort_results(results: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    def _metric(record: dict[str, Any], key: str) -> Decimal:
        value = record.get(key)
        return Decimal("-999999") if value is None else Decimal(str(value))

    return sorted(
        results,
        key=lambda record: (
            _metric(record, "total_return"),
            _metric(record, "annualized_return"),
            Decimal("999999") - _metric(record, "max_drawdown"),
        ),
        reverse=True,
    )


def main() -> None:
    args = parse_args()
    start_time = _parse_ts(args.start_time)
    end_time = _parse_ts(args.end_time)
    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    variants = _build_variants(args.preset)
    run_repository = BacktestRunRepository()
    projector = BacktestCompareProjector()
    compare_review = CompareReviewService()
    engine = get_engine()

    results: list[dict[str, Any]] = []
    committed_run_ids: list[int] = []

    for variant in variants:
        run_config = _build_run_config(args, start_time=start_time, end_time=end_time, variant=variant)
        runner = BacktestRunnerSkeleton(run_config)
        print(f"[ablation] running {variant.variant_id}: {variant.label}")
        started = time.perf_counter()
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                persisted = runner.load_run_and_persist(
                    connection,
                    persist_signals=args.persist_signals,
                    persist_debug_traces=args.persist_debug_traces,
                )
                elapsed = time.perf_counter() - started
                if args.commit:
                    transaction.commit()
                    committed_run_ids.append(persisted.run_id)
                    with engine.connect() as committed_connection:
                        results.append(
                            _build_run_result(
                                run_repository,
                                committed_connection,
                                run_id=persisted.run_id,
                                variant=variant,
                                elapsed_seconds=elapsed,
                            )
                        )
                else:
                    results.append(
                        _build_in_memory_result(
                            persisted,
                            variant=variant,
                            elapsed_seconds=elapsed,
                        )
                    )
                    transaction.rollback()
            except Exception:
                transaction.rollback()
                raise

    compare_info: dict[str, Any] | None = None
    if args.commit and len(committed_run_ids) >= 2:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                compare_set = projector.build(
                    connection,
                    run_ids=committed_run_ids,
                    compare_name=f"{args.run_name_prefix}_{args.preset}",
                    benchmark_run_id=committed_run_ids[0],
                )
                compare_set = compare_review.persist_compare_set(
                    connection,
                    compare_set=compare_set,
                    actor_name=args.actor_name,
                )
                transaction.commit()
                compare_info = {
                    "compare_set_id": compare_set.compare_set_id,
                    "compare_name": compare_set.compare_name,
                    "benchmark_run_id": compare_set.benchmark_run_id,
                    "run_ids": compare_set.run_ids,
                    "comparison_flags": [
                        {
                            "code": flag.code,
                            "severity": flag.severity,
                            "message": flag.message,
                        }
                        for flag in compare_set.comparison_flags
                    ],
                }
            except Exception:
                transaction.rollback()
                raise

    sorted_results = _sort_results(results)
    payload = {
        "preset": args.preset,
        "commit": args.commit,
        "window": {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
        "base": {
            "exchange_code": args.exchange_code,
            "unified_symbol": args.unified_symbol,
            "strategy_code": args.strategy_code,
            "strategy_version": args.strategy_version,
            "assumption_bundle_code": args.assumption_bundle_code,
            "assumption_bundle_version": args.assumption_bundle_version,
            "risk_policy_code": args.risk_policy_code,
            "initial_cash": args.initial_cash,
            "debug_trace_level": args.debug_trace_level,
            "persist_signals": args.persist_signals,
            "persist_debug_traces": args.persist_debug_traces,
        },
        "variant_count": len(variants),
        "results_ranked": _normalize(sorted_results),
        "compare_set": _normalize(compare_info),
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"[ablation] report written to {report_path}")


if __name__ == "__main__":
    main()
