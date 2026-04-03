from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from itertools import groupby
from typing import Iterable, Mapping, Sequence

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
from .state import PortfolioState, PositionState


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
    ) -> BacktestRunLoopResult:
        portfolio = PortfolioState(
            cash=initial_cash if initial_cash is not None else self.run_config.initial_cash,
            position_states={},
        )
        for symbol, value in (initial_positions or {}).items():
            portfolio.position_states[symbol] = PositionState(qty=Decimal(value))
        recent_bars_by_symbol: dict[str, list[BarEvent] | deque[BarEvent]] = {}
        step_results: list[BacktestStepResult] = []
        persisted_signal_ids: list[int] = []
        pending_orders_by_symbol: dict[str, list[SimulatedOrder]] = {}
        all_orders: list[SimulatedOrder] = []
        all_fills: list[SimulatedFill] = []
        all_risk_outcomes: list[RiskGuardrailOutcome] = []
        performance_points: list[PerformancePoint] = []
        latest_close_by_symbol: dict[str, Decimal] = {}
        running_peak_equity = portfolio.cash

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
                        portfolio.apply_fill(order_update.fill)
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
    ) -> BacktestRunLoopResult:
        loader = bar_loader or BacktestBarLoader()
        bars = loader.load_bars(connection, self.run_config)
        return self.run_bars(
            bars,
            persist_signals=persist_signals,
            connection=connection,
            capture_steps=capture_steps,
        )

    def load_run_and_persist(
        self,
        connection: Connection,
        *,
        bar_loader: BacktestBarLoader | None = None,
        persist_signals: bool = True,
        capture_steps: bool = False,
    ) -> PersistedBacktestRunResult:
        loop_result = self.load_and_run(
            connection,
            bar_loader=bar_loader,
            persist_signals=persist_signals,
            capture_steps=capture_steps,
        )
        run_id = self.run_repository.insert_run(
            connection,
            self.run_config,
            runtime_metadata=self._build_runtime_metadata(loop_result),
        )
        order_id_map = self.run_repository.insert_orders(connection, run_id=run_id, orders=loop_result.orders)
        self.run_repository.insert_fills(
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
        return PersistedBacktestRunResult(run_id=run_id, loop_result=loop_result)

    @staticmethod
    def _build_runtime_metadata(loop_result: BacktestRunLoopResult) -> dict[str, object]:
        blocked_outcomes = [outcome for outcome in loop_result.risk_outcomes if outcome.decision == RiskDecision.BLOCK]
        block_counts_by_code: dict[str, int] = {}
        for outcome in blocked_outcomes:
            block_counts_by_code[outcome.code] = block_counts_by_code.get(outcome.code, 0) + 1

        return {
            "risk_summary": {
                "evaluated_intent_count": len(loop_result.risk_outcomes),
                "allowed_intent_count": sum(
                    1 for outcome in loop_result.risk_outcomes if outcome.decision == RiskDecision.ALLOW
                ),
                "blocked_intent_count": len(blocked_outcomes),
                "block_counts_by_code": block_counts_by_code,
            }
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
