from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.engine import Connection

from models.strategy import Signal
from storage.lookups import resolve_instrument_id, resolve_strategy_version_id


class StrategySignalRepository:
    def insert(self, connection: Connection, signal: Signal) -> int:
        strategy_version_id = resolve_strategy_version_id(
            connection,
            signal.strategy_code,
            signal.strategy_version,
        )
        instrument_id = resolve_instrument_id(connection, signal.exchange_code, signal.unified_symbol)
        return int(
            connection.execute(
                text(
                    """
                    insert into strategy.signals (
                        strategy_version_id,
                        instrument_id,
                        signal_time,
                        signal_type,
                        direction,
                        score,
                        target_qty,
                        target_notional,
                        reason_code,
                        metadata_json
                    ) values (
                        :strategy_version_id,
                        :instrument_id,
                        :signal_time,
                        :signal_type,
                        :direction,
                        :score,
                        :target_qty,
                        :target_notional,
                        :reason_code,
                        cast(:metadata_json as jsonb)
                    )
                    returning signal_id
                    """
                ),
                {
                    "strategy_version_id": strategy_version_id,
                    "instrument_id": instrument_id,
                    "signal_time": signal.signal_time,
                    "signal_type": signal.signal_type.value,
                    "direction": signal.direction.value if signal.direction is not None else None,
                    "score": signal.score,
                    "target_qty": signal.target_qty,
                    "target_notional": signal.target_notional,
                    "reason_code": signal.reason_code,
                    "metadata_json": json.dumps(signal.metadata_json, default=str),
                },
            ).scalar_one()
        )
