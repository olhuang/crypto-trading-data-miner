from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys
import unittest
from uuid import uuid4

from sqlalchemy.exc import OperationalError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from models.execution import (
    AccountLedgerEvent,
    BalanceSnapshot,
    Fill,
    FundingPnlEvent,
    OrderEvent,
    OrderRequest,
    PositionSnapshot,
)
from models.market import (
    BarEvent,
    IndexPriceEvent,
    MarkPriceEvent,
    OrderBookDeltaEvent,
    OrderBookSnapshotEvent,
    RawMarketEvent,
    TradeEvent,
)
from models.risk import RiskEvent, RiskLimit
from storage.db import connection_scope, get_engine, run_with_retry, transaction_scope
from storage.lookups import (
    LookupResolutionError,
    resolve_account_id,
    resolve_instrument_id,
    resolve_strategy_id,
    resolve_strategy_version_id,
)
from storage.repositories.execution import (
    AccountRecord,
    AccountLedgerRepository,
    AccountRepository,
    BalanceRepository,
    FillRepository,
    FundingPnlRepository,
    OrderEventRepository,
    OrderRepository,
    PositionRepository,
)
from storage.repositories.instruments import AssetRepository, ExchangeRepository
from storage.repositories.market_data import (
    BarRepository,
    IndexPriceRepository,
    MarkPriceRepository,
    OrderBookDeltaRepository,
    OrderBookSnapshotRepository,
    RawMarketEventRepository,
    TradeRepository,
)
from storage.repositories.ops import IngestionJobRecord, IngestionJobRepository, SystemLogRecord, SystemLogRepository
from storage.repositories.risk import RiskEventRepository, RiskLimitRepository


