from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Mapping, Sequence

from models.backtest import BacktestRunConfig
from models.common import LiquidityFlag, OrderStatus, OrderSide, OrderType, RiskDecision
from models.market import BarEvent
from sqlalchemy.engine import Connection

from .fills import FeeModel, SimulatedOrder, SlippageModel
from .lifecycle import ExecutionIntent
from .state import PortfolioMark, PortfolioState


@dataclass(slots=True)
class RiskGuardrailOutcome:
    decision: RiskDecision
    code: str
    message: str
    evaluated_at: datetime
    unified_symbol: str
    current_qty: Decimal
    target_qty: Decimal
    delta_qty: Decimal
    estimated_notional: Decimal | None = None
    details_json: dict[str, object] = field(default_factory=dict)


class BacktestRiskGuardrailEngine:
    def __init__(
        self,
        run_config: BacktestRunConfig,
        *,
        fee_model: FeeModel,
        slippage_model: SlippageModel,
    ) -> None:
        self.run_config = run_config
        self.policy = run_config.session.risk_policy
        self.fee_model = fee_model
        self.slippage_model = slippage_model

    def filter_execution_intents(
        self,
        intents: Sequence[ExecutionIntent],
        *,
        current_bar: BarEvent,
        portfolio: PortfolioState,
        latest_mark_prices: Mapping[str, Decimal],
        connection: Connection | None = None,
    ) -> tuple[list[ExecutionIntent], list[RiskGuardrailOutcome]]:
        marks = dict(latest_mark_prices)
        marks[current_bar.unified_symbol] = current_bar.close
        portfolio_mark = portfolio.mark_to_market(marks)

        allowed_intents: list[ExecutionIntent] = []
        outcomes: list[RiskGuardrailOutcome] = []
        for intent in intents:
            outcome = self.evaluate_intent(
                intent,
                current_bar=current_bar,
                portfolio=portfolio,
                portfolio_mark=portfolio_mark,
                mark_prices=marks,
                connection=connection,
            )
            outcomes.append(outcome)
            if outcome.decision == RiskDecision.ALLOW:
                allowed_intents.append(intent)
        return allowed_intents, outcomes

    def evaluate_intent(
        self,
        intent: ExecutionIntent,
        *,
        current_bar: BarEvent,
        portfolio: PortfolioState,
        portfolio_mark: PortfolioMark,
        mark_prices: Mapping[str, Decimal],
        connection: Connection | None = None,
    ) -> RiskGuardrailOutcome:
        estimated_notional = abs(intent.delta_qty) * current_bar.close
        violation = self._detect_violation(
            intent,
            current_bar=current_bar,
            portfolio=portfolio,
            portfolio_mark=portfolio_mark,
            mark_prices=mark_prices,
            estimated_notional=estimated_notional,
            connection=connection,
        )
        if violation is None:
            return self._allow_outcome(
                intent,
                code="allowed",
                message="execution intent passed backtest risk guardrails",
                estimated_notional=estimated_notional,
            )

        if self._can_bypass_violation(intent):
            return self._allow_outcome(
                intent,
                code="allowed_reduce_only_bypass",
                message="reduce-only intent was allowed despite a breached guardrail",
                estimated_notional=estimated_notional,
                details_json={"bypassed_rule": violation.code, **violation.details_json},
            )

        return RiskGuardrailOutcome(
            decision=RiskDecision.BLOCK,
            code=violation.code,
            message=violation.message,
            evaluated_at=intent.generated_at,
            unified_symbol=intent.unified_symbol,
            current_qty=intent.current_qty,
            target_qty=intent.target_qty,
            delta_qty=intent.delta_qty,
            estimated_notional=estimated_notional,
            details_json=violation.details_json,
        )

    def _detect_violation(
        self,
        intent: ExecutionIntent,
        *,
        current_bar: BarEvent,
        portfolio: PortfolioState,
        portfolio_mark: PortfolioMark,
        mark_prices: Mapping[str, Decimal],
        estimated_notional: Decimal,
        connection: Connection | None,
    ) -> RiskGuardrailOutcome | None:
        if self._would_expand_exposure(intent):
            equity_floor = self.policy.block_new_entries_below_equity
            if equity_floor is not None and portfolio_mark.equity <= equity_floor:
                return self._block_outcome(
                    intent,
                    code="equity_floor_breach",
                    message="new exposure is blocked because current equity is at or below the configured floor",
                    estimated_notional=estimated_notional,
                    details_json={
                        "equity": str(portfolio_mark.equity),
                        "equity_floor": str(equity_floor),
                    },
                )

        if self.policy.enforce_spot_cash_check and self._requires_spot_cash(intent):
            required_cash = self._estimate_spot_cash_requirement(
                intent,
                current_bar=current_bar,
                connection=connection,
            )
            if required_cash is not None and portfolio.cash < required_cash:
                return self._block_outcome(
                    intent,
                    code="spot_cash_insufficient",
                    message="spot entry is blocked because estimated cash is insufficient for notional plus fees",
                    estimated_notional=estimated_notional,
                    details_json={
                        "cash": str(portfolio.cash),
                        "required_cash": str(required_cash),
                    },
                )

        max_order_qty = self.policy.max_order_qty
        if max_order_qty is not None and abs(intent.delta_qty) > max_order_qty:
            return self._block_outcome(
                intent,
                code="max_order_qty_breach",
                message="execution intent exceeds configured max_order_qty",
                estimated_notional=estimated_notional,
                details_json={
                    "delta_qty": str(abs(intent.delta_qty)),
                    "max_order_qty": str(max_order_qty),
                },
            )

        max_order_notional = self.policy.max_order_notional
        if max_order_notional is not None and estimated_notional > max_order_notional:
            return self._block_outcome(
                intent,
                code="max_order_notional_breach",
                message="execution intent exceeds configured max_order_notional",
                estimated_notional=estimated_notional,
                details_json={
                    "estimated_notional": str(estimated_notional),
                    "max_order_notional": str(max_order_notional),
                },
            )

        max_position_qty = self.policy.max_position_qty
        if max_position_qty is not None and abs(intent.target_qty) > max_position_qty:
            return self._block_outcome(
                intent,
                code="max_position_qty_breach",
                message="resulting target position exceeds configured max_position_qty",
                estimated_notional=estimated_notional,
                details_json={
                    "target_qty": str(abs(intent.target_qty)),
                    "max_position_qty": str(max_position_qty),
                },
            )

        max_gross_multiple = self.policy.max_gross_exposure_multiple
        if max_gross_multiple is not None:
            allowed_gross = max(portfolio_mark.equity, Decimal("0")) * max_gross_multiple
            resulting_gross = self._estimate_resulting_gross_exposure(
                intent,
                portfolio=portfolio,
                mark_prices=mark_prices,
            )
            if resulting_gross > allowed_gross:
                return self._block_outcome(
                    intent,
                    code="max_gross_exposure_breach",
                    message="resulting gross exposure exceeds configured max_gross_exposure_multiple",
                    estimated_notional=estimated_notional,
                    details_json={
                        "resulting_gross_exposure": str(resulting_gross),
                        "allowed_gross_exposure": str(allowed_gross),
                        "equity": str(portfolio_mark.equity),
                        "max_gross_exposure_multiple": str(max_gross_multiple),
                    },
                )

        return None

    def _estimate_resulting_gross_exposure(
        self,
        intent: ExecutionIntent,
        *,
        portfolio: PortfolioState,
        mark_prices: Mapping[str, Decimal],
    ) -> Decimal:
        gross_exposure = Decimal("0")
        symbols = set(portfolio.position_states) | {intent.unified_symbol}
        for symbol in symbols:
            qty = intent.target_qty if symbol == intent.unified_symbol else portfolio.position_qty(symbol)
            if qty == 0:
                continue
            price = mark_prices.get(symbol)
            if price is None:
                position_state = portfolio.position_states.get(symbol)
                price = position_state.average_entry_price if position_state is not None else Decimal("0")
            gross_exposure += abs(qty * price)
        return gross_exposure

    def _estimate_spot_cash_requirement(
        self,
        intent: ExecutionIntent,
        *,
        current_bar: BarEvent,
        connection: Connection | None,
    ) -> Decimal | None:
        qty = abs(intent.delta_qty)
        if qty == 0:
            return Decimal("0")

        provisional_order = SimulatedOrder(
            order_id="risk_probe",
            signal_id=None,
            exchange_code=intent.exchange_code,
            unified_symbol=intent.unified_symbol,
            order_time=intent.generated_at,
            side=intent.side,
            order_type=intent.order_type,
            requested_price=intent.limit_price,
            qty=qty,
            reduce_only=intent.reduce_only,
            status=OrderStatus.NEW,
        )
        reference_price = provisional_order.requested_price or current_bar.close
        fill_price, _ = self.slippage_model.apply(order=provisional_order, reference_price=reference_price)
        liquidity_flag = (
            LiquidityFlag.MAKER
            if provisional_order.order_type in {OrderType.LIMIT, OrderType.LIMIT.value}
            else LiquidityFlag.TAKER
        )
        fee = Decimal("0")
        try:
            fee = self.fee_model.compute_fee(
                connection=connection,
                order=provisional_order,
                fill_time=current_bar.bar_time,
                fill_price=fill_price,
                qty=qty,
                liquidity_flag=liquidity_flag,
            )
        except Exception:
            fee = Decimal("0")
        return (fill_price * qty) + fee

    @staticmethod
    def _requires_spot_cash(intent: ExecutionIntent) -> bool:
        return (
            intent.unified_symbol.endswith("_SPOT")
            and intent.side in {OrderSide.BUY, OrderSide.BUY.value}
            and not intent.reduce_only
        )

    def _can_bypass_violation(self, intent: ExecutionIntent) -> bool:
        return bool(
            self.policy.allow_reduce_only_when_blocked
            and intent.reduce_only
            and abs(intent.target_qty) <= abs(intent.current_qty)
        )

    @staticmethod
    def _would_expand_exposure(intent: ExecutionIntent) -> bool:
        if intent.current_qty == 0:
            return intent.target_qty != 0
        if intent.current_qty > 0 and intent.target_qty < 0:
            return True
        if intent.current_qty < 0 and intent.target_qty > 0:
            return True
        if intent.current_qty > 0 and intent.target_qty > 0 and abs(intent.target_qty) > abs(intent.current_qty):
            return True
        if intent.current_qty < 0 and intent.target_qty < 0 and abs(intent.target_qty) > abs(intent.current_qty):
            return True
        return False

    @staticmethod
    def _allow_outcome(
        intent: ExecutionIntent,
        *,
        code: str,
        message: str,
        estimated_notional: Decimal,
        details_json: dict[str, object] | None = None,
    ) -> RiskGuardrailOutcome:
        return RiskGuardrailOutcome(
            decision=RiskDecision.ALLOW,
            code=code,
            message=message,
            evaluated_at=intent.generated_at,
            unified_symbol=intent.unified_symbol,
            current_qty=intent.current_qty,
            target_qty=intent.target_qty,
            delta_qty=intent.delta_qty,
            estimated_notional=estimated_notional,
            details_json=details_json or {},
        )

    @staticmethod
    def _block_outcome(
        intent: ExecutionIntent,
        *,
        code: str,
        message: str,
        estimated_notional: Decimal,
        details_json: dict[str, object] | None = None,
    ) -> RiskGuardrailOutcome:
        return RiskGuardrailOutcome(
            decision=RiskDecision.BLOCK,
            code=code,
            message=message,
            evaluated_at=intent.generated_at,
            unified_symbol=intent.unified_symbol,
            current_qty=intent.current_qty,
            target_qty=intent.target_qty,
            delta_qty=intent.delta_qty,
            estimated_notional=estimated_notional,
            details_json=details_json or {},
        )
