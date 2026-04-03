from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Sequence

from backtest.diagnostics import BacktestDiagnosticsProjector
from storage.repositories.backtest import BacktestRunRepository


class BacktestCompareValidationError(ValueError):
    pass


class BacktestCompareNotFoundError(LookupError):
    def __init__(self, missing_run_ids: Sequence[int]) -> None:
        self.missing_run_ids = list(missing_run_ids)
        super().__init__(f"backtest runs not found: {', '.join(str(run_id) for run_id in self.missing_run_ids)}")


@dataclass(slots=True)
class ComparisonFlag:
    code: str
    severity: str
    message: str


@dataclass(slots=True)
class ComparedRunSummary:
    run_id: int
    run_name: str
    strategy_code: str
    strategy_version: str
    account_code: str | None
    environment: str | None
    status: str
    start_time: datetime
    end_time: datetime
    universe: list[str]
    diagnostic_status: str | None
    total_return: Decimal | None
    annualized_return: Decimal | None
    max_drawdown: Decimal | None
    turnover: Decimal | None
    win_rate: Decimal | None
    fee_cost: Decimal | None
    slippage_cost: Decimal | None


@dataclass(slots=True)
class AssumptionDiffValue:
    run_id: int
    value: Any


@dataclass(slots=True)
class AssumptionDiff:
    field_name: str
    distinct_value_count: int
    values_by_run: list[AssumptionDiffValue]


@dataclass(slots=True)
class BenchmarkDelta:
    run_id: int
    benchmark_run_id: int
    total_return_delta: Decimal | None
    annualized_return_delta: Decimal | None
    max_drawdown_delta: Decimal | None
    turnover_delta: Decimal | None
    win_rate_delta: Decimal | None


@dataclass(slots=True)
class BacktestCompareSet:
    compare_name: str | None
    run_ids: list[int]
    benchmark_run_id: int | None
    persisted: bool
    compared_runs: list[ComparedRunSummary]
    assumption_diffs: list[AssumptionDiff]
    benchmark_deltas: list[BenchmarkDelta]
    comparison_flags: list[ComparisonFlag]
    available_period_types: list[str]


@dataclass(slots=True)
class _CompareRunEnvelope:
    summary: ComparedRunSummary
    assumptions: dict[str, Any]
    has_performance_summary: bool


class BacktestCompareProjector:
    def __init__(
        self,
        run_repository: BacktestRunRepository | None = None,
        diagnostics_projector: BacktestDiagnosticsProjector | None = None,
    ) -> None:
        self.run_repository = run_repository or BacktestRunRepository()
        self.diagnostics_projector = diagnostics_projector or BacktestDiagnosticsProjector()

    def build(
        self,
        connection,
        *,
        run_ids: Sequence[int],
        compare_name: str | None = None,
        benchmark_run_id: int | None = None,
    ) -> BacktestCompareSet:
        deduped_run_ids = list(dict.fromkeys(run_ids))
        if len(deduped_run_ids) < 2:
            raise BacktestCompareValidationError("comparison requires at least two unique run_ids")
        if benchmark_run_id is not None and benchmark_run_id not in deduped_run_ids:
            raise BacktestCompareValidationError("benchmark_run_id must be included in run_ids")

        envelopes: list[_CompareRunEnvelope] = []
        missing_run_ids: list[int] = []
        for run_id in deduped_run_ids:
            run_row = self.run_repository.get_run(connection, run_id)
            if run_row is None:
                missing_run_ids.append(run_id)
                continue
            summary_row = self.run_repository.get_performance_summary(connection, run_id=run_id)
            diagnostics = self.diagnostics_projector.build_summary(connection, run_id)
            params_json = run_row.get("params_json") or {}
            universe = list(run_row.get("universe_json") or [])

            envelopes.append(
                _CompareRunEnvelope(
                    summary=ComparedRunSummary(
                        run_id=run_id,
                        run_name=str(run_row["run_name"]),
                        strategy_code=str(run_row["strategy_code"]),
                        strategy_version=str(run_row["strategy_version"]),
                        account_code=run_row.get("account_code"),
                        environment=params_json.get("environment"),
                        status=str(run_row["status"]),
                        start_time=run_row["start_time"],
                        end_time=run_row["end_time"],
                        universe=universe,
                        diagnostic_status=diagnostics.diagnostic_status if diagnostics is not None else None,
                        total_return=_decimal_or_none(summary_row, "total_return"),
                        annualized_return=_decimal_or_none(summary_row, "annualized_return"),
                        max_drawdown=_decimal_or_none(summary_row, "max_drawdown"),
                        turnover=_decimal_or_none(summary_row, "turnover"),
                        win_rate=_decimal_or_none(summary_row, "win_rate"),
                        fee_cost=_decimal_or_none(summary_row, "fee_cost"),
                        slippage_cost=_decimal_or_none(summary_row, "slippage_cost"),
                    ),
                    assumptions={
                        "strategy_code": run_row["strategy_code"],
                        "strategy_version": run_row["strategy_version"],
                        "account_code": run_row.get("account_code"),
                        "environment": params_json.get("environment"),
                        "bar_interval": params_json.get("bar_interval"),
                        "initial_cash": params_json.get("initial_cash"),
                        "netting_mode": params_json.get("netting_mode"),
                        "universe": universe,
                        "market_data_version": run_row.get("market_data_version"),
                        "fee_model_version": run_row.get("fee_model_version"),
                        "slippage_model_version": run_row.get("slippage_model_version"),
                        "latency_model_version": run_row.get("latency_model_version"),
                        "execution_policy": params_json.get("execution_policy"),
                        "protection_policy": params_json.get("protection_policy"),
                        "strategy_params": params_json.get("strategy_params"),
                    },
                    has_performance_summary=summary_row is not None,
                )
            )

        if missing_run_ids:
            raise BacktestCompareNotFoundError(missing_run_ids)

        assumption_diffs = _build_assumption_diffs(envelopes)
        benchmark_deltas = _build_benchmark_deltas(envelopes, benchmark_run_id)
        comparison_flags = _build_comparison_flags(envelopes, assumption_diffs)
        return BacktestCompareSet(
            compare_name=compare_name,
            run_ids=deduped_run_ids,
            benchmark_run_id=benchmark_run_id,
            persisted=False,
            compared_runs=[envelope.summary for envelope in envelopes],
            assumption_diffs=assumption_diffs,
            benchmark_deltas=benchmark_deltas,
            comparison_flags=comparison_flags,
            available_period_types=["year", "quarter", "month"],
        )


