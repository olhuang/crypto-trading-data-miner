from __future__ import annotations

from dataclasses import dataclass
import json

from sqlalchemy import text
from sqlalchemy.engine import Connection

from models.execution import BalanceSnapshot, Fill, OrderEvent, OrderRequest, OrderState, PositionSnapshot
from storage.lookups import resolve_account_id, resolve_asset_id, resolve_exchange_id, resolve_instrument_id


@dataclass(slots=True)
class AccountRecord:
    account_code: str
    exchange_code: str
    account_type: str
    base_currency: str | None = None
    is_active: bool = True


class AccountRepository:
    def upsert(self, connection: Connection, account: AccountRecord) -> int:
        exchange_id = resolve_exchange_id(connection, account.exchange_code)
        base_currency_id = resolve_asset_id(connection, account.base_currency) if account.base_currency else None
        return int(
            connection.execute(
                text(
                    """
                    insert into execution.accounts (
                        account_code,
                        exchange_id,
                        account_type,
                        base_currency_id,
                        is_active
                    ) values (
                        :account_code,
                        :exchange_id,
                        :account_type,
                        :base_currency_id,
                        :is_active
                    )
                    on conflict (account_code) do update
                    set
                        exchange_id = excluded.exchange_id,
                        account_type = excluded.account_type,
                        base_currency_id = excluded.base_currency_id,
                        is_active = excluded.is_active
                    returning account_id
                    """
                ),
                {
                    "account_code": account.account_code,
                    "exchange_id": exchange_id,
                    "account_type": account.account_type,
                    "base_currency_id": base_currency_id,
                    "is_active": account.is_active,
                },
            ).scalar_one()
        )


class OrderRepository:
    def upsert_order_state(self, connection: Connection, state: OrderState) -> int:
        account_id = resolve_account_id(connection, state.account_code)
        instrument_id = resolve_instrument_id(connection, state.exchange_code, state.unified_symbol)

        existing_order_id = None
        if state.client_order_id:
            existing_order_id = connection.execute(
                text(
                    """
                    select order_id
                    from execution.orders
                    where account_id = :account_id
                      and client_order_id = :client_order_id
                    order by order_id desc
                    limit 1
                    """
                ),
                {"account_id": account_id, "client_order_id": state.client_order_id},
            ).scalar_one_or_none()

        params = {
            "order_id": existing_order_id,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "environment": state.environment,
            "client_order_id": state.client_order_id,
            "exchange_order_id": state.exchange_order_id,
            "side": state.side,
            "order_type": state.order_type,
            "time_in_force": state.time_in_force,
            "price": state.price,
            "qty": state.qty,
            "status": state.status,
            "reject_reason": state.reject_reason,
            "event_time": state.event_time,
            "submit_time": state.submit_time,
            "ack_time": state.ack_time,
            "cancel_time": state.cancel_time,
        }

        if existing_order_id is None:
            return int(
                connection.execute(
                    text(
                        """
                        insert into execution.orders (
                            account_id,
                            instrument_id,
                            environment,
                            client_order_id,
                            exchange_order_id,
                            side,
                            order_type,
                            time_in_force,
                            price,
                            qty,
                            status,
                            reject_reason,
                            event_time,
                            submit_time,
                            ack_time,
                            cancel_time
                        ) values (
                            :account_id,
                            :instrument_id,
                            :environment,
                            :client_order_id,
                            :exchange_order_id,
                            :side,
                            :order_type,
                            :time_in_force,
                            :price,
                            :qty,
                            :status,
                            :reject_reason,
                            :event_time,
                            :submit_time,
                            :ack_time,
                            :cancel_time
                        )
                        returning order_id
                        """
                    ),
                    params,
                ).scalar_one()
            )

        connection.execute(
            text(
                """
                update execution.orders
                set
                    exchange_order_id = :exchange_order_id,
                    side = :side,
                    order_type = :order_type,
                    time_in_force = :time_in_force,
                    price = :price,
                    qty = :qty,
                    status = :status,
                    reject_reason = :reject_reason,
                    event_time = :event_time,
                    submit_time = :submit_time,
                    ack_time = :ack_time,
                    cancel_time = :cancel_time
                where order_id = :order_id
                """
            ),
            params,
        )
        return int(existing_order_id)

    def create_from_request(self, connection: Connection, request: OrderRequest, *, status: str = "new") -> int:
        state = OrderState(
            order_id="pending",
            environment=request.environment,
            account_code=request.account_code,
            strategy_code=request.strategy_code,
            strategy_version=request.strategy_version,
            signal_id=request.signal_id,
            exchange_code=request.exchange_code,
            unified_symbol=request.unified_symbol,
            client_order_id=request.client_order_id,
            side=request.side,
            order_type=request.order_type,
            time_in_force=request.time_in_force,
            price=request.price,
            qty=request.qty,
            status=status,
        )
        return self.upsert_order_state(connection, state)


