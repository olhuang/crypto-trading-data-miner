from __future__ import annotations

from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from storage.db import connection_scope, transaction_scope
from storage.lookups import resolve_instrument_id


MODULE_PATH = PROJECT_ROOT / "scripts" / "binance_btc_history_backfill.py"
SPEC = spec_from_file_location("binance_btc_history_backfill", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
binance_btc_history_backfill = module_from_spec(SPEC)
sys.modules[SPEC.name] = binance_btc_history_backfill
SPEC.loader.exec_module(binance_btc_history_backfill)


class BinanceBtcHistoryBackfillTests(unittest.TestCase):
    def test_open_interest_history_window_is_chunked_daily(self) -> None:
        start_time = datetime(2036, 1, 1, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2036, 1, 3, 12, 0, tzinfo=timezone.utc)
        original_refresh = binance_btc_history_backfill.run_market_snapshot_refresh
        original_floor = binance_btc_history_backfill.open_interest_available_from
        calls: list[tuple[datetime, datetime]] = []

        def fake_refresh(**kwargs):
            calls.append((kwargs["history_start_time"], kwargs["history_end_time"]))
            return SimpleNamespace(
                status="succeeded",
                records_written=10,
                history_rows_written=10,
                ingestion_job_id=len(calls),
            )

        try:
            binance_btc_history_backfill.run_market_snapshot_refresh = fake_refresh
            binance_btc_history_backfill.open_interest_available_from = lambda: start_time
            result = binance_btc_history_backfill.run_open_interest_history_window(
                symbol="BTCUSDT",
                unified_symbol="BTCUSDT_PERP",
                requested_by="test",
                start_time=start_time,
                end_time=end_time,
            )
        finally:
            binance_btc_history_backfill.run_market_snapshot_refresh = original_refresh
            binance_btc_history_backfill.open_interest_available_from = original_floor

        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0][0], datetime(2036, 1, 1, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(calls[0][1], datetime(2036, 1, 1, 23, 59, 59, 999000, tzinfo=timezone.utc))
        self.assertEqual(calls[1][0], datetime(2036, 1, 2, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(calls[1][1], datetime(2036, 1, 2, 23, 59, 59, 999000, tzinfo=timezone.utc))
        self.assertEqual(calls[2][0], datetime(2036, 1, 3, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(calls[2][1], end_time)
        self.assertEqual(result["rows_written"], 30)
        self.assertEqual(result["history_rows_written"], 30)
        self.assertEqual(len(result["chunk_results"]), 3)

    def test_mark_price_checkpoint_prefers_aligned_safe_timestamp(self) -> None:
        aligned_ts = datetime(2036, 1, 1, 0, 4, tzinfo=timezone.utc)
        offgrid_ts = datetime(2036, 1, 1, 0, 4, 15, tzinfo=timezone.utc)

        with transaction_scope() as connection:
            instrument_id = resolve_instrument_id(connection, "binance", "BTCUSDT_PERP")
            connection.execute(
                text(
                    """
                    insert into md.mark_prices (
                        instrument_id,
                        ts,
                        mark_price,
                        funding_basis_bps,
                        ingest_time
                    ) values
                        (:instrument_id, :aligned_ts, '100', null, :aligned_ts),
                        (:instrument_id, :offgrid_ts, '101', null, :offgrid_ts)
                    on conflict (instrument_id, ts) do update
                    set mark_price = excluded.mark_price,
                        funding_basis_bps = excluded.funding_basis_bps,
                        ingest_time = excluded.ingest_time
                    """
                ),
                {
                    "instrument_id": instrument_id,
                    "aligned_ts": aligned_ts,
                    "offgrid_ts": offgrid_ts,
                },
            )

        try:
            with connection_scope() as connection:
                coverage = binance_btc_history_backfill.coverage_row(
                    connection,
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_PERP",
                    table_name="md.mark_prices",
                    time_column="ts",
                    safe_upper_bound=offgrid_ts,
                    checkpoint_interval_seconds=60,
                )

            self.assertEqual(coverage["safe_available_to"], offgrid_ts.isoformat())
            self.assertEqual(coverage["checkpoint_available_to"], aligned_ts.isoformat())

            spec = binance_btc_history_backfill.DatasetSpec(
                dataset_key="btc_perp_mark_prices",
                label="BTCUSDT_PERP mark_prices",
                symbol="BTCUSDT",
                unified_symbol="BTCUSDT_PERP",
                task_kind="mark_prices",
                table_name="md.mark_prices",
                time_column="ts",
                checkpoint_interval_seconds=60,
            )
            next_start = binance_btc_history_backfill.next_start_from_coverage(
                spec,
                default_start=datetime(2020, 1, 1, tzinfo=timezone.utc),
                coverage=coverage,
            )
            self.assertEqual(next_start, aligned_ts + binance_btc_history_backfill.timedelta(milliseconds=1))
        finally:
            with transaction_scope() as connection:
                instrument_id = resolve_instrument_id(connection, "binance", "BTCUSDT_PERP")
                connection.execute(
                    text(
                        """
                        delete from md.mark_prices
                        where instrument_id = :instrument_id
                          and ts in (:aligned_ts, :offgrid_ts)
                        """
                    ),
                    {
                        "instrument_id": instrument_id,
                        "aligned_ts": aligned_ts,
                        "offgrid_ts": offgrid_ts,
                    },
                )

    def test_open_interest_available_from_is_rounded_down_to_day_start(self) -> None:
        fake_now = datetime(2036, 4, 5, 2, 53, 30, tzinfo=timezone.utc)
        with patch.object(binance_btc_history_backfill, "utc_now", return_value=fake_now):
            available_from = binance_btc_history_backfill.open_interest_available_from()
        self.assertEqual(available_from, datetime(2036, 3, 6, 0, 0, tzinfo=timezone.utc))

    def test_planned_gap_windows_include_internal_funding_gap(self) -> None:
        start_time = datetime(2036, 1, 1, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2036, 1, 1, 23, 59, 59, tzinfo=timezone.utc)
        first_time = datetime(2036, 1, 1, 0, 0, 0, 1000, tzinfo=timezone.utc)
        third_time = datetime(2036, 1, 1, 16, 0, 0, 0, tzinfo=timezone.utc)
        spec = binance_btc_history_backfill.DatasetSpec(
            dataset_key="btc_perp_funding_rates",
            label="BTCUSDT_PERP funding_rates",
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_PERP",
            task_kind="funding_rates",
            table_name="md.funding_rates",
            time_column="funding_time",
        )

        with transaction_scope() as connection:
            instrument_id = resolve_instrument_id(connection, "binance", "BTCUSDT_PERP")
            connection.execute(
                text(
                    """
                    insert into md.funding_rates (
                        instrument_id,
                        funding_time,
                        funding_rate,
                        mark_price,
                        index_price
                    ) values
                        (:instrument_id, :first_time, '0.0001', '100', '100'),
                        (:instrument_id, :third_time, '0.0002', '101', '101')
                    on conflict (instrument_id, funding_time) do update
                    set funding_rate = excluded.funding_rate,
                        mark_price = excluded.mark_price,
                        index_price = excluded.index_price
                    """
                ),
                {
                    "instrument_id": instrument_id,
                    "first_time": first_time,
                    "third_time": third_time,
                },
            )

        try:
            with connection_scope() as connection:
                windows = binance_btc_history_backfill.planned_gap_windows(
                    connection,
                    spec=spec,
                    exchange_code="binance",
                    start_time=start_time,
                    end_time=end_time,
                )

            self.assertEqual(
                windows,
                [
                    (
                        datetime(2036, 1, 1, 8, 0, tzinfo=timezone.utc),
                        datetime(2036, 1, 1, 8, 0, tzinfo=timezone.utc),
                    ),
                ],
            )
        finally:
            with transaction_scope() as connection:
                instrument_id = resolve_instrument_id(connection, "binance", "BTCUSDT_PERP")
                connection.execute(
                    text(
                        """
                        delete from md.funding_rates
                        where instrument_id = :instrument_id
                          and funding_time in (:first_time, :third_time)
                        """
                    ),
                    {
                        "instrument_id": instrument_id,
                        "first_time": first_time,
                        "third_time": third_time,
                    },
                )

    def test_planned_gap_windows_ignore_offgrid_funding_bucket_at_window_end(self) -> None:
        start_time = datetime(2036, 1, 1, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2036, 1, 1, 8, 0, tzinfo=timezone.utc)
        first_time = datetime(2036, 1, 1, 0, 0, 0, 1000, tzinfo=timezone.utc)
        second_time = datetime(2036, 1, 1, 8, 0, 0, 8000, tzinfo=timezone.utc)
        spec = binance_btc_history_backfill.DatasetSpec(
            dataset_key="btc_perp_funding_rates",
            label="BTCUSDT_PERP funding_rates",
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_PERP",
            task_kind="funding_rates",
            table_name="md.funding_rates",
            time_column="funding_time",
        )

        with transaction_scope() as connection:
            instrument_id = resolve_instrument_id(connection, "binance", "BTCUSDT_PERP")
            connection.execute(
                text(
                    """
                    insert into md.funding_rates (
                        instrument_id,
                        funding_time,
                        funding_rate,
                        mark_price,
                        index_price
                    ) values
                        (:instrument_id, :first_time, '0.0001', '100', '100'),
                        (:instrument_id, :second_time, '0.0002', '101', '101')
                    on conflict (instrument_id, funding_time) do update
                    set funding_rate = excluded.funding_rate,
                        mark_price = excluded.mark_price,
                        index_price = excluded.index_price
                    """
                ),
                {
                    "instrument_id": instrument_id,
                    "first_time": first_time,
                    "second_time": second_time,
                },
            )

        try:
            with connection_scope() as connection:
                windows = binance_btc_history_backfill.planned_gap_windows(
                    connection,
                    spec=spec,
                    exchange_code="binance",
                    start_time=start_time,
                    end_time=end_time,
                )

            self.assertEqual(windows, [])
        finally:
            with transaction_scope() as connection:
                instrument_id = resolve_instrument_id(connection, "binance", "BTCUSDT_PERP")
                connection.execute(
                    text(
                        """
                        delete from md.funding_rates
                        where instrument_id = :instrument_id
                          and funding_time in (:first_time, :second_time)
                        """
                    ),
                    {
                        "instrument_id": instrument_id,
                        "first_time": first_time,
                        "second_time": second_time,
                    },
                )

    def test_execute_task_expands_funding_fetch_window(self) -> None:
        original_refresh = binance_btc_history_backfill.run_market_snapshot_refresh
        calls: list[tuple[datetime, datetime]] = []

        def fake_refresh(**kwargs):
            calls.append((kwargs["funding_start_time"], kwargs["funding_end_time"]))
            return SimpleNamespace(
                status="succeeded",
                records_written=1,
                history_rows_written=0,
                ingestion_job_id=1,
            )

        task = binance_btc_history_backfill.ChunkTask(
            dataset_key="btc_perp_funding_rates",
            label="BTCUSDT_PERP funding_rates",
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_PERP",
            task_kind="funding_rates",
            chunk_index=1,
            chunk_total=1,
            start_time=datetime(2036, 1, 1, 8, 0, tzinfo=timezone.utc),
            end_time=datetime(2036, 1, 1, 8, 0, tzinfo=timezone.utc),
        )

        try:
            binance_btc_history_backfill.run_market_snapshot_refresh = fake_refresh
            result = binance_btc_history_backfill.execute_task(task, requested_by="test")
        finally:
            binance_btc_history_backfill.run_market_snapshot_refresh = original_refresh

        self.assertEqual(
            calls,
            [
                (
                    datetime(2036, 1, 1, 8, 0, tzinfo=timezone.utc),
                    datetime(2036, 1, 1, 16, 0, tzinfo=timezone.utc),
                )
            ],
        )
        self.assertEqual(result["rows_written"], 1)

    def test_filter_incremental_dataset_specs_supports_aliases(self) -> None:
        dataset_specs = binance_btc_history_backfill.build_incremental_dataset_specs()

        filtered = binance_btc_history_backfill.filter_incremental_dataset_specs(
            dataset_specs,
            ["funding_rates", "perp_bars_1m", "global_long_short_account_ratios"],
        )

        self.assertEqual(
            [spec.dataset_key for spec in filtered],
            [
                "btc_perp_bars_1m",
                "btc_perp_funding_rates",
                "btc_perp_global_long_short_account_ratios",
            ],
        )

    def test_execute_task_dispatches_sentiment_ratio_history_window(self) -> None:
        original_runner = binance_btc_history_backfill.run_sentiment_ratio_history_window
        calls: list[dict[str, object]] = []

        def fake_runner(**kwargs):
            calls.append(kwargs)
            return {
                "status": "succeeded",
                "rows_written": 2,
                "history_rows_written": 2,
                "ingestion_job_id": 77,
                "effective_start": kwargs["start_time"].isoformat(),
                "availability_note": None,
            }

        task = binance_btc_history_backfill.ChunkTask(
            dataset_key="btc_perp_global_long_short_account_ratios",
            label="BTCUSDT_PERP global_long_short_account_ratios",
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_PERP",
            task_kind="global_long_short_account_ratios",
            chunk_index=1,
            chunk_total=1,
            start_time=datetime(2036, 1, 1, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2036, 1, 1, 23, 59, tzinfo=timezone.utc),
            period_code="5m",
        )

        try:
            binance_btc_history_backfill.run_sentiment_ratio_history_window = fake_runner
            result = binance_btc_history_backfill.execute_task(task, requested_by="test")
        finally:
            binance_btc_history_backfill.run_sentiment_ratio_history_window = original_runner

        self.assertEqual(result["rows_written"], 2)
        self.assertEqual(calls[0]["period_code"], "5m")
        self.assertTrue(calls[0]["include_global_long_short_account_ratio"])

    def test_filter_incremental_dataset_specs_rejects_unknown_dataset(self) -> None:
        dataset_specs = binance_btc_history_backfill.build_incremental_dataset_specs()

        with self.assertRaisesRegex(ValueError, "unsupported --dataset value"):
            binance_btc_history_backfill.filter_incremental_dataset_specs(
                dataset_specs,
                ["unknown_dataset"],
            )


if __name__ == "__main__":
    unittest.main()
