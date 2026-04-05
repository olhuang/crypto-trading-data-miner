from __future__ import annotations

from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
