from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection


@dataclass(slots=True)
class DiagnosticFlag:
    code: str
    severity: str
    message: str
    related_count: int | None = None


@dataclass(slots=True)
class RunIntegritySummary:
    run_status: str
    start_time: datetime
    end_time: datetime
    timepoints_observed: int
    expected_timepoints: int | None
    missing_timepoints: int


@dataclass(slots=True)
class StrategyActivitySummary:
    signal_count: int
    entry_signals: int
    exit_signals: int
    reduce_signals: int
    reverse_signals: int
    rebalance_signals: int


@dataclass(slots=True)
class ExecutionSummary:
    simulated_order_count: int
    simulated_fill_count: int
    expired_order_count: int
    unlinked_order_count: int
    fill_rate_pct: str | None


@dataclass(slots=True)
class PnlSummary:
    total_return: str | None
    max_drawdown: str | None
    turnover: str | None
    fee_cost: str | None
    slippage_cost: str | None


@dataclass(slots=True)
class BacktestDiagnosticsSummary:
    run_id: int
    diagnostic_status: str
    has_errors: bool
    has_warnings: bool
    error_count: int
    warning_count: int
    run_integrity: RunIntegritySummary
    strategy_activity: StrategyActivitySummary
    execution_summary: ExecutionSummary
    pnl_summary: PnlSummary
    diagnostic_flags: list[DiagnosticFlag]


