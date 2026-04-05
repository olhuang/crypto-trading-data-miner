from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from storage.db import connection_scope


class SeedDefaultsTests(unittest.TestCase):
    def test_strategy_version_seed_defaults_exist(self) -> None:
        with connection_scope() as connection:
            rows = connection.exec_driver_sql(
                """
                select s.strategy_code, sv.version_code, sv.is_active
                from strategy.strategy_versions sv
                join strategy.strategies s on s.strategy_id = sv.strategy_id
                where (s.strategy_code = %s and sv.version_code = %s)
                   or (s.strategy_code = %s and sv.version_code = %s)
                order by s.strategy_code
                """,
                ("btc_momentum", "v1.0.0", "btc_sentiment_momentum", "v1.0.0"),
            ).all()

        self.assertEqual(
            rows,
            [
                ("btc_momentum", "v1.0.0", True),
                ("btc_sentiment_momentum", "v1.0.0", True),
            ],
        )

    def test_account_seed_defaults_exist(self) -> None:
        with connection_scope() as connection:
            rows = connection.exec_driver_sql(
                """
                select account_code, account_type, is_active
                from execution.accounts
                where account_code in (%s, %s)
                order by account_code
                """,
                ("binance_live_placeholder", "paper_main"),
            ).all()

        self.assertEqual(
            rows,
            [
                ("binance_live_placeholder", "live", False),
                ("paper_main", "paper", True),
            ],
        )


if __name__ == "__main__":
    unittest.main()
