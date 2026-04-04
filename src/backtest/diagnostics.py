from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
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
class DiagnosticTraceAnchor:
    source_kind: str
    source_code: str
    title: str
    message: str
    anchor_type: str
    debug_trace_id: int
    step_index: int
    bar_time: datetime
    unified_symbol: str
    related_count: int | None = None
    matched_block_code: str | None = None
    bar_time_from: datetime | None = None
    bar_time_to: datetime | None = None


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
    blocked_intent_count: int
    fill_rate_pct: str | None


@dataclass(slots=True)
class RiskGuardrailSummary:
    blocked_intent_count: int
    block_counts_by_code: dict[str, int]
    outcome_counts_by_code: dict[str, int]
    state_snapshot: dict[str, Any]


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
    risk_summary: RiskGuardrailSummary
    pnl_summary: PnlSummary
    diagnostic_flags: list[DiagnosticFlag]
    trace_anchors: list[DiagnosticTraceAnchor]


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
        runtime_metadata = params_json.get("runtime_metadata") or {}
        risk_summary = runtime_metadata.get("risk_summary") or {}
        block_counts_by_code = dict(risk_summary.get("block_counts_by_code") or {})
        state_snapshot = dict(risk_summary.get("state_snapshot") or {})
        expected_timepoints = self._expected_timepoints(
            start_time=run_row["start_time"],
            end_time=run_row["end_time"],
            bar_interval=params_json.get("bar_interval"),
        )
        observed_timepoints = int(timeseries_row["timepoints_observed"])
        missing_timepoints = 0 if expected_timepoints is None else max(expected_timepoints - observed_timepoints, 0)
        blocked_intent_count = int(risk_summary.get("blocked_intent_count") or 0)
        outcome_counts_by_code = {
            str(key): int(value)
            for key, value in dict(risk_summary.get("outcome_counts_by_code") or {}).items()
        }
        block_counts_by_code = {
            str(key): int(value)
            for key, value in dict(risk_summary.get("block_counts_by_code") or {}).items()
        }

        flags = self._build_flags(
            missing_timepoints=missing_timepoints,
            simulated_order_count=int(execution_row["simulated_order_count"]),
            simulated_fill_count=fill_count,
            expired_order_count=int(execution_row["expired_order_count"]),
            unlinked_order_count=int(execution_row["unlinked_order_count"]),
            signal_count=int(signal_row["signal_count"]),
            blocked_intent_count=blocked_intent_count,
            block_counts_by_code=block_counts_by_code,
            risk_state_snapshot=state_snapshot,
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
                blocked_intent_count=blocked_intent_count,
                fill_rate_pct=self._format_ratio(fill_count, int(execution_row["simulated_order_count"])),
            ),
            risk_summary=RiskGuardrailSummary(
                blocked_intent_count=blocked_intent_count,
                block_counts_by_code=block_counts_by_code,
                outcome_counts_by_code=outcome_counts_by_code,
                state_snapshot=state_snapshot,
            ),
            pnl_summary=PnlSummary(
                total_return=self._stringify_numeric(pnl_row, "total_return"),
                max_drawdown=self._stringify_numeric(pnl_row, "max_drawdown"),
                turnover=self._stringify_numeric(pnl_row, "turnover"),
                fee_cost=self._stringify_numeric(pnl_row, "fee_cost"),
                slippage_cost=self._stringify_numeric(pnl_row, "slippage_cost"),
            ),
            diagnostic_flags=flags,
            trace_anchors=self._build_trace_anchors(
                connection,
                run_id=run_id,
                blocked_intent_count=blocked_intent_count,
                block_counts_by_code=block_counts_by_code,
            ),
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
        blocked_intent_count: int,
        block_counts_by_code: dict[str, Any],
        risk_state_snapshot: dict[str, Any],
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
        if blocked_intent_count > 0:
            flags.append(
                DiagnosticFlag(
                    code="risk_blocks_present",
                    severity="warning",
                    message="one or more execution intents were blocked by backtest risk guardrails",
                    related_count=blocked_intent_count,
                )
            )
        if int(block_counts_by_code.get("max_drawdown_pct_breach") or 0) > 0:
            flags.append(
                DiagnosticFlag(
                    code="drawdown_guard_triggered",
                    severity="warning",
                    message="drawdown guard blocked one or more new entries during the run",
                    related_count=int(block_counts_by_code.get("max_drawdown_pct_breach") or 0),
                )
            )
        if int(block_counts_by_code.get("max_daily_loss_pct_breach") or 0) > 0:
            flags.append(
                DiagnosticFlag(
                    code="daily_loss_guard_triggered",
                    severity="warning",
                    message="daily-loss guard blocked one or more new entries during the run",
                    related_count=int(block_counts_by_code.get("max_daily_loss_pct_breach") or 0),
                )
            )
        if int(block_counts_by_code.get("max_leverage_breach") or 0) > 0:
            flags.append(
                DiagnosticFlag(
                    code="leverage_guard_triggered",
                    severity="warning",
                    message="leverage guard blocked one or more new entries during the run",
                    related_count=int(block_counts_by_code.get("max_leverage_breach") or 0),
                )
            )
        if int(block_counts_by_code.get("cooldown_active") or 0) > 0:
            flags.append(
                DiagnosticFlag(
                    code="cooldown_guard_triggered",
                    severity="warning",
                    message="cooldown blocked one or more new entries after a recent loss-close event",
                    related_count=int(block_counts_by_code.get("cooldown_active") or 0),
                )
            )
        if int((risk_state_snapshot.get("activation_counts_by_code") or {}).get("cooldown_activated_after_loss_close") or 0) > 0:
            flags.append(
                DiagnosticFlag(
                    code="cooldown_activated",
                    severity="warning",
                    message="cooldown was activated at least once after a realized losing close event",
                    related_count=int(
                        (risk_state_snapshot.get("activation_counts_by_code") or {}).get(
                            "cooldown_activated_after_loss_close"
                        )
                        or 0
                    ),
                )
            )
        return flags

    @classmethod
    def _build_trace_anchors(
        cls,
        connection: Connection,
        *,
        run_id: int,
        blocked_intent_count: int,
        block_counts_by_code: dict[str, Any],
    ) -> list[DiagnosticTraceAnchor]:
        anchors: list[DiagnosticTraceAnchor] = []
        seen: set[tuple[str, str, int]] = set()

        if blocked_intent_count > 0:
            row = cls._latest_blocked_trace(connection, run_id=run_id)
            if row is not None:
                cls._append_trace_anchor(
                    anchors,
                    seen,
                    cls._trace_anchor_from_row(
                        row,
                        source_kind="diagnostic_flag",
                        source_code="risk_blocks_present",
                        title="Latest blocked intent trace",
                        message="Latest trace row where a backtest risk guardrail blocked an execution intent.",
                        related_count=blocked_intent_count,
                    ),
                )

        for block_code, count in sorted(block_counts_by_code.items()):
            normalized_count = int(count or 0)
            if normalized_count <= 0:
                continue
            row = cls._latest_blocked_trace(connection, run_id=run_id, blocked_code=str(block_code))
            if row is None:
                continue
            source_kind, source_code, title, message = cls._trace_anchor_meta_for_block_code(str(block_code))
            cls._append_trace_anchor(
                anchors,
                seen,
                cls._trace_anchor_from_row(
                    row,
                    source_kind=source_kind,
                    source_code=source_code,
                    title=title,
                    message=message,
                    related_count=normalized_count,
                    matched_block_code=str(block_code),
                ),
            )

        return anchors

    @staticmethod
    def _append_trace_anchor(
        anchors: list[DiagnosticTraceAnchor],
        seen: set[tuple[str, str, int]],
        anchor: DiagnosticTraceAnchor,
    ) -> None:
        key = (anchor.source_kind, anchor.source_code, anchor.debug_trace_id)
        if key in seen:
            return
        seen.add(key)
        anchors.append(anchor)

    @staticmethod
    def _trace_anchor_meta_for_block_code(block_code: str) -> tuple[str, str, str, str]:
        mapping = {
            "max_drawdown_pct_breach": (
                "diagnostic_flag",
                "drawdown_guard_triggered",
                "Latest drawdown-guard block",
                "Latest trace row blocked by the drawdown guard.",
            ),
            "max_daily_loss_pct_breach": (
                "diagnostic_flag",
                "daily_loss_guard_triggered",
                "Latest daily-loss-guard block",
                "Latest trace row blocked by the daily-loss guard.",
            ),
            "max_leverage_breach": (
                "diagnostic_flag",
                "leverage_guard_triggered",
                "Latest leverage-guard block",
                "Latest trace row blocked by the leverage guard.",
            ),
            "cooldown_active": (
                "diagnostic_flag",
                "cooldown_guard_triggered",
                "Latest cooldown block",
                "Latest trace row blocked because cooldown was active.",
            ),
        }
        if block_code in mapping:
            return mapping[block_code]
        return (
            "block_summary",
            block_code,
            f"Latest block for {block_code}",
            f"Latest trace row matching blocked code {block_code}.",
        )

    @classmethod
    def _trace_anchor_from_row(
        cls,
        row: dict[str, Any],
        *,
        source_kind: str,
        source_code: str,
        title: str,
        message: str,
        related_count: int | None,
        matched_block_code: str | None = None,
    ) -> DiagnosticTraceAnchor:
        bar_time = row["bar_time"]
        return DiagnosticTraceAnchor(
            source_kind=source_kind,
            source_code=source_code,
            title=title,
            message=message,
            anchor_type="step",
            debug_trace_id=int(row["debug_trace_id"]),
            step_index=int(row["step_index"]),
            bar_time=bar_time,
            unified_symbol=str(row["unified_symbol"]),
            related_count=related_count,
            matched_block_code=matched_block_code,
            bar_time_from=bar_time - timedelta(minutes=2),
            bar_time_to=bar_time + timedelta(minutes=2),
        )

    @staticmethod
    def _latest_blocked_trace(
        connection: Connection,
        *,
        run_id: int,
        blocked_code: str | None = None,
    ) -> dict[str, Any] | None:
        filters = ["trace.run_id = :run_id", "trace.blocked_intent_count > 0"]
        params: dict[str, Any] = {"run_id": run_id}
        if blocked_code is not None:
            filters.append("trace.blocked_codes_json ? :blocked_code")
            params["blocked_code"] = blocked_code
        where_clause = " and ".join(filters)
        return connection.execute(
            text(
                f"""
                select
                    trace.debug_trace_id,
                    trace.step_index,
                    trace.bar_time,
                    instrument.unified_symbol
                from backtest.debug_traces trace
                join ref.instruments instrument on instrument.instrument_id = trace.instrument_id
                where {where_clause}
                order by trace.step_index desc
                limit 1
                """
            ),
            params,
        ).mappings().first()
