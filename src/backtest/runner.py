from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from itertools import groupby
from typing import Any, Callable, Iterable, Mapping, Sequence

from models.backtest import BacktestRunConfig
from models.common import RiskDecision
from models.market import BarEvent
from models.strategy import Signal, TargetPosition
from sqlalchemy.engine import Connection
from storage.repositories.backtest import BacktestRunRepository
from storage.repositories.strategy import StrategySignalRepository
from strategy import StrategyBase, StrategyEvaluationInput, StrategyMarketContext, StrategyRegistry, build_default_registry

from .data import BacktestBarLoader, BacktestPerpContextCursor, BacktestPerpContextLoader
from .fills import DeterministicBarsFillModel, SimulatedFill, SimulatedOrder
from .lifecycle import BacktestLifecycle, BacktestStepPlan
from .performance import (
    PerformancePoint,
    PerformanceSummary,
    build_performance_point,
    summarize_performance,
    summarize_performance_from_latest_point,
)
from .risk import BacktestRiskGuardrailEngine, RiskGuardrailOutcome
from .signals import build_signals_from_target_position
from .state import PortfolioMark, PortfolioState, PositionState
from .traces import BacktestDebugTraceRecord


@dataclass(slots=True)
class BacktestStepResult:
    bar_time: datetime
    plan: BacktestStepPlan
    signals: list[Signal]
    created_orders: list[SimulatedOrder]
    fills: list[SimulatedFill]
    risk_outcomes: list[RiskGuardrailOutcome]

@dataclass(slots=True)
class BacktestRunLoopResult:
    steps: list[BacktestStepResult]
    debug_traces: list[BacktestDebugTraceRecord]
    debug_trace_count: int
    final_positions: dict[str, Decimal]
    final_cash: Decimal
    persisted_signal_ids: list[int]
    orders: list[SimulatedOrder]
    fills: list[SimulatedFill]
    risk_outcomes: list[RiskGuardrailOutcome]
    open_orders: list[SimulatedOrder]
    performance_points: list[PerformancePoint]
    performance_summary: PerformanceSummary


@dataclass(slots=True)
class PersistedArtifactState:
    order_id_map: dict[str, int]
    fill_id_map: dict[str, int]


@dataclass(slots=True)
class PersistedBacktestRunResult:
    run_id: int
    loop_result: BacktestRunLoopResult


@dataclass(slots=True)
class QuietTraceCompressionSpan:
    first: BacktestDebugTraceRecord
    high: BacktestDebugTraceRecord
    low: BacktestDebugTraceRecord
    last: BacktestDebugTraceRecord

    def add(self, record: BacktestDebugTraceRecord) -> None:
        self.last = record
        if record.close_price > self.high.close_price:
            self.high = record
        if record.close_price < self.low.close_price:
            self.low = record

    def selected_records(self) -> list[BacktestDebugTraceRecord]:
        ordered_records = sorted(
            (self.first, self.high, self.low, self.last),
            key=lambda record: record.step_index,
        )
        selected: list[BacktestDebugTraceRecord] = []
        seen_step_indexes: set[int] = set()
        for record in ordered_records:
            if record.step_index in seen_step_indexes:
                continue
            seen_step_indexes.add(record.step_index)
            selected.append(record)
        return selected


