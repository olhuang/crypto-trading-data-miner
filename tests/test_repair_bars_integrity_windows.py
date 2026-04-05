from __future__ import annotations

from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from jobs.data_quality import (  # noqa: E402
    DatasetIntegrityDatasetReport,
    DatasetIntegrityFinding,
    DatasetIntegritySummary,
    DatasetIntegrityValidationResult,
)


MODULE_PATH = PROJECT_ROOT / "scripts" / "repair_bars_integrity_windows.py"
SPEC = spec_from_file_location("repair_bars_integrity_windows", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
repair_bars_integrity_windows = module_from_spec(SPEC)
sys.modules[SPEC.name] = repair_bars_integrity_windows
SPEC.loader.exec_module(repair_bars_integrity_windows)


class RepairBarsIntegrityWindowsTests(unittest.TestCase):
    def test_build_detected_windows_includes_gap_and_corrupt_windows(self) -> None:
        validation_result = DatasetIntegrityValidationResult(
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            start_time=datetime(2020, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 4, 23, 59, 59, tzinfo=timezone.utc),
            observed_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
            persisted_checks_written=0,
            persisted_gaps_written=0,
            summary=DatasetIntegritySummary(
                dataset_count=1,
                passed_datasets=0,
                warning_datasets=0,
                failed_datasets=1,
                total_gap_count=1,
                total_missing_count=7,
                total_coverage_shortfall_count=0,
                total_internal_missing_count=6,
                total_tail_missing_count=0,
                total_duplicate_count=0,
                total_corrupt_count=1,
                total_future_row_count=0,
            ),
            datasets=[
                DatasetIntegrityDatasetReport(
                    data_type="bars_1m",
                    status="fail",
                    row_count=0,
                    expected_interval_seconds=60,
                    expected_points=0,
                    profile_window_start=None,
                    available_from=None,
                    available_to=None,
                    safe_available_to=None,
                    selected_window_available_from=None,
                    selected_window_available_to=None,
                    missing_count=7,
                    coverage_shortfall_count=0,
                    internal_missing_count=6,
                    tail_missing_count=0,
                    gap_count=1,
                    duplicate_count=0,
                    corrupt_count=1,
                    future_row_count=0,
                    findings=[
                        DatasetIntegrityFinding(
                            category="gap",
                            severity="error",
                            status="fail",
                            message="gap",
                            related_count=1,
                            detail_json={
                                "segments": [
                                    {
                                        "gap_start": "2026-04-01T00:00:00+00:00",
                                        "gap_end": "2026-04-01T00:05:00+00:00",
                                        "missing_points": 6,
                                    }
                                ]
                            },
                        ),
                        DatasetIntegrityFinding(
                            category="corrupt",
                            severity="error",
                            status="fail",
                            message="corrupt",
                            related_count=1,
                            detail_json={
                                "corrupt_examples": [
                                    {"ts": "2026-04-02T12:34:00+00:00"}
                                ]
                            },
                        ),
                    ],
                )
            ],
        )

        windows = repair_bars_integrity_windows._build_detected_windows(validation_result)

        self.assertEqual(
            windows,
            [
                {
                    "label": "auto_detected_window_1",
                    "start_time": "2026-04-01T00:00:00+00:00",
                    "end_time": "2026-04-01T00:05:59+00:00",
                    "source_summary": "gap:2026-04-01T00:00:00+00:00->2026-04-01T00:05:00+00:00",
                },
                {
                    "label": "auto_detected_window_2",
                    "start_time": "2026-04-02T12:34:00+00:00",
                    "end_time": "2026-04-02T12:34:59+00:00",
                    "source_summary": "corrupt:2026-04-02T12:34:00+00:00",
                },
            ],
        )

    def test_build_detected_windows_merges_overlapping_gap_and_corrupt_windows(self) -> None:
        validation_result = DatasetIntegrityValidationResult(
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            start_time=datetime(2020, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 4, 23, 59, 59, tzinfo=timezone.utc),
            observed_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
            persisted_checks_written=0,
            persisted_gaps_written=0,
            summary=DatasetIntegritySummary(
                dataset_count=1,
                passed_datasets=0,
                warning_datasets=0,
                failed_datasets=1,
                total_gap_count=1,
                total_missing_count=2,
                total_coverage_shortfall_count=0,
                total_internal_missing_count=1,
                total_tail_missing_count=0,
                total_duplicate_count=0,
                total_corrupt_count=1,
                total_future_row_count=0,
            ),
            datasets=[
                DatasetIntegrityDatasetReport(
                    data_type="bars_1m",
                    status="fail",
                    row_count=0,
                    expected_interval_seconds=60,
                    expected_points=0,
                    profile_window_start=None,
                    available_from=None,
                    available_to=None,
                    safe_available_to=None,
                    selected_window_available_from=None,
                    selected_window_available_to=None,
                    missing_count=2,
                    coverage_shortfall_count=0,
                    internal_missing_count=1,
                    tail_missing_count=0,
                    gap_count=1,
                    duplicate_count=0,
                    corrupt_count=1,
                    future_row_count=0,
                    findings=[
                        DatasetIntegrityFinding(
                            category="gap",
                            severity="error",
                            status="fail",
                            message="gap",
                            related_count=1,
                            detail_json={
                                "segments": [
                                    {
                                        "gap_start": "2026-04-01T00:00:00+00:00",
                                        "gap_end": "2026-04-01T00:00:00+00:00",
                                        "missing_points": 1,
                                    }
                                ]
                            },
                        ),
                        DatasetIntegrityFinding(
                            category="corrupt",
                            severity="error",
                            status="fail",
                            message="corrupt",
                            related_count=1,
                            detail_json={
                                "corrupt_examples": [
                                    {"ts": "2026-04-01T00:00:15+00:00"}
                                ]
                            },
                        ),
                    ],
                )
            ],
        )

        windows = repair_bars_integrity_windows._build_detected_windows(validation_result)

        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]["start_time"], "2026-04-01T00:00:00+00:00")
        self.assertEqual(windows[0]["end_time"], "2026-04-01T00:00:59+00:00")
        self.assertIn("gap:2026-04-01T00:00:00+00:00->2026-04-01T00:00:00+00:00", windows[0]["source_summary"])
        self.assertIn("corrupt:2026-04-01T00:00:15+00:00", windows[0]["source_summary"])

    def test_build_windows_defaults_to_auto_detect_for_spot_symbol(self) -> None:
        validation_result = DatasetIntegrityValidationResult(
            exchange_code="binance",
            unified_symbol="BTCUSDT_SPOT",
            start_time=datetime(2020, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 4, 23, 59, 59, tzinfo=timezone.utc),
            observed_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
            persisted_checks_written=0,
            persisted_gaps_written=0,
            summary=DatasetIntegritySummary(
                dataset_count=1,
                passed_datasets=0,
                warning_datasets=0,
                failed_datasets=1,
                total_gap_count=1,
                total_missing_count=6,
                total_coverage_shortfall_count=0,
                total_internal_missing_count=6,
                total_tail_missing_count=0,
                total_duplicate_count=0,
                total_corrupt_count=0,
                total_future_row_count=0,
            ),
            datasets=[
                DatasetIntegrityDatasetReport(
                    data_type="bars_1m",
                    status="fail",
                    row_count=0,
                    expected_interval_seconds=60,
                    expected_points=0,
                    profile_window_start=None,
                    available_from=None,
                    available_to=None,
                    safe_available_to=None,
                    selected_window_available_from=None,
                    selected_window_available_to=None,
                    missing_count=6,
                    coverage_shortfall_count=0,
                    internal_missing_count=6,
                    tail_missing_count=0,
                    gap_count=1,
                    duplicate_count=0,
                    corrupt_count=0,
                    future_row_count=0,
                    findings=[
                        DatasetIntegrityFinding(
                            category="gap",
                            severity="error",
                            status="fail",
                            message="gap",
                            related_count=1,
                            detail_json={
                                "segments": [
                                    {
                                        "gap_start": "2026-04-01T00:00:00+00:00",
                                        "gap_end": "2026-04-01T00:05:00+00:00",
                                        "missing_points": 6,
                                    }
                                ]
                            },
                        )
                    ],
                )
            ],
        )

        args = SimpleNamespace(
            auto_detect=False,
            start_time=None,
            end_time=None,
            unified_symbol="BTCUSDT_SPOT",
        )

        with patch.object(repair_bars_integrity_windows, "validate_dataset_integrity", return_value=validation_result):
            windows, summary = repair_bars_integrity_windows.build_windows(args)

        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]["start_time"], "2026-04-01T00:00:00+00:00")
        self.assertIsNotNone(summary)
        self.assertEqual(summary["gap_count"], 1)
