"""Seed btc_hourly_momentum into strategy reference tables."""
import sys
sys.path.insert(0, "src")

from storage.db import transaction_scope
from sqlalchemy import text


def seed(conn):
    # Check if strategy exists
    sid = conn.execute(
        text("SELECT strategy_id FROM strategy.strategies WHERE strategy_code = 'btc_hourly_momentum'")
    ).scalar_one_or_none()

    if sid is None:
        sid = conn.execute(
            text(
                "INSERT INTO strategy.strategies (strategy_code, strategy_name, description) "
                "VALUES ('btc_hourly_momentum', 'BTC Hourly Momentum', "
                "'MA crossover on dynamically aggregated 1-hour bars') "
                "RETURNING strategy_id"
            )
        ).scalar_one()
        print(f"Inserted strategy btc_hourly_momentum, id={sid}")
    else:
        print(f"Strategy btc_hourly_momentum already exists, id={sid}")

    # Check if version exists
    vid = conn.execute(
        text(
            "SELECT strategy_version_id FROM strategy.strategy_versions "
            "WHERE strategy_id = :sid AND version_code = 'v1.0.0'"
        ),
        {"sid": sid},
    ).scalar_one_or_none()

    if vid is None:
        vid = conn.execute(
            text(
                "INSERT INTO strategy.strategy_versions "
                "(strategy_id, version_code, params_json, feature_version, execution_version, risk_version, is_active) "
                "VALUES (:sid, 'v1.0.0', '{}'::jsonb, 'seed-v1', 'seed-v1', 'seed-v1', true) "
                "RETURNING strategy_version_id"
            ),
            {"sid": sid},
        ).scalar_one()
        print(f"Inserted version v1.0.0, id={vid}")
    else:
        print(f"Version v1.0.0 already exists, id={vid}")

    print("Seed complete!")


with transaction_scope() as conn:
    seed(conn)
