from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys
import unittest
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from models.execution import BalanceSnapshot, Fill, OrderEvent, OrderRequest, PositionSnapshot
from models.market import BarEvent, TradeEvent
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
from storage.repositories.market_data import BarRepository, TradeRepository


class Phase2RepositoryIntegrationTests(unittest.TestCase):
    def test_market_repositories_are_idempotent_and_instrument_resolution_works(self) -> None:
        run_id = uuid4().hex[:10]
        bar_time = datetime(2026, 4, 2, 12, 34, tzinfo=timezone.utc)

        bar_event = BarEvent(
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            bar_interval="1m",
            bar_time=bar_time,
            open=Decimal("84210.10"),
            high=Decimal("84255.00"),
            low=Decimal("84190.50"),
            close=Decimal("84250.12"),
            volume=Decimal("152.2301"),
            quote_volume=Decimal("12824611.91"),
            trade_count=1289,
            event_time=datetime(2026, 4, 2, 12, 34, 59, 999000, tzinfo=timezone.utc),
        )
        updated_bar_event = bar_event.model_copy(update={"close": Decimal("84260.12")})

        trade_event = TradeEvent(
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            exchange_trade_id=f"repo_trade_{run_id}",
            event_time=datetime(2026, 4, 2, 12, 34, 56, 789000, tzinfo=timezone.utc),
            ingest_time=datetime(2026, 4, 2, 12, 34, 56, 900000, tzinfo=timezone.utc),
            price=Decimal("84250.12"),
            qty=Decimal("0.015"),
            aggressor_side="buy",
        )
        updated_trade_event = trade_event.model_copy(update={"qty": Decimal("0.025")})

        with transaction_scope() as connection:
            instrument_id = resolve_instrument_id(connection, "binance", "BTCUSDT_PERP")
            bar_repo = BarRepository()
            trade_repo = TradeRepository()

            bar_repo.upsert(connection, bar_event)
            bar_repo.upsert(connection, updated_bar_event)
            trade_repo.upsert(connection, trade_event)
            trade_repo.upsert(connection, updated_trade_event)

        with connection_scope() as connection:
            resolved_again = resolve_instrument_id(connection, "binance", "BTCUSDT_PERP")
            self.assertEqual(resolved_again, instrument_id)

            bar_row = connection.exec_driver_sql(
                """
                select count(*), max(close)
                from md.bars_1m
                where instrument_id = %s
                  and bar_time = %s
                """,
                (instrument_id, bar_time),
            ).first()
            self.assertEqual(bar_row[0], 1)
            self.assertEqual(bar_row[1], Decimal("84260.120000000000"))

            trade_row = connection.exec_driver_sql(
                """
                select count(*), max(qty)
                from md.trades
                where instrument_id = %s
                  and exchange_trade_id = %s
                """,
                (instrument_id, trade_event.exchange_trade_id),
            ).first()
            self.assertEqual(trade_row[0], 1)
            self.assertEqual(trade_row[1], Decimal("0.025000000000"))

    def test_execution_repositories_persist_order_fill_position_and_balance(self) -> None:
        run_id = uuid4().hex[:10]
        account_code = f"phase2_test_{run_id}"
        client_order_id = f"phase2_order_{run_id}"
        fill_trade_id = f"phase2_fill_{run_id}"

        account = AccountRecord(
            account_code=account_code,
            exchange_code="binance",
            account_type="paper",
            base_currency="USDT",
        )
        order_request = OrderRequest(
            environment="paper",
            account_code=account_code,
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            client_order_id=client_order_id,
            side="buy",
            order_type="limit",
            time_in_force="gtc",
            price=Decimal("84240.00"),
            qty=Decimal("0.5000"),
            metadata={"source": "repository_test"},
        )
        order_event = OrderEvent(
            order_id="0",
            client_order_id=client_order_id,
            event_type="acknowledged",
            event_time=datetime(2026, 4, 2, 12, 34, 1, 100000, tzinfo=timezone.utc),
            status_before="new",
            status_after="acknowledged",
            detail={"raw_status": "NEW"},
        )
        fill = Fill(
            order_id="0",
            exchange_trade_id=fill_trade_id,
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
            account_code=account_code,
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
            account_code=account_code,
            asset="USDT",
            snapshot_time=datetime(2026, 4, 2, 12, 35, 0, tzinfo=timezone.utc),
            wallet_balance=Decimal("100000.00"),
            available_balance=Decimal("78935.7880"),
            margin_balance=Decimal("100001.0450"),
            equity=Decimal("100001.0450"),
        )

        with transaction_scope() as connection:
            account_repo = AccountRepository()
            order_repo = OrderRepository()
            order_event_repo = OrderEventRepository()
            fill_repo = FillRepository()
            position_repo = PositionRepository()
            balance_repo = BalanceRepository()

            account_id = account_repo.upsert(connection, account)
            order_id = order_repo.create_from_request(connection, order_request)

            order_event.order_id = str(order_id)
            order_event_id = order_event_repo.insert(connection, order_event)

            fill.order_id = str(order_id)
            fill_id = fill_repo.insert(connection, fill)

            position_repo.upsert_current(connection, position_snapshot)
            position_repo.insert_snapshot(connection, position_snapshot)
            balance_repo.upsert_snapshot(connection, balance_snapshot)

        with connection_scope() as connection:
            resolved_account_id = resolve_account_id(connection, account_code)
            instrument_id = resolve_instrument_id(connection, "binance", "BTCUSDT_PERP")

            self.assertEqual(resolved_account_id, account_id)

            order_count = connection.exec_driver_sql(
                """
                select count(*)
                from execution.orders
                where account_id = %s
                  and client_order_id = %s
                """,
                (resolved_account_id, client_order_id),
            ).scalar_one()
            fill_count = connection.exec_driver_sql(
                """
                select count(*)
                from execution.fills
                where order_id = %s
                  and exchange_trade_id = %s
                """,
                (order_id, fill_trade_id),
            ).scalar_one()
            position_count = connection.exec_driver_sql(
                """
                select count(*)
                from execution.positions
                where account_id = %s
                  and instrument_id = %s
                """,
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

            self.assertEqual(order_count, 1)
            self.assertEqual(fill_count, 1)
            self.assertEqual(position_count, 1)
            self.assertEqual(balance_count, 1)
            self.assertGreater(order_event_id, 0)
            self.assertGreater(fill_id, 0)


if __name__ == "__main__":
    unittest.main()