class BacktestRunnerSkeleton:
    _EMPTY_RISK_OUTCOMES_JSON: list[dict[str, Any]] = []

    def __init__(
        self,
        run_config: BacktestRunConfig,
        *,
        registry: StrategyRegistry | None = None,
        strategy: StrategyBase | None = None,
        signal_repository: StrategySignalRepository | None = None,
        fill_model: DeterministicBarsFillModel | None = None,
        run_repository: BacktestRunRepository | None = None,
    ) -> None:
        self.run_config = run_config
        self.registry = registry or build_default_registry()
        self.strategy = strategy or self.registry.create(
            run_config.session.strategy_code,
            run_config.session.strategy_version,
            run_config.strategy_params_json,
        )
        self.lifecycle = BacktestLifecycle(run_config)
        self.signal_repository = signal_repository or StrategySignalRepository()
        self.fill_model = fill_model or DeterministicBarsFillModel()
        self.risk_guardrails = BacktestRiskGuardrailEngine(
            run_config,
            fee_model=self.fill_model.fee_model,
            slippage_model=self.fill_model.slippage_model,
        )
        self.run_repository = run_repository or BacktestRunRepository()

    def evaluate_bar(
        self,
        bar: BarEvent,
        recent_bars: Sequence[BarEvent],
        *,
        current_positions: Mapping[str, Decimal] | None = None,
        current_cash: Decimal = Decimal("0"),
        market_context: StrategyMarketContext | None = None,
    ) -> BacktestStepResult:
        if bar.unified_symbol not in self.run_config.session.universe:
            raise ValueError("bar unified_symbol must belong to the configured strategy session universe")
        positions = current_positions or {}
        decision = self.strategy.evaluate(
            StrategyEvaluationInput(
                session=self.run_config.session,
                run_config=self.run_config,
                bar=bar,
                recent_bars=recent_bars,
                current_positions=positions,
                current_cash=current_cash,
                market_context=market_context,
            )
        )
        plan = self.lifecycle.plan_from_decision(decision, positions)
        signals = self._build_signals(decision, positions)
        return BacktestStepResult(
            bar_time=bar.bar_time,
            plan=plan,
            signals=signals,
            created_orders=[],
            fills=[],
            risk_outcomes=[],
        )

    def run_bars(
        self,
        bars: Iterable[BarEvent],
        *,
        initial_positions: Mapping[str, Decimal] | None = None,
        initial_cash: Decimal | None = None,
        market_context_by_symbol: Mapping[str, BacktestPerpContextCursor] | None = None,
        persist_signals: bool = False,
        connection: Connection | None = None,
        capture_steps: bool = True,
        capture_debug_traces: bool = False,
        assume_sorted: bool = False,
        collect_performance_points: bool = True,
        performance_point_sink: Callable[[Sequence[PerformancePoint]], None] | None = None,
        performance_point_sink_chunk_size: int = 5000,
        collect_orders: bool = True,
        order_sink: Callable[[Sequence[SimulatedOrder]], dict[str, int] | None] | None = None,
        order_status_sink: Callable[[Sequence[SimulatedOrder]], None] | None = None,
        collect_fills: bool = True,
        fill_sink: Callable[[Sequence[SimulatedFill]], dict[str, int] | None] | None = None,
        collect_debug_traces: bool = True,
        debug_trace_sink: Callable[[Sequence[BacktestDebugTraceRecord]], None] | None = None,
        debug_trace_sink_chunk_size: int = 500,
        progress_callback: Callable[[datetime], None] | None = None,
    ) -> BacktestRunLoopResult:
        portfolio = PortfolioState(
            cash=initial_cash if initial_cash is not None else self.run_config.initial_cash,
            position_states={},
        )
        for symbol, value in (initial_positions or {}).items():
            portfolio.position_states[symbol] = PositionState(qty=Decimal(value))
        recent_bars_by_symbol: dict[str, list[BarEvent] | deque[BarEvent]] = {}
        step_results: list[BacktestStepResult] = []
        debug_traces: list[BacktestDebugTraceRecord] = []
        persisted_signal_ids: list[int] = []
        pending_orders_by_symbol: dict[str, list[SimulatedOrder]] = {}
        all_orders: list[SimulatedOrder] = []
        all_fills: list[SimulatedFill] = []
        all_risk_outcomes: list[RiskGuardrailOutcome] = []
        performance_points: list[PerformancePoint] = []
        performance_point_buffer: list[PerformancePoint] = []
        debug_trace_buffer: list[BacktestDebugTraceRecord] = []
        latest_close_by_symbol: dict[str, Decimal] = {}
        serialized_market_context_cache: dict[tuple[object, ...], dict[str, Any]] = {}
        serialized_empty_decision_cache: dict[tuple[object, ...], dict[str, Any]] = {}
        running_peak_equity = portfolio.cash
        max_drawdown = Decimal("0")
        latest_performance_point: PerformancePoint | None = None
        trace_running_peak_equity = portfolio.cash
        trace_step_index = 0
        captured_debug_trace_count = 0
        previous_trace_cash = portfolio.cash
        previous_trace_equity = portfolio.cash
        quiet_trace_span: QuietTraceCompressionSpan | None = None
        previous_position_qty_by_symbol: dict[str, Decimal] = {
            symbol: qty for symbol, qty in portfolio.positions.items()
        }
        use_full_trace_quiet_compression = self.run_config.debug_trace_level == "full_compressed"

        def flush_debug_trace_buffer() -> None:
            if debug_trace_sink is not None and debug_trace_buffer:
                debug_trace_sink(tuple(debug_trace_buffer))
                debug_trace_buffer.clear()

        def emit_debug_trace_record(record: BacktestDebugTraceRecord) -> None:
            nonlocal captured_debug_trace_count
            captured_debug_trace_count += 1
            if collect_debug_traces:
                debug_traces.append(record)
            elif debug_trace_sink is not None:
                debug_trace_buffer.append(record)
                if len(debug_trace_buffer) >= debug_trace_sink_chunk_size:
                    flush_debug_trace_buffer()

        def flush_quiet_trace_span() -> None:
            nonlocal quiet_trace_span
            if quiet_trace_span is None:
                return
            for record in quiet_trace_span.selected_records():
                emit_debug_trace_record(record)
            quiet_trace_span = None

        history_cap = self.strategy.required_bar_history
        ordered_bars = bars if assume_sorted else sorted(bars, key=lambda item: (item.bar_time, item.unified_symbol))
        for bar_time, grouped_bars in groupby(ordered_bars, key=lambda item: item.bar_time):
            for bar in grouped_bars:
                existing_position = portfolio.position_states.get(bar.unified_symbol)
                if existing_position is not None and existing_position.average_entry_price is None:
                    existing_position.average_entry_price = bar.open
                step_fills: list[SimulatedFill] = []
                updated_orders: list[SimulatedOrder] = []
                current_pending = pending_orders_by_symbol.get(bar.unified_symbol, [])
                remaining_orders: list[SimulatedOrder] = []
                previous_cooldown_activation_count = int(
                    self.risk_guardrails.session_state.activation_counts_by_code.get(
                        "cooldown_activated_after_loss_close",
                        0,
                    )
                )
                for pending_order in current_pending:
                    previous_status = pending_order.status
                    order_update = self.fill_model.process_open_order(
                        pending_order,
                        current_bar=bar,
                        connection=connection,
                    )
                    if order_update.order.status != previous_status:
                        updated_orders.append(order_update.order)
                    if order_update.fill is not None:
                        fill_outcome = portfolio.apply_fill(order_update.fill)
                        self.risk_guardrails.observe_fill_application(fill_outcome=fill_outcome)
                        step_fills.append(order_update.fill)
                        if collect_fills:
                            all_fills.append(order_update.fill)
                    else:
                        remaining_orders.append(order_update.order)
                if fill_sink is not None and step_fills:
                    fill_sink(tuple(step_fills))
                if order_status_sink is not None and updated_orders:
                    order_status_sink(tuple(updated_orders))
                pending_orders_by_symbol[bar.unified_symbol] = remaining_orders

                recent_bars = recent_bars_by_symbol.get(bar.unified_symbol)
                if recent_bars is None:
                    recent_bars = deque(maxlen=history_cap) if history_cap is not None else []
                    recent_bars_by_symbol[bar.unified_symbol] = recent_bars
                recent_bars.append(bar)
                market_context = None
                if market_context_by_symbol is not None:
                    context_cursor = market_context_by_symbol.get(bar.unified_symbol)
                    if context_cursor is not None:
                        market_context = context_cursor.context_at(bar.bar_time)
                step_result = self.evaluate_bar(
                    bar,
                    recent_bars,
                    current_positions=portfolio.positions,
                    current_cash=portfolio.cash,
                    market_context=market_context,
                )

                signal_id_by_symbol: dict[str, int] = {}
                if persist_signals:
                    if connection is None:
                        raise ValueError("connection is required when persist_signals is true")
                    for signal in step_result.signals:
                        signal_id = self.signal_repository.insert(connection, signal)
                        persisted_signal_ids.append(signal_id)
                        signal_id_by_symbol[signal.unified_symbol] = signal_id

                allowed_intents, risk_outcomes = self.risk_guardrails.filter_execution_intents(
                    step_result.plan.execution_intents,
                    current_bar=bar,
                    portfolio=portfolio,
                    latest_mark_prices=latest_close_by_symbol,
                    connection=connection,
                )
                step_result.risk_outcomes.extend(risk_outcomes)
                all_risk_outcomes.extend(risk_outcomes)
                created_orders = [
                    self.fill_model.create_order(
                        intent,
                        current_bar=bar,
                        signal_id=signal_id_by_symbol.get(intent.unified_symbol),
                    )
                    for intent in allowed_intents
                ]
                if collect_orders:
                    all_orders.extend(created_orders)
                if order_sink is not None and created_orders:
                    order_sink(tuple(created_orders))
                pending_orders_by_symbol.setdefault(bar.unified_symbol, []).extend(created_orders)
                latest_close_by_symbol[bar.unified_symbol] = bar.close
                if capture_debug_traces:
                    trace_mark = portfolio.mark_to_market(latest_close_by_symbol)
                    trace_running_peak_equity = max(trace_running_peak_equity, trace_mark.equity)
                    trace_drawdown = Decimal("0")
                    if trace_running_peak_equity > 0:
                        trace_drawdown = (trace_running_peak_equity - trace_mark.equity) / trace_running_peak_equity
                    current_position_qty = portfolio.position_qty(bar.unified_symbol)
                    previous_position_qty = previous_position_qty_by_symbol.get(
                        bar.unified_symbol,
                        Decimal("0"),
                    )
                    risk_state_snapshot = self.risk_guardrails.build_runtime_state_snapshot()
                    trace_step_index += 1
                    is_activity_step = self._is_activity_trace_step(
                        step_result=step_result,
                        created_orders=created_orders,
                        step_fills=step_fills,
                    )
                    if self._should_capture_debug_trace(
                        step_index=trace_step_index,
                        is_activity_step=is_activity_step,
                    ):
                        trace_record = self._build_debug_trace_record(
                            step_index=trace_step_index,
                            bar=bar,
                            step_result=step_result,
                            created_orders=created_orders,
                            step_fills=step_fills,
                            trace_mark=trace_mark,
                            current_position_qty=current_position_qty,
                            previous_position_qty=previous_position_qty,
                            previous_cash=previous_trace_cash,
                            previous_equity=previous_trace_equity,
                            drawdown=trace_drawdown,
                            serialized_market_context=(
                                self._serialize_market_context_snapshot_cached(
                                    market_context,
                                    serialized_market_context_cache,
                                )
                                if is_activity_step
                                else None
                            ),
                            serialized_decision=self._serialize_step_decision_cached(
                                step_result,
                                serialized_empty_decision_cache,
                                risk_state_snapshot=risk_state_snapshot,
                                previous_cooldown_activation_count=previous_cooldown_activation_count,
                            ),
                            previous_cooldown_activation_count=previous_cooldown_activation_count,
                        )
                        if use_full_trace_quiet_compression and not is_activity_step:
                            if quiet_trace_span is None:
                                quiet_trace_span = QuietTraceCompressionSpan(
                                    first=trace_record,
                                    high=trace_record,
                                    low=trace_record,
                                    last=trace_record,
                                )
                            else:
                                quiet_trace_span.add(trace_record)
                        else:
                            flush_quiet_trace_span()
                            emit_debug_trace_record(trace_record)
                    elif use_full_trace_quiet_compression:
                        flush_quiet_trace_span()
                    previous_trace_cash = trace_mark.cash
                    previous_trace_equity = trace_mark.equity
                    if current_position_qty == 0:
                        previous_position_qty_by_symbol.pop(bar.unified_symbol, None)
                    else:
                        previous_position_qty_by_symbol[bar.unified_symbol] = current_position_qty
                if capture_steps:
                    step_result.created_orders.extend(created_orders)
                    step_result.fills.extend(step_fills)
                    step_results.append(step_result)

            mark = portfolio.mark_to_market(latest_close_by_symbol)
            performance_point, running_peak_equity = build_performance_point(
                ts=bar_time,
                mark=mark,
                running_peak_equity=running_peak_equity,
            )
            latest_performance_point = performance_point
            max_drawdown = max(max_drawdown, performance_point.drawdown)
            if collect_performance_points:
                performance_points.append(performance_point)
            if performance_point_sink is not None:
                performance_point_buffer.append(performance_point)
                if len(performance_point_buffer) >= performance_point_sink_chunk_size:
                    performance_point_sink(tuple(performance_point_buffer))
                    performance_point_buffer.clear()
            if progress_callback is not None:
                progress_callback(bar_time)
            self.risk_guardrails.complete_bar()

        open_orders: list[SimulatedOrder] = []
        for remaining_orders in pending_orders_by_symbol.values():
            for order in remaining_orders:
                open_orders.append(self.fill_model.expire_open_order(order))
        if order_status_sink is not None and open_orders:
            order_status_sink(tuple(open_orders))

        flush_quiet_trace_span()
        if performance_point_sink is not None and performance_point_buffer:
            performance_point_sink(tuple(performance_point_buffer))
        flush_debug_trace_buffer()

        summary_initial_cash = initial_cash if initial_cash is not None else self.run_config.initial_cash
        if collect_performance_points:
            performance_summary = summarize_performance(
                initial_cash=summary_initial_cash,
                run_start=self.run_config.start_time,
                run_end=self.run_config.end_time,
                performance_points=performance_points,
            )
        else:
            performance_summary = summarize_performance_from_latest_point(
                initial_cash=summary_initial_cash,
                run_start=self.run_config.start_time,
                run_end=self.run_config.end_time,
                final_point=latest_performance_point,
                max_drawdown=max_drawdown,
            )

        return BacktestRunLoopResult(
            steps=step_results,
            debug_traces=debug_traces,
            debug_trace_count=captured_debug_trace_count,
            final_positions=portfolio.positions,
            final_cash=portfolio.cash,
            persisted_signal_ids=persisted_signal_ids,
            orders=all_orders,
            fills=all_fills,
            risk_outcomes=all_risk_outcomes,
            open_orders=open_orders,
            performance_points=performance_points,
            performance_summary=performance_summary,
        )

    def load_and_run(
        self,
        connection: Connection,
        *,
        bar_loader: BacktestBarLoader | None = None,
        context_loader: BacktestPerpContextLoader | None = None,
        persist_signals: bool = False,
        capture_steps: bool = True,
        capture_debug_traces: bool = False,
        collect_performance_points: bool = True,
        performance_point_sink: Callable[[Sequence[PerformancePoint]], None] | None = None,
        collect_orders: bool = True,
        order_sink: Callable[[Sequence[SimulatedOrder]], dict[str, int] | None] | None = None,
        order_status_sink: Callable[[Sequence[SimulatedOrder]], None] | None = None,
        collect_fills: bool = True,
        fill_sink: Callable[[Sequence[SimulatedFill]], dict[str, int] | None] | None = None,
        collect_debug_traces: bool = True,
        debug_trace_sink: Callable[[Sequence[BacktestDebugTraceRecord]], None] | None = None,
        debug_trace_sink_chunk_size: int = 500,
        progress_callback: Callable[[datetime], None] | None = None,
    ) -> BacktestRunLoopResult:
        loader = bar_loader or BacktestBarLoader()
        bars = loader.iter_bars(
            connection,
            self.run_config,
            required_bar_history=self.strategy.required_bar_history,
        )
        market_context_by_symbol = (context_loader or BacktestPerpContextLoader()).load_contexts(connection, self.run_config)
        return self.run_bars(
            bars,
            market_context_by_symbol=market_context_by_symbol,
            persist_signals=persist_signals,
            connection=connection,
            capture_steps=capture_steps,
            capture_debug_traces=capture_debug_traces,
            assume_sorted=True,
            collect_performance_points=collect_performance_points,
            performance_point_sink=performance_point_sink,
            collect_orders=collect_orders,
            order_sink=order_sink,
            order_status_sink=order_status_sink,
            collect_fills=collect_fills,
            fill_sink=fill_sink,
            collect_debug_traces=collect_debug_traces,
            debug_trace_sink=debug_trace_sink,
            debug_trace_sink_chunk_size=debug_trace_sink_chunk_size,
            progress_callback=progress_callback,
        )

    def load_run_and_persist(
        self,
        connection: Connection,
        *,
        bar_loader: BacktestBarLoader | None = None,
        context_loader: BacktestPerpContextLoader | None = None,
        persist_signals: bool = True,
        capture_steps: bool = False,
        persist_debug_traces: bool = False,
        progress_callback: Callable[[datetime], None] | None = None,
    ) -> PersistedBacktestRunResult:
        persisted_artifacts = PersistedArtifactState(order_id_map={}, fill_id_map={})
        run_id = self.run_repository.insert_run(
            connection,
            self.run_config,
            status="running",
        )
        loop_result = self.load_and_run(
            connection,
            bar_loader=bar_loader,
            context_loader=context_loader,
            persist_signals=persist_signals,
            capture_steps=capture_steps,
            capture_debug_traces=persist_debug_traces,
            collect_performance_points=False,
            performance_point_sink=lambda chunk: self.run_repository.upsert_timeseries(
                connection,
                run_id=run_id,
                performance_points=chunk,
            ),
            collect_orders=False,
            order_sink=lambda chunk: persisted_artifacts.order_id_map.update(
                self.run_repository.insert_orders(
                    connection,
                    run_id=run_id,
                    orders=chunk,
                )
            ),
            order_status_sink=lambda chunk: self.run_repository.update_order_statuses(
                connection,
                orders=chunk,
                order_id_map=persisted_artifacts.order_id_map,
            ),
            collect_fills=False,
            fill_sink=lambda chunk: persisted_artifacts.fill_id_map.update(
                self.run_repository.insert_fills(
                    connection,
                    run_id=run_id,
                    fills=chunk,
                    order_id_map=persisted_artifacts.order_id_map,
                )
            ),
            collect_debug_traces=not persist_debug_traces,
            debug_trace_sink=(
                (lambda chunk: self.run_repository.insert_debug_traces(
                    connection,
                    run_id=run_id,
                    debug_traces=chunk,
                    order_id_map=persisted_artifacts.order_id_map,
                    fill_id_map=persisted_artifacts.fill_id_map,
                    return_ids=False,
                ))
                if persist_debug_traces
                else None
            ),
            progress_callback=progress_callback,
        )
        self.run_repository.finalize_run(
            connection,
            run_id=run_id,
            run_config=self.run_config,
            runtime_metadata=self._build_runtime_metadata(
                loop_result,
                self.risk_guardrails,
                persist_debug_traces=persist_debug_traces,
            ),
            status="finished",
        )
        self.run_repository.upsert_summary(
            connection,
            run_id=run_id,
            summary=loop_result.performance_summary,
        )
        if persist_debug_traces:
            pass
        return PersistedBacktestRunResult(run_id=run_id, loop_result=loop_result)

    @staticmethod
    def _build_runtime_metadata(
        loop_result: BacktestRunLoopResult,
        risk_guardrails: BacktestRiskGuardrailEngine,
        *,
        persist_debug_traces: bool,
    ) -> dict[str, object]:
        blocked_outcomes = [outcome for outcome in loop_result.risk_outcomes if outcome.decision == RiskDecision.BLOCK]
        block_counts_by_code: dict[str, int] = {}
        outcome_counts_by_code: dict[str, int] = {}
        for outcome in blocked_outcomes:
            block_counts_by_code[outcome.code] = block_counts_by_code.get(outcome.code, 0) + 1
        for outcome in loop_result.risk_outcomes:
            outcome_counts_by_code[outcome.code] = outcome_counts_by_code.get(outcome.code, 0) + 1

        return {
            "risk_summary": {
                "evaluated_intent_count": len(loop_result.risk_outcomes),
                "allowed_intent_count": sum(
                    1 for outcome in loop_result.risk_outcomes if outcome.decision == RiskDecision.ALLOW
                ),
                "blocked_intent_count": len(blocked_outcomes),
                "block_counts_by_code": block_counts_by_code,
                "outcome_counts_by_code": outcome_counts_by_code,
                "state_snapshot": risk_guardrails.build_runtime_state_snapshot(),
            },
            "debug_trace_summary": {
                "persisted": persist_debug_traces,
                "captured_trace_count": loop_result.debug_trace_count,
                "sampling_level": risk_guardrails.run_config.debug_trace_level,
                "sampling_stride": risk_guardrails.run_config.debug_trace_stride,
                "activity_only": risk_guardrails.run_config.debug_trace_activity_only,
            },
        }

    def _should_capture_debug_trace(
        self,
        *,
        step_index: int,
        is_activity_step: bool,
    ) -> bool:
        stride = self.run_config.debug_trace_stride or 1
        activity_only = self.run_config.debug_trace_activity_only
        if is_activity_step:
            return True
        if activity_only:
            return False
        return step_index % stride == 0

    @staticmethod
    def _is_activity_trace_step(
        *,
        step_result: BacktestStepResult,
        created_orders: Sequence[SimulatedOrder],
        step_fills: Sequence[SimulatedFill],
    ) -> bool:
        return bool(
            step_result.signals
            or created_orders
            or step_fills
            or any(outcome.decision == RiskDecision.BLOCK for outcome in step_result.risk_outcomes)
        )

    def _build_signals(
        self,
        decision: Signal | TargetPosition | None,
        current_positions: Mapping[str, Decimal],
    ) -> list[Signal]:
        if isinstance(decision, Signal):
            return [decision]
        if isinstance(decision, TargetPosition):
            return build_signals_from_target_position(
                decision,
                current_positions,
                session_code=self.run_config.session.session_code,
            )
        return []

    @staticmethod
    def _build_debug_trace_record(
        *,
        step_index: int,
        bar: BarEvent,
        step_result: BacktestStepResult,
        created_orders: Sequence[SimulatedOrder],
        step_fills: Sequence[SimulatedFill],
        trace_mark: PortfolioMark,
        current_position_qty: Decimal,
        previous_position_qty: Decimal,
        previous_cash: Decimal,
        previous_equity: Decimal,
        drawdown: Decimal,
        serialized_market_context: dict[str, Any] | None,
        serialized_decision: dict[str, Any],
        previous_cooldown_activation_count: int,
    ) -> BacktestDebugTraceRecord:
        blocked_count, blocked_codes, serialized_risk_outcomes = (
            BacktestRunnerSkeleton._summarize_and_serialize_risk_outcomes(step_result.risk_outcomes)
        )
        return BacktestDebugTraceRecord(
            step_index=step_index,
            bar_time=bar.bar_time,
            exchange_code=bar.exchange_code,
            unified_symbol=bar.unified_symbol,
            close_price=bar.close,
            current_position_qty=current_position_qty,
            position_qty_delta=current_position_qty - previous_position_qty,
            signal_count=len(step_result.signals),
            intent_count=len(step_result.plan.execution_intents),
            blocked_intent_count=blocked_count,
            blocked_codes=blocked_codes,
            created_order_count=len(created_orders),
            created_order_ids=[order.order_id for order in created_orders],
            fill_count=len(step_fills),
            fill_ids=[fill.fill_id for fill in step_fills],
            cash=trace_mark.cash,
            cash_delta=trace_mark.cash - previous_cash,
            equity=trace_mark.equity,
            equity_delta=trace_mark.equity - previous_equity,
            gross_exposure=trace_mark.gross_exposure,
            net_exposure=trace_mark.net_exposure,
            drawdown=drawdown,
            market_context_json=serialized_market_context,
            decision_json=serialized_decision,
            risk_outcomes_json=serialized_risk_outcomes,
        )

    @staticmethod
    def _serialize_market_context_snapshot(
        market_context: StrategyMarketContext | None,
    ) -> dict[str, Any] | None:
        if market_context is None:
            return None

        snapshot: dict[str, Any] = {
            "feature_input_version": market_context.feature_input_version,
        }
        for field_name in (
            "funding_rate",
            "open_interest",
            "mark_price",
            "index_price",
            "global_long_short_account_ratio",
            "top_trader_long_short_account_ratio",
            "top_trader_long_short_position_ratio",
            "taker_long_short_ratio",
            "minutes_to_next_funding",
            "oi_change_pct_window",
            "price_change_pct_window",
            "weak_price_oi_push",
        ):
            value = getattr(market_context, field_name)
            if value is not None:
                snapshot[field_name] = BacktestRunnerSkeleton._serialize_context_value(value)
        return snapshot

    @staticmethod
    def _serialize_context_value(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, Mapping):
            return {
                str(key): BacktestRunnerSkeleton._serialize_context_value(item)
                for key, item in value.items()
            }
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [BacktestRunnerSkeleton._serialize_context_value(item) for item in value]
        return value

    @staticmethod
    def _market_context_snapshot_cache_key(
        market_context: StrategyMarketContext | None,
    ) -> tuple[object, ...] | None:
        if market_context is None:
            return None
        return (
            market_context.feature_input_version,
            id(market_context.funding_rate) if market_context.funding_rate is not None else None,
            id(market_context.open_interest) if market_context.open_interest is not None else None,
            id(market_context.mark_price) if market_context.mark_price is not None else None,
            id(market_context.index_price) if market_context.index_price is not None else None,
            id(market_context.global_long_short_account_ratio)
            if market_context.global_long_short_account_ratio is not None
            else None,
            id(market_context.top_trader_long_short_account_ratio)
            if market_context.top_trader_long_short_account_ratio is not None
            else None,
            id(market_context.top_trader_long_short_position_ratio)
            if market_context.top_trader_long_short_position_ratio is not None
            else None,
            id(market_context.taker_long_short_ratio) if market_context.taker_long_short_ratio is not None else None,
            market_context.minutes_to_next_funding,
            market_context.oi_change_pct_window,
            market_context.price_change_pct_window,
            market_context.weak_price_oi_push,
        )

    @staticmethod
    def _serialize_market_context_snapshot_cached(
        market_context: StrategyMarketContext | None,
        cache: dict[tuple[object, ...], dict[str, Any]],
    ) -> dict[str, Any] | None:
        cache_key = BacktestRunnerSkeleton._market_context_snapshot_cache_key(market_context)
        if cache_key is None:
            return None
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        serialized = BacktestRunnerSkeleton._serialize_market_context_snapshot(market_context)
        if serialized is None:
            return None
        cache[cache_key] = serialized
        return serialized

    @staticmethod
    def _serialize_step_decision(
        step_result: BacktestStepResult,
        *,
        risk_state_snapshot: dict[str, object] | None = None,
        previous_cooldown_activation_count: int = 0,
    ) -> dict[str, Any]:
        decision = step_result.plan.decision
        cooldown_activation_count = 0
        cooldown_bars_remaining = 0
        if risk_state_snapshot is not None:
            activation_counts = risk_state_snapshot.get("activation_counts_by_code") or {}
            cooldown_activation_count = int(
                activation_counts.get("cooldown_activated_after_loss_close") or 0
            )
            cooldown_bars_remaining = int(risk_state_snapshot.get("cooldown_bars_remaining") or 0)
        risk_state = {
            "cooldown_bars_remaining": cooldown_bars_remaining,
            "cooldown_active": cooldown_bars_remaining > 0,
            "cooldown_activation_count": cooldown_activation_count,
            "cooldown_activated_this_step": cooldown_activation_count > previous_cooldown_activation_count,
        }
        if decision is None:
            return BacktestRunnerSkeleton._serialize_empty_step_decision(
                risk_state_snapshot=risk_state,
            )
        if isinstance(decision, Signal):
            decision_type = "signal"
            decision_payload = {
                "strategy_code": decision.strategy_code,
                "strategy_version": decision.strategy_version,
                "signal_time": decision.signal_time.isoformat(),
                "signal_type": str(decision.signal_type),
                "direction": decision.direction,
                "target_qty": str(decision.target_qty) if decision.target_qty is not None else None,
                "target_notional": (
                    str(decision.target_notional)
                    if decision.target_notional is not None
                    else None
                ),
                "reason_code": decision.reason_code,
            }
        elif isinstance(decision, TargetPosition):
            decision_type = "target_position"
            decision_payload = {
                "strategy_code": decision.strategy_code,
                "strategy_version": decision.strategy_version,
                "target_time": decision.target_time.isoformat(),
                "positions": [
                    {
                        "exchange_code": item.exchange_code,
                        "unified_symbol": item.unified_symbol,
                        "target_qty": str(item.target_qty) if item.target_qty is not None else None,
                        "target_notional": (
                            str(item.target_notional)
                            if item.target_notional is not None
                            else None
                        ),
                    }
                    for item in decision.positions
                ],
            }
        else:
            decision_type = type(decision).__name__
            decision_payload = {"repr": str(decision)}

        return {
            "decision_type": decision_type,
            "decision": decision_payload,
            "risk_state": risk_state,
            "signals": [
                {
                    "signal_type": str(signal.signal_type),
                    "direction": signal.direction,
                    "target_qty": str(signal.target_qty) if signal.target_qty is not None else None,
                    "target_notional": (
                        str(signal.target_notional)
                        if signal.target_notional is not None
                        else None
                    ),
                    "reason_code": signal.reason_code,
                }
                for signal in step_result.signals
            ],
            "execution_intents": [
                {
                    "unified_symbol": intent.unified_symbol,
                    "side": str(intent.side),
                    "order_type": str(intent.order_type),
                    "current_qty": str(intent.current_qty),
                    "target_qty": str(intent.target_qty),
                    "delta_qty": str(intent.delta_qty),
                    "reduce_only": intent.reduce_only,
                }
                for intent in step_result.plan.execution_intents
            ],
        }

    @staticmethod
    def _empty_step_decision_cache_key(
        *,
        risk_state_snapshot: dict[str, object] | None = None,
        previous_cooldown_activation_count: int = 0,
    ) -> tuple[object, ...]:
        cooldown_activation_count = 0
        cooldown_bars_remaining = 0
        if risk_state_snapshot is not None:
            activation_counts = risk_state_snapshot.get("activation_counts_by_code") or {}
            cooldown_activation_count = int(
                activation_counts.get("cooldown_activated_after_loss_close") or 0
            )
            cooldown_bars_remaining = int(risk_state_snapshot.get("cooldown_bars_remaining") or 0)
        return (
            cooldown_bars_remaining,
            cooldown_bars_remaining > 0,
            cooldown_activation_count,
            cooldown_activation_count > previous_cooldown_activation_count,
        )

    @staticmethod
    def _serialize_empty_step_decision(
        *,
        risk_state_snapshot: dict[str, object],
    ) -> dict[str, Any]:
        return {
            "decision_type": "none",
            "risk_state": risk_state_snapshot,
        }

    @staticmethod
    def _serialize_step_decision_cached(
        step_result: BacktestStepResult,
        cache: dict[tuple[object, ...], dict[str, Any]],
        *,
        risk_state_snapshot: dict[str, object] | None = None,
        previous_cooldown_activation_count: int = 0,
    ) -> dict[str, Any]:
        if (
            step_result.plan.decision is None
            and not step_result.signals
            and not step_result.plan.execution_intents
        ):
            cache_key = BacktestRunnerSkeleton._empty_step_decision_cache_key(
                risk_state_snapshot=risk_state_snapshot,
                previous_cooldown_activation_count=previous_cooldown_activation_count,
            )
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
            serialized = BacktestRunnerSkeleton._serialize_step_decision(
                step_result,
                risk_state_snapshot=risk_state_snapshot,
                previous_cooldown_activation_count=previous_cooldown_activation_count,
            )
            cache[cache_key] = serialized
            return serialized
        return BacktestRunnerSkeleton._serialize_step_decision(
            step_result,
            risk_state_snapshot=risk_state_snapshot,
            previous_cooldown_activation_count=previous_cooldown_activation_count,
        )

    @staticmethod
    def _serialize_risk_outcome(outcome: RiskGuardrailOutcome) -> dict[str, Any]:
        return {
            "decision": str(outcome.decision),
            "code": outcome.code,
            "message": outcome.message,
            "evaluated_at": outcome.evaluated_at.isoformat(),
            "unified_symbol": outcome.unified_symbol,
            "current_qty": str(outcome.current_qty),
            "target_qty": str(outcome.target_qty),
            "delta_qty": str(outcome.delta_qty),
            "estimated_notional": (
                str(outcome.estimated_notional)
                if outcome.estimated_notional is not None
                else None
            ),
            "details_json": outcome.details_json if outcome.details_json else {},
        }

    @staticmethod
    def _serialize_risk_outcomes(
        outcomes: Sequence[RiskGuardrailOutcome],
    ) -> list[dict[str, Any]]:
        if not outcomes:
            return BacktestRunnerSkeleton._EMPTY_RISK_OUTCOMES_JSON
        return [
            BacktestRunnerSkeleton._serialize_risk_outcome(outcome)
            for outcome in outcomes
        ]

    @staticmethod
    def _summarize_and_serialize_risk_outcomes(
        outcomes: Sequence[RiskGuardrailOutcome],
    ) -> tuple[int, list[str], list[dict[str, Any]]]:
        if not outcomes:
            return 0, [], BacktestRunnerSkeleton._EMPTY_RISK_OUTCOMES_JSON

        blocked_count = 0
        blocked_codes: list[str] = []
        serialized: list[dict[str, Any]] = []
        for outcome in outcomes:
            if outcome.decision == RiskDecision.BLOCK:
                blocked_count += 1
                blocked_codes.append(outcome.code)
            serialized.append(BacktestRunnerSkeleton._serialize_risk_outcome(outcome))
        return blocked_count, blocked_codes, serialized