class OrderEventRepository:
    def insert(self, connection: Connection, event: OrderEvent) -> int:
        return int(
            connection.execute(
                text(
                    """
                    insert into execution.order_events (
                        order_id,
                        event_type,
                        event_time,
                        status_before,
                        status_after,
                        exchange_order_id,
                        client_order_id,
                        reason_code,
                        detail_json
                    ) values (
                        :order_id,
                        :event_type,
                        :event_time,
                        :status_before,
                        :status_after,
                        :exchange_order_id,
                        :client_order_id,
                        :reason_code,
                        cast(:detail_json as jsonb)
                    )
                    returning order_event_id
                    """
                ),
                {
                    "order_id": int(event.order_id),
                    "event_type": event.event_type,
                    "event_time": event.event_time,
                    "status_before": event.status_before,
                    "status_after": event.status_after,
                    "exchange_order_id": event.exchange_order_id,
                    "client_order_id": event.client_order_id,
                    "reason_code": event.reason_code,
                    "detail_json": "{}" if not event.detail_json else json.dumps(event.detail_json),
                },
            ).scalar_one()
        )


class FillRepository:
    def insert(self, connection: Connection, fill: Fill) -> int:
        instrument_id = resolve_instrument_id(connection, fill.exchange_code, fill.unified_symbol)
        fee_asset_id = resolve_asset_id(connection, fill.fee_asset) if fill.fee_asset else None

        if fill.exchange_trade_id:
            existing_fill_id = connection.execute(
                text(
                    """
                    select fill_id
                    from execution.fills
                    where order_id = :order_id
                      and exchange_trade_id = :exchange_trade_id
                    order by fill_id desc
                    limit 1
                    """
                ),
                {
                    "order_id": int(fill.order_id),
                    "exchange_trade_id": fill.exchange_trade_id,
                },
            ).scalar_one_or_none()
            if existing_fill_id is not None:
                connection.execute(
                    text(
                        """
                        update execution.fills
                        set
                            instrument_id = :instrument_id,
                            fill_time = :fill_time,
                            price = :price,
                            qty = :qty,
                            notional = :notional,
                            fee = :fee,
                            fee_asset_id = :fee_asset_id,
                            liquidity_flag = :liquidity_flag
                        where fill_id = :fill_id
                        """
                    ),
                    {
                        "fill_id": int(existing_fill_id),
                        "instrument_id": instrument_id,
                        "fill_time": fill.fill_time,
                        "price": fill.price,
                        "qty": fill.qty,
                        "notional": fill.notional,
                        "fee": fill.fee,
                        "fee_asset_id": fee_asset_id,
                        "liquidity_flag": fill.liquidity_flag,
                    },
                )
                return int(existing_fill_id)

        return int(
            connection.execute(
                text(
                    """
                    insert into execution.fills (
                        order_id,
                        instrument_id,
                        exchange_trade_id,
                        fill_time,
                        price,
                        qty,
                        notional,
                        fee,
                        fee_asset_id,
                        liquidity_flag
                    ) values (
                        :order_id,
                        :instrument_id,
                        :exchange_trade_id,
                        :fill_time,
                        :price,
                        :qty,
                        :notional,
                        :fee,
                        :fee_asset_id,
                        :liquidity_flag
                    )
                    returning fill_id
                    """
                ),
                {
                    "order_id": int(fill.order_id),
                    "instrument_id": instrument_id,
                    "exchange_trade_id": fill.exchange_trade_id,
                    "fill_time": fill.fill_time,
                    "price": fill.price,
                    "qty": fill.qty,
                    "notional": fill.notional,
                    "fee": fill.fee,
                    "fee_asset_id": fee_asset_id,
                    "liquidity_flag": fill.liquidity_flag,
                },
            ).scalar_one()
        )


