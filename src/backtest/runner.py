from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from itertools import groupby
from typing import Any, Iterable, Mapping, Sequence

from models.backtest import BacktestRunConfig
from models.common import RiskDecision
from models.market import BarEvent
from models.strategy import Signal, TargetPosition
from sqlalchemy.engine import Connection
from storage.repositories.backtest import BacktestRunRepository
from storage.repositories.strategy import StrategySignalRepository
from strategy import StrategyBase, StrategyEvaluationInput, StrategyRegistry, build_default_registry

from .data import BacktestBarLoader
from .fills import DeterministicBarsFillModel, SimulatedFill, SimulatedOrder
from .lifecycle import BacktestLifecycle, BacktestStepPlan
from .performance import PerformancePoint, PerformanceSummary, build_performance_point, summarize_performance
from .risk import BacktestRiskGuardrailEngine, RiskGuardrailOutcome
from .signals import build_signals_from_target_position
from .state import PortfolioMark, PortfolioState, PositionState
from .traces import BacktestDebugTraceRecord


@dataclass(slots=True)
class BacktestStepResult:
    bar_time: str
    plan: BacktestStepPlan
    signals: list[Signal]
    created_orders: list[SimulatedOrder]
    fills: list[SimulatedFill]
    risk_outcomes: list[RiskGuardrailOutcome]

@dataclass(slots=True)
class BacktestRunLoopResult:
    steps: list[BacktestStepResult]
    debug_traces: list[BacktestDebugTraceRecord]
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
class PersistedBacktestRunResult:
    run_id: int
    loop_result: BacktestRunLoopResult


