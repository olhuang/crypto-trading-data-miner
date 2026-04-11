"""Seed btc_4h_breakout_perp into strategy reference tables."""
import sys

sys.path.insert(0, "src")

from sqlalchemy import text

from storage.db import transaction_scope


def seed(conn):
    sid = conn.execute(
        text("SELECT strategy_id FROM strategy.strategies WHERE strategy_code = 'btc_4h_breakout_perp'")
    ).scalar_one_or_none()

    if sid is None:
        sid = conn.execute(
            text(
                "INSERT INTO strategy.strategies (strategy_code, strategy_name, description) "
                "VALUES ('btc_4h_breakout_perp', 'BTC 4H Breakout Perp', "
                "'BTC perpetual 4H breakout strategy for Phase 5 research flows') "
                "RETURNING strategy_id"
            )
        ).scalar_one()
        print(f"Inserted strategy btc_4h_breakout_perp, id={sid}")
    else:
        print(f"Strategy btc_4h_breakout_perp already exists, id={sid}")

    vid = conn.execute(
        text(
            "SELECT strategy_version_id FROM strategy.strategy_versions "
            "WHERE strategy_id = :sid AND version_code = 'v0.1.0'"
        ),
        {"sid": sid},
    ).scalar_one_or_none()

    if vid is None:
        vid = conn.execute(
            text(
                "INSERT INTO strategy.strategy_versions "
                "(strategy_id, version_code, params_json, feature_version, execution_version, risk_version, is_active) "
                "VALUES (:sid, 'v0.1.0', '{}'::jsonb, 'seed-v1', 'seed-v1', 'seed-v1', true) "
                "RETURNING strategy_version_id"
            ),
            {"sid": sid},
        ).scalar_one()
        print(f"Inserted version v0.1.0, id={vid}")
    else:
        print(f"Version v0.1.0 already exists, id={vid}")

    print("Seed complete!")


with transaction_scope() as conn:
    seed(conn)