class Phase2RepositoryIntegrationTests(unittest.TestCase):
    def test_run_with_retry_retries_transient_operational_errors(self) -> None:
        attempts = {"count": 0}

        def flaky_operation() -> str:
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise OperationalError("select 1", {}, RuntimeError("transient"))
            return "ok"

        result = run_with_retry(flaky_operation, attempts=3, backoff_seconds=0)

        self.assertEqual(result, "ok")
        self.assertEqual(attempts["count"], 3)

    def test_strategy_and_version_resolution_use_seed_defaults(self) -> None:
        with connection_scope() as connection:
            strategy_id = resolve_strategy_id(connection, "btc_momentum")
            strategy_version_id = resolve_strategy_version_id(connection, "btc_momentum", "v1.0.0")

            self.assertGreater(strategy_id, 0)
            self.assertGreater(strategy_version_id, 0)

            with self.assertRaises(LookupResolutionError):
                resolve_strategy_version_id(connection, "btc_momentum", "v9.9.9")

    def test_market_repositories_are_idempotent_and_instrument_resolution_works(self) -> None:
        run_id = uuid4().hex[:10]
        bar_time = datetime(2036, 4, 2, 12, 34, tzinfo=timezone.utc)

        bar_event = BarEvent(
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            ingest_time=datetime(2036, 4, 2, 12, 35, 0, 100000, tzinfo=timezone.utc),
            bar_interval="1m",
            bar_time=bar_time,
            open=Decimal("84210.10"),
            high=Decimal("84255.00"),
            low=Decimal("84190.50"),
            close=Decimal("84250.12"),
            volume=Decimal("152.2301"),
            quote_volume=Decimal("12824611.91"),
            trade_count=1289,
            event_time=datetime(2036, 4, 2, 12, 34, 59, 999000, tzinfo=timezone.utc),
        )
        updated_bar_event = bar_event.model_copy(update={"close": Decimal("84260.12")})

        trade_event = TradeEvent(
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            exchange_trade_id=f"repo_trade_{run_id}",
            event_time=datetime(2036, 4, 2, 12, 34, 56, 789000, tzinfo=timezone.utc),
            ingest_time=datetime(2036, 4, 2, 12, 34, 56, 900000, tzinfo=timezone.utc),
            price=Decimal("84250.12"),
            qty=Decimal("0.015"),
            aggressor_side="buy",
        )
        updated_trade_event = trade_event.model_copy(update={"qty": Decimal("0.025")})

        connection = get_engine().connect()
        transaction = connection.begin()
        try:
            instrument_id = resolve_instrument_id(connection, "binance", "BTCUSDT_PERP")
            bar_repo = BarRepository()
            trade_repo = TradeRepository()

            bar_repo.upsert(connection, bar_event)
            bar_repo.upsert(connection, updated_bar_event)
            trade_repo.upsert(connection, trade_event)
            trade_repo.upsert(connection, updated_trade_event)

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
        finally:
            transaction.rollback()
            connection.close()

    def test_execution_repositories_persist_order_fill_position_and_balance(self) -> None:
        run_id = uuid4().hex[:10]
        base_time = datetime(2036, 4, 2, 12, 34, tzinfo=timezone.utc)
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
            event_time=base_time.replace(second=1, microsecond=100000),
            status_before="new",
            status_after="acknowledged",
            detail={"raw_status": "NEW"},
        )
        fill = Fill(
            order_id="0",
            exchange_trade_id=fill_trade_id,
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            fill_time=base_time.replace(second=2, microsecond=120000),
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
            snapshot_time=base_time.replace(minute=35, second=0, microsecond=0),
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
            snapshot_time=base_time.replace(minute=35, second=0, microsecond=0),
            wallet_balance=Decimal("100000.00"),
            available_balance=Decimal("78935.7880"),
            margin_balance=Decimal("100001.0450"),
            equity=Decimal("100001.0450"),
        )

        connection = get_engine().connect()
        transaction = connection.begin()
        try:
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
        finally:
            transaction.rollback()
            connection.close()

    def test_duplicate_fill_handling_is_idempotent_for_same_order_and_exchange_trade_id(self) -> None:
        run_id = uuid4().hex[:10]
        fill_time = datetime(2036, 4, 2, 12, 34, 2, 120000, tzinfo=timezone.utc)
        account_code = f"phase2_fill_dedup_{run_id}"
        client_order_id = f"phase2_fill_order_{run_id}"
        fill_trade_id = f"phase2_fill_trade_{run_id}"

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
            metadata={"source": "fill_dedup_test"},
        )
        first_fill = Fill(
            order_id="0",
            exchange_trade_id=fill_trade_id,
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            fill_time=fill_time,
            price=Decimal("84240.00"),
            qty=Decimal("0.2500"),
            notional=Decimal("21060.00"),
            fee=Decimal("4.2120"),
            fee_asset="USDT",
            liquidity_flag="maker",
        )
        updated_fill = first_fill.model_copy(
            update={
                "qty": Decimal("0.3000"),
                "notional": Decimal("25272.00"),
            }
        )

        connection = get_engine().connect()
        transaction = connection.begin()
        try:
            account_repo = AccountRepository()
            order_repo = OrderRepository()
            fill_repo = FillRepository()

            account_repo.upsert(connection, account)
            order_id = order_repo.create_from_request(connection, order_request)

            first_fill.order_id = str(order_id)
            updated_fill.order_id = str(order_id)

            first_fill_id = fill_repo.insert(connection, first_fill)
            second_fill_id = fill_repo.insert(connection, updated_fill)

            row = connection.exec_driver_sql(
                """
                select count(*), max(qty), max(notional)
                from execution.fills
                where order_id = %s
                  and exchange_trade_id = %s
                """,
                (order_id, fill_trade_id),
            ).first()

            self.assertEqual(first_fill_id, second_fill_id)
            self.assertEqual(row[0], 1)
            self.assertEqual(row[1], Decimal("0.300000000000"))
            self.assertEqual(row[2], Decimal("25272.000000000000"))
        finally:
            transaction.rollback()
            connection.close()

    def test_reference_market_risk_and_ops_repositories_cover_remaining_phase2_entities(self) -> None:
        run_id = uuid4().hex[:10]
        base_time = datetime(2036, 4, 2, 12, 34, tzinfo=timezone.utc)
        account_code = f"phase2_risk_ops_{run_id}"

        snapshot_event = OrderBookSnapshotEvent(
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            snapshot_time=base_time.replace(second=0, microsecond=0),
            ingest_time=base_time.replace(second=0, microsecond=100000),
            depth_levels=2,
            bids=[(Decimal("84250.10"), Decimal("3.12"))],
            asks=[(Decimal("84250.20"), Decimal("2.65"))],
            checksum="abc123",
            source="rest_snapshot",
        )
        delta_event = OrderBookDeltaEvent(
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            event_time=base_time.replace(second=1, microsecond=250000),
            ingest_time=base_time.replace(second=1, microsecond=320000),
            first_update_id=10001,
            final_update_id=10005,
            bids=[(Decimal("84250.10"), Decimal("0"))],
            asks=[(Decimal("84250.20"), Decimal("1.10"))],
            checksum="def456",
            source="ws_depth",
        )
        mark_event = MarkPriceEvent(
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            event_time=base_time.replace(second=2, microsecond=0),
            ingest_time=base_time.replace(second=2, microsecond=100000),
            mark_price=Decimal("84244.18"),
            funding_basis_bps=Decimal("0.82"),
        )
        index_event = IndexPriceEvent(
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            event_time=base_time.replace(second=2, microsecond=0),
            ingest_time=base_time.replace(second=2, microsecond=100000),
            index_price=Decimal("84240.01"),
        )
        raw_event = RawMarketEvent(
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            channel="depth",
            event_type="depth_update",
            event_time=base_time.replace(second=1, microsecond=250000),
            ingest_time=base_time.replace(second=1, microsecond=320000),
            source_message_id=f"u_{run_id}",
            payload_json={"u": 10005, "pu": 10000},
        )
        ledger_event = AccountLedgerEvent(
            environment="paper",
            account_code=account_code,
            asset="USDT",
            event_time=base_time.replace(hour=8, minute=0, second=1, microsecond=0),
            ledger_type="funding_payment",
            amount=Decimal("-12.45"),
            balance_after=Decimal("100120.55"),
            reference_type="funding",
            reference_id=f"funding_{run_id}",
            external_reference_id=f"ext_{run_id}",
            detail_json={"source": "integration_test"},
        )
        funding_pnl_event = FundingPnlEvent(
            environment="paper",
            account_code=account_code,
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            funding_time=base_time.replace(hour=8, minute=0, second=0, microsecond=0),
            position_qty=Decimal("0.5000"),
            funding_rate=Decimal("0.00010000"),
            funding_payment=Decimal("-4.21"),
            asset="USDT",
            detail_json={"batch_id": f"batch_{run_id}"},
        )
        risk_limit = RiskLimit(
            account_code=account_code,
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            max_notional=Decimal("25000"),
            max_leverage=Decimal("3"),
        )
        updated_risk_limit = risk_limit.model_copy(update={"max_notional": Decimal("30000")})
        risk_event = RiskEvent(
            account_code=account_code,
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            event_time=base_time.replace(minute=40, second=0, microsecond=0),
            event_type="pre_trade_check_blocked",
            severity="warning",
            decision="block",
            detail_json={"reason_code": "max_notional"},
        )
        system_log = SystemLogRecord(
            service_name="phase2_test",
            level="info",
            message=f"phase2 repo coverage {run_id}",
            context_json={"run_id": run_id},
        )
        ingestion_job = IngestionJobRecord(
            service_name="phase2_test",
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            data_type="mark_price",
            schedule_type="manual",
            status="success",
            records_expected=1,
            records_written=1,
            finished_at=base_time.replace(minute=45, second=0, microsecond=0),
            metadata_json={"run_id": run_id},
        )

        connection = get_engine().connect()
        transaction = connection.begin()
        try:
            exchange_repo = ExchangeRepository()
            asset_repo = AssetRepository()
            account_repo = AccountRepository()
            account_ledger_repo = AccountLedgerRepository()
            funding_pnl_repo = FundingPnlRepository()
            risk_limit_repo = RiskLimitRepository()
            risk_event_repo = RiskEventRepository()
            system_log_repo = SystemLogRepository()
            ingestion_job_repo = IngestionJobRepository()

            exchanges = exchange_repo.list_all(connection)
            assets = asset_repo.list_all(connection)
            self.assertTrue(any(exchange["exchange_code"] == "binance" for exchange in exchanges))
            self.assertTrue(any(asset["asset_code"] == "USDT" for asset in assets))

            account_repo.upsert(
                connection,
                AccountRecord(
                    account_code=account_code,
                    exchange_code="binance",
                    account_type="paper",
                    base_currency="USDT",
                ),
            )

            OrderBookSnapshotRepository().upsert(connection, snapshot_event)
            delta_id = OrderBookDeltaRepository().insert(connection, delta_event)
            MarkPriceRepository().upsert(connection, mark_event)
            IndexPriceRepository().upsert(connection, index_event)
            raw_event_id = RawMarketEventRepository().insert(connection, raw_event)
            ledger_id = account_ledger_repo.insert(connection, ledger_event)
            funding_pnl_id = funding_pnl_repo.insert(connection, funding_pnl_event)
            first_risk_limit_id = risk_limit_repo.upsert(connection, risk_limit)
            second_risk_limit_id = risk_limit_repo.upsert(connection, updated_risk_limit)
            risk_event_id = risk_event_repo.insert(connection, risk_event)
            log_id = system_log_repo.insert(connection, system_log)
            ingestion_job_id = ingestion_job_repo.insert(connection, ingestion_job)

            account_id = resolve_account_id(connection, account_code)
            instrument_id = resolve_instrument_id(connection, "binance", "BTCUSDT_PERP")

            snapshot_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.orderbook_snapshots
                where instrument_id = %s
                  and snapshot_time = %s
                """,
                (instrument_id, snapshot_event.snapshot_time),
            ).scalar_one()
            mark_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.mark_prices
                where instrument_id = %s
                  and ts = %s
                """,
                (instrument_id, mark_event.event_time),
            ).scalar_one()
            index_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.index_prices
                where instrument_id = %s
                  and ts = %s
                """,
                (instrument_id, index_event.event_time),
            ).scalar_one()
            raw_payload = connection.exec_driver_sql(
                """
                select payload_json->>'u'
                from md.raw_market_events
                where raw_event_id = %s
                """,
                (raw_event_id,),
            ).scalar_one()
            ledger_count = connection.exec_driver_sql(
                """
                select count(*)
                from execution.account_ledger
                where ledger_id = %s
                  and account_id = %s
                """,
                (ledger_id, account_id),
            ).scalar_one()
            funding_pnl_count = connection.exec_driver_sql(
                """
                select count(*)
                from execution.funding_pnl
                where funding_pnl_id = %s
                  and account_id = %s
                """,
                (funding_pnl_id, account_id),
            ).scalar_one()
            risk_limit_row = connection.exec_driver_sql(
                """
                select count(*), max(max_notional)
                from risk.risk_limits
                where account_id = %s
                  and instrument_id = %s
                """,
                (account_id, instrument_id),
            ).first()
            risk_event_count = connection.exec_driver_sql(
                """
                select count(*)
                from risk.risk_events
                where risk_event_id = %s
                """,
                (risk_event_id,),
            ).scalar_one()
            log_count = connection.exec_driver_sql(
                """
                select count(*)
                from ops.system_logs
                where log_id = %s
                """,
                (log_id,),
            ).scalar_one()
            ingestion_job_count = connection.exec_driver_sql(
                """
                select count(*)
                from ops.ingestion_jobs
                where ingestion_job_id = %s
                """,
                (ingestion_job_id,),
            ).scalar_one()

            self.assertGreater(delta_id, 0)
            self.assertEqual(snapshot_count, 1)
            self.assertEqual(mark_count, 1)
            self.assertEqual(index_count, 1)
            self.assertEqual(raw_payload, "10005")
            self.assertEqual(ledger_count, 1)
            self.assertEqual(funding_pnl_count, 1)
            self.assertEqual(first_risk_limit_id, second_risk_limit_id)
            self.assertEqual(risk_limit_row[0], 1)
            self.assertEqual(risk_limit_row[1], Decimal("30000.000000000000"))
            self.assertEqual(risk_event_count, 1)
            self.assertEqual(log_count, 1)
            self.assertEqual(ingestion_job_count, 1)
        finally:
            transaction.rollback()
            connection.close()


if __name__ == "__main__":
    unittest.main()
