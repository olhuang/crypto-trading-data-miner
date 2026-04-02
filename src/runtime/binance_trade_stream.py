from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from ingestion.binance.public_ws import BinancePublicWsAdapter
from storage.db import transaction_scope
from storage.repositories.market_data import LiquidationRepository, MarkPriceRepository, RawMarketEventRepository, TradeRepository
from storage.repositories.ops import WsConnectionEventRecord, WsConnectionEventRepository


@dataclass(slots=True)
class TradeStreamRunResult:
    messages_seen: int
    trades_written: int
    mark_prices_written: int
    liquidations_written: int
    raw_events_written: int


class BinanceTradeStreamProcessor:
    def __init__(self, adapter: BinancePublicWsAdapter | None = None) -> None:
        self.adapter = adapter or BinancePublicWsAdapter()

    def consume_messages(
        self,
        messages: Iterable[str | dict],
        *,
        service_name: str = "binance_trade_stream",
        exchange_code: str = "binance",
    ) -> TradeStreamRunResult:
        result = TradeStreamRunResult(0, 0, 0, 0, 0)
        with transaction_scope() as connection:
            ws_repo = WsConnectionEventRepository()
            ws_repo.insert(
                connection,
                WsConnectionEventRecord(
                    service_name=service_name,
                    exchange_code=exchange_code,
                    channel="futures_public",
                    event_type="connected",
                    event_time=datetime.now(timezone.utc),
                    connection_id=f"{service_name}:{int(datetime.now(timezone.utc).timestamp())}",
                    detail_json={},
                ),
            )
            for message in messages:
                result.messages_seen += 1
                envelope = self.adapter.normalize_message(message)
                RawMarketEventRepository().insert(connection, envelope.raw_event)
                result.raw_events_written += 1

                if envelope.trade_event is not None:
                    TradeRepository().upsert(connection, envelope.trade_event)
                    result.trades_written += 1
                if envelope.mark_price_event is not None:
                    MarkPriceRepository().upsert(connection, envelope.mark_price_event)
                    result.mark_prices_written += 1
                if envelope.liquidation_event is not None:
                    LiquidationRepository().insert(connection, envelope.liquidation_event)
                    result.liquidations_written += 1

            ws_repo.insert(
                connection,
                WsConnectionEventRecord(
                    service_name=service_name,
                    exchange_code=exchange_code,
                    channel="futures_public",
                    event_type="disconnected",
                    event_time=datetime.now(timezone.utc),
                    connection_id=f"{service_name}:closed",
                    detail_json={"messages_seen": result.messages_seen},
                ),
            )
        return result
