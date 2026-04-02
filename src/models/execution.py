from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field, model_validator

from .common import (
    BaseContractModel,
    Environment,
    LiquidityFlag,
    OrderSide,
    OrderStatus,
    OrderType,
    TimeInForce,
)


class OrderRequest(BaseContractModel):
    environment: Environment
    account_code: str
    strategy_code: str | None = None
    strategy_version: str | None = None
    signal_id: str | None = None
    exchange_code: str
    unified_symbol: str
    client_order_id: str
    side: OrderSide
    order_type: OrderType
    time_in_force: TimeInForce | None = None
    price: Decimal | None = None
    qty: Decimal
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="metadata",
        serialization_alias="metadata_json",
    )

    @model_validator(mode="after")
    def validate_price_rules(self) -> "OrderRequest":
        priced_order_types = {
            OrderType.LIMIT,
            OrderType.POST_ONLY,
            OrderType.STOP,
            OrderType.TAKE_PROFIT,
        }
        if self.order_type in priced_order_types and self.price is None:
            raise ValueError("price is required for priced order types")
        return self


class OrderState(BaseContractModel):
    order_id: str
    environment: Environment
    account_code: str
    strategy_code: str | None = None
    strategy_version: str | None = None
    signal_id: str | None = None
    exchange_code: str
    unified_symbol: str
    client_order_id: str | None = None
    exchange_order_id: str | None = None
    side: OrderSide
    order_type: OrderType
    time_in_force: TimeInForce | None = None
    price: Decimal | None = None
    qty: Decimal
    status: OrderStatus
    event_time: datetime | None = None
    submit_time: datetime | None = None
    ack_time: datetime | None = None
    cancel_time: datetime | None = None
    reject_reason: str | None = None
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="metadata",
        serialization_alias="metadata_json",
    )


class OrderEvent(BaseContractModel):
    order_id: str
    client_order_id: str | None = None
    exchange_order_id: str | None = None
    event_type: str
    event_time: datetime
    status_before: str | None = None
    status_after: str | None = None
    reason_code: str | None = None
    detail_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="detail",
        serialization_alias="detail_json",
    )


class Fill(BaseContractModel):
    fill_id: str | None = None
    order_id: str
    exchange_trade_id: str | None = None
    exchange_code: str
    unified_symbol: str
    fill_time: datetime
    price: Decimal
    qty: Decimal
    notional: Decimal | None = None
    fee: Decimal | None = None
    fee_asset: str | None = None
    liquidity_flag: LiquidityFlag = LiquidityFlag.UNKNOWN
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="metadata",
        serialization_alias="metadata_json",
    )


class PositionSnapshot(BaseContractModel):
    environment: Environment
    account_code: str
    exchange_code: str
    unified_symbol: str
    snapshot_time: datetime
    position_qty: Decimal
    avg_entry_price: Decimal | None = None
    mark_price: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    realized_pnl: Decimal | None = None


class BalanceSnapshot(BaseContractModel):
    environment: Environment
    account_code: str
    asset: str
    snapshot_time: datetime
    wallet_balance: Decimal
    available_balance: Decimal
    margin_balance: Decimal | None = None
    equity: Decimal | None = None
