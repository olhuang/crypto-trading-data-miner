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
from models.execution import BalanceSnapshot, Fill, OrderEvent, OrderRequest, PositionSnapshot
from storage.db import connection_scope, transaction_scope
from storage.lookups import resolve_account_id, resolve_instrument_id
from storage.repositories.execution import (
    AccountRecord,
    AccountRepository,
    BalanceRepository,
    FillRepository,
    OrderEventRepository,
    OrderRepository,
    PositionRepository,
)
from storage.repositories.instruments import InstrumentRepository
from storage.repositories.market_data import BarRepository, TradeRepository


def main() -> None:
    instrument_repo = InstrumentRepository()
    bar_repo = BarRepository()
    trade_repo = TradeRepository()
    account_repo = AccountRepository()
    order_repo = OrderRepository()
    order_event_repo = OrderEventRepository()
    fill_repo = FillRepository()
    position_repo = PositionRepository()
    balance_repo = BalanceRepository()

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

    account = AccountRecord(
        account_code="phase2_paper_main",
        exchange_code="binance",
        account_type="paper",
        base_currency="USDT",
    )

    order_request = OrderRequest(
        environment="paper",
        account_code="phase2_paper_main",
        exchange_code="binance",
        unified_symbol="BTCUSDT_PERP",
        client_order_id="phase2_smoke_order_001",
        side="buy",
        order_type="limit",
        time_in_force="gtc",
        price=Decimal("84240.00"),
        qty=Decimal("0.5000"),
        metadata={"source": "phase2_smoke"},
    )

    order_event = OrderEvent(
        order_id="0",
        client_order_id="phase2_smoke_order_001",
        event_type="acknowledged",
        event_time=datetime(2026, 4, 2, 12, 34, 1, 100000, tzinfo=timezone.utc),
        status_before="new",
        status_after="acknowledged",
        detail={"raw_status": "NEW"},
    )

    fill = Fill(
        order_id="0",
        exchange_trade_id="phase2_smoke_fill_001",
        exchange_code="binance",
        unified_symbol="BTCUSDT_PERP",
        fill_time=datetime(2026, 4, 2, 12, 34, 2, 120000, tzinfo=timezone.utc),
        price=Decimal("84240.00"),
        qty=Decimal("0.2500"),
        notional=Decimal("21060.00"),
        fee=Decimal("4.2120"),
        fee_asset="USDT",
        liquidity_flag="maker",
    )

    position_snapshot = PositionSnapshot(
        environment="paper",
        account_code="phase2_paper_main",
        exchange_code="binance",
        unified_symbol="BTCUSDT_PERP",
        snapshot_time=datetime(2026, 4, 2, 12, 35, 0, tzinfo=timezone.utc),
        position_qty=Decimal("0.2500"),
        avg_entry_price=Decimal("84240.00"),
        mark_price=Decimal("84244.18"),
        unrealized_pnl=Decimal("1.0450"),
        realized_pnl=Decimal("0"),
    )

    balance_snapshot = BalanceSnapshot(
        environment="paper",
        account_code="phase2_paper_main",
        asset="USDT",
        snapshot_time=datetime(2026, 4, 2, 12, 35, 0, tzinfo=timezone.utc),
        wallet_balance=Decimal("100000.00"),
        available_balance=Decimal("78935.7880"),
        margin_balance=Decimal("100001.0450"),
        equity=Decimal("100001.0450"),
    )

    with transaction_scope() as connection:
        instrument_repo.upsert(connection, seeded_instrument)
        instrument_id = resolve_instrument_id(connection, "binance", "BTCUSDT_PERP")
        account_id = account_repo.upsert(connection, account)
        bar_repo.upsert(connection, bar_event)
        trade_repo.upsert(connection, trade_event)
        order_id = order_repo.create_from_request(connection, order_request)

        order_event.order_id = str(order_id)
        order_event_id = order_event_repo.insert(connection, order_event)

        fill.order_id = str(order_id)
        fill_id = fill_repo.insert(connection, fill)

        position_repo.upsert_current(connection, position_snapshot)
        position_repo.insert_snapshot(connection, position_snapshot)
        balance_repo.upsert_snapshot(connection, balance_snapshot)

    with connection_scope() as connection:
        bar_count = connection.exec_driver_sql(
            "select count(*) from md.bars_1m where instrument_id = %s",
            (instrument_id,),
        ).scalar_one()
        trade_count = connection.exec_driver_sql(
            "select count(*) from md.trades where instrument_id = %s and exchange_trade_id = %s",
            (instrument_id, "phase2_smoke_trade_001"),
        ).scalar_one()
        resolved_account_id = resolve_account_id(connection, "phase2_paper_main")
        order_count = connection.exec_driver_sql(
            "select count(*) from execution.orders where account_id = %s and client_order_id = %s",
            (resolved_account_id, "phase2_smoke_order_001"),
        ).scalar_one()
        fill_count = connection.exec_driver_sql(
            "select count(*) from execution.fills where order_id = %s",
            (order_id,),
        ).scalar_one()
        position_count = connection.exec_driver_sql(
            "select count(*) from execution.positions where account_id = %s and instrument_id = %s",
            (resolved_account_id, instrument_id),
        ).scalar_one()
        balance_count = connection.exec_driver_sql(
            """
            select count(*)
            from execution.balances
            where account_id = %s
              and snapshot_time = %s
            """,
            (resolved_account_id, balance_snapshot.snapshot_time),
        ).scalar_one()

    print("Phase 2 smoke checks passed")
    print(f"instrument_id={instrument_id}")
    print(f"account_id={account_id}")
    print(f"bars_for_instrument={bar_count}")
    print(f"smoke_trade_rows={trade_count}")
    print(f"smoke_order_rows={order_count}")
    print(f"smoke_order_event_id={order_event_id}")
    print(f"smoke_fill_id={fill_id}")
    print(f"smoke_fill_rows_for_order={fill_count}")
    print(f"smoke_position_rows={position_count}")
    print(f"smoke_balance_rows={balance_count}")


if __name__ == "__main__":
    main()
