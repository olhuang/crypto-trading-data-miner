from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from models.market import BarEvent, InstrumentMetadata, TradeEvent
from storage.db import connection_scope, transaction_scope
from storage.lookups import resolve_instrument_id
from storage.repositories.instruments import InstrumentRepository
from storage.repositories.market_data import BarRepository, TradeRepository


def main() -> None:
    instrument_repo = InstrumentRepository()
    bar_repo = BarRepository()
    trade_repo = TradeRepository()

    # Use existing Phase 1 seed rows to validate code-paths without introducing new entities.
    seeded_instrument = InstrumentMetadata(
        exchange_code="binance",
        venue_symbol="BTCUSDT",
        unified_symbol="BTCUSDT_PERP",
        instrument_type="perp",
        base_asset="BTC",
        quote_asset="USDT",
        settlement_asset="USDT",
        tick_size=Decimal("0.10"),
        lot_size=Decimal("0.001"),
        min_qty=Decimal("0.001"),
        min_notional=Decimal("100"),
        contract_size=Decimal("1"),
        status="trading",
    )

    bar_event = BarEvent(
        exchange_code="binance",
        unified_symbol="BTCUSDT_PERP",
        bar_interval="1m",
        bar_time=datetime(2026, 4, 2, 12, 34, tzinfo=timezone.utc),
        open=Decimal("84210.10"),
        high=Decimal("84255.00"),
        low=Decimal("84190.50"),
        close=Decimal("84250.12"),
        volume=Decimal("152.2301"),
        quote_volume=Decimal("12824611.91"),
        trade_count=1289,
        event_time=datetime(2026, 4, 2, 12, 34, 59, 999000, tzinfo=timezone.utc),
    )

    trade_event = TradeEvent(
        exchange_code="binance",
        unified_symbol="BTCUSDT_PERP",
        exchange_trade_id="phase2_smoke_trade_001",
        event_time=datetime(2026, 4, 2, 12, 34, 56, 789000, tzinfo=timezone.utc),
        ingest_time=datetime(2026, 4, 2, 12, 34, 56, 900000, tzinfo=timezone.utc),
        price=Decimal("84250.12"),
        qty=Decimal("0.015"),
        aggressor_side="buy",
    )

    with transaction_scope() as connection:
        instrument_repo.upsert(connection, seeded_instrument)
        instrument_id = resolve_instrument_id(connection, "binance", "BTCUSDT_PERP")
        bar_repo.upsert(connection, bar_event)
        trade_repo.upsert(connection, trade_event)

    with connection_scope() as connection:
        bar_count = connection.exec_driver_sql(
            "select count(*) from md.bars_1m where instrument_id = %s",
            (instrument_id,),
        ).scalar_one()
        trade_count = connection.exec_driver_sql(
            "select count(*) from md.trades where instrument_id = %s and exchange_trade_id = %s",
            (instrument_id, "phase2_smoke_trade_001"),
        ).scalar_one()

    print("Phase 2 smoke checks passed")
    print(f"instrument_id={instrument_id}")
    print(f"bars_for_instrument={bar_count}")
    print(f"smoke_trade_rows={trade_count}")


if __name__ == "__main__":
    main()
