from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(slots=True)
class BacktestDebugTraceRecord:
    step_index: int
    bar_time: datetime
    exchange_code: str
    unified_symbol: str
    close_price: Decimal
    current_position_qty: Decimal
    position_qty_delta: Decimal
    signal_count: int
    intent_count: int
    blocked_intent_count: int
    blocked_codes: list[str]
    created_order_count: int
    created_order_ids: list[str]
    fill_count: int
    fill_ids: list[str]
    cash: Decimal
    cash_delta: Decimal
    equity: Decimal
    equity_delta: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    drawdown: Decimal
    decision_json: dict[str, Any]
    risk_outcomes_json: list[dict[str, Any]]
