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
    ingest_time: datetime | None = None
    funding_time: datetime
    funding_rate: Decimal
    mark_price: Decimal | None = None
    index_price: Decimal | None = None


class OpenInterestEvent(MarketEventBase):
    ingest_time: datetime
    event_time: datetime = Field(validation_alias="ts", serialization_alias="event_time")
    open_interest: Decimal


class OrderBookSnapshotEvent(MarketEventBase):
    ingest_time: datetime
    snapshot_time: datetime
    depth_levels: int
    bids: list[tuple[Decimal, Decimal]]
    asks: list[tuple[Decimal, Decimal]]
    checksum: str | None = None
    source: str | None = None


class OrderBookDeltaEvent(MarketEventBase):
    ingest_time: datetime
    event_time: datetime
    first_update_id: int | None = None
    final_update_id: int | None = None
    bids: list[tuple[Decimal, Decimal]] = Field(default_factory=list)
    asks: list[tuple[Decimal, Decimal]] = Field(default_factory=list)
    checksum: str | None = None
    source: str | None = None


class MarkPriceEvent(MarketEventBase):
    ingest_time: datetime
    event_time: datetime = Field(validation_alias="ts", serialization_alias="event_time")
    mark_price: Decimal
    funding_basis_bps: Decimal | None = None


class IndexPriceEvent(MarketEventBase):
    ingest_time: datetime
    event_time: datetime = Field(validation_alias="ts", serialization_alias="event_time")
    index_price: Decimal


class LiquidationEvent(MarketEventBase):
    ingest_time: datetime
    event_time: datetime
    side: str | None = None
    price: Decimal | None = None
    qty: Decimal | None = None
    notional: Decimal | None = None
    source: str | None = None
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="metadata",
        serialization_alias="metadata_json",
    )


class RawMarketEvent(BaseContractModel):
    exchange_code: str
    unified_symbol: str | None = None
    channel: str
    event_type: str | None = None
    event_time: datetime | None = None
    ingest_time: datetime
    source_message_id: str | None = None
    payload_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="raw_payload",
        serialization_alias="payload_json",
    )
