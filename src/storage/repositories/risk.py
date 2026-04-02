from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.engine import Connection

from models.risk import RiskEvent, RiskLimit
from storage.lookups import resolve_account_id, resolve_instrument_id


class RiskLimitRepository:
    def upsert(self, connection: Connection, limit: RiskLimit) -> int:
        account_id = resolve_account_id(connection, limit.account_code)
        instrument_id = None
        if limit.exchange_code and limit.unified_symbol:
            instrument_id = resolve_instrument_id(connection, limit.exchange_code, limit.unified_symbol)

        existing_risk_limit_id = connection.execute(
            text(
                """
                select risk_limit_id
                from risk.risk_limits
                where account_id = :account_id
                  and (
                    (instrument_id is null and :instrument_id is null)
                    or instrument_id = :instrument_id
                  )
                order by risk_limit_id desc
                limit 1
                """
            ),
            {
                "account_id": account_id,
                "instrument_id": instrument_id,
            },
        ).scalar_one_or_none()

        params = {
            "risk_limit_id": existing_risk_limit_id,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "max_position_qty": limit.max_position_qty,
            "max_notional": limit.max_notional,
            "max_leverage": limit.max_leverage,
            "max_daily_loss": limit.max_daily_loss,
            "is_active": limit.is_active,
        }

        if existing_risk_limit_id is None:
            return int(
                connection.execute(
                    text(
                        """
                        insert into risk.risk_limits (
                            account_id,
                            instrument_id,
                            max_position_qty,
                            max_notional,
                            max_leverage,
                            max_daily_loss,
                            is_active
                        ) values (
                            :account_id,
                            :instrument_id,
                            :max_position_qty,
                            :max_notional,
                            :max_leverage,
                            :max_daily_loss,
                            :is_active
                        )
                        returning risk_limit_id
                        """
                    ),
                    params,
                ).scalar_one()
            )

        connection.execute(
            text(
                """
                update risk.risk_limits
                set
                    max_position_qty = :max_position_qty,
                    max_notional = :max_notional,
                    max_leverage = :max_leverage,
                    max_daily_loss = :max_daily_loss,
                    is_active = :is_active
                where risk_limit_id = :risk_limit_id
                """
            ),
            params,
        )
        return int(existing_risk_limit_id)


class RiskEventRepository:
    def insert(self, connection: Connection, event: RiskEvent) -> int:
        account_id = resolve_account_id(connection, event.account_code) if event.account_code else None
        instrument_id = None
        if event.exchange_code and event.unified_symbol:
            instrument_id = resolve_instrument_id(connection, event.exchange_code, event.unified_symbol)

        return int(
            connection.execute(
                text(
                    """
                    insert into risk.risk_events (
                        account_id,
                        instrument_id,
                        event_time,
                        event_type,
                        severity,
                        detail_json
                    ) values (
                        :account_id,
                        :instrument_id,
                        :event_time,
                        :event_type,
                        :severity,
                        cast(:detail_json as jsonb)
                    )
                    returning risk_event_id
                    """
                ),
                {
                    "account_id": account_id,
                    "instrument_id": instrument_id,
                    "event_time": event.event_time,
                    "event_type": event.event_type,
                    "severity": event.severity,
                    "detail_json": json.dumps(
                        {
                            **event.detail_json,
                            **({"decision": event.decision} if event.decision is not None else {}),
                        }
                    ),
                },
            ).scalar_one()
        )
