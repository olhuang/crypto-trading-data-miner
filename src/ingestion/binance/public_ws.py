from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from models.market import LiquidationEvent, MarkPriceEvent, RawMarketEvent, TradeEvent


BINANCE_FUTURES_WS_BASE_URL = "wss://fstream.binance.com/stream"


def _utc_from_millis(value: int | str) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)


@dataclass(slots=True)
class WsNormalizedEnvelope:
    channel: str
    event_type: str
    raw_event: RawMarketEvent
    trade_event: TradeEvent | None = None
    mark_price_event: MarkPriceEvent | None = None
    liquidation_event: LiquidationEvent | None = None


class BinancePublicWsAdapter:
    def build_stream_url(self, *streams: str) -> str:
        joined = "/".join(streams)
        return f"{BINANCE_FUTURES_WS_BASE_URL}?streams={joined}"

    def normalize_message(self, message: str | dict[str, Any]) -> WsNormalizedEnvelope:
        payload = json.loads(message) if isinstance(message, str) else message
        stream = str(payload["stream"])
        data = payload["data"]
        event_time = _utc_from_millis(data.get("E", int(datetime.now(timezone.utc).timestamp() * 1000)))
        symbol = data.get("s")
        unified_symbol = f"{symbol}_PERP" if symbol else None
        event_type = str(data.get("e", "unknown"))
        raw_event = RawMarketEvent(
            exchange_code="binance",
            unified_symbol=unified_symbol,
            channel=stream,
            event_type=event_type,
            event_time=event_time,
            ingest_time=datetime.now(timezone.utc),
            source_message_id=str(data.get("u") or data.get("a") or data.get("T") or ""),
            payload_json=data,
        )

        if event_type == "trade":
            trade_event = TradeEvent(
                exchange_code="binance",
                unified_symbol=unified_symbol or "",
                exchange_trade_id=str(data["t"]),
                event_time=_utc_from_millis(data["T"]),
                ingest_time=datetime.now(timezone.utc),
                price=Decimal(str(data["p"])),
                qty=Decimal(str(data["q"])),
                aggressor_side="sell" if data.get("m") else "buy",
                payload_json=data,
            )
            return WsNormalizedEnvelope(stream, event_type, raw_event, trade_event=trade_event)

        if event_type == "markPriceUpdate":
            index_price = Decimal(str(data["i"]))
            mark_price = Decimal(str(data["p"]))
            mark_event = MarkPriceEvent(
                exchange_code="binance",
                unified_symbol=unified_symbol or "",
                event_time=_utc_from_millis(data["E"]),
                ingest_time=datetime.now(timezone.utc),
                mark_price=mark_price,
                funding_basis_bps=((mark_price - index_price) / index_price * Decimal("10000")) if index_price else None,
                payload_json=data,
            )
            return WsNormalizedEnvelope(stream, event_type, raw_event, mark_price_event=mark_event)

        if event_type == "forceOrder":
            order_data = data.get("o", {})
            liquidation_event = LiquidationEvent(
                exchange_code="binance",
                unified_symbol=f"{order_data['s']}_PERP",
                event_time=_utc_from_millis(order_data["T"]),
                ingest_time=datetime.now(timezone.utc),
                side=str(order_data.get("S", "")).lower() or None,
                price=Decimal(str(order_data["p"])) if order_data.get("p") else None,
                qty=Decimal(str(order_data["q"])) if order_data.get("q") else None,
                notional=(
                    Decimal(str(order_data["p"])) * Decimal(str(order_data["q"]))
                    if order_data.get("p") and order_data.get("q")
                    else None
                ),
                source=stream,
                metadata_json=data,
            )
            return WsNormalizedEnvelope(stream, event_type, raw_event, liquidation_event=liquidation_event)

        return WsNormalizedEnvelope(stream, event_type, raw_event)
