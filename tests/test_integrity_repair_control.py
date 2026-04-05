from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from jobs.backfill_bars import BarBackfillResult
from services.integrity_repair_control import repair_bars_integrity_windows


class IntegrityRepairControlTests(unittest.TestCase):
    def test_repair_bars_integrity_windows_deletes_future_rows_instead_of_backfill(self) -> None:
        now = datetime.now(timezone.utc)
        past_start = now - timedelta(minutes=10)
        past_end = past_start.replace(second=59, microsecond=0)
        future_start = now + timedelta(days=1)
        future_start = future_start.replace(second=0, microsecond=0)
        future_end = future_start.replace(second=59, microsecond=0)

        with patch("services.integrity_repair_control.run_bar_backfill") as backfill_mock, patch(
            "services.integrity_repair_control._delete_bar_rows_in_window",
            return_value=1,
        ) as delete_mock:
            backfill_mock.return_value = BarBackfillResult(ingestion_job_id=321, status="succeeded", rows_written=1)

            result = repair_bars_integrity_windows(
                symbol="BTCUSDT",
                unified_symbol="BTCUSDT_PERP",
                interval="1m",
                windows=[
                    {
                        "label": "corrupt_1",
                        "start_time": past_start,
                        "end_time": past_end,
                    },
                    {
                        "label": "future_1",
                        "start_time": future_start,
                        "end_time": future_end,
                    },
                ],
                requested_by="tester",
            )

        backfill_mock.assert_called_once()
        delete_mock.assert_called_once()
        self.assertEqual(result["windows_completed"], 2)
        self.assertEqual(result["total_rows_written"], 2)
        self.assertEqual(result["results"][0]["ingestion_job_id"], 321)
        self.assertEqual(result["results"][0]["status"], "succeeded")
        self.assertEqual(result["results"][1]["ingestion_job_id"], 0)
        self.assertEqual(result["results"][1]["status"], "deleted_future_rows")
        self.assertEqual(result["results"][1]["rows_written"], 1)


if __name__ == "__main__":
    unittest.main()
