from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Environment(StrEnum):
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


class InstrumentType(StrEnum):
    SPOT = "spot"
    PERP = "perp"
    FUTURE = "future"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_MARKET = "stop_market"
    TAKE_PROFIT = "take_profit"
    POST_ONLY = "post_only"


class TimeInForce(StrEnum):
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    POST_ONLY = "post_only"


class ExecutionInstruction(StrEnum):
    POST_ONLY = "post_only"
    REDUCE_ONLY = "reduce_only"
    CLOSE_POSITION = "close_position"


class OrderStatus(StrEnum):
    NEW = "new"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class LiquidityFlag(StrEnum):
    MAKER = "maker"
    TAKER = "taker"
    UNKNOWN = "unknown"


class SignalType(StrEnum):
    ENTRY = "entry"
    EXIT = "exit"
    REDUCE = "reduce"
    REVERSE = "reverse"
    REBALANCE = "rebalance"


class Direction(StrEnum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class LedgerType(StrEnum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRADE_FEE = "trade_fee"
    FUNDING_PAYMENT = "funding_payment"
    FUNDING_RECEIPT = "funding_receipt"
    REALIZED_PNL = "realized_pnl"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    REBATE = "rebate"
    ADJUSTMENT = "adjustment"


class BaseContractModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    @field_validator("*", mode="before")
    @classmethod
    def normalize_datetimes(cls, value: Any) -> Any:
        if not isinstance(value, datetime):
            return value

        if value.tzinfo is None:
            raise ValueError("datetime values must be timezone-aware UTC timestamps")

        return value.astimezone(timezone.utc)


class MarketEventBase(BaseContractModel):
    exchange_code: str
    unified_symbol: str
    ingest_time: datetime | None = None
    payload_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="raw_payload",
        serialization_alias="payload_json",
    )


DecimalLike = Decimal | str | int | float
