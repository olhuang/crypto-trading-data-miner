from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from models.execution import BalanceSnapshot, Fill, OrderRequest, OrderState, PositionSnapshot
from models.market import BarEvent, FundingRateEvent, InstrumentMetadata, OpenInterestEvent, TradeEvent
from storage.repositories.execution import (
    BalanceRepository,
    FillRepository,
    OrderRepository,
    PositionRepository,
)
from storage.repositories.instruments import InstrumentRepository
from storage.repositories.market_data import (
    BarRepository,
    FundingRateRepository,
    OpenInterestRepository,
    TradeRepository,
)


@dataclass(slots=True)
class ValidateAndStoreResult:
    payload_type: str
    model_name: str
    stored: bool
    record_locator: str
    normalized_payload: dict[str, Any]


class UnsupportedPayloadTypeError(ValueError):
    """Raised when the requested payload type is not supported."""


def _store_instrument(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model = InstrumentMetadata.model_validate(payload)
    InstrumentRepository().upsert(connection, model)
    return ValidateAndStoreResult(
        payload_type="instrument_metadata",
        model_name=type(model).__name__,
        stored=True,
        record_locator=f"{model.exchange_code}:{model.venue_symbol}:{model.instrument_type}",
        normalized_payload=model.model_dump(mode="json", by_alias=True),
    )


def _store_bar_event(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model = BarEvent.model_validate(payload)
    BarRepository().upsert(connection, model)
    return ValidateAndStoreResult(
        payload_type="bar_event",
        model_name=type(model).__name__,
        stored=True,
        record_locator=f"{model.exchange_code}:{model.unified_symbol}:{model.bar_time.isoformat()}",
        normalized_payload=model.model_dump(mode="json", by_alias=True),
    )


def _store_trade_event(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model = TradeEvent.model_validate(payload)
    TradeRepository().upsert(connection, model)
    return ValidateAndStoreResult(
        payload_type="trade_event",
        model_name=type(model).__name__,
        stored=True,
        record_locator=f"{model.exchange_code}:{model.unified_symbol}:{model.exchange_trade_id}",
        normalized_payload=model.model_dump(mode="json", by_alias=True),
    )


def _store_funding_rate(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model = FundingRateEvent.model_validate(payload)
    FundingRateRepository().upsert(connection, model)
    return ValidateAndStoreResult(
        payload_type="funding_rate",
        model_name=type(model).__name__,
        stored=True,
        record_locator=f"{model.exchange_code}:{model.unified_symbol}:{model.funding_time.isoformat()}",
        normalized_payload=model.model_dump(mode="json", by_alias=True),
    )


def _store_open_interest(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model = OpenInterestEvent.model_validate(payload)
    OpenInterestRepository().upsert(connection, model)
    return ValidateAndStoreResult(
        payload_type="open_interest",
        model_name=type(model).__name__,
        stored=True,
        record_locator=f"{model.exchange_code}:{model.unified_symbol}:{model.ts.isoformat()}",
        normalized_payload=model.model_dump(mode="json", by_alias=True),
    )


def _store_order_request(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model = OrderRequest.model_validate(payload)
    order_id = OrderRepository().create_from_request(connection, model)
    return ValidateAndStoreResult(
        payload_type="order_request",
        model_name=type(model).__name__,
        stored=True,
        record_locator=f"order_id:{order_id}",
        normalized_payload=model.model_dump(mode="json", by_alias=True),
    )


def _store_order_state(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model = OrderState.model_validate(payload)
    order_id = OrderRepository().upsert_order_state(connection, model)
    return ValidateAndStoreResult(
        payload_type="order_state",
        model_name=type(model).__name__,
        stored=True,
        record_locator=f"order_id:{order_id}",
        normalized_payload=model.model_dump(mode="json", by_alias=True),
    )


def _store_fill(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model = Fill.model_validate(payload)
    fill_id = FillRepository().insert(connection, model)
    return ValidateAndStoreResult(
        payload_type="fill",
        model_name=type(model).__name__,
        stored=True,
        record_locator=f"fill_id:{fill_id}",
        normalized_payload=model.model_dump(mode="json", by_alias=True),
    )


def _store_position_snapshot(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model = PositionSnapshot.model_validate(payload)
    repo = PositionRepository()
    repo.upsert_current(connection, model)
    repo.insert_snapshot(connection, model)
    return ValidateAndStoreResult(
        payload_type="position_snapshot",
        model_name=type(model).__name__,
        stored=True,
        record_locator=(
            f"{model.account_code}:{model.exchange_code}:{model.unified_symbol}:{model.snapshot_time.isoformat()}"
        ),
        normalized_payload=model.model_dump(mode="json", by_alias=True),
    )


def _store_balance_snapshot(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model = BalanceSnapshot.model_validate(payload)
    BalanceRepository().upsert_snapshot(connection, model)
    return ValidateAndStoreResult(
        payload_type="balance_snapshot",
        model_name=type(model).__name__,
        stored=True,
        record_locator=f"{model.account_code}:{model.asset}:{model.snapshot_time.isoformat()}",
        normalized_payload=model.model_dump(mode="json", by_alias=True),
    )


STORE_HANDLERS = {
    "instrument_metadata": _store_instrument,
    "bar_event": _store_bar_event,
    "trade_event": _store_trade_event,
    "funding_rate": _store_funding_rate,
    "open_interest": _store_open_interest,
    "order_request": _store_order_request,
    "order_state": _store_order_state,
    "fill": _store_fill,
    "position_snapshot": _store_position_snapshot,
    "balance_snapshot": _store_balance_snapshot,
}


def supported_payload_types() -> list[str]:
    return sorted(STORE_HANDLERS)


def validate_and_store(connection, payload_type: str, payload: dict[str, Any]) -> ValidateAndStoreResult:
    try:
        handler = STORE_HANDLERS[payload_type]
    except KeyError as exc:
        raise UnsupportedPayloadTypeError(f"unsupported payload_type: {payload_type}") from exc
    return handler(connection, payload)
