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


MODEL_TYPES = {
    "instrument_metadata": InstrumentMetadata,
    "bar_event": BarEvent,
    "trade_event": TradeEvent,
    "funding_rate": FundingRateEvent,
    "open_interest": OpenInterestEvent,
    "order_request": OrderRequest,
    "order_state": OrderState,
    "fill": Fill,
    "position_snapshot": PositionSnapshot,
    "balance_snapshot": BalanceSnapshot,
}


def validate_payload(payload_type: str, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    try:
        model_type = MODEL_TYPES[payload_type]
    except KeyError as exc:
        raise UnsupportedPayloadTypeError(f"unsupported payload_type: {payload_type}") from exc

    model = model_type.model_validate(payload)
    return type(model).__name__, model.model_dump(mode="json", by_alias=True)


def _store_instrument(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("instrument_metadata", payload)
    model = InstrumentMetadata.model_validate(payload)
    InstrumentRepository().upsert(connection, model)
    return ValidateAndStoreResult(
        payload_type="instrument_metadata",
        model_name=model_name,
        stored=True,
        record_locator=f"{model.exchange_code}:{model.venue_symbol}:{model.instrument_type}",
        normalized_payload=normalized_payload,
    )


def _store_bar_event(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("bar_event", payload)
    model = BarEvent.model_validate(payload)
    BarRepository().upsert(connection, model)
    return ValidateAndStoreResult(
        payload_type="bar_event",
        model_name=model_name,
        stored=True,
        record_locator=f"{model.exchange_code}:{model.unified_symbol}:{model.bar_time.isoformat()}",
        normalized_payload=normalized_payload,
    )


def _store_trade_event(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("trade_event", payload)
    model = TradeEvent.model_validate(payload)
    TradeRepository().upsert(connection, model)
    return ValidateAndStoreResult(
        payload_type="trade_event",
        model_name=model_name,
        stored=True,
        record_locator=f"{model.exchange_code}:{model.unified_symbol}:{model.exchange_trade_id}",
        normalized_payload=normalized_payload,
    )


def _store_funding_rate(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("funding_rate", payload)
    model = FundingRateEvent.model_validate(payload)
    FundingRateRepository().upsert(connection, model)
    return ValidateAndStoreResult(
        payload_type="funding_rate",
        model_name=model_name,
        stored=True,
        record_locator=f"{model.exchange_code}:{model.unified_symbol}:{model.funding_time.isoformat()}",
        normalized_payload=normalized_payload,
    )


def _store_open_interest(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("open_interest", payload)
    model = OpenInterestEvent.model_validate(payload)
    OpenInterestRepository().upsert(connection, model)
    return ValidateAndStoreResult(
        payload_type="open_interest",
        model_name=model_name,
        stored=True,
        record_locator=f"{model.exchange_code}:{model.unified_symbol}:{model.ts.isoformat()}",
        normalized_payload=normalized_payload,
    )


def _store_order_request(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("order_request", payload)
    model = OrderRequest.model_validate(payload)
    order_id = OrderRepository().create_from_request(connection, model)
    return ValidateAndStoreResult(
        payload_type="order_request",
        model_name=model_name,
        stored=True,
        record_locator=f"order_id:{order_id}",
        normalized_payload=normalized_payload,
    )


def _store_order_state(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("order_state", payload)
    model = OrderState.model_validate(payload)
    order_id = OrderRepository().upsert_order_state(connection, model)
    return ValidateAndStoreResult(
        payload_type="order_state",
        model_name=model_name,
        stored=True,
        record_locator=f"order_id:{order_id}",
        normalized_payload=normalized_payload,
    )


def _store_fill(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("fill", payload)
    model = Fill.model_validate(payload)
    fill_id = FillRepository().insert(connection, model)
    return ValidateAndStoreResult(
        payload_type="fill",
        model_name=model_name,
        stored=True,
        record_locator=f"fill_id:{fill_id}",
        normalized_payload=normalized_payload,
    )


def _store_position_snapshot(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("position_snapshot", payload)
    model = PositionSnapshot.model_validate(payload)
    repo = PositionRepository()
    repo.upsert_current(connection, model)
    repo.insert_snapshot(connection, model)
    return ValidateAndStoreResult(
        payload_type="position_snapshot",
        model_name=model_name,
        stored=True,
        record_locator=(
            f"{model.account_code}:{model.exchange_code}:{model.unified_symbol}:{model.snapshot_time.isoformat()}"
        ),
        normalized_payload=normalized_payload,
    )


def _store_balance_snapshot(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("balance_snapshot", payload)
    model = BalanceSnapshot.model_validate(payload)
    BalanceRepository().upsert_snapshot(connection, model)
    return ValidateAndStoreResult(
        payload_type="balance_snapshot",
        model_name=model_name,
        stored=True,
        record_locator=f"{model.account_code}:{model.asset}:{model.snapshot_time.isoformat()}",
        normalized_payload=normalized_payload,
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
