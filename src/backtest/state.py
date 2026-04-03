from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from models.common import OrderSide

from .fills import SimulatedFill


@dataclass(slots=True)
class PortfolioState:
    cash: Decimal
    positions: dict[str, Decimal] = field(default_factory=dict)

    def position_qty(self, unified_symbol: str) -> Decimal:
        return self.positions.get(unified_symbol, Decimal("0"))

    def apply_fill(self, fill: SimulatedFill) -> None:
        current_qty = self.positions.get(fill.unified_symbol, Decimal("0"))
        signed_qty = fill.qty if fill.side == OrderSide.BUY else -fill.qty
        new_qty = current_qty + signed_qty
        if new_qty == 0:
            self.positions.pop(fill.unified_symbol, None)
        else:
            self.positions[fill.unified_symbol] = new_qty

        notional = fill.fill_price * fill.qty
        if fill.side == OrderSide.BUY:
            self.cash -= notional + fill.fee
        else:
            self.cash += notional - fill.fee
