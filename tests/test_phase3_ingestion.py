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
from jobs.remediate_market_snapshots import build_market_snapshot_remediation_plan, run_market_snapshot_remediation
from jobs.refresh_market_snapshots import run_market_snapshot_refresh
from jobs.scheduler import phase3_schedule_plan, phase4_schedule_plan
from jobs.sync_instruments import run_instrument_sync
from runtime.binance_trade_stream import BinanceTradeStreamProcessor
from storage.db import connection_scope, transaction_scope
from storage.repositories.ops import IngestionJobRepository


class Phase3IngestionTests(unittest.TestCase):
    @staticmethod
    def _cleanup_market_snapshot_history_window(*, start_time: datetime, end_time: datetime) -> None:
        with transaction_scope() as connection:
            for table_name in (
                "md.open_interest",
                "md.mark_prices",
                "md.index_prices",
                "md.global_long_short_account_ratios",
                "md.top_trader_long_short_account_ratios",
                "md.top_trader_long_short_position_ratios",
                "md.taker_long_short_ratios",
            ):
                connection.exec_driver_sql(
                    f"""
                    delete from {table_name}
                    where instrument_id = (
                        select instrument.instrument_id
                        from ref.instruments instrument
                        join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                        where exchange.exchange_code = %s and instrument.unified_symbol = %s
                        limit 1
                    )
                      and ts between %s and %s
                    """,
                    ("binance", "BTCUSDT_PERP", start_time, end_time),
                )

    @staticmethod
    def _transport(url: str, params):
        if url.endswith("/fapi/v1/klines") and params and params.get("startTime") == 1712061300000:
            return JsonHttpResponse(200, [])
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
                        {
                            "symbol": "BNBUSDT",
                            "baseAsset": "BNB",
                            "quoteAsset": "USDT",
                            "status": "TRADING",
                            "filters": [
                                {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                                {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"},
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
        if url.endswith("/api/v3/klines"):
            return JsonHttpResponse(
                200,
                [
                    [
                        1712061240000,
                        "61250.10",
                        "61280.00",
                        "61200.50",
                        "61270.12",
                        "52.2301",
                        1712061299999,
                        "3204611.91",
                        689,
                    ]
                ],
            )
        if url.endswith("/fapi/v1/fundingRate") and params and params.get("startTime") == 1712044800001:
            return JsonHttpResponse(200, [])
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
        if url.endswith("/futures/data/openInterestHist"):
            if params and params.get("startTime") == 1712061300001:
                return JsonHttpResponse(200, [])
            return JsonHttpResponse(
                200,
                [
                    {
                        "symbol": "BTCUSDT",
                        "sumOpenInterest": "18540.000",
                        "timestamp": 1712061000000,
                    },
                    {
                        "symbol": "BTCUSDT",
                        "sumOpenInterest": "18542.991",
                        "timestamp": 1712061300000,
                    },
                ],
            )
        if url.endswith("/futures/data/globalLongShortAccountRatio"):
            if params and params.get("startTime") == 1712061300001:
                return JsonHttpResponse(200, [])
            return JsonHttpResponse(
                200,
                [
                    {
                        "symbol": "BTCUSDT",
                        "longShortRatio": "1.2222",
                        "longAccount": "0.55",
                        "shortAccount": "0.45",
                        "timestamp": 1712061000000,
                    },
                    {
                        "symbol": "BTCUSDT",
                        "longShortRatio": "1.1050",
                        "longAccount": "0.525",
                        "shortAccount": "0.475",
                        "timestamp": 1712061300000,
                    },
                ],
            )
        if url.endswith("/futures/data/topLongShortAccountRatio"):
            if params and params.get("startTime") == 1712061300001:
                return JsonHttpResponse(200, [])
            return JsonHttpResponse(
                200,
                [
                    {
                        "symbol": "BTCUSDT",
                        "longShortRatio": "1.45",
                        "longAccount": "0.592",
                        "shortAccount": "0.408",
                        "timestamp": 1712061000000,
                    },
                    {
                        "symbol": "BTCUSDT",
                        "longShortRatio": "1.41",
                        "longAccount": "0.585",
                        "shortAccount": "0.415",
                        "timestamp": 1712061300000,
                    },
                ],
            )
        if url.endswith("/futures/data/topLongShortPositionRatio"):
            if params and params.get("startTime") == 1712061300001:
                return JsonHttpResponse(200, [])
            return JsonHttpResponse(
                200,
                [
                    {
                        "symbol": "BTCUSDT",
                        "longShortRatio": "1.72",
                        "longAccount": "0.632",
                        "shortAccount": "0.368",
                        "timestamp": 1712061000000,
                    },
                    {
                        "symbol": "BTCUSDT",
                        "longShortRatio": "1.69",
                        "longAccount": "0.628",
                        "shortAccount": "0.372",
                        "timestamp": 1712061300000,
                    },
                ],
            )
        if url.endswith("/futures/data/takerlongshortRatio"):
            if params and params.get("startTime") == 1712061300001:
                return JsonHttpResponse(200, [])
            return JsonHttpResponse(
                200,
                [
                    {
                        "buySellRatio": "1.33",
                        "buyVol": "1234.5",
                        "sellVol": "928.2",
                        "timestamp": 1712061000000,
                    },
                    {
                        "buySellRatio": "0.97",
                        "buyVol": "990.0",
                        "sellVol": "1020.1",
                        "timestamp": 1712061300000,
                    },
                ],
            )
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
        if url.endswith("/fapi/v1/markPriceKlines"):
            if params and params.get("startTime") == 1712061300001:
                return JsonHttpResponse(200, [])
            return JsonHttpResponse(
                200,
                [
                    [
                        1712061000000,
                        "84200.00",
                        "84210.00",
                        "84190.00",
                        "84205.50",
                        "0",
                        1712061059999,
                    ],
                    [
                        1712061300000,
                        "84240.00",
                        "84250.00",
                        "84230.00",
                        "84244.18",
                        "0",
                        1712061359999,
                    ],
                ],
            )
        if url.endswith("/fapi/v1/indexPriceKlines"):
            if params and params.get("pair") != "BTCUSDT":
                raise AssertionError(f"unexpected pair for indexPriceKlines: {params}")
            if params and params.get("startTime") == 1712061300001:
                return JsonHttpResponse(200, [])
            return JsonHttpResponse(
                200,
                [
                    [
                        1712061000000,
                        "84195.00",
                        "84205.00",
                        "84185.00",
                        "84201.25",
                        "0",
                        1712061059999,
                    ],
                    [
                        1712061300000,
                        "84235.00",
                        "84245.00",
                        "84225.00",
                        "84240.01",
                        "0",
                        1712061359999,
                    ],
                ],
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
        self.assertEqual(refresh_result.history_rows_written, 3)

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
            snapshot_mark_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.mark_prices price
                join ref.instruments instrument on instrument.instrument_id = price.instrument_id
                where instrument.unified_symbol = %s
                  and price.ts = %s
                  and price.mark_price = %s
                """,
                (
                    "BTCUSDT_PERP",
                    datetime.fromtimestamp(1712061242000 / 1000, tz=timezone.utc),
                    "84244.18",
                ),
            ).scalar_one()
            snapshot_index_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.index_prices price
                join ref.instruments instrument on instrument.instrument_id = price.instrument_id
                where instrument.unified_symbol = %s
                  and price.ts = %s
                  and price.index_price = %s
                """,
                (
                    "BTCUSDT_PERP",
                    datetime.fromtimestamp(1712061242000 / 1000, tz=timezone.utc),
                    "84240.01",
                ),
            ).scalar_one()

            self.assertEqual(btcusdc_spot, 1)
            self.assertEqual(ethusdc_perp, 1)
            self.assertGreaterEqual(bar_count, 1)
            self.assertGreaterEqual(funding_count, 1)
            self.assertGreaterEqual(oi_count, 1)
            self.assertGreaterEqual(mark_count, 1)
            self.assertGreaterEqual(index_count, 1)
            self.assertEqual(snapshot_mark_count, 1)
            self.assertEqual(snapshot_index_count, 1)
            bnb_asset = connection.exec_driver_sql(
                "select count(*) from ref.assets where asset_code = %s",
                ("BNB",),
            ).scalar_one()
            self.assertEqual(bnb_asset, 1)

            sync_job = IngestionJobRepository().get_job(connection, sync_result.ingestion_job_id)
            self.assertEqual(sync_job["status"], "succeeded")
            self.assertIn("diffs", sync_job["metadata_json"])
            self.assertGreaterEqual(sync_job["metadata_json"]["summary"]["assets_touched"], 4)

    def test_market_snapshot_refresh_supports_historical_oi_mark_and_index_windows(self) -> None:
        fixture_start = datetime.fromtimestamp(1712061000000 / 1000, tz=timezone.utc)
        fixture_end = datetime.fromtimestamp(1712061300000 / 1000, tz=timezone.utc)
        self.addCleanup(
            self._cleanup_market_snapshot_history_window,
            start_time=fixture_start,
            end_time=fixture_end,
        )
        client = self._client()
        result = run_market_snapshot_refresh(
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_PERP",
            client=client,
            requested_by="test-user",
            funding_start_time=datetime(2026, 4, 2, 8, 0, tzinfo=timezone.utc),
            funding_end_time=datetime(2026, 4, 2, 8, 1, tzinfo=timezone.utc),
            history_start_time=datetime(2026, 4, 2, 12, 30, tzinfo=timezone.utc),
            history_end_time=datetime(2026, 4, 2, 12, 35, tzinfo=timezone.utc),
        )

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.records_written, 7)
        self.assertEqual(result.history_rows_written, 6)

        with connection_scope() as connection:
            oi_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.open_interest oi
                join ref.instruments instrument on instrument.instrument_id = oi.instrument_id
                where instrument.unified_symbol = %s
                  and oi.ts in (%s, %s)
                """,
                ("BTCUSDT_PERP", fixture_start, fixture_end),
            ).scalar_one()
            mark_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.mark_prices price
                join ref.instruments instrument on instrument.instrument_id = price.instrument_id
                where instrument.unified_symbol = %s
                  and price.ts in (%s, %s)
                """,
                ("BTCUSDT_PERP", fixture_start, fixture_end),
            ).scalar_one()
            index_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.index_prices price
                join ref.instruments instrument on instrument.instrument_id = price.instrument_id
                where instrument.unified_symbol = %s
                  and price.ts in (%s, %s)
                """,
                ("BTCUSDT_PERP", fixture_start, fixture_end),
            ).scalar_one()

        self.assertEqual(oi_count, 2)
        self.assertEqual(mark_count, 2)
        self.assertEqual(index_count, 2)

    def test_market_snapshot_refresh_supports_historical_sentiment_ratio_windows(self) -> None:
        fixture_start = datetime.fromtimestamp(1712061000000 / 1000, tz=timezone.utc)
        fixture_end = datetime.fromtimestamp(1712061300000 / 1000, tz=timezone.utc)
        self.addCleanup(
            self._cleanup_market_snapshot_history_window,
            start_time=fixture_start,
            end_time=fixture_end,
        )
        client = self._client()
        result = run_market_snapshot_refresh(
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_PERP",
            client=client,
            requested_by="test-user",
            history_start_time=datetime(2026, 4, 2, 12, 30, tzinfo=timezone.utc),
            history_end_time=datetime(2026, 4, 2, 12, 35, tzinfo=timezone.utc),
            sentiment_ratio_period="5m",
            include_funding=False,
            include_open_interest=False,
            include_mark_price=False,
            include_index_price=False,
            include_global_long_short_account_ratio=True,
            include_top_trader_long_short_account_ratio=True,
            include_top_trader_long_short_position_ratio=True,
            include_taker_long_short_ratio=True,
        )

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.records_written, 8)
        self.assertEqual(result.history_rows_written, 8)

        with connection_scope() as connection:
            global_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.global_long_short_account_ratios ratio
                join ref.instruments instrument on instrument.instrument_id = ratio.instrument_id
                where instrument.unified_symbol = %s
                  and ratio.period_code = %s
                  and ratio.ts in (%s, %s)
                """,
                (
                    "BTCUSDT_PERP",
                    "5m",
                    fixture_start,
                    fixture_end,
                ),
            ).scalar_one()
            top_account_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.top_trader_long_short_account_ratios ratio
                join ref.instruments instrument on instrument.instrument_id = ratio.instrument_id
                where instrument.unified_symbol = %s
                  and ratio.period_code = %s
                  and ratio.ts in (%s, %s)
                """,
                (
                    "BTCUSDT_PERP",
                    "5m",
                    fixture_start,
                    fixture_end,
                ),
            ).scalar_one()
            top_position_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.top_trader_long_short_position_ratios ratio
                join ref.instruments instrument on instrument.instrument_id = ratio.instrument_id
                where instrument.unified_symbol = %s
                  and ratio.period_code = %s
                  and ratio.ts in (%s, %s)
                """,
                (
                    "BTCUSDT_PERP",
                    "5m",
                    fixture_start,
                    fixture_end,
                ),
            ).scalar_one()
            taker_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.taker_long_short_ratios ratio
                join ref.instruments instrument on instrument.instrument_id = ratio.instrument_id
                where instrument.unified_symbol = %s
                  and ratio.period_code = %s
                  and ratio.ts in (%s, %s)
                """,
                (
                    "BTCUSDT_PERP",
                    "5m",
                    fixture_start,
                    fixture_end,
                ),
            ).scalar_one()

        self.assertEqual(global_count, 2)
        self.assertEqual(top_account_count, 2)
        self.assertEqual(top_position_count, 2)
        self.assertEqual(taker_count, 2)

    def test_market_snapshot_refresh_recent_history_mode_persists_canonical_oi_and_sentiment_rows(self) -> None:
        fixture_start = datetime.fromtimestamp(1712061000000 / 1000, tz=timezone.utc)
        fixture_end = datetime.fromtimestamp(1712061300000 / 1000, tz=timezone.utc)
        self.addCleanup(
            self._cleanup_market_snapshot_history_window,
            start_time=fixture_start,
            end_time=fixture_end,
        )
        client = self._client()

        result = run_market_snapshot_refresh(
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_PERP",
            client=client,
            requested_by="test-user",
            include_funding=False,
            include_mark_price=False,
            include_index_price=False,
            include_global_long_short_account_ratio=True,
            include_top_trader_long_short_account_ratio=True,
            include_top_trader_long_short_position_ratio=True,
            include_taker_long_short_ratio=True,
            observed_at=fixture_end,
            use_recent_history_for_retention_limited=True,
            retention_history_lookback_minutes=60,
        )

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.records_written, 10)
        self.assertEqual(result.history_rows_written, 10)

        with connection_scope() as connection:
            open_interest_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.open_interest oi
                join ref.instruments instrument on instrument.instrument_id = oi.instrument_id
                where instrument.unified_symbol = %s
                  and oi.ts in (%s, %s)
                """,
                ("BTCUSDT_PERP", fixture_start, fixture_end),
            ).scalar_one()
            taker_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.taker_long_short_ratios ratio
                join ref.instruments instrument on instrument.instrument_id = ratio.instrument_id
                where instrument.unified_symbol = %s
                  and ratio.period_code = %s
                  and ratio.ts in (%s, %s)
                """,
                ("BTCUSDT_PERP", "5m", fixture_start, fixture_end),
            ).scalar_one()

        self.assertEqual(open_interest_count, 2)
        self.assertEqual(taker_count, 2)

    def test_sentiment_ratio_history_fetch_and_normalize(self) -> None:
        client = self._client()
        start_time = datetime(2026, 4, 2, 12, 30, tzinfo=timezone.utc)
        end_time = datetime(2026, 4, 2, 12, 35, tzinfo=timezone.utc)

        global_rows = client.fetch_global_long_short_account_ratio_history(
            "BTCUSDT",
            period="5m",
            start_time=start_time,
            end_time=end_time,
        )
        top_account_rows = client.fetch_top_trader_long_short_account_ratio_history(
            "BTCUSDT",
            period="5m",
            start_time=start_time,
            end_time=end_time,
        )
        top_position_rows = client.fetch_top_trader_long_short_position_ratio_history(
            "BTCUSDT",
            period="5m",
            start_time=start_time,
            end_time=end_time,
        )
        taker_rows = client.fetch_taker_long_short_ratio_history(
            "BTCUSDT",
            period="5m",
            start_time=start_time,
            end_time=end_time,
        )

        self.assertEqual(len(global_rows), 2)
        self.assertEqual(len(top_account_rows), 2)
        self.assertEqual(len(top_position_rows), 2)
        self.assertEqual(len(taker_rows), 2)

        global_events = client.normalize_global_long_short_account_ratios(
            "BTCUSDT",
            global_rows,
            period="5m",
            unified_symbol="BTCUSDT_PERP",
        )
        top_account_events = client.normalize_top_trader_long_short_account_ratios(
            "BTCUSDT",
            top_account_rows,
            period="5m",
            unified_symbol="BTCUSDT_PERP",
        )
        top_position_events = client.normalize_top_trader_long_short_position_ratios(
            "BTCUSDT",
            top_position_rows,
            period="5m",
            unified_symbol="BTCUSDT_PERP",
        )
        taker_events = client.normalize_taker_long_short_ratios(
            "BTCUSDT",
            taker_rows,
            period="5m",
            unified_symbol="BTCUSDT_PERP",
        )

        self.assertEqual(global_events[0].period_code, "5m")
        self.assertEqual(str(global_events[0].long_short_ratio), "1.2222")
        self.assertEqual(str(global_events[0].long_account_ratio), "0.55")
        self.assertEqual(str(top_account_events[0].long_short_ratio), "1.45")
        self.assertEqual(str(top_position_events[0].long_short_ratio), "1.72")
        self.assertEqual(str(taker_events[0].buy_sell_ratio), "1.33")
        self.assertEqual(str(taker_events[0].buy_vol), "1234.5")
        self.assertEqual(str(taker_events[0].sell_vol), "928.2")

    def test_spot_bar_backfill_uses_spot_klines_endpoint(self) -> None:
        client = self._client()
        run_instrument_sync(client=client, requested_by="test-user")

        result = run_bar_backfill(
            symbol="BTCUSDC",
            unified_symbol="BTCUSDC_SPOT",
            interval="1m",
            start_time=datetime(2026, 4, 2, 12, 34, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 2, 12, 35, tzinfo=timezone.utc),
            client=client,
            requested_by="test-user",
        )

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.rows_written, 1)

        with connection_scope() as connection:
            bar_count = connection.exec_driver_sql(
                """
                select count(*)
                from md.bars_1m bar
                join ref.instruments instrument on instrument.instrument_id = bar.instrument_id
                where instrument.unified_symbol = %s
                """,
                ("BTCUSDC_SPOT",),
            ).scalar_one()

        self.assertGreaterEqual(bar_count, 1)

    def test_paginated_market_history_fetches_multiple_pages(self) -> None:
        call_counts = {
            "futures_klines": 0,
            "funding": 0,
            "oi": 0,
            "mark": 0,
            "index": 0,
        }

        def transport(url: str, params):
            if url.endswith("/fapi/v1/klines"):
                call_counts["futures_klines"] += 1
                if call_counts["futures_klines"] == 1:
                    return JsonHttpResponse(
                        200,
                        [
                            [1000, "1", "1", "1", "1", "1", 1999, "1", 1],
                            [2000, "1", "1", "1", "1", "1", 2999, "1", 1],
                        ],
                    )
                return JsonHttpResponse(200, [])
            if url.endswith("/fapi/v1/fundingRate"):
                call_counts["funding"] += 1
                if call_counts["funding"] == 1:
                    return JsonHttpResponse(
                        200,
                        [
                            {"symbol": "BTCUSDT", "fundingTime": 1000, "fundingRate": "0.001", "markPrice": "1"},
                            {"symbol": "BTCUSDT", "fundingTime": 2000, "fundingRate": "0.001", "markPrice": "1"},
                        ],
                    )
                return JsonHttpResponse(200, [])
            if url.endswith("/futures/data/openInterestHist"):
                call_counts["oi"] += 1
                if call_counts["oi"] == 1:
                    return JsonHttpResponse(
                        200,
                        [
                            {"symbol": "BTCUSDT", "sumOpenInterest": "1", "timestamp": 1000},
                            {"symbol": "BTCUSDT", "sumOpenInterest": "1", "timestamp": 2000},
                        ],
                    )
                return JsonHttpResponse(200, [])
            if url.endswith("/fapi/v1/markPriceKlines"):
                call_counts["mark"] += 1
                if call_counts["mark"] == 1:
                    return JsonHttpResponse(
                        200,
                        [
                            [1000, "1", "1", "1", "1", "0", 1999],
                            [2000, "1", "1", "1", "1", "0", 2999],
                        ],
                    )
                return JsonHttpResponse(200, [])
            if url.endswith("/fapi/v1/indexPriceKlines"):
                call_counts["index"] += 1
                self.assertEqual(params.get("pair"), "BTCUSDT")
                if call_counts["index"] == 1:
                    return JsonHttpResponse(
                        200,
                        [
                            [1000, "1", "1", "1", "1", "0", 1999],
                            [2000, "1", "1", "1", "1", "0", 2999],
                        ],
                    )
                return JsonHttpResponse(200, [])
            raise AssertionError(f"unexpected url: {url} params={params}")

        client = BinancePublicRestClient(http_client=JsonHttpClient(transport))
        bars = client.fetch_klines(
            "BTCUSDT",
            interval="1m",
            start_time=datetime.fromtimestamp(1, tz=timezone.utc),
            end_time=datetime.fromtimestamp(10, tz=timezone.utc),
            limit=2,
        )
        funding = client.fetch_funding_rate_history(
            "BTCUSDT",
            start_time=datetime.fromtimestamp(1, tz=timezone.utc),
            end_time=datetime.fromtimestamp(10, tz=timezone.utc),
            limit=2,
        )
        oi = client.fetch_open_interest_history(
            "BTCUSDT",
            period="5m",
            start_time=datetime.fromtimestamp(1, tz=timezone.utc),
            end_time=datetime.fromtimestamp(10, tz=timezone.utc),
            limit=2,
        )
        mark = client.fetch_mark_price_klines(
            "BTCUSDT",
            interval="1m",
            start_time=datetime.fromtimestamp(1, tz=timezone.utc),
            end_time=datetime.fromtimestamp(10, tz=timezone.utc),
            limit=2,
        )
        index = client.fetch_index_price_klines(
            "BTCUSDT",
            interval="1m",
            start_time=datetime.fromtimestamp(1, tz=timezone.utc),
            end_time=datetime.fromtimestamp(10, tz=timezone.utc),
            limit=2,
        )

        self.assertEqual(len(bars), 2)
        self.assertEqual(len(funding), 2)
        self.assertEqual(len(oi), 2)
        self.assertEqual(len(mark), 2)
        self.assertEqual(len(index), 2)
        self.assertGreaterEqual(call_counts["futures_klines"], 2)
        self.assertGreaterEqual(call_counts["funding"], 2)
        self.assertGreaterEqual(call_counts["oi"], 2)
        self.assertGreaterEqual(call_counts["mark"], 2)
        self.assertGreaterEqual(call_counts["index"], 2)

    def test_market_snapshot_remediation_plans_and_runs_scheduler_ready_refresh(self) -> None:
        client = self._client()
        observed_at = datetime(2035, 4, 2, 12, 35, tzinfo=timezone.utc)
        requested_datasets = [
            "funding_rates",
            "open_interest",
            "mark_prices",
            "index_prices",
            "global_long_short_account_ratios",
            "top_trader_long_short_account_ratios",
            "top_trader_long_short_position_ratios",
            "taker_long_short_ratios",
        ]

        plan_before = build_market_snapshot_remediation_plan(
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            datasets=requested_datasets,
            observed_at=observed_at,
            lookback_hours=6,
        )
        self.assertTrue(all(item.remediation_required for item in plan_before))

        result = run_market_snapshot_remediation(
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_PERP",
            client=client,
            requested_by="test-user",
            datasets=requested_datasets,
            observed_at=observed_at,
            lookback_hours=6,
        )

        self.assertEqual(result.status, "succeeded")
        self.assertIsNotNone(result.refresh_job_id)
        self.assertGreater(result.records_written, 0)

        with connection_scope() as connection:
            remediation_job = IngestionJobRepository().get_job(connection, result.ingestion_job_id)
            refresh_jobs = [
                IngestionJobRepository().get_job(connection, refresh_job_id)
                for refresh_job_id in remediation_job["metadata_json"]["refresh_job_ids"]
            ]

        self.assertEqual(remediation_job["status"], "succeeded")
        self.assertTrue(remediation_job["metadata_json"]["scheduler_ready"])
        self.assertEqual(remediation_job["metadata_json"]["refresh_job_id"], result.refresh_job_id)
        self.assertEqual(
            {action["data_type"] for action in remediation_job["metadata_json"]["remediation_actions"]},
            set(requested_datasets),
        )
        self.assertGreaterEqual(len(refresh_jobs), 3)
        self.assertTrue(all(job["status"] == "succeeded" for job in refresh_jobs))
        self.assertTrue(any(job["metadata_json"]["include_open_interest"] for job in refresh_jobs))
        self.assertTrue(any(job["metadata_json"]["include_mark_price"] for job in refresh_jobs))
        self.assertTrue(any(job["metadata_json"]["include_index_price"] for job in refresh_jobs))
        self.assertTrue(any(job["metadata_json"]["include_global_long_short_account_ratio"] for job in refresh_jobs))
        self.assertTrue(any(job["metadata_json"]["include_top_trader_long_short_account_ratio"] for job in refresh_jobs))
        self.assertTrue(any(job["metadata_json"]["include_top_trader_long_short_position_ratio"] for job in refresh_jobs))
        self.assertTrue(any(job["metadata_json"]["include_taker_long_short_ratio"] for job in refresh_jobs))

    def test_market_snapshot_remediation_uses_retention_window_for_limited_datasets(self) -> None:
        observed_at = datetime(2035, 4, 2, 12, 35, tzinfo=timezone.utc)

        plans = build_market_snapshot_remediation_plan(
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            datasets=["open_interest", "taker_long_short_ratios"],
            observed_at=observed_at,
            lookback_hours=6,
        )

        plan_by_type = {plan.data_type: plan for plan in plans}
        expected_floor = datetime(2035, 3, 3, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(plan_by_type["open_interest"].planned_start_time, expected_floor)
        self.assertEqual(plan_by_type["taker_long_short_ratios"].planned_start_time, expected_floor)
        self.assertEqual(plan_by_type["open_interest"].profile_window_start, expected_floor)
        self.assertEqual(plan_by_type["taker_long_short_ratios"].profile_window_start, expected_floor)
        self.assertEqual(plan_by_type["open_interest"].remediation_reason, "missing")
        self.assertEqual(plan_by_type["taker_long_short_ratios"].remediation_reason, "missing")

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
        refresh_job = next(definition for definition in phase3_schedule_plan() if definition.job_id == "binance_market_snapshot_refresh")
        self.assertTrue(refresh_job.kwargs["include_global_long_short_account_ratio"])
        self.assertTrue(refresh_job.kwargs["include_top_trader_long_short_account_ratio"])
        self.assertTrue(refresh_job.kwargs["include_top_trader_long_short_position_ratio"])
        self.assertTrue(refresh_job.kwargs["include_taker_long_short_ratio"])
        self.assertTrue(refresh_job.kwargs["use_recent_history_for_retention_limited"])

    def test_phase4_schedule_plan_includes_market_snapshot_remediation_job(self) -> None:
        plan = phase4_schedule_plan()
        job_ids = {definition.job_id for definition in plan}
        self.assertIn("binance_market_snapshot_remediation", job_ids)
        remediation_job = next(definition for definition in plan if definition.job_id == "binance_market_snapshot_remediation")
        self.assertIn("global_long_short_account_ratios", remediation_job.kwargs["datasets"])
        self.assertIn("top_trader_long_short_account_ratios", remediation_job.kwargs["datasets"])
        self.assertIn("top_trader_long_short_position_ratios", remediation_job.kwargs["datasets"])
        self.assertIn("taker_long_short_ratios", remediation_job.kwargs["datasets"])


if __name__ == "__main__":
    unittest.main()
