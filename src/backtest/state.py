from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping

from models.common import OrderSide

from .fills import SimulatedFill


@dataclass(slots=True)
class PositionState:
    qty: Decimal = Decimal("0")
    average_entry_price: Decimal | None = None

    @property
    def is_flat(self) -> bool:
        return self.qty == 0


@dataclass(slots=True)
class PortfolioMark:
    cash: Decimal
    equity: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    fee_cost: Decimal
    slippage_cost: Decimal
    turnover_notional: Decimal
    close_event_count: int
    winning_close_count: int


@dataclass(slots=True)
class FillApplicationOutcome:
    realized_delta: Decimal = Decimal("0")
    close_event: bool = False
    winning_close: bool = False


@dataclass(slots=True)
class PortfolioState:
    cash: Decimal
    position_states: dict[str, PositionState] = field(default_factory=dict)
    realized_pnl: Decimal = Decimal("0")
    fee_cost: Decimal = Decimal("0")
    slippage_cost: Decimal = Decimal("0")
    turnover_notional: Decimal = Decimal("0")
    close_event_count: int = 0
    winning_close_count: int = 0

    def position_qty(self, unified_symbol: str) -> Decimal:
        return self.position_states.get(unified_symbol, PositionState()).qty

    @property
    def positions(self) -> dict[str, Decimal]:
        d = {}
        for symbol, position in self.position_states.items():
            if position.qty != 0:
                d[symbol] = position.qty
        return d

    def apply_fill(self, fill: SimulatedFill) -> FillApplicationOutcome:
        signed_qty = fill.qty if fill.side == OrderSide.BUY else -fill.qty
        position = self.position_states.setdefault(fill.unified_symbol, PositionState())
        current_qty = position.qty
        current_entry = position.average_entry_price

        notional = fill.fill_price * fill.qty
        if fill.side == OrderSide.BUY:
            self.cash -= notional + fill.fee
        else:
            self.cash += notional - fill.fee

        self.fee_cost += fill.fee
        self.slippage_cost += fill.slippage_cost
        self.turnover_notional += notional

        realized_delta = Decimal("0")
        if current_qty == 0:
            position.qty = signed_qty
            position.average_entry_price = fill.fill_price
            return FillApplicationOutcome()

        if current_qty > 0 and signed_qty > 0:
            total_qty = current_qty + signed_qty
            assert current_entry is not None
            position.average_entry_price = (
                (current_entry * current_qty) + (fill.fill_price * signed_qty)
            ) / total_qty
            position.qty = total_qty
            return FillApplicationOutcome()

        if current_qty < 0 and signed_qty < 0:
            total_abs_qty = abs(current_qty) + abs(signed_qty)
            assert current_entry is not None
            position.average_entry_price = (
                (current_entry * abs(current_qty)) + (fill.fill_price * abs(signed_qty))
            ) / total_abs_qty
            position.qty = current_qty + signed_qty
            return FillApplicationOutcome()

        closing_qty = min(abs(current_qty), abs(signed_qty))
        assert current_entry is not None
        if current_qty > 0:
            realized_delta = (fill.fill_price - current_entry) * closing_qty
        else:
            realized_delta = (current_entry - fill.fill_price) * closing_qty

        self.realized_pnl += realized_delta
        self.close_event_count += 1
        winning_close = realized_delta > 0
        if realized_delta > 0:
            self.winning_close_count += 1

        new_qty = current_qty + signed_qty
        if new_qty == 0:
            self.position_states.pop(fill.unified_symbol, None)
            return FillApplicationOutcome(
                realized_delta=realized_delta,
                close_event=True,
                winning_close=winning_close,
            )

        position.qty = new_qty
        if (current_qty > 0 and new_qty > 0) or (current_qty < 0 and new_qty < 0):
            position.average_entry_price = current_entry
        else:
            position.average_entry_price = fill.fill_price
        return FillApplicationOutcome(
            realized_delta=realized_delta,
            close_event=True,
            winning_close=winning_close,
        )

    def calculate_equity(self, mark_prices: Mapping[str, Decimal]) -> Decimal:
        net_exposure = Decimal("0")
        for symbol, position in self.position_states.items():
            if position.is_flat:
                continue
            mark_price = mark_prices.get(symbol)
            if mark_price is None:
                mark_price = position.average_entry_price or Decimal("0")
            net_exposure += position.qty * mark_price
        return self.cash + net_exposure

    def mark_to_market(self, mark_prices: Mapping[str, Decimal]) -> PortfolioMark:
        gross_exposure = Decimal("0")
        net_exposure = Decimal("0")
        unrealized_pnl = Decimal("0")

        for symbol, position in self.position_states.items():
            if position.is_flat:
                continue
            mark_price = mark_prices.get(symbol)
            if mark_price is None:
                mark_price = position.average_entry_price or Decimal("0")

            signed_notional = position.qty * mark_price
            gross_exposure += abs(signed_notional)
            net_exposure += signed_notional

            if position.average_entry_price is not None:
                if position.qty > 0:
                    unrealized_pnl += (mark_price - position.average_entry_price) * position.qty
                else:
                    unrealized_pnl += (position.average_entry_price - mark_price) * abs(position.qty)

        equity = self.cash + net_exposure
        return PortfolioMark(
            cash=self.cash,
            equity=equity,
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
            realized_pnl=self.realized_pnl,
            unrealized_pnl=unrealized_pnl,
            fee_cost=self.fee_cost,
            slippage_cost=self.slippage_cost,
            turnover_notional=self.turnover_notional,
            close_event_count=self.close_event_count,
            winning_close_count=self.winning_close_count,
        )
