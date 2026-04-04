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
    def insert_run(
        self,
        connection: Connection,
        run_config: BacktestRunConfig,
        *,
        runtime_metadata: dict[str, object] | None = None,
    ) -> int:
        strategy_version_id = resolve_strategy_version_id(
            connection,
            run_config.session.strategy_code,
            run_config.session.strategy_version,
        )
        account_id = resolve_account_id(connection, run_config.session.account_code)
        effective_risk_policy = run_config.build_effective_risk_policy()
        params_json = {
            "session_code": run_config.session.session_code,
            "environment": run_config.session.environment,
            "netting_mode": run_config.session.netting_mode,
            "bar_interval": run_config.bar_interval,
            "initial_cash": str(run_config.initial_cash),
            "assumption_bundle_code": run_config.assumption_bundle_code,
            "assumption_bundle_version": run_config.assumption_bundle_version,
            "strategy_params": run_config.strategy_params_json,
            "run_metadata": run_config.metadata_json,
            "runtime_metadata": runtime_metadata or {},
            "session_metadata": run_config.session.metadata_json,
            "execution_policy": run_config.session.execution_policy.model_dump(mode="json", by_alias=True),
            "protection_policy": run_config.session.protection_policy.model_dump(mode="json", by_alias=True),
            "session_risk_policy": run_config.session.risk_policy.model_dump(mode="json", by_alias=True),
            "risk_overrides": run_config.risk_overrides.as_patch_dict(),
            "risk_policy": effective_risk_policy.model_dump(mode="json", by_alias=True),
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

    def get_run(self, connection: Connection, run_id: int) -> dict[str, object] | None:
        row = connection.execute(
            text(
                """
                select
                    backtest.runs.run_id,
                    strategy_version.strategy_version_id,
                    strategy.strategy_code,
                    strategy_version.version_code as strategy_version,
                    account.account_id,
                    account.account_code,
                    backtest.runs.run_name,
                    backtest.runs.universe_json,
                    backtest.runs.start_time,
                    backtest.runs.end_time,
                    backtest.runs.market_data_version,
                    backtest.runs.fee_model_version,
                    backtest.runs.slippage_model_version,
                    backtest.runs.latency_model_version,
                    backtest.runs.params_json,
                    backtest.runs.status,
                    backtest.runs.created_at
                from backtest.runs
                join strategy.strategy_versions strategy_version
                  on strategy_version.strategy_version_id = backtest.runs.strategy_version_id
                join strategy.strategies strategy
                  on strategy.strategy_id = strategy_version.strategy_id
                left join execution.accounts account
                  on account.account_id = backtest.runs.account_id
                where backtest.runs.run_id = :run_id
                """
            ),
            {"run_id": run_id},
        ).mappings().first()
        return dict(row) if row is not None else None

    def list_runs(
        self,
        connection: Connection,
        *,
        strategy_code: str | None = None,
        strategy_version: str | None = None,
        account_code: str | None = None,
        unified_symbol: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        filters: list[str] = []
        params: dict[str, object] = {"limit": limit}

        if strategy_code is not None:
            filters.append("strategy.strategy_code = :strategy_code")
            params["strategy_code"] = strategy_code
        if strategy_version is not None:
            filters.append("strategy_version.version_code = :strategy_version")
            params["strategy_version"] = strategy_version
        if account_code is not None:
            filters.append("account.account_code = :account_code")
            params["account_code"] = account_code
        if unified_symbol is not None:
            filters.append("backtest.runs.universe_json ? :unified_symbol")
            params["unified_symbol"] = unified_symbol
        if status is not None:
            filters.append("backtest.runs.status = :status")
            params["status"] = status

        where_clause = ""
        if filters:
            where_clause = "where " + " and ".join(filters)

        rows = connection.execute(
            text(
                f"""
                select
                    backtest.runs.run_id,
                    strategy.strategy_code,
                    strategy_version.version_code as strategy_version,
                    account.account_code,
                    backtest.runs.run_name,
                    backtest.runs.universe_json,
                    backtest.runs.start_time,
                    backtest.runs.end_time,
                    backtest.runs.market_data_version,
                    backtest.runs.fee_model_version,
                    backtest.runs.slippage_model_version,
                    backtest.runs.latency_model_version,
                    backtest.runs.params_json,
                    backtest.runs.status,
                    backtest.runs.created_at,
                    performance.total_return,
                    performance.annualized_return,
                    performance.max_drawdown,
                    performance.turnover,
                    performance.win_rate,
                    performance.fee_cost,
                    performance.slippage_cost
                from backtest.runs
                join strategy.strategy_versions strategy_version
                  on strategy_version.strategy_version_id = backtest.runs.strategy_version_id
                join strategy.strategies strategy
                  on strategy.strategy_id = strategy_version.strategy_id
                left join execution.accounts account
                  on account.account_id = backtest.runs.account_id
                left join backtest.performance_summary performance
                  on performance.run_id = backtest.runs.run_id
                {where_clause}
                order by backtest.runs.created_at desc, backtest.runs.run_id desc
                limit :limit
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def get_performance_summary(self, connection: Connection, *, run_id: int) -> dict[str, object] | None:
        row = connection.execute(
            text(
                """
                select
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
                from backtest.performance_summary
                where run_id = :run_id
                """
            ),
            {"run_id": run_id},
        ).mappings().first()
        return dict(row) if row is not None else None

    def list_timeseries(
        self,
        connection: Connection,
        *,
        run_id: int,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        query = """
            select ts, equity, cash, gross_exposure, net_exposure, drawdown
            from backtest.performance_timeseries
            where run_id = :run_id
            order by ts asc
        """
        params: dict[str, object] = {"run_id": run_id}
        if limit is not None:
            query = """
                select ts, equity, cash, gross_exposure, net_exposure, drawdown
                from (
                    select
                        ts,
                        equity,
                        cash,
                        gross_exposure,
                        net_exposure,
                        drawdown
                    from backtest.performance_timeseries
                    where run_id = :run_id
                    order by ts desc
                    limit :limit
                ) sliced
                order by ts asc
            """
            params["limit"] = limit

        rows = connection.execute(text(query), params).mappings().all()
        return [dict(row) for row in rows]

    def list_order_records(
        self,
        connection: Connection,
        *,
        run_id: int,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        query = """
            select
                sim_order.sim_order_id,
                sim_order.signal_id,
                instrument.unified_symbol,
                sim_order.order_time,
                sim_order.side,
                sim_order.order_type,
                sim_order.price,
                sim_order.qty,
                sim_order.status
            from backtest.simulated_orders sim_order
            join ref.instruments instrument on instrument.instrument_id = sim_order.instrument_id
            where sim_order.run_id = :run_id
            order by sim_order.order_time asc, sim_order.sim_order_id asc
        """
        params: dict[str, object] = {"run_id": run_id}
        if limit is not None:
            query = """
                select *
                from (
                    select
                        sim_order.sim_order_id,
                        sim_order.signal_id,
                        instrument.unified_symbol,
                        sim_order.order_time,
                        sim_order.side,
                        sim_order.order_type,
                        sim_order.price,
                        sim_order.qty,
                        sim_order.status
                    from backtest.simulated_orders sim_order
                    join ref.instruments instrument on instrument.instrument_id = sim_order.instrument_id
                    where sim_order.run_id = :run_id
                    order by sim_order.order_time desc, sim_order.sim_order_id desc
                    limit :limit
                ) sliced
                order by order_time asc, sim_order_id asc
            """
            params["limit"] = limit

        rows = connection.execute(text(query), params).mappings().all()
        return [dict(row) for row in rows]

    def list_fill_records(
        self,
        connection: Connection,
        *,
        run_id: int,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        query = """
            select
                fill.sim_fill_id,
                fill.sim_order_id,
                instrument.unified_symbol,
                fill.fill_time,
                fill.price,
                fill.qty,
                fill.fee,
                fill.slippage_cost
            from backtest.simulated_fills fill
            join ref.instruments instrument on instrument.instrument_id = fill.instrument_id
            where fill.run_id = :run_id
            order by fill.fill_time asc, fill.sim_fill_id asc
        """
        params: dict[str, object] = {"run_id": run_id}
        if limit is not None:
            query = """
                select *
                from (
                    select
                        fill.sim_fill_id,
                        fill.sim_order_id,
                        instrument.unified_symbol,
                        fill.fill_time,
                        fill.price,
                        fill.qty,
                        fill.fee,
                        fill.slippage_cost
                    from backtest.simulated_fills fill
                    join ref.instruments instrument on instrument.instrument_id = fill.instrument_id
                    where fill.run_id = :run_id
                    order by fill.fill_time desc, fill.sim_fill_id desc
                    limit :limit
                ) sliced
                order by fill_time asc, sim_fill_id asc
            """
            params["limit"] = limit

        rows = connection.execute(text(query), params).mappings().all()
        return [dict(row) for row in rows]

    def list_signal_records(
        self,
        connection: Connection,
        *,
        run_id: int,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        query = """
            select distinct
                signal.signal_id,
                instrument.unified_symbol,
                signal.signal_time,
                signal.signal_type,
                signal.direction,
                signal.target_qty,
                signal.target_notional,
                signal.reason_code
            from backtest.simulated_orders sim_order
            join strategy.signals signal on signal.signal_id = sim_order.signal_id
            join ref.instruments instrument on instrument.instrument_id = signal.instrument_id
            where sim_order.run_id = :run_id
            order by signal.signal_time asc, signal.signal_id asc
        """
        params: dict[str, object] = {"run_id": run_id}
        if limit is not None:
            query = """
                select *
                from (
                    select distinct
                        signal.signal_id,
                        instrument.unified_symbol,
                        signal.signal_time,
                        signal.signal_type,
                        signal.direction,
                        signal.target_qty,
                        signal.target_notional,
                        signal.reason_code
                    from backtest.simulated_orders sim_order
                    join strategy.signals signal on signal.signal_id = sim_order.signal_id
                    join ref.instruments instrument on instrument.instrument_id = signal.instrument_id
                    where sim_order.run_id = :run_id
                    order by signal.signal_time desc, signal.signal_id desc
                    limit :limit
                ) sliced
                order by signal_time asc, signal_id asc
            """
            params["limit"] = limit

        rows = connection.execute(text(query), params).mappings().all()
        return [dict(row) for row in rows]
