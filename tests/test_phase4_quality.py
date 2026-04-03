from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from uuid import uuid4

from fastapi.routing import APIRoute

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from api.app import Phase4QualityRunRequest, create_app
from jobs.data_quality import run_bar_gap_checks, run_freshness_checks, run_phase4_quality_suite
from models.market import (
    BarEvent,
    FundingRateEvent,
    LiquidationEvent,
    MarkPriceEvent,
    OpenInterestEvent,
    RawMarketEvent,
    TradeEvent,
)
from services.traceability import normalized_links_for_raw_event, replay_readiness_summary
from storage.db import connection_scope, transaction_scope
from storage.repositories.market_data import (
    BarRepository,
    FundingRateRepository,
    LiquidationRepository,
    MarkPriceRepository,
    OpenInterestRepository,
    RawMarketEventRepository,
    TradeRepository,
)
from storage.repositories.ops import DataGapRecord, DataGapRepository, DataQualityCheckRepository


def _resolve_route(app, path: str, method: str):
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"route not found: {method} {path}")


def _seed_phase4_dataset() -> dict[str, object]:
    suffix = uuid4().hex[:10]
    start_time = datetime(2031, 5, 1, 0, 0, tzinfo=timezone.utc)
    middle_time = datetime(2031, 5, 1, 0, 1, tzinfo=timezone.utc)
    end_time = datetime(2031, 5, 1, 0, 2, tzinfo=timezone.utc)
    trade_id = f"phase4_trade_{suffix}"
    duplicate_source_message_id = f"phase4_raw_dup_{suffix}"
    raw_trade_id = None

    with transaction_scope() as connection:
        connection.exec_driver_sql(
            """
            delete from ops.data_quality_checks
            where instrument_id = (
                select instrument.instrument_id
                from ref.instruments instrument
                join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                where exchange.exchange_code = %s and instrument.unified_symbol = %s
                limit 1
            )
              and check_time between %s and (%s + interval '1 day')
            """,
            ("binance", "BTCUSDT_PERP", start_time, end_time),
        )
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
              and gap_start between %s and %s
            """,
            ("binance", "BTCUSDT_PERP", start_time, end_time),
        )
        connection.exec_driver_sql(
            """
            delete from md.raw_market_events
            where instrument_id = (
                select instrument.instrument_id
                from ref.instruments instrument
                join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                where exchange.exchange_code = %s and instrument.unified_symbol = %s
                limit 1
            )
              and event_time between %s and %s
            """,
            ("binance", "BTCUSDT_PERP", start_time, end_time),
        )
        connection.exec_driver_sql(
            """
            delete from md.liquidations
            where instrument_id = (
                select instrument.instrument_id
                from ref.instruments instrument
                join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                where exchange.exchange_code = %s and instrument.unified_symbol = %s
                limit 1
            )
              and event_time between %s and %s
            """,
            ("binance", "BTCUSDT_PERP", start_time, end_time),
        )
        connection.exec_driver_sql(
            """
            delete from md.mark_prices
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
        connection.exec_driver_sql(
            """
            delete from md.open_interest
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
        connection.exec_driver_sql(
            """
            delete from md.funding_rates
            where instrument_id = (
                select instrument.instrument_id
                from ref.instruments instrument
                join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                where exchange.exchange_code = %s and instrument.unified_symbol = %s
                limit 1
            )
              and funding_time between %s and %s
            """,
            ("binance", "BTCUSDT_PERP", start_time, end_time),
        )
        connection.exec_driver_sql(
            """
            delete from md.trades
            where instrument_id = (
                select instrument.instrument_id
                from ref.instruments instrument
                join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                where exchange.exchange_code = %s and instrument.unified_symbol = %s
                limit 1
            )
              and event_time between %s and %s
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
        TradeRepository().upsert(
            connection,
            TradeEvent(
                exchange_code="binance",
                unified_symbol="BTCUSDT_PERP",
                exchange_trade_id=trade_id,
                event_time=end_time,
                ingest_time=end_time,
                price="84030.00",
                qty="0.25",
                aggressor_side="buy",
            ),
        )
        FundingRateRepository().upsert(
            connection,
            FundingRateEvent(
                exchange_code="binance",
                unified_symbol="BTCUSDT_PERP",
                ingest_time=start_time,
                funding_time=start_time,
                funding_rate="0.0001",
                mark_price="84015.00",
                index_price="84012.00",
            ),
        )
        OpenInterestRepository().upsert(
            connection,
            OpenInterestEvent(
                exchange_code="binance",
                unified_symbol="BTCUSDT_PERP",
                event_time=end_time,
                ingest_time=end_time,
                open_interest="18500.5",
            ),
        )
        MarkPriceRepository().upsert(
            connection,
            MarkPriceEvent(
                exchange_code="binance",
                unified_symbol="BTCUSDT_PERP",
                event_time=end_time,
                ingest_time=end_time,
                mark_price="84030.20",
            ),
        )
        LiquidationRepository().insert(
            connection,
            LiquidationEvent(
                exchange_code="binance",
                unified_symbol="BTCUSDT_PERP",
                event_time=end_time,
                ingest_time=end_time,
                side="sell",
                price="83980.00",
                qty="1.25",
                notional="104975.00",
                source="phase4_test",
                metadata_json={"batch": suffix},
            ),
        )
        raw_trade_id = RawMarketEventRepository().insert(
            connection,
            RawMarketEvent(
                exchange_code="binance",
                unified_symbol="BTCUSDT_PERP",
                channel="phase4_trade_stream",
                event_type="trade",
                event_time=end_time,
                ingest_time=end_time,
                source_message_id=trade_id,
                payload_json={"t": trade_id},
            ),
        )
        RawMarketEventRepository().insert(
            connection,
            RawMarketEvent(
                exchange_code="binance",
                unified_symbol="BTCUSDT_PERP",
                channel="phase4_duplicate_stream",
                event_type="trade",
                event_time=middle_time,
                ingest_time=middle_time,
                source_message_id=duplicate_source_message_id,
                payload_json={"t": duplicate_source_message_id, "seq": 1},
            ),
        )
        RawMarketEventRepository().insert(
            connection,
            RawMarketEvent(
                exchange_code="binance",
                unified_symbol="BTCUSDT_PERP",
                channel="phase4_duplicate_stream",
                event_type="trade",
                event_time=middle_time,
                ingest_time=middle_time,
                source_message_id=duplicate_source_message_id,
                payload_json={"t": duplicate_source_message_id, "seq": 2},
            ),
        )
        RawMarketEventRepository().insert(
            connection,
            RawMarketEvent(
                exchange_code="binance",
                unified_symbol="BTCUSDT_PERP",
                channel="phase4_mark_stream",
                event_type="markPriceUpdate",
                event_time=end_time,
                ingest_time=end_time,
                source_message_id=f"mark_{suffix}",
                payload_json={"p": "84030.20"},
            ),
        )
        RawMarketEventRepository().insert(
            connection,
            RawMarketEvent(
                exchange_code="binance",
                unified_symbol="BTCUSDT_PERP",
                channel="phase4_liq_stream",
                event_type="forceOrder",
                event_time=end_time,
                ingest_time=end_time,
                source_message_id=f"liq_{suffix}",
                payload_json={"q": "1.25"},
            ),
        )

    return {
        "start_time": start_time,
        "middle_time": middle_time,
        "end_time": end_time,
        "raw_trade_id": raw_trade_id,
        "trade_id": trade_id,
    }


class Phase4QualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.seed = _seed_phase4_dataset()
        cls.quality_result = run_phase4_quality_suite(
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            gap_start_time=cls.seed["start_time"],
            gap_end_time=cls.seed["end_time"],
            observed_at=datetime(2026, 5, 1, 0, 20, tzinfo=timezone.utc),
            raw_event_channel="phase4_duplicate_stream",
        )

    def test_quality_suite_persists_checks_and_gap_rows(self) -> None:
        self.assertEqual(self.__class__.quality_result.checks_written, 16)
        self.assertEqual(self.__class__.quality_result.gaps_written, 1)

        with connection_scope() as connection:
            summary = DataQualityCheckRepository().summary(
                connection,
                exchange_code="binance",
                unified_symbol="BTCUSDT_PERP",
            )
            gaps = DataGapRepository().list_recent(
                connection,
                data_type="bars_1m",
                exchange_code="binance",
                unified_symbol="BTCUSDT_PERP",
                limit=20,
            )

        self.assertGreaterEqual(summary["total_checks"], 16)
        self.assertGreaterEqual(summary["failed_checks"], 4)
        self.assertTrue(any(gap["gap_start"] == self.__class__.seed["middle_time"] for gap in gaps))

    def test_quality_suite_now_covers_snapshot_dataset_checks(self) -> None:
        with connection_scope() as connection:
            checks = DataQualityCheckRepository().list_recent(
                connection,
                exchange_code="binance",
                unified_symbol="BTCUSDT_PERP",
                limit=50,
            )

        self.assertTrue(any(check["data_type"] == "funding_rates" and check["check_name"] == "continuity_check" for check in checks))
        self.assertTrue(any(check["data_type"] == "open_interest" and check["check_name"] == "continuity_check" for check in checks))
        self.assertTrue(any(check["data_type"] == "mark_prices" and check["check_name"] == "duplicate_check" for check in checks))
        self.assertTrue(any(check["data_type"] == "index_prices" and check["check_name"] == "freshness_check" for check in checks))

    def test_traceability_links_trade_raw_event_back_to_normalized_trade(self) -> None:
        with connection_scope() as connection:
            links = normalized_links_for_raw_event(connection, self.__class__.seed["raw_trade_id"])

        self.assertTrue(any(link.resource_type == "trade" for link in links))
        self.assertTrue(any(link.match_strategy == "exchange_trade_id" for link in links))

    def test_replay_readiness_summary_reflects_retained_streams(self) -> None:
        with connection_scope() as connection:
            summary = replay_readiness_summary(connection)

        self.assertIn("phase4_trade_stream", summary["retained_streams"])
        self.assertIn("phase4_duplicate_stream", summary["retained_streams"])
        self.assertIn(summary["raw_coverage_status"], {"ready", "not_ready"})
        self.assertIn(summary["normalized_coverage_status"], {"ready", "partial"})


class Phase4ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.seed = _seed_phase4_dataset()
        run_phase4_quality_suite(
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            gap_start_time=cls.seed["start_time"],
            gap_end_time=cls.seed["end_time"],
            observed_at=datetime(2026, 5, 1, 0, 20, tzinfo=timezone.utc),
            raw_event_channel="phase4_duplicate_stream",
        )
        cls.app = create_app()
        cls.quality_run_endpoint = _resolve_route(cls.app, "/api/v1/quality/run", "POST")
        cls.quality_checks_endpoint = _resolve_route(cls.app, "/api/v1/quality/checks", "GET")
        cls.quality_summary_endpoint = _resolve_route(cls.app, "/api/v1/quality/summary", "GET")
        cls.quality_gaps_endpoint = _resolve_route(cls.app, "/api/v1/quality/gaps", "GET")
        cls.raw_events_endpoint = _resolve_route(cls.app, "/api/v1/market/raw-events", "GET")
        cls.raw_event_detail_endpoint = _resolve_route(cls.app, "/api/v1/market/raw-events/{raw_event_id}", "GET")
        cls.raw_event_links_endpoint = _resolve_route(cls.app, "/api/v1/market/raw-events/{raw_event_id}/normalized-links", "GET")
        cls.replay_readiness_endpoint = _resolve_route(cls.app, "/api/v1/replay/readiness", "GET")

    def test_quality_endpoints_expose_checks_summary_and_gaps(self) -> None:
        checks_response = self.__class__.quality_checks_endpoint(
            data_type="bars_1m",
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            limit=20,
        )
        latest_checks_response = self.__class__.quality_checks_endpoint(
            data_type="bars_1m",
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            latest_only=True,
            limit=20,
        )
        summary_response = self.__class__.quality_summary_endpoint(
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
        )
        latest_summary_response = self.__class__.quality_summary_endpoint(
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            latest_only=True,
        )
        gaps_response = self.__class__.quality_gaps_endpoint(
            data_type="bars_1m",
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            limit=20,
        )

        self.assertTrue(checks_response.success)
        self.assertGreaterEqual(len(checks_response.data.records), 1)
        self.assertTrue(latest_checks_response.success)
        self.assertLessEqual(len(latest_checks_response.data.records), len(checks_response.data.records))
        self.assertTrue(summary_response.success)
        self.assertGreaterEqual(summary_response.data.total_checks, 1)
        self.assertTrue(latest_summary_response.success)
        self.assertTrue(latest_summary_response.data.latest_only)
        self.assertLessEqual(latest_summary_response.data.total_checks, summary_response.data.total_checks)
        self.assertTrue(gaps_response.success)
        self.assertGreaterEqual(len(gaps_response.data.records), 1)

    def test_raw_event_endpoints_support_filters_detail_and_links(self) -> None:
        list_response = self.__class__.raw_events_endpoint(
            exchange_code="binance",
            channel="phase4_trade_stream",
            event_type="trade",
            start_time=self.__class__.seed["start_time"],
            end_time=self.__class__.seed["end_time"],
            limit=20,
        )
        listed_raw_event_id = next(record["raw_event_id"] for record in list_response.data.records)
        detail_response = self.__class__.raw_event_detail_endpoint(listed_raw_event_id)
        links_response = self.__class__.raw_event_links_endpoint(listed_raw_event_id)

        self.assertTrue(list_response.success)
        self.assertEqual(detail_response.data.raw_event_id, listed_raw_event_id)
        self.assertTrue(any(link["resource_type"] == "trade" for link in links_response.data.links))

    def test_replay_readiness_and_quality_run_endpoints_work(self) -> None:
        quality_run_response = self.__class__.quality_run_endpoint(
            Phase4QualityRunRequest(
                exchange_code="binance",
                unified_symbol="BTCUSDT_PERP",
                gap_start_time=self.__class__.seed["start_time"],
                gap_end_time=self.__class__.seed["end_time"],
                observed_at=datetime(2026, 5, 1, 0, 20, tzinfo=timezone.utc),
                raw_event_channel="phase4_duplicate_stream",
            )
        )
        replay_response = self.__class__.replay_readiness_endpoint()

        self.assertTrue(quality_run_response.success)
        self.assertIn("checks:", quality_run_response.data.status)
        self.assertTrue(replay_response.success)
        self.assertIn("phase4_trade_stream", replay_response.data.retained_streams)


class Phase4QualityScopeTests(unittest.TestCase):
    def test_bar_gap_checks_align_non_minute_windows(self) -> None:
        start_time = datetime(2031, 6, 1, 0, 0, 30, tzinfo=timezone.utc)
        end_time = datetime(2031, 6, 1, 0, 2, 45, tzinfo=timezone.utc)

        with transaction_scope() as connection:
            connection.exec_driver_sql(
                """
                delete from ops.data_quality_checks
                where instrument_id = (
                    select instrument.instrument_id
                    from ref.instruments instrument
                    join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                    where exchange.exchange_code = %s and instrument.unified_symbol = %s
                    limit 1
                )
                  and check_name = 'bar_gap_check'
                  and check_time > %s - interval '1 hour'
                """,
                ("binance", "BTCUSDT_SPOT", start_time),
            )
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
                ("binance", "BTCUSDT_SPOT", start_time, end_time),
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
                ("binance", "BTCUSDT_SPOT", start_time, end_time),
            )
            bar_repo = BarRepository()
            for bar_time in (
                datetime(2031, 6, 1, 0, 1, tzinfo=timezone.utc),
                datetime(2031, 6, 1, 0, 2, tzinfo=timezone.utc),
            ):
                bar_repo.upsert(
                    connection,
                    BarEvent(
                        exchange_code="binance",
                        unified_symbol="BTCUSDT_SPOT",
                        ingest_time=bar_time,
                        bar_interval="1m",
                        bar_time=bar_time,
                        event_time=bar_time,
                        open="100000.0",
                        high="100010.0",
                        low="99990.0",
                        close="100005.0",
                        volume="5.0",
                        quote_volume="500025.0",
                        trade_count=50,
                    ),
                )

        result = run_bar_gap_checks(
            exchange_code="binance",
            unified_symbol="BTCUSDT_SPOT",
            start_time=start_time,
            end_time=end_time,
        )
        self.assertEqual(result.checks_written, 1)
        self.assertEqual(result.gaps_written, 0)

        with connection_scope() as connection:
            checks = DataQualityCheckRepository().list_recent(
                connection,
                exchange_code="binance",
                unified_symbol="BTCUSDT_SPOT",
                data_type="bars_1m",
                limit=5,
            )
        latest = next(check for check in checks if check["check_name"] == "bar_gap_check")
        self.assertEqual(latest["status"], "pass")
        self.assertEqual(latest["expected_value"], "2")
        self.assertEqual(latest["observed_value"], "2")
        self.assertEqual(latest["detail_json"]["aligned_window_start"], "2031-06-01T00:01:00+00:00")
        self.assertEqual(latest["detail_json"]["aligned_window_end"], "2031-06-01T00:02:00+00:00")

    def test_spot_freshness_checks_skip_perp_only_datasets(self) -> None:
        observed_at = datetime(2031, 6, 1, 0, 5, tzinfo=timezone.utc)
        bar_time = datetime(2031, 6, 1, 0, 4, tzinfo=timezone.utc)
        trade_time = datetime(2031, 6, 1, 0, 4, tzinfo=timezone.utc)

        with transaction_scope() as connection:
            connection.exec_driver_sql(
                """
                delete from ops.data_quality_checks
                where instrument_id = (
                    select instrument.instrument_id
                    from ref.instruments instrument
                    join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                    where exchange.exchange_code = %s and instrument.unified_symbol = %s
                    limit 1
                )
                  and check_name = 'freshness_check'
                  and check_time > %s - interval '1 hour'
                """,
                ("binance", "BTCUSDT_SPOT", observed_at),
            )
            connection.exec_driver_sql(
                """
                delete from md.trades
                where instrument_id = (
                    select instrument.instrument_id
                    from ref.instruments instrument
                    join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                    where exchange.exchange_code = %s and instrument.unified_symbol = %s
                    limit 1
                )
                  and event_time between %s - interval '1 hour' and %s
                """,
                ("binance", "BTCUSDT_SPOT", observed_at, observed_at),
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
                  and bar_time between %s - interval '1 hour' and %s
                """,
                ("binance", "BTCUSDT_SPOT", observed_at, observed_at),
            )
            BarRepository().upsert(
                connection,
                BarEvent(
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_SPOT",
                    ingest_time=bar_time,
                    bar_interval="1m",
                    bar_time=bar_time,
                    event_time=bar_time,
                    open="100000.0",
                    high="100010.0",
                    low="99990.0",
                    close="100005.0",
                    volume="5.0",
                    quote_volume="500025.0",
                    trade_count=50,
                ),
            )
            TradeRepository().upsert(
                connection,
                TradeEvent(
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_SPOT",
                    exchange_trade_id=f"spot_quality_trade_{uuid4().hex[:8]}",
                    event_time=trade_time,
                    ingest_time=trade_time,
                    price="100005.0",
                    qty="0.1",
                    aggressor_side="buy",
                ),
            )

        result = run_freshness_checks(
            exchange_code="binance",
            unified_symbol="BTCUSDT_SPOT",
            observed_at=observed_at,
        )
        self.assertEqual(result.checks_written, 2)

        with connection_scope() as connection:
            checks = DataQualityCheckRepository().list_recent(
                connection,
                exchange_code="binance",
                unified_symbol="BTCUSDT_SPOT",
                limit=10,
            )
        freshness_data_types = {
            check["data_type"]
            for check in checks
            if check["check_name"] == "freshness_check"
        }
        self.assertEqual(freshness_data_types, {"bars_1m", "trades"})

    def test_bar_gap_checks_resolve_overlapping_open_gaps_when_window_is_clean(self) -> None:
        start_time = datetime(2031, 6, 2, 0, 0, 30, tzinfo=timezone.utc)
        end_time = datetime(2031, 6, 2, 0, 2, 45, tzinfo=timezone.utc)

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
                  and gap_start between %s - interval '5 minute' and %s + interval '5 minute'
                """,
                ("binance", "BTCUSDT_SPOT", start_time, end_time),
            )
            bar_repo = BarRepository()
            for bar_time in (
                datetime(2031, 6, 2, 0, 1, tzinfo=timezone.utc),
                datetime(2031, 6, 2, 0, 2, tzinfo=timezone.utc),
            ):
                bar_repo.upsert(
                    connection,
                    BarEvent(
                        exchange_code="binance",
                        unified_symbol="BTCUSDT_SPOT",
                        ingest_time=bar_time,
                        bar_interval="1m",
                        bar_time=bar_time,
                        event_time=bar_time,
                        open="100000.0",
                        high="100010.0",
                        low="99990.0",
                        close="100005.0",
                        volume="5.0",
                        quote_volume="500025.0",
                        trade_count=50,
                    ),
                )
            gap_id = DataGapRepository().insert(
                connection,
                DataGapRecord(
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_SPOT",
                    data_type="bars_1m",
                    gap_start=start_time,
                    gap_end=end_time,
                    expected_count=2,
                    actual_count=0,
                    detail_json={"seeded_for_test": True},
                ),
            )

        result = run_bar_gap_checks(
            exchange_code="binance",
            unified_symbol="BTCUSDT_SPOT",
            start_time=start_time,
            end_time=end_time,
        )
        self.assertEqual(result.gaps_written, 0)

        with connection_scope() as connection:
            gap_rows = DataGapRepository().list_recent(
                connection,
                exchange_code="binance",
                unified_symbol="BTCUSDT_SPOT",
                data_type="bars_1m",
                limit=10,
            )
        resolved_gap = next(gap for gap in gap_rows if gap["gap_id"] == gap_id)
        self.assertEqual(resolved_gap["status"], "resolved")
        self.assertEqual(resolved_gap["detail_json"]["resolved_by"], "bar_gap_check")


if __name__ == "__main__":
    unittest.main()
