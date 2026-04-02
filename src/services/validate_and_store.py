from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from models.execution import (
    AccountLedgerEvent,
    BalanceSnapshot,
    Fill,
    FundingPnlEvent,
    OrderRequest,
    OrderState,
    PositionSnapshot,
)
from models.market import (
    BarEvent,
    FundingRateEvent,
    IndexPriceEvent,
    InstrumentMetadata,
    LiquidationEvent,
    MarkPriceEvent,
    OpenInterestEvent,
    OrderBookDeltaEvent,
    OrderBookSnapshotEvent,
    RawMarketEvent,
    TradeEvent,
)
from models.risk import RiskEvent, RiskLimit
from models.strategy import Signal, TargetPosition
from storage.repositories.execution import (
    AccountLedgerRepository,
    BalanceRepository,
    FillRepository,
    FundingPnlRepository,
    OrderRepository,
    PositionRepository,
)
from storage.repositories.instruments import InstrumentRepository
from storage.repositories.market_data import (
    BarRepository,
    FundingRateRepository,
    IndexPriceRepository,
    LiquidationRepository,
    MarkPriceRepository,
    OpenInterestRepository,
    OrderBookDeltaRepository,
    OrderBookSnapshotRepository,
    RawMarketEventRepository,
    TradeRepository,
)
from storage.repositories.ops import IngestionJobRepository, SystemLogRepository
from storage.repositories.risk import RiskEventRepository, RiskLimitRepository


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
    "orderbook_snapshot": OrderBookSnapshotEvent,
    "orderbook_delta": OrderBookDeltaEvent,
    "mark_price": MarkPriceEvent,
    "index_price": IndexPriceEvent,
    "liquidation_event": LiquidationEvent,
    "raw_market_event": RawMarketEvent,
    "signal": Signal,
    "target_position": TargetPosition,
    "order_request": OrderRequest,
    "order_state": OrderState,
    "fill": Fill,
    "position_snapshot": PositionSnapshot,
    "balance_snapshot": BalanceSnapshot,
    "account_ledger_event": AccountLedgerEvent,
    "funding_pnl_event": FundingPnlEvent,
    "risk_limit": RiskLimit,
    "risk_event": RiskEvent,
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
        record_locator=f"{model.exchange_code}:{model.unified_symbol}:{model.event_time.isoformat()}",
        normalized_payload=normalized_payload,
    )


