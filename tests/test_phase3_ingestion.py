from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ingestion.base import JsonHttpClient, JsonHttpResponse
from ingestion.binance.public_rest import BinancePublicRestClient
from jobs.backfill_bars import run_bar_backfill
from jobs.refresh_market_snapshots import run_market_snapshot_refresh
from jobs.scheduler import phase3_schedule_plan
from jobs.sync_instruments import run_instrument_sync
from runtime.binance_trade_stream import BinanceTradeStreamProcessor
from storage.db import connection_scope
from storage.repositories.ops import IngestionJobRepository


class Phase3IngestionTests(unittest.TestCase):
    @staticmethod
    def _transport(url: str, params):
        if url.endswith("/api/v3/exchangeInfo"):
            return JsonHttpResponse(
                200,
                {
                    "symbols": [
                        {
                            "symbol": "BTCUSDT",
                            "baseAsset": "BTC",
                            "quoteAsset": "USDT",
                            "status": "TRADING",
                            "filters": [
                                {"filterType": "PRICE_FILTER", "tickSize": "0.10"},
                                {"filterType": "LOT_SIZE", "stepSize": "0.00010", "minQty": "0.00010"},
                                {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
                            ],
                        },
                        {
                            "symbol": "BTCUSDC",
                            "baseAsset": "BTC",
                            "quoteAsset": "USDC",
                            "status": "TRADING",
                            "filters": [
                                {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                                {"filterType": "LOT_SIZE", "stepSize": "0.00010", "minQty": "0.00010"},
                                {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
                            ],
                        },
                    ]
                },
            )
        if url.endswith("/fapi/v1/exchangeInfo"):
            return JsonHttpResponse(
                200,
                {
                    "symbols": [
                        {
                            "symbol": "BTCUSDT",
                            "contractType": "PERPETUAL",
                            "baseAsset": "BTC",
                            "quoteAsset": "USDT",
                            "marginAsset": "USDT",
                            "status": "TRADING",
                            "onboardDate": 1712011200000,
                            "filters": [
                                {"filterType": "PRICE_FILTER", "tickSize": "0.10"},
                                {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"},
                                {"filterType": "MIN_NOTIONAL", "notional": "5"},
                            ],
                        },
                        {
                            "symbol": "ETHUSDC",
                            "contractType": "PERPETUAL",
                            "baseAsset": "ETH",
                            "quoteAsset": "USDC",
                            "marginAsset": "USDC",
                            "status": "TRADING",
                            "onboardDate": 1712011200000,
                            "filters": [
                                {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                                {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"},
                                {"filterType": "MIN_NOTIONAL", "notional": "5"},
                            ],
                        },
                    ]
                },
            )
        if url.endswith("/fapi/v1/klines"):
            return JsonHttpResponse(
                200,
                [
                    [
                        1712061240000,
                        "84210.10",
                        "84255.00",
                        "84190.50",
                        "84250.12",
                        "152.2301",
                        1712061299999,
                        "12824611.91",
                        1289,
                    ]
                ],
            )
        if url.endswith("/fapi/v1/fundingRate"):
            return JsonHttpResponse(
                200,
                [
                    {
                        "symbol": "BTCUSDT",
                        "fundingTime": 1712044800000,
                        "fundingRate": "0.00010000",
                        "markPrice": "84195.22",
                    }
                ],
            )
        if url.endswith("/fapi/v1/openInterest"):
            return JsonHttpResponse(200, {"symbol": "BTCUSDT", "openInterest": "18542.991"})
        if url.endswith("/fapi/v1/premiumIndex"):
            return JsonHttpResponse(
                200,
                {
                    "symbol": "BTCUSDT",
                    "markPrice": "84244.18",
                    "indexPrice": "84240.01",
                    "time": 1712061242000,
                },
            )
        raise AssertionError(f"unexpected url: {url} params={params}")

    def _client(self) -> BinancePublicRestClient:
        return BinancePublicRestClient(http_client=JsonHttpClient(self._transport))

    def test_instrument_sync_backfill_and_snapshot_refresh_persist_phase3_data(self) -> None:
        client = self._client()
        sync_result = run_instrument_sync(client=client, requested_by="test-user")
        self.assertEqual(sync_result.status, "succeeded")
        self.assertGreaterEqual(sync_result.summary["instruments_seen"], 4)

        backfill_result = run_bar_backfill(
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_PERP",
            interval="1m",
            start_time=datetime(2026, 4, 2, 12, 34, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 2, 12, 35, tzinfo=timezone.utc),
            client=client,
            requested_by="test-user",
        )
        self.assertEqual(backfill_result.status, "succeeded")
        self.assertEqual(backfill_result.rows_written, 1)

        refresh_result = run_market_snapshot_refresh(
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_PERP",
            client=client,
            requested_by="test-user",
            funding_start_time=datetime(2026, 4, 2, 8, 0, tzinfo=timezone.utc),
            funding_end_time=datetime(2026, 4, 2, 8, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(refresh_result.status, "succeeded")
        self.assertEqual(refresh_result.records_written, 4)

        with connection_scope() as connection:
            btcusdc_spot = connection.exec_driver_sql(
                """
                select count(*)
                from ref.instruments instrument
                join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                where exchange.exchange_code = %s
                  and instrument.unified_symbol = %s
                """,
                ("binance", "BTCUSDC_SPOT"),
            ).scalar_one()
            ethusdc_perp = connection.exec_driver_sql(
                """
                select count(*)
                from ref.instruments instrument
                join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                where exchange.exchange_code = %s
                  and instrument.unified_symbol = %s
                """,
                ("binance", "ETHUSDC_PERP"),
            ).scalar_one()
            bar_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.bars_1m bar
                join ref.instruments instrument on instrument.instrument_id = bar.instrument_id
                where instrument.unified_symbol = %s
                """,
                ("BTCUSDT_PERP",),
            ).scalar_one()
            funding_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.funding_rates rate
                join ref.instruments instrument on instrument.instrument_id = rate.instrument_id
                where instrument.unified_symbol = %s
                """,
                ("BTCUSDT_PERP",),
            ).scalar_one()
            oi_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.open_interest oi
                join ref.instruments instrument on instrument.instrument_id = oi.instrument_id
                where instrument.unified_symbol = %s
                """,
                ("BTCUSDT_PERP",),
            ).scalar_one()
            mark_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.mark_prices price
                join ref.instruments instrument on instrument.instrument_id = price.instrument_id
                where instrument.unified_symbol = %s
                """,
                ("BTCUSDT_PERP",),
            ).scalar_one()
            index_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.index_prices price
                join ref.instruments instrument on instrument.instrument_id = price.instrument_id
                where instrument.unified_symbol = %s
                """,
                ("BTCUSDT_PERP",),
            ).scalar_one()

            self.assertEqual(btcusdc_spot, 1)
            self.assertEqual(ethusdc_perp, 1)
            self.assertGreaterEqual(bar_count, 1)
            self.assertGreaterEqual(funding_count, 1)
            self.assertGreaterEqual(oi_count, 1)
            self.assertGreaterEqual(mark_count, 1)
            self.assertGreaterEqual(index_count, 1)

            sync_job = IngestionJobRepository().get_job(connection, sync_result.ingestion_job_id)
            self.assertEqual(sync_job["status"], "succeeded")
            self.assertIn("diffs", sync_job["metadata_json"])

    def test_trade_stream_processor_persists_trade_raw_mark_and_liquidation_events(self) -> None:
        processor = BinanceTradeStreamProcessor()
        result = processor.consume_messages(
            [
                {
                    "stream": "btcusdt@trade",
                    "data": {
                        "e": "trade",
                        "E": 1712061296900,
                        "s": "BTCUSDT",
                        "t": 123456789,
                        "p": "84250.12",
                        "q": "0.015",
                        "T": 1712061296789,
                        "m": False,
                    },
                },
                {
                    "stream": "btcusdt@markPrice",
                    "data": {
                        "e": "markPriceUpdate",
                        "E": 1712061242000,
                        "s": "BTCUSDT",
                        "p": "84244.18",
                        "i": "84240.01",
                    },
                },
                {
                    "stream": "btcusdt@forceOrder",
                    "data": {
                        "e": "forceOrder",
                        "E": 1712061300000,
                        "o": {
                            "s": "BTCUSDT",
                            "S": "SELL",
                            "p": "84110.50",
                            "q": "12.50",
                            "T": 1712061300000,
                        },
                    },
                },
            ]
        )

        self.assertEqual(result.messages_seen, 3)
        self.assertEqual(result.trades_written, 1)
        self.assertEqual(result.mark_prices_written, 1)
        self.assertEqual(result.liquidations_written, 1)
        self.assertEqual(result.raw_events_written, 3)

        with connection_scope() as connection:
            trade_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.trades trade
                join ref.instruments instrument on instrument.instrument_id = trade.instrument_id
                where instrument.unified_symbol = %s
                  and trade.exchange_trade_id = %s
                """,
                ("BTCUSDT_PERP", "123456789"),
            ).scalar_one()
            raw_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.raw_market_events
                where channel in (%s, %s, %s)
                """,
                ("btcusdt@trade", "btcusdt@markPrice", "btcusdt@forceOrder"),
            ).scalar_one()
            ws_event_count = connection.exec_driver_sql(
                """
                select count(*)
                from ops.ws_connection_events
                where service_name = %s
                """,
                ("binance_trade_stream",),
            ).scalar_one()

            self.assertEqual(trade_count, 1)
            self.assertGreaterEqual(raw_count, 3)
            self.assertGreaterEqual(ws_event_count, 2)

    def test_phase3_schedule_plan_has_reference_and_market_jobs(self) -> None:
        job_ids = {definition.job_id for definition in phase3_schedule_plan()}
        self.assertIn("binance_instrument_sync_hourly", job_ids)
        self.assertIn("binance_market_snapshot_refresh", job_ids)


if __name__ == "__main__":
    unittest.main()
