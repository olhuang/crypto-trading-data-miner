from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo

from models.backtest import BacktestRunConfig
from models.common import LiquidityFlag, OrderStatus, OrderSide, OrderType, RiskDecision
from models.market import BarEvent
from sqlalchemy.engine import Connection

from .fills import FeeModel, SimulatedOrder, SlippageModel
from .lifecycle import ExecutionIntent
from .state import FillApplicationOutcome, PortfolioMark, PortfolioState


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


@dataclass(slots=True)
class RiskGuardrailSessionState:
    peak_equity: Decimal | None = None
    last_equity: Decimal | None = None
    active_trading_day: str | None = None
    daily_start_equity: Decimal | None = None
    cooldown_bars_remaining: int = 0
    activation_counts_by_code: dict[str, int] = field(default_factory=dict)


class BacktestRiskGuardrailEngine:
    def __init__(
        self,
        run_config: BacktestRunConfig,
        *,
        fee_model: FeeModel,
        slippage_model: SlippageModel,
    ) -> None:
        self.run_config = run_config
        self.policy = run_config.build_effective_risk_policy()
        self.fee_model = fee_model
        self.slippage_model = slippage_model
        self.session_state = RiskGuardrailSessionState()
        self.trading_timezone = run_config.session.trading_timezone
        self._trading_tz = ZoneInfo(self.trading_timezone)

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
        self._refresh_session_state(current_bar=current_bar, current_equity=portfolio_mark.equity)

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

    def observe_fill_application(
        self,
        *,
        fill_outcome: FillApplicationOutcome,
    ) -> None:
        cooldown_bars = self.policy.cooldown_bars_after_stop
        if cooldown_bars is None:
            return
        if not fill_outcome.close_event or fill_outcome.realized_delta >= 0:
            return
        self.session_state.cooldown_bars_remaining = max(
            self.session_state.cooldown_bars_remaining,
            cooldown_bars,
        )
        self._record_activation("cooldown_activated_after_loss_close")

    def complete_bar(self) -> None:
        if self.session_state.cooldown_bars_remaining > 0:
            self.session_state.cooldown_bars_remaining -= 1

    def build_runtime_state_snapshot(self) -> dict[str, object]:
        snapshot: dict[str, object] = {
            "policy_code": self.policy.policy_code,
            "trading_timezone": self.trading_timezone,
            "active_trading_day": self.session_state.active_trading_day,
            "cooldown_bars_remaining": self.session_state.cooldown_bars_remaining,
            "activation_counts_by_code": dict(self.session_state.activation_counts_by_code),
        }
        if self.session_state.peak_equity is not None:
            snapshot["peak_equity"] = str(self.session_state.peak_equity)
        if self.session_state.daily_start_equity is not None:
            snapshot["daily_start_equity"] = str(self.session_state.daily_start_equity)
        current_drawdown_pct = self._current_drawdown_pct()
        if current_drawdown_pct is not None:
            snapshot["current_drawdown_pct"] = str(current_drawdown_pct)
        current_daily_loss_pct = self._current_daily_loss_pct()
        if current_daily_loss_pct is not None:
            snapshot["current_daily_loss_pct"] = str(current_daily_loss_pct)
        return snapshot

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
        if self._would_expand_exposure(intent) and self.session_state.cooldown_bars_remaining > 0:
            return self._block_outcome(
                intent,
                code="cooldown_active",
                message="new exposure is blocked because cooldown is active after a recent loss-close event",
                estimated_notional=estimated_notional,
                details_json={
                    "cooldown_bars_remaining": self.session_state.cooldown_bars_remaining,
                },
            )

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
            max_drawdown_pct = self.policy.max_drawdown_pct
            current_drawdown_pct = self._current_drawdown_pct()
            if (
                max_drawdown_pct is not None
                and current_drawdown_pct is not None
                and current_drawdown_pct >= max_drawdown_pct
            ):
                return self._block_outcome(
                    intent,
                    code="max_drawdown_pct_breach",
                    message="new exposure is blocked because current drawdown is at or above the configured maximum",
                    estimated_notional=estimated_notional,
                    details_json={
                        "current_drawdown_pct": str(current_drawdown_pct),
                        "max_drawdown_pct": str(max_drawdown_pct),
                        "peak_equity": (
                            str(self.session_state.peak_equity)
                            if self.session_state.peak_equity is not None
                            else None
                        ),
                        "equity": str(portfolio_mark.equity),
                    },
                )
            max_daily_loss_pct = self.policy.max_daily_loss_pct
            current_daily_loss_pct = self._current_daily_loss_pct()
            if (
                max_daily_loss_pct is not None
                and current_daily_loss_pct is not None
                and current_daily_loss_pct >= max_daily_loss_pct
            ):
                return self._block_outcome(
                    intent,
                    code="max_daily_loss_pct_breach",
                    message="new exposure is blocked because the configured daily loss limit has been breached",
                    estimated_notional=estimated_notional,
                    details_json={
                        "current_daily_loss_pct": str(current_daily_loss_pct),
                        "max_daily_loss_pct": str(max_daily_loss_pct),
                        "daily_start_equity": (
                            str(self.session_state.daily_start_equity)
                            if self.session_state.daily_start_equity is not None
                            else None
                        ),
                        "trading_timezone": self.trading_timezone,
                        "active_trading_day": self.session_state.active_trading_day,
                        "equity": str(portfolio_mark.equity),
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

        max_leverage = self.policy.max_leverage
        if max_leverage is not None and self._would_expand_exposure(intent):
            resulting_gross = self._estimate_resulting_gross_exposure(
                intent,
                portfolio=portfolio,
                mark_prices=mark_prices,
            )
            equity = portfolio_mark.equity
            if equity <= 0 and resulting_gross > 0:
                return self._block_outcome(
                    intent,
                    code="max_leverage_breach",
                    message="resulting leverage exceeds configured max_leverage because current equity is non-positive",
                    estimated_notional=estimated_notional,
                    details_json={
                        "resulting_gross_exposure": str(resulting_gross),
                        "equity": str(equity),
                        "max_leverage": str(max_leverage),
                    },
                )
            if equity > 0 and resulting_gross > 0:
                resulting_leverage = resulting_gross / equity
                if resulting_leverage > max_leverage:
                    return self._block_outcome(
                        intent,
                        code="max_leverage_breach",
                        message="resulting leverage exceeds configured max_leverage",
                        estimated_notional=estimated_notional,
                        details_json={
                            "resulting_gross_exposure": str(resulting_gross),
                            "equity": str(equity),
                            "resulting_leverage": str(resulting_leverage),
                            "max_leverage": str(max_leverage),
                        },
                    )

        return None

    def _refresh_session_state(self, *, current_bar: BarEvent, current_equity: Decimal) -> None:
        active_trading_day = current_bar.bar_time.astimezone(self._trading_tz).date().isoformat()
        if self.session_state.active_trading_day != active_trading_day:
            self.session_state.active_trading_day = active_trading_day
            self.session_state.daily_start_equity = current_equity

        if self.session_state.peak_equity is None:
            self.session_state.peak_equity = current_equity
        else:
            self.session_state.peak_equity = max(self.session_state.peak_equity, current_equity)

        self.session_state.last_equity = current_equity

    def _current_drawdown_pct(self) -> Decimal | None:
        peak_equity = self.session_state.peak_equity
        current_equity = self.session_state.last_equity
        if peak_equity is None or current_equity is None:
            return None
        if peak_equity <= 0:
            return None
        return (peak_equity - current_equity) / peak_equity

    def _current_daily_loss_pct(self) -> Decimal | None:
        daily_start_equity = self.session_state.daily_start_equity
        current_equity = self.session_state.last_equity
        if daily_start_equity is None or current_equity is None:
            return None
        if daily_start_equity <= 0:
            return None
        loss = daily_start_equity - current_equity
        if loss <= 0:
            return Decimal("0")
        return loss / daily_start_equity

    def _record_activation(self, code: str) -> None:
        counts = self.session_state.activation_counts_by_code
        counts[code] = counts.get(code, 0) + 1

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
