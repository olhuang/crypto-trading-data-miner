from __future__ import annotations

import asyncio
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
from services import builtin_scheduler as scheduler_module


class BuiltinSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_enable_builtin_scheduler = settings.enable_builtin_scheduler
        self.original_builtin_scheduler_job_groups = settings.builtin_scheduler_job_groups

    def tearDown(self) -> None:
        settings.enable_builtin_scheduler = self.original_enable_builtin_scheduler
        settings.builtin_scheduler_job_groups = self.original_builtin_scheduler_job_groups

    def test_enabled_builtin_scheduler_definitions_respect_group_setting(self) -> None:
        settings.builtin_scheduler_job_groups = "phase4"

        definitions = scheduler_module.enabled_builtin_scheduler_definitions()

        self.assertEqual([definition.job_id for definition in definitions], ["binance_market_snapshot_remediation"])

    def test_start_builtin_scheduler_returns_none_when_disabled(self) -> None:
        settings.enable_builtin_scheduler = False

        self.assertIsNone(scheduler_module.start_builtin_scheduler())

    def test_app_lifespan_starts_and_stops_builtin_scheduler_handle(self) -> None:
        original_starter = app_module.start_builtin_scheduler
        calls = {"start": 0, "stop": 0}

        class _Handle:
            async def stop(self) -> None:
                calls["stop"] += 1

        def _fake_start():
            calls["start"] += 1
            return _Handle()

        app_module.start_builtin_scheduler = _fake_start
        try:
            app = create_app()

            async def _run_lifespan(application):
                async with application.router.lifespan_context(application):
                    pass

            asyncio.run(_run_lifespan(app))
        finally:
            app_module.start_builtin_scheduler = original_starter

        self.assertEqual(calls["start"], 1)
        self.assertEqual(calls["stop"], 1)


if __name__ == "__main__":
    unittest.main()
