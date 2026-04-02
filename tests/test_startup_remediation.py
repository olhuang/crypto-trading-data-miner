from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import api.app as app_module
from api.app import create_app
from config import settings
from ingestion.base import JsonHttpClient, JsonHttpResponse
from ingestion.binance.public_rest import BinancePublicRestClient
from models.market import BarEvent
from services import startup_remediation as remediation_module
from storage.db import connection_scope, transaction_scope
from storage.repositories.market_data import BarRepository
from storage.repositories.ops import DataGapRepository


class StartupRemediationTests(unittest.TestCase):
    @staticmethod
    def _transport(url: str, params):
        if url.endswith("/fapi/v1/klines"):
            start_time_ms = params.get("startTime")
            end_time_ms = params.get("endTime")
            return JsonHttpResponse(
                200,
                [
                    [
                        start_time_ms,
                        "84210.10",
                        "84255.00",
                        "84190.50",
                        "84250.12",
                        "152.2301",
                        end_time_ms or start_time_ms + 59999,
                        "12824611.91",
                        1289,
                    ]
                ],
            )
        raise AssertionError(f"unexpected url: {url} params={params}")

    def setUp(self) -> None:
        self.original_app_env = settings.app_env
        self.original_enable_startup_gap_remediation = settings.enable_startup_gap_remediation
        self.original_symbols = settings.startup_gap_remediation_symbols
        self.original_lookback = settings.startup_gap_remediation_lookback_hours

    def tearDown(self) -> None:
        settings.app_env = self.original_app_env
        settings.enable_startup_gap_remediation = self.original_enable_startup_gap_remediation
        settings.startup_gap_remediation_symbols = self.original_symbols
        settings.startup_gap_remediation_lookback_hours = self.original_lookback

    def test_run_startup_gap_remediation_backfills_and_resolves_gap(self) -> None:
        start_time = datetime.now(timezone.utc).replace(second=0, microsecond=0) - timedelta(minutes=2)
        gap_time = start_time + timedelta(minutes=1)
        end_time = start_time + timedelta(minutes=2)

        with transaction_scope() as connection:
            connection.exec_driver_sql(
                """
                delete from ops.data_gaps
                where instrument_id = (
                    select instrument.instrument_id
                    from ref.instruments instrument
                    join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                    where exchange.exchange_code = %s and instrument.unified_symbol = %s
                    limit 1
                )
                  and data_type = 'bars_1m'
                  and gap_start between %s and %s
                """,
                ("binance", "BTCUSDT_PERP", start_time, end_time),
            )
            connection.exec_driver_sql(
                """
                delete from md.bars_1m
                where instrument_id = (
                    select instrument.instrument_id
                    from ref.instruments instrument
                    join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                    where exchange.exchange_code = %s and instrument.unified_symbol = %s
                    limit 1
                )
                  and bar_time between %s and %s
                """,
                ("binance", "BTCUSDT_PERP", start_time, end_time),
            )

            BarRepository().upsert(
                connection,
                BarEvent(
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_PERP",
                    ingest_time=start_time,
                    bar_interval="1m",
                    bar_time=start_time,
                    event_time=start_time,
                    open="84000.00",
                    high="84020.00",
                    low="83980.00",
                    close="84010.00",
                    volume="10.0",
                    quote_volume="840100.0",
                    trade_count=100,
                ),
            )
            BarRepository().upsert(
                connection,
                BarEvent(
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_PERP",
                    ingest_time=end_time,
                    bar_interval="1m",
                    bar_time=end_time,
                    event_time=end_time,
                    open="84010.00",
                    high="84040.00",
                    low="84005.00",
                    close="84030.00",
                    volume="12.0",
                    quote_volume="1008360.0",
                    trade_count=120,
                ),
            )

        client = BinancePublicRestClient(http_client=JsonHttpClient(self._transport))
        result = remediation_module.run_startup_gap_remediation(
            exchange_code="binance",
            unified_symbols=["BTCUSDT_PERP"],
            lookback_hours=0.05,
            client=client,
            observed_at=end_time,
        )

        self.assertEqual(result.symbols_checked, 1)
        self.assertGreaterEqual(result.gaps_detected, 1)
        self.assertGreaterEqual(result.gaps_resolved, 1)
        self.assertGreaterEqual(result.backfill_runs, 1)

        with connection_scope() as connection:
            backfilled_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.bars_1m bar
                join ref.instruments instrument on instrument.instrument_id = bar.instrument_id
                join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                where instrument.unified_symbol = %s
                  and exchange.exchange_code = %s
                  and bar.bar_time = %s
                """,
                ("BTCUSDT_PERP", "binance", gap_time),
            ).scalar_one()
            open_gaps = DataGapRepository().list_recent(
                connection,
                data_type="bars_1m",
                status="open",
                exchange_code="binance",
                unified_symbol="BTCUSDT_PERP",
                limit=200,
            )
            resolved_gaps = connection.exec_driver_sql(
                """
                select count(*)
                from ops.data_gaps gap
                join ref.instruments instrument on instrument.instrument_id = gap.instrument_id
                join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                where exchange.exchange_code = %s
                  and instrument.unified_symbol = %s
                  and gap.gap_start = %s
                  and gap.status = 'resolved'
                """,
                ("binance", "BTCUSDT_PERP", gap_time),
            ).scalar_one()
            target_open_gaps = [
                gap for gap in open_gaps if gap["gap_start"] == gap_time
            ]

            self.assertEqual(backfilled_count, 1)
            self.assertEqual(len(target_open_gaps), 0)
            self.assertGreaterEqual(resolved_gaps, 1)

    def test_startup_hook_only_runs_when_local_flag_is_enabled(self) -> None:
        original_runner = app_module.run_startup_gap_remediation
        call_counter = {"count": 0}

        def _fake_runner():
            call_counter["count"] += 1
            return None

        app_module.run_startup_gap_remediation = _fake_runner
        try:
            settings.app_env = "local"
            settings.enable_startup_gap_remediation = True
            app = create_app()
            async def _run_lifespan(application):
                async with application.router.lifespan_context(application):
                    pass

            asyncio.run(_run_lifespan(app))

            self.assertEqual(call_counter["count"], 1)

            settings.app_env = "staging"
            settings.enable_startup_gap_remediation = True
            app = create_app()
            asyncio.run(_run_lifespan(app))

            self.assertEqual(call_counter["count"], 1)
        finally:
            app_module.run_startup_gap_remediation = original_runner


if __name__ == "__main__":
    unittest.main()