class BacktestDiagnosticsProjector:
    def build_summary(self, connection: Connection, run_id: int) -> BacktestDiagnosticsSummary | None:
        run_row = connection.execute(
            text(
                """
                select run_id, status, start_time, end_time, params_json
                from backtest.runs
                where run_id = :run_id
                """
            ),
            {"run_id": run_id},
        ).mappings().first()
        if run_row is None:
            return None

        signal_row = connection.execute(
            text(
                """
                select
                    count(distinct s.signal_id) as signal_count,
                    coalesce(sum(case when s.signal_type = 'entry' then 1 else 0 end), 0) as entry_signals,
                    coalesce(sum(case when s.signal_type = 'exit' then 1 else 0 end), 0) as exit_signals,
                    coalesce(sum(case when s.signal_type = 'reduce' then 1 else 0 end), 0) as reduce_signals,
                    coalesce(sum(case when s.signal_type = 'reverse' then 1 else 0 end), 0) as reverse_signals,
                    coalesce(sum(case when s.signal_type = 'rebalance' then 1 else 0 end), 0) as rebalance_signals
                from backtest.simulated_orders o
                left join strategy.signals s on s.signal_id = o.signal_id
                where o.run_id = :run_id
                """
            ),
            {"run_id": run_id},
        ).mappings().one()
        execution_row = connection.execute(
            text(
                """
                select
                    count(*) as simulated_order_count,
                    coalesce(sum(case when status = 'expired' then 1 else 0 end), 0) as expired_order_count,
                    coalesce(sum(case when signal_id is null then 1 else 0 end), 0) as unlinked_order_count
                from backtest.simulated_orders
                where run_id = :run_id
                """
            ),
            {"run_id": run_id},
        ).mappings().one()
        fill_count = int(
            connection.execute(
                text("select count(*) from backtest.simulated_fills where run_id = :run_id"),
                {"run_id": run_id},
            ).scalar_one()
        )
        timeseries_row = connection.execute(
            text(
                """
                select
                    count(*) as timepoints_observed
                from backtest.performance_timeseries
                where run_id = :run_id
                """
            ),
            {"run_id": run_id},
        ).mappings().one()
        pnl_row = connection.execute(
            text(
                """
                select
                    total_return,
                    max_drawdown,
                    turnover,
                    fee_cost,
                    slippage_cost
                from backtest.performance_summary
                where run_id = :run_id
                """
            ),
            {"run_id": run_id},
        ).mappings().first()

        params_json = run_row["params_json"] or {}
        expected_timepoints = self._expected_timepoints(
            start_time=run_row["start_time"],
            end_time=run_row["end_time"],
            bar_interval=params_json.get("bar_interval"),
        )
        observed_timepoints = int(timeseries_row["timepoints_observed"])
        missing_timepoints = 0 if expected_timepoints is None else max(expected_timepoints - observed_timepoints, 0)

        flags = self._build_flags(
            missing_timepoints=missing_timepoints,
            simulated_order_count=int(execution_row["simulated_order_count"]),
            simulated_fill_count=fill_count,
            expired_order_count=int(execution_row["expired_order_count"]),
            unlinked_order_count=int(execution_row["unlinked_order_count"]),
            signal_count=int(signal_row["signal_count"]),
        )
        warning_count = sum(1 for flag in flags if flag.severity == "warning")
        error_count = sum(1 for flag in flags if flag.severity == "error")
        diagnostic_status = "error" if error_count else "warning" if warning_count else "ok"

        return BacktestDiagnosticsSummary(
            run_id=run_id,
            diagnostic_status=diagnostic_status,
            has_errors=error_count > 0,
            has_warnings=warning_count > 0,
            error_count=error_count,
            warning_count=warning_count,
            run_integrity=RunIntegritySummary(
                run_status=run_row["status"],
                start_time=run_row["start_time"],
                end_time=run_row["end_time"],
                timepoints_observed=observed_timepoints,
                expected_timepoints=expected_timepoints,
                missing_timepoints=missing_timepoints,
            ),
            strategy_activity=StrategyActivitySummary(
                signal_count=int(signal_row["signal_count"]),
                entry_signals=int(signal_row["entry_signals"]),
                exit_signals=int(signal_row["exit_signals"]),
                reduce_signals=int(signal_row["reduce_signals"]),
                reverse_signals=int(signal_row["reverse_signals"]),
                rebalance_signals=int(signal_row["rebalance_signals"]),
            ),
            execution_summary=ExecutionSummary(
                simulated_order_count=int(execution_row["simulated_order_count"]),
                simulated_fill_count=fill_count,
                expired_order_count=int(execution_row["expired_order_count"]),
                unlinked_order_count=int(execution_row["unlinked_order_count"]),
                fill_rate_pct=self._format_ratio(fill_count, int(execution_row["simulated_order_count"])),
            ),
            pnl_summary=PnlSummary(
                total_return=self._stringify_numeric(pnl_row, "total_return"),
                max_drawdown=self._stringify_numeric(pnl_row, "max_drawdown"),
                turnover=self._stringify_numeric(pnl_row, "turnover"),
                fee_cost=self._stringify_numeric(pnl_row, "fee_cost"),
                slippage_cost=self._stringify_numeric(pnl_row, "slippage_cost"),
            ),
            diagnostic_flags=flags,
        )

    @staticmethod
    def _expected_timepoints(*, start_time: datetime, end_time: datetime, bar_interval: Any) -> int | None:
        if bar_interval != "1m":
            return None
        duration_seconds = int((end_time - start_time).total_seconds())
        if duration_seconds <= 0:
            return 0
        return duration_seconds // 60

    @staticmethod
    def _format_ratio(numerator: int, denominator: int) -> str | None:
        if denominator <= 0:
            return None
        return format(numerator / denominator, ".4f")

    @staticmethod
    def _stringify_numeric(row: dict[str, Any] | None, key: str) -> str | None:
        if row is None:
            return None
        value = row.get(key)
        return None if value is None else str(value)

    @staticmethod
    def _build_flags(
        *,
        missing_timepoints: int,
        simulated_order_count: int,
        simulated_fill_count: int,
        expired_order_count: int,
        unlinked_order_count: int,
        signal_count: int,
    ) -> list[DiagnosticFlag]:
        flags: list[DiagnosticFlag] = []
        if missing_timepoints > 0:
            flags.append(
                DiagnosticFlag(
                    code="missing_timepoints",
                    severity="warning",
                    message="performance timeseries is missing expected timestamps",
                    related_count=missing_timepoints,
                )
            )
        if signal_count == 0:
            flags.append(
                DiagnosticFlag(
                    code="no_signals_generated",
                    severity="warning",
                    message="strategy produced no persisted signals for this run",
                    related_count=0,
                )
            )
        if simulated_order_count > 0 and simulated_fill_count == 0:
            flags.append(
                DiagnosticFlag(
                    code="no_fills_generated",
                    severity="warning",
                    message="simulated orders were created but no fills were produced",
                    related_count=simulated_order_count,
                )
            )
        if expired_order_count > 0:
            flags.append(
                DiagnosticFlag(
                    code="expired_orders_present",
                    severity="warning",
                    message="one or more simulated orders expired without filling",
                    related_count=expired_order_count,
                )
            )
        if unlinked_order_count > 0:
            flags.append(
                DiagnosticFlag(
                    code="signal_link_gap",
                    severity="warning",
                    message="one or more simulated orders are not linked to a persisted signal",
                    related_count=unlinked_order_count,
                )
            )
        return flags
