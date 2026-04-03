from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Mapping

from models.backtest import BacktestRunConfig
from models.common import Direction, OrderSide
from models.strategy import Signal, TargetPosition, TargetPositionItem
from strategy.base import StrategyDecision


class LifecyclePlanningError(ValueError):
    """Raised when a Phase 5 backtest decision cannot be planned safely."""


@dataclass(slots=True)
class ExecutionIntent:
    exchange_code: str
    unified_symbol: str
    generated_at: datetime
    current_qty: Decimal
    target_qty: Decimal
    delta_qty: Decimal
    side: OrderSide
    reduce_only: bool
    metadata_json: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class BacktestStepPlan:
    decision: StrategyDecision
    execution_intents: list[ExecutionIntent]


def _position_sign(value: Decimal) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


class BacktestLifecycle:
    def __init__(self, run_config: BacktestRunConfig) -> None:
        self.run_config = run_config

    def plan_from_decision(
        self,
        decision: StrategyDecision,
        current_positions: Mapping[str, Decimal],
    ) -> BacktestStepPlan:
        if decision is None:
            return BacktestStepPlan(decision=None, execution_intents=[])
        if isinstance(decision, TargetPosition):
            intents = self.plan_from_target_position(decision, current_positions)
            return BacktestStepPlan(decision=decision, execution_intents=intents)
        if isinstance(decision, Signal):
            intents = self.plan_from_signal(decision, current_positions)
            return BacktestStepPlan(decision=decision, execution_intents=intents)
        raise LifecyclePlanningError(f"unsupported strategy decision type: {type(decision).__name__}")

    def plan_from_signal(self, signal: Signal, current_positions: Mapping[str, Decimal]) -> list[ExecutionIntent]:
        if signal.target_qty is None:
            raise LifecyclePlanningError("Phase 5 skeleton only supports signal planning when target_qty is present")

        signed_target_qty = signal.target_qty
        if signal.direction == Direction.SHORT and signed_target_qty > 0:
            signed_target_qty = -signed_target_qty
        elif signal.direction == Direction.FLAT:
            signed_target_qty = Decimal("0")

        return self.plan_from_target_position(
            TargetPosition(
                strategy_code=signal.strategy_code,
                strategy_version=signal.strategy_version,
                target_time=signal.signal_time,
                positions=[
                    TargetPositionItem(
                        exchange_code=signal.exchange_code,
                        unified_symbol=signal.unified_symbol,
                        target_qty=signed_target_qty,
                    )
                ],
                metadata_json={"source_signal_id": signal.signal_id},
            ),
            current_positions,
        )

    def plan_from_target_position(
        self,
        target_position: TargetPosition,
        current_positions: Mapping[str, Decimal],
    ) -> list[ExecutionIntent]:
        intents: list[ExecutionIntent] = []
        execution_policy = self.run_config.session.execution_policy

        for position in target_position.positions:
            if position.exchange_code != self.run_config.session.exchange_code:
                raise LifecyclePlanningError(
                    "target position exchange_code must match session exchange_code in Phase 5 skeleton"
                )
            if position.unified_symbol not in self.run_config.session.universe:
                raise LifecyclePlanningError(
                    "target position unified_symbol must belong to the configured strategy session universe"
                )
            if position.target_qty is None:
                raise LifecyclePlanningError(
                    "Phase 5 skeleton only supports target_qty-based position planning"
                )

            current_qty = Decimal(current_positions.get(position.unified_symbol, Decimal("0")))
            target_qty = position.target_qty
            delta_qty = target_qty - current_qty

            if delta_qty == 0:
                continue

            current_sign = _position_sign(current_qty)
            target_sign = _position_sign(target_qty)
            flips_position = current_sign != 0 and target_sign != 0 and current_sign != target_sign
            if flips_position and not execution_policy.allow_position_flip:
                raise LifecyclePlanningError("position flip requested while allow_position_flip is false")

            reduce_only = self._is_reduce_only(current_qty, target_qty)
            intents.append(
                ExecutionIntent(
                    exchange_code=position.exchange_code,
                    unified_symbol=position.unified_symbol,
                    generated_at=target_position.target_time,
                    current_qty=current_qty,
                    target_qty=target_qty,
                    delta_qty=delta_qty,
                    side=OrderSide.BUY if delta_qty > 0 else OrderSide.SELL,
                    reduce_only=reduce_only and execution_policy.reduce_only_on_exit,
                    metadata_json={
                        "strategy_code": target_position.strategy_code,
                        "strategy_version": target_position.strategy_version,
                        "order_type_preference": execution_policy.order_type_preference,
                    },
                )
            )

        return intents

    @staticmethod
    def _is_reduce_only(current_qty: Decimal, target_qty: Decimal) -> bool:
        current_sign = _position_sign(current_qty)
        target_sign = _position_sign(target_qty)
        if current_sign == 0:
            return False
        if target_sign == 0:
            return True
        return current_sign == target_sign and abs(target_qty) < abs(current_qty)
