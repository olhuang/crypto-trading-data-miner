from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field, model_validator

from .common import BaseContractModel, InstrumentType, MarketEventBase


class InstrumentMetadata(BaseContractModel):
    exchange_code: str
    venue_symbol: str
    unified_symbol: str
    instrument_type: InstrumentType
    base_asset: str
    quote_asset: str
    settlement_asset: str | None = None
    tick_size: Decimal | None = None
    lot_size: Decimal | None = None
    min_qty: Decimal | None = None
    min_notional: Decimal | None = None
    contract_size: Decimal | None = None
    status: str
    launch_time: datetime | None = None
    delist_time: datetime | None = None
    payload_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="raw_payload",
        serialization_alias="payload_json",
    )

    @model_validator(mode="after")
    def validate_contract_semantics(self) -> "InstrumentMetadata":
        if self.instrument_type == InstrumentType.SPOT and self.contract_size is not None:
            raise ValueError("spot instruments should not set contract_size")
        return self


class BarEvent(MarketEventBase):
    ingest_time: datetime
    bar_interval: str
    bar_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    quote_volume: Decimal | None = None
    trade_count: int | None = None
    event_time: datetime


class TradeEvent(MarketEventBase):
    ingest_time: datetime
    exchange_trade_id: str
    event_time: datetime
    price: Decimal
    qty: Decimal
    aggressor_side: str | None = None


class FundingRateEvent(MarketEventBase):
    funding_time: datetime
    funding_rate: Decimal
    mark_price: Decimal | None = None
    index_price: Decimal | None = None


class OpenInterestEvent(MarketEventBase):
    ingest_time: datetime
    event_time: datetime = Field(validation_alias="ts", serialization_alias="event_time")
    open_interest: Decimal