def _decimal_or_none(summary_row: dict[str, object] | None, field_name: str) -> Decimal | None:
    if summary_row is None:
        return None
    value = summary_row.get(field_name)
    return None if value is None else Decimal(value)


def _build_assumption_diffs(envelopes: Sequence[_CompareRunEnvelope]) -> list[AssumptionDiff]:
    diffs: list[AssumptionDiff] = []
    if not envelopes:
        return diffs

    field_names = list(envelopes[0].assumptions.keys())
    for field_name in field_names:
        values_by_run = [
            AssumptionDiffValue(run_id=envelope.summary.run_id, value=_normalize_value(envelope.assumptions.get(field_name)))
            for envelope in envelopes
        ]
        distinct_value_count = len({_comparison_key(value.value) for value in values_by_run})
        if distinct_value_count > 1:
            diffs.append(
                AssumptionDiff(
                    field_name=field_name,
                    distinct_value_count=distinct_value_count,
                    values_by_run=values_by_run,
                )
            )
    return diffs


def _build_benchmark_deltas(
    envelopes: Sequence[_CompareRunEnvelope],
    benchmark_run_id: int | None,
) -> list[BenchmarkDelta]:
    if benchmark_run_id is None:
        return []

    benchmark = next(envelope.summary for envelope in envelopes if envelope.summary.run_id == benchmark_run_id)
    deltas: list[BenchmarkDelta] = []
    for envelope in envelopes:
        if envelope.summary.run_id == benchmark_run_id:
            continue
        deltas.append(
            BenchmarkDelta(
                run_id=envelope.summary.run_id,
                benchmark_run_id=benchmark_run_id,
                total_return_delta=_delta(envelope.summary.total_return, benchmark.total_return),
                annualized_return_delta=_delta(envelope.summary.annualized_return, benchmark.annualized_return),
                max_drawdown_delta=_delta(envelope.summary.max_drawdown, benchmark.max_drawdown),
                turnover_delta=_delta(envelope.summary.turnover, benchmark.turnover),
                win_rate_delta=_delta(envelope.summary.win_rate, benchmark.win_rate),
            )
        )
    return deltas


def _delta(value: Decimal | None, benchmark_value: Decimal | None) -> Decimal | None:
    if value is None or benchmark_value is None:
        return None
    return value - benchmark_value


def _build_comparison_flags(
    envelopes: Sequence[_CompareRunEnvelope],
    assumption_diffs: Sequence[AssumptionDiff],
) -> list[ComparisonFlag]:
    flags: list[ComparisonFlag] = []
    diff_fields = {diff.field_name for diff in assumption_diffs}

    if "strategy_code" in diff_fields:
        flags.append(
            ComparisonFlag(
                code="mixed_strategy_variants",
                severity="info",
                message="selected runs span multiple strategy variants",
            )
        )
    if "strategy_version" in diff_fields:
        flags.append(
            ComparisonFlag(
                code="mixed_strategy_versions",
                severity="info",
                message="selected runs span multiple strategy versions",
            )
        )
    if len(
        {
            (envelope.summary.start_time, envelope.summary.end_time)
            for envelope in envelopes
        }
    ) > 1:
        flags.append(
            ComparisonFlag(
                code="window_mismatch",
                severity="warning",
                message="selected runs use different backtest windows",
            )
        )
    if "universe" in diff_fields:
        flags.append(
            ComparisonFlag(
                code="universe_mismatch",
                severity="warning",
                message="selected runs use different instrument universes",
            )
        )
    if diff_fields.intersection(
        {
            "market_data_version",
            "fee_model_version",
            "slippage_model_version",
            "latency_model_version",
            "bar_interval",
            "execution_policy",
            "protection_policy",
            "strategy_params",
            "initial_cash",
        }
    ):
        flags.append(
            ComparisonFlag(
                code="execution_assumption_mismatch",
                severity="warning",
                message="selected runs differ on market-data, pricing, or execution assumptions",
            )
        )
    if any(not envelope.has_performance_summary for envelope in envelopes):
        flags.append(
            ComparisonFlag(
                code="missing_performance_summary",
                severity="warning",
                message="one or more selected runs do not have a persisted performance summary",
            )
        )
    if any(envelope.summary.diagnostic_status in {"warning", "error"} for envelope in envelopes):
        flags.append(
            ComparisonFlag(
                code="diagnostic_warnings_present",
                severity="warning",
                message="one or more selected runs already carry diagnostics warnings or errors",
            )
        )
    return flags


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _normalize_value(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_value(item) for item in value]
    return value


def _comparison_key(value: Any) -> str:
    return json.dumps(_normalize_value(value), sort_keys=True, separators=(",", ":"), default=str)
