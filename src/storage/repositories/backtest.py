from __future__ import annotations

import json
from typing import Sequence

from sqlalchemy import text
from sqlalchemy.engine import Connection

from backtest.fills import SimulatedFill, SimulatedOrder
from backtest.performance import PerformancePoint, PerformanceSummary
from models.backtest import BacktestRunConfig
from storage.lookups import resolve_account_id, resolve_instrument_id, resolve_strategy_version_id


class BacktestRunRepository:
    def insert_run(self, connection: Connection, run_config: BacktestRunConfig) -> int:
        strategy_version_id = resolve_strategy_version_id(
            connection,
            run_config.session.strategy_code,
            run_config.session.strategy_version,
        )
        account_id = resolve_account_id(connection, run_config.session.account_code)
        params_json = {
            "session_code": run_config.session.session_code,
            "environment": run_config.session.environment,
            "netting_mode": run_config.session.netting_mode,
            "strategy_params": run_config.strategy_params_json,
            "run_metadata": run_config.metadata_json,
            "session_metadata": run_config.session.metadata_json,
            "execution_policy": run_config.session.execution_policy.model_dump(mode="json", by_alias=True),
            "protection_policy": run_config.session.protection_policy.model_dump(mode="json", by_alias=True),
        }
        return int(
            connection.execute(
                text(
                    """
                    insert into backtest.runs (
                        strategy_version_id,
                        account_id,
                        run_name,
                        universe_json,
                        start_time,
                        end_time,
                        market_data_version,
                        fee_model_version,
                        slippage_model_version,
                        latency_model_version,
                        params_json,
                        status
                    ) values (
                        :strategy_version_id,
                        :account_id,
                        :run_name,
                        cast(:universe_json as jsonb),
                        :start_time,
                        :end_time,
                        :market_data_version,
                        :fee_model_version,
                        :slippage_model_version,
                        :latency_model_version,
                        cast(:params_json as jsonb),
                        :status
                    )
                    returning run_id
                    """
                ),
                {
                    "strategy_version_id": strategy_version_id,
                    "account_id": account_id,
                    "run_name": run_config.run_name,
                    "universe_json": json.dumps(run_config.session.universe),
                    "start_time": run_config.start_time,
                    "end_time": run_config.end_time,
                    "market_data_version": run_config.market_data_version,
                    "fee_model_version": run_config.fee_model_version,
                    "slippage_model_version": run_config.slippage_model_version,
                    "latency_model_version": run_config.latency_model_version,
                    "params_json": json.dumps(params_json, default=str),
                    "status": "finished",
                },
            ).scalar_one()
        )

    def insert_orders(
        self,
        connection: Connection,
        *,
        run_id: int,
        orders: Sequence[SimulatedOrder],
    ) -> dict[str, int]:
        persisted_ids: dict[str, int] = {}
        instrument_cache: dict[tuple[str, str], int] = {}
        for order in orders:
            cache_key = (order.exchange_code, order.unified_symbol)
            instrument_id = instrument_cache.get(cache_key)
            if instrument_id is None:
                instrument_id = resolve_instrument_id(connection, order.exchange_code, order.unified_symbol)
                instrument_cache[cache_key] = instrument_id

            sim_order_id = int(
                connection.execute(
                    text(
                        """
                        insert into backtest.simulated_orders (
                            run_id,
                            signal_id,
                            instrument_id,
                            order_time,
                            side,
                            order_type,
                            price,
                            qty,
                            status
                        ) values (
                            :run_id,
                            :signal_id,
                            :instrument_id,
                            :order_time,
                            :side,
                            :order_type,
                            :price,
                            :qty,
                            :status
                        )
                        returning sim_order_id
                        """
                    ),
                    {
                        "run_id": run_id,
                        "signal_id": order.signal_id,
                        "instrument_id": instrument_id,
                        "order_time": order.order_time,
                        "side": order.side.value,
                        "order_type": order.order_type.value,
                        "price": order.requested_price,
                        "qty": order.qty,
                        "status": order.status.value,
                    },
                ).scalar_one()
            )
            persisted_ids[order.order_id] = sim_order_id
        return persisted_ids

    def insert_fills(
        self,
        connection: Connection,
        *,
        run_id: int,
        fills: Sequence[SimulatedFill],
        order_id_map: dict[str, int],
    ) -> list[int]:
        persisted_ids: list[int] = []
        instrument_cache: dict[tuple[str, str], int] = {}
        for fill in fills:
            cache_key = (fill.exchange_code, fill.unified_symbol)
            instrument_id = instrument_cache.get(cache_key)
            if instrument_id is None:
                instrument_id = resolve_instrument_id(connection, fill.exchange_code, fill.unified_symbol)
                instrument_cache[cache_key] = instrument_id

            sim_fill_id = int(
                connection.execute(
                    text(
                        """
                        insert into backtest.simulated_fills (
                            run_id,
                            sim_order_id,
                            instrument_id,
                            fill_time,
                            price,
                            qty,
                            fee,
                            slippage_cost
                        ) values (
                            :run_id,
                            :sim_order_id,
                            :instrument_id,
                            :fill_time,
                            :price,
                            :qty,
                            :fee,
                            :slippage_cost
                        )
                        returning sim_fill_id
                        """
                    ),
                    {
                        "run_id": run_id,
                        "sim_order_id": order_id_map[fill.order_id],
                        "instrument_id": instrument_id,
                        "fill_time": fill.fill_time,
                        "price": fill.fill_price,
                        "qty": fill.qty,
                        "fee": fill.fee,
                        "slippage_cost": fill.slippage_cost,
                    },
                ).scalar_one()
            )
            persisted_ids.append(sim_fill_id)
        return persisted_ids

    def upsert_summary(self, connection: Connection, *, run_id: int, summary: PerformanceSummary) -> None:
        connection.execute(
            text(
                """
                insert into backtest.performance_summary (
                    run_id,
                    total_return,
                    annualized_return,
                    sharpe,
                    sortino,
                    max_drawdown,
                    turnover,
                    win_rate,
                    avg_holding_seconds,
                    fee_cost,
                    slippage_cost
                ) values (
                    :run_id,
                    :total_return,
                    :annualized_return,
                    null,
                    null,
                    :max_drawdown,
                    :turnover,
                    :win_rate,
                    null,
                    :fee_cost,
                    :slippage_cost
                )
                on conflict (run_id) do update
                set total_return = excluded.total_return,
                    annualized_return = excluded.annualized_return,
                    max_drawdown = excluded.max_drawdown,
                    turnover = excluded.turnover,
                    win_rate = excluded.win_rate,
                    fee_cost = excluded.fee_cost,
                    slippage_cost = excluded.slippage_cost
                """
            ),
            {
                "run_id": run_id,
                "total_return": summary.total_return,
                "annualized_return": summary.annualized_return,
                "max_drawdown": summary.max_drawdown,
                "turnover": summary.turnover,
                "win_rate": summary.win_rate,
                "fee_cost": summary.fee_cost,
                "slippage_cost": summary.slippage_cost,
            },
        )

    def upsert_timeseries(
        self,
        connection: Connection,
        *,
        run_id: int,
        performance_points: Sequence[PerformancePoint],
    ) -> None:
        for point in performance_points:
            connection.execute(
                text(
                    """
                    insert into backtest.performance_timeseries (
                        run_id,
                        ts,
                        equity,
                        cash,
                        gross_exposure,
                        net_exposure,
                        drawdown
                    ) values (
                        :run_id,
                        :ts,
                        :equity,
                        :cash,
                        :gross_exposure,
                        :net_exposure,
                        :drawdown
                    )
                    on conflict (run_id, ts) do update
                    set equity = excluded.equity,
                        cash = excluded.cash,
                        gross_exposure = excluded.gross_exposure,
                        net_exposure = excluded.net_exposure,
                        drawdown = excluded.drawdown
                    """
                ),
                {
                    "run_id": run_id,
                    "ts": point.ts,
                    "equity": point.equity,
                    "cash": point.cash,
                    "gross_exposure": point.gross_exposure,
                    "net_exposure": point.net_exposure,
                    "drawdown": point.drawdown,
                },
            )