class PositionRepository:
    def upsert_current(self, connection: Connection, snapshot: PositionSnapshot) -> None:
        account_id = resolve_account_id(connection, snapshot.account_code)
        instrument_id = resolve_instrument_id(connection, snapshot.exchange_code, snapshot.unified_symbol)
        connection.execute(
            text(
                """
                insert into execution.positions (
                    account_id,
                    instrument_id,
                    position_qty,
                    avg_entry_price,
                    realized_pnl,
                    unrealized_pnl,
                    mark_price,
                    updated_at
                ) values (
                    :account_id,
                    :instrument_id,
                    :position_qty,
                    :avg_entry_price,
                    coalesce(:realized_pnl, 0),
                    coalesce(:unrealized_pnl, 0),
                    :mark_price,
                    :updated_at
                )
                on conflict (account_id, instrument_id) do update
                set
                    position_qty = excluded.position_qty,
                    avg_entry_price = excluded.avg_entry_price,
                    realized_pnl = excluded.realized_pnl,
                    unrealized_pnl = excluded.unrealized_pnl,
                    mark_price = excluded.mark_price,
                    updated_at = excluded.updated_at
                """
            ),
            {
                "account_id": account_id,
                "instrument_id": instrument_id,
                "position_qty": snapshot.position_qty,
                "avg_entry_price": snapshot.avg_entry_price,
                "realized_pnl": snapshot.realized_pnl,
                "unrealized_pnl": snapshot.unrealized_pnl,
                "mark_price": snapshot.mark_price,
                "updated_at": snapshot.snapshot_time,
            },
        )

    def insert_snapshot(self, connection: Connection, snapshot: PositionSnapshot) -> None:
        account_id = resolve_account_id(connection, snapshot.account_code)
        instrument_id = resolve_instrument_id(connection, snapshot.exchange_code, snapshot.unified_symbol)
        connection.execute(
            text(
                """
                insert into execution.position_snapshots (
                    account_id,
                    instrument_id,
                    snapshot_time,
                    position_qty,
                    avg_entry_price,
                    mark_price,
                    unrealized_pnl,
                    realized_pnl
                ) values (
                    :account_id,
                    :instrument_id,
                    :snapshot_time,
                    :position_qty,
                    :avg_entry_price,
                    :mark_price,
                    :unrealized_pnl,
                    :realized_pnl
                )
                on conflict (account_id, instrument_id, snapshot_time) do update
                set
                    position_qty = excluded.position_qty,
                    avg_entry_price = excluded.avg_entry_price,
                    mark_price = excluded.mark_price,
                    unrealized_pnl = excluded.unrealized_pnl,
                    realized_pnl = excluded.realized_pnl
                """
            ),
            {
                "account_id": account_id,
                "instrument_id": instrument_id,
                "snapshot_time": snapshot.snapshot_time,
                "position_qty": snapshot.position_qty,
                "avg_entry_price": snapshot.avg_entry_price,
                "mark_price": snapshot.mark_price,
                "unrealized_pnl": snapshot.unrealized_pnl,
                "realized_pnl": snapshot.realized_pnl,
            },
        )


class BalanceRepository:
    def upsert_snapshot(self, connection: Connection, snapshot: BalanceSnapshot) -> None:
        account_id = resolve_account_id(connection, snapshot.account_code)
        asset_id = resolve_asset_id(connection, snapshot.asset)
        connection.execute(
            text(
                """
                insert into execution.balances (
                    account_id,
                    asset_id,
                    snapshot_time,
                    wallet_balance,
                    available_balance,
                    margin_balance,
                    equity
                ) values (
                    :account_id,
                    :asset_id,
                    :snapshot_time,
                    :wallet_balance,
                    :available_balance,
                    :margin_balance,
                    :equity
                )
                on conflict (account_id, asset_id, snapshot_time) do update
                set
                    wallet_balance = excluded.wallet_balance,
                    available_balance = excluded.available_balance,
                    margin_balance = excluded.margin_balance,
                    equity = excluded.equity
                """
            ),
            {
                "account_id": account_id,
                "asset_id": asset_id,
                "snapshot_time": snapshot.snapshot_time,
                "wallet_balance": snapshot.wallet_balance,
                "available_balance": snapshot.available_balance,
                "margin_balance": snapshot.margin_balance,
                "equity": snapshot.equity,
            },
        )