def _store_orderbook_snapshot(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("orderbook_snapshot", payload)
    model = OrderBookSnapshotEvent.model_validate(payload)
    OrderBookSnapshotRepository().upsert(connection, model)
    return ValidateAndStoreResult(
        payload_type="orderbook_snapshot",
        model_name=model_name,
        stored=True,
        record_locator=f"{model.exchange_code}:{model.unified_symbol}:{model.snapshot_time.isoformat()}",
        normalized_payload=normalized_payload,
    )


def _store_orderbook_delta(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("orderbook_delta", payload)
    model = OrderBookDeltaEvent.model_validate(payload)
    delta_id = OrderBookDeltaRepository().insert(connection, model)
    return ValidateAndStoreResult(
        payload_type="orderbook_delta",
        model_name=model_name,
        stored=True,
        record_locator=f"delta_id:{delta_id}",
        normalized_payload=normalized_payload,
    )


def _store_mark_price(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("mark_price", payload)
    model = MarkPriceEvent.model_validate(payload)
    MarkPriceRepository().upsert(connection, model)
    return ValidateAndStoreResult(
        payload_type="mark_price",
        model_name=model_name,
        stored=True,
        record_locator=f"{model.exchange_code}:{model.unified_symbol}:{model.event_time.isoformat()}",
        normalized_payload=normalized_payload,
    )


def _store_index_price(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("index_price", payload)
    model = IndexPriceEvent.model_validate(payload)
    IndexPriceRepository().upsert(connection, model)
    return ValidateAndStoreResult(
        payload_type="index_price",
        model_name=model_name,
        stored=True,
        record_locator=f"{model.exchange_code}:{model.unified_symbol}:{model.event_time.isoformat()}",
        normalized_payload=normalized_payload,
    )


def _store_liquidation_event(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("liquidation_event", payload)
    model = LiquidationEvent.model_validate(payload)
    liquidation_id = LiquidationRepository().insert(connection, model)
    return ValidateAndStoreResult(
        payload_type="liquidation_event",
        model_name=model_name,
        stored=True,
        record_locator=f"liquidation_id:{liquidation_id}",
        normalized_payload=normalized_payload,
    )


def _store_raw_market_event(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("raw_market_event", payload)
    model = RawMarketEvent.model_validate(payload)
    raw_event_id = RawMarketEventRepository().insert(connection, model)
    return ValidateAndStoreResult(
        payload_type="raw_market_event",
        model_name=model_name,
        stored=True,
        record_locator=f"raw_event_id:{raw_event_id}",
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


def _store_account_ledger_event(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("account_ledger_event", payload)
    model = AccountLedgerEvent.model_validate(payload)
    ledger_id = AccountLedgerRepository().insert(connection, model)
    return ValidateAndStoreResult(
        payload_type="account_ledger_event",
        model_name=model_name,
        stored=True,
        record_locator=f"ledger_id:{ledger_id}",
        normalized_payload=normalized_payload,
    )


def _store_funding_pnl_event(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("funding_pnl_event", payload)
    model = FundingPnlEvent.model_validate(payload)
    funding_pnl_id = FundingPnlRepository().insert(connection, model)
    return ValidateAndStoreResult(
        payload_type="funding_pnl_event",
        model_name=model_name,
        stored=True,
        record_locator=f"funding_pnl_id:{funding_pnl_id}",
        normalized_payload=normalized_payload,
    )


def _store_risk_event(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("risk_event", payload)
    model = RiskEvent.model_validate(payload)
    risk_event_id = RiskEventRepository().insert(connection, model)
    return ValidateAndStoreResult(
        payload_type="risk_event",
        model_name=model_name,
        stored=True,
        record_locator=f"risk_event_id:{risk_event_id}",
        normalized_payload=normalized_payload,
    )


def _store_risk_limit(connection, payload: dict[str, Any]) -> ValidateAndStoreResult:
    model_name, normalized_payload = validate_payload("risk_limit", payload)
    model = RiskLimit.model_validate(payload)
    risk_limit_id = RiskLimitRepository().upsert(connection, model)
    scope = (
        f"{model.exchange_code}:{model.unified_symbol}"
        if model.exchange_code and model.unified_symbol
        else "account_scope"
    )
    return ValidateAndStoreResult(
        payload_type="risk_limit",
        model_name=model_name,
        stored=True,
        record_locator=f"risk_limit_id:{risk_limit_id}:{model.account_code}:{scope}",
        normalized_payload=normalized_payload,
    )


STORE_HANDLERS = {
    "instrument_metadata": _store_instrument,
    "bar_event": _store_bar_event,
    "trade_event": _store_trade_event,
    "funding_rate": _store_funding_rate,
    "open_interest": _store_open_interest,
    "orderbook_snapshot": _store_orderbook_snapshot,
    "orderbook_delta": _store_orderbook_delta,
    "mark_price": _store_mark_price,
    "index_price": _store_index_price,
    "liquidation_event": _store_liquidation_event,
    "raw_market_event": _store_raw_market_event,
    "order_request": _store_order_request,
    "order_state": _store_order_state,
    "fill": _store_fill,
    "position_snapshot": _store_position_snapshot,
    "balance_snapshot": _store_balance_snapshot,
    "account_ledger_event": _store_account_ledger_event,
    "funding_pnl_event": _store_funding_pnl_event,
    "risk_limit": _store_risk_limit,
    "risk_event": _store_risk_event,
}


def supported_payload_types() -> list[str]:
    return sorted(STORE_HANDLERS)


def validate_and_store(connection, payload_type: str, payload: dict[str, Any]) -> ValidateAndStoreResult:
    try:
        handler = STORE_HANDLERS[payload_type]
    except KeyError as exc:
        raise UnsupportedPayloadTypeError(f"unsupported payload_type: {payload_type}") from exc
    return handler(connection, payload)