class BacktestRunnerSkeleton:
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
            )
        )
        plan = self.lifecycle.plan_from_decision(decision, positions)
        signals = self._build_signals(decision, positions)
        return BacktestStepResult(
            bar_time=bar.bar_time.isoformat(),
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
        persist_signals: bool = False,
        connection: Connection | None = None,
        capture_steps: bool = True,
        capture_debug_traces: bool = False,
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
        latest_close_by_symbol: dict[str, Decimal] = {}
        running_peak_equity = portfolio.cash
        trace_running_peak_equity = portfolio.cash
        previous_trace_cash = portfolio.cash
        previous_trace_equity = portfolio.cash
        previous_position_qty_by_symbol: dict[str, Decimal] = {
            symbol: qty for symbol, qty in portfolio.positions.items()
        }

        history_cap = self.strategy.required_bar_history
        sorted_bars = sorted(bars, key=lambda item: (item.bar_time, item.unified_symbol))
        for bar_time, grouped_bars in groupby(sorted_bars, key=lambda item: item.bar_time):
            for bar in grouped_bars:
                existing_position = portfolio.position_states.get(bar.unified_symbol)
                if existing_position is not None and existing_position.average_entry_price is None:
                    existing_position.average_entry_price = bar.open
                step_fills: list[SimulatedFill] = []
                current_pending = pending_orders_by_symbol.get(bar.unified_symbol, [])
                remaining_orders: list[SimulatedOrder] = []
                for pending_order in current_pending:
                    order_update = self.fill_model.process_open_order(
                        pending_order,
                        current_bar=bar,
                        connection=connection,
                    )
                    if order_update.fill is not None:
                        fill_outcome = portfolio.apply_fill(order_update.fill)
                        self.risk_guardrails.observe_fill_application(fill_outcome=fill_outcome)
                        step_fills.append(order_update.fill)
                        all_fills.append(order_update.fill)
                    else:
                        remaining_orders.append(order_update.order)
                pending_orders_by_symbol[bar.unified_symbol] = remaining_orders

                recent_bars = recent_bars_by_symbol.get(bar.unified_symbol)
                if recent_bars is None:
                    recent_bars = deque(maxlen=history_cap) if history_cap is not None else []
                    recent_bars_by_symbol[bar.unified_symbol] = recent_bars
                recent_bars.append(bar)
                step_result = self.evaluate_bar(
                    bar,
                    recent_bars,
                    current_positions=portfolio.positions,
                    current_cash=portfolio.cash,
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
                all_orders.extend(created_orders)
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
                    debug_traces.append(
                        self._build_debug_trace_record(
                            step_index=len(debug_traces) + 1,
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
                        )
                    )
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
            performance_points.append(performance_point)
            self.risk_guardrails.complete_bar()

        open_orders: list[SimulatedOrder] = []
        for remaining_orders in pending_orders_by_symbol.values():
            for order in remaining_orders:
                open_orders.append(self.fill_model.expire_open_order(order))

        performance_summary = summarize_performance(
            initial_cash=initial_cash if initial_cash is not None else self.run_config.initial_cash,
            run_start=self.run_config.start_time,
            run_end=self.run_config.end_time,
            performance_points=performance_points,
        )

        return BacktestRunLoopResult(
            steps=step_results,
            debug_traces=debug_traces,
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
        persist_signals: bool = False,
        capture_steps: bool = True,
        capture_debug_traces: bool = False,
    ) -> BacktestRunLoopResult:
        loader = bar_loader or BacktestBarLoader()
        bars = loader.load_bars(connection, self.run_config)
        return self.run_bars(
            bars,
            persist_signals=persist_signals,
            connection=connection,
            capture_steps=capture_steps,
            capture_debug_traces=capture_debug_traces,
        )

    def load_run_and_persist(
        self,
        connection: Connection,
        *,
        bar_loader: BacktestBarLoader | None = None,
        persist_signals: bool = True,
        capture_steps: bool = False,
        persist_debug_traces: bool = False,
    ) -> PersistedBacktestRunResult:
        loop_result = self.load_and_run(
            connection,
            bar_loader=bar_loader,
            persist_signals=persist_signals,
            capture_steps=capture_steps,
            capture_debug_traces=persist_debug_traces,
        )
        run_id = self.run_repository.insert_run(
            connection,
            self.run_config,
            runtime_metadata=self._build_runtime_metadata(
                loop_result,
                self.risk_guardrails,
                persist_debug_traces=persist_debug_traces,
            ),
        )
        order_id_map = self.run_repository.insert_orders(connection, run_id=run_id, orders=loop_result.orders)
        fill_id_map = self.run_repository.insert_fills(
            connection,
            run_id=run_id,
            fills=loop_result.fills,
            order_id_map=order_id_map,
        )
        self.run_repository.upsert_summary(
            connection,
            run_id=run_id,
            summary=loop_result.performance_summary,
        )
        self.run_repository.upsert_timeseries(
            connection,
            run_id=run_id,
            performance_points=loop_result.performance_points,
        )
        if persist_debug_traces:
            self.run_repository.insert_debug_traces(
                connection,
                run_id=run_id,
                debug_traces=loop_result.debug_traces,
                order_id_map=order_id_map,
                fill_id_map=fill_id_map,
            )
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
                "captured_trace_count": len(loop_result.debug_traces),
            },
        }

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
    ) -> BacktestDebugTraceRecord:
        blocked_count = sum(
            1 for outcome in step_result.risk_outcomes if outcome.decision == RiskDecision.BLOCK
        )
        blocked_codes = [
            outcome.code for outcome in step_result.risk_outcomes if outcome.decision == RiskDecision.BLOCK
        ]
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
            decision_json=BacktestRunnerSkeleton._serialize_step_decision(step_result),
            risk_outcomes_json=[
                BacktestRunnerSkeleton._serialize_risk_outcome(outcome)
                for outcome in step_result.risk_outcomes
            ],
        )

    @staticmethod
    def _serialize_step_decision(step_result: BacktestStepResult) -> dict[str, Any]:
        decision = step_result.plan.decision
        if decision is None:
            return {
                "decision_type": "none",
                "signals": [],
                "execution_intents": [],
            }
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
            "details_json": dict(outcome.details_json),
        }
