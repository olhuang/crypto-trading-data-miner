from __future__ import annotations

import json
from typing import Sequence

from sqlalchemy import text
from sqlalchemy.engine import Connection

from backtest.fills import SimulatedFill, SimulatedOrder
from backtest.performance import PerformancePoint, PerformanceSummary
from backtest.traces import BacktestDebugTraceRecord
from models.backtest import BacktestRunConfig
from storage.lookups import resolve_account_id, resolve_instrument_id, resolve_strategy_version_id


class BacktestRunRepository:
    _BATCH_WRITE_CHUNK_SIZE = 500
    _EMPTY_JSON_ARRAY = "[]"
    _EMPTY_JSON_OBJECT = "{}"
    _JSON_NULL = "null"
    _INSERT_DEBUG_TRACES_SQL = text(
        """
        with input_rows as (
            select *
            from unnest(
                cast(:run_ids as bigint[]),
                cast(:instrument_ids as bigint[]),
                cast(:step_indexes as integer[]),
                cast(:bar_times as timestamptz[]),
                cast(:close_prices as numeric[]),
                cast(:current_position_qtys as numeric[]),
                cast(:position_qty_deltas as numeric[]),
                cast(:signal_counts as integer[]),
                cast(:intent_counts as integer[]),
                cast(:blocked_intent_counts as integer[]),
                cast(:blocked_codes_json_texts as text[]),
                cast(:created_order_counts as integer[]),
                cast(:sim_order_ids_json_texts as text[]),
                cast(:fill_counts as integer[]),
                cast(:sim_fill_ids_json_texts as text[]),
                cast(:cash_values as numeric[]),
                cast(:cash_deltas as numeric[]),
                cast(:equity_values as numeric[]),
                cast(:equity_deltas as numeric[]),
                cast(:gross_exposures as numeric[]),
                cast(:net_exposures as numeric[]),
                cast(:drawdowns as numeric[]),
                cast(:market_context_json_texts as text[]),
                cast(:decision_json_texts as text[]),
                cast(:risk_outcomes_json_texts as text[])
            ) as rows(
                run_id,
                instrument_id,
                step_index,
                bar_time,
                close_price,
                current_position_qty,
                position_qty_delta,
                signal_count,
                intent_count,
                blocked_intent_count,
                blocked_codes_json_text,
                created_order_count,
                sim_order_ids_json_text,
                fill_count,
                sim_fill_ids_json_text,
                cash,
                cash_delta,
                equity,
                equity_delta,
                gross_exposure,
                net_exposure,
                drawdown,
                market_context_json_text,
                decision_json_text,
                risk_outcomes_json_text
            )
        )
        insert into backtest.debug_traces (
            run_id,
            instrument_id,
            step_index,
            bar_time,
            close_price,
            current_position_qty,
            position_qty_delta,
            signal_count,
            intent_count,
            blocked_intent_count,
            blocked_codes_json,
            created_order_count,
            sim_order_ids_json,
            fill_count,
            sim_fill_ids_json,
            cash,
            cash_delta,
            equity,
            equity_delta,
            gross_exposure,
            net_exposure,
            drawdown,
            market_context_json,
            decision_json,
            risk_outcomes_json
        )
        select
            run_id,
            instrument_id,
            step_index,
            bar_time,
            close_price,
            current_position_qty,
            position_qty_delta,
            signal_count,
            intent_count,
            blocked_intent_count,
            cast(blocked_codes_json_text as jsonb),
            created_order_count,
            cast(sim_order_ids_json_text as jsonb),
            fill_count,
            cast(sim_fill_ids_json_text as jsonb),
            cash,
            cash_delta,
            equity,
            equity_delta,
            gross_exposure,
            net_exposure,
            drawdown,
            cast(market_context_json_text as jsonb),
            cast(decision_json_text as jsonb),
            cast(risk_outcomes_json_text as jsonb)
        from input_rows
        returning debug_trace_id
        """
    )

    def insert_run(
        self,
        connection: Connection,
        run_config: BacktestRunConfig,
        *,
        runtime_metadata: dict[str, object] | None = None,
        status: str = "finished",
    ) -> int:
        strategy_version_id = resolve_strategy_version_id(
            connection,
            run_config.session.strategy_code,
            run_config.session.strategy_version,
        )
        account_id = resolve_account_id(connection, run_config.session.account_code)
        effective_assumptions = run_config.build_effective_assumption_snapshot()
        params_json = self._build_params_json(run_config, runtime_metadata=runtime_metadata)
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
                    "market_data_version": effective_assumptions.market_data_version,
                    "fee_model_version": effective_assumptions.fee_model_version,
                    "slippage_model_version": effective_assumptions.slippage_model_version,
                    "latency_model_version": effective_assumptions.latency_model_version,
                    "params_json": json.dumps(params_json, default=str),
                    "status": status,
                },
            ).scalar_one()
        )

    def finalize_run(
        self,
        connection: Connection,
        *,
        run_id: int,
        run_config: BacktestRunConfig,
        runtime_metadata: dict[str, object] | None = None,
        status: str = "finished",
    ) -> None:
        params_json = self._build_params_json(run_config, runtime_metadata=runtime_metadata)
        connection.execute(
            text(
                """
                update backtest.runs
                set params_json = cast(:params_json as jsonb),
                    status = :status
                where run_id = :run_id
                """
            ),
            {
                "run_id": run_id,
                "params_json": json.dumps(params_json, default=str),
                "status": status,
            },
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

    def update_order_statuses(
        self,
        connection: Connection,
        *,
        orders: Sequence[SimulatedOrder],
        order_id_map: dict[str, int],
    ) -> None:
        updates = [
            {
                "sim_order_id": order_id_map[order.order_id],
                "status": order.status.value,
            }
            for order in orders
            if order.order_id in order_id_map
        ]
        if not updates:
            return

        for i in range(0, len(updates), self._BATCH_WRITE_CHUNK_SIZE):
            chunk = updates[i : i + self._BATCH_WRITE_CHUNK_SIZE]
            connection.execute(
                text(
                    """
                    update backtest.simulated_orders as sim_order
                    set status = updates.status
                    from (
                        values (:sim_order_id_0, :status_0)
                    ) as updates(sim_order_id, status)
                    where sim_order.sim_order_id = updates.sim_order_id
                    """
                )
                if len(chunk) == 1
                else text(
                    """
                    update backtest.simulated_orders as sim_order
                    set status = updates.status
                    from (
                        values
                    """
                    + ", ".join(
                        f"(:sim_order_id_{index}, :status_{index})"
                        for index in range(len(chunk))
                    )
                    + """
                    ) as updates(sim_order_id, status)
                    where sim_order.sim_order_id = updates.sim_order_id
                    """
                ),
                {
                    key: value
                    for index, row in enumerate(chunk)
                    for key, value in (
                        (f"sim_order_id_{index}", row["sim_order_id"]),
                        (f"status_{index}", row["status"]),
                    )
                },
            )

    def insert_fills(
        self,
        connection: Connection,
        *,
        run_id: int,
        fills: Sequence[SimulatedFill],
        order_id_map: dict[str, int],
    ) -> dict[str, int]:
        persisted_ids: dict[str, int] = {}
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
            persisted_ids[fill.fill_id] = sim_fill_id
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
        if not performance_points:
            return

        chunk_size = 5000
        for i in range(0, len(performance_points), chunk_size):
            chunk = performance_points[i : i + chunk_size]
            values_list = []
            for point in chunk:
                # Casts to avoid psycopg/SQLAlchemy parameter limit constraints and inject fast
                # ts is isoformat, others are numeric
                values_list.append(
                    f"({run_id}, '{point.ts.isoformat()}', {point.equity}, {point.cash}, {point.gross_exposure}, {point.net_exposure}, {point.drawdown})"
                )
            
            values_str = ", ".join(values_list)
            connection.execute(
                text(
                    f"""
                    insert into backtest.performance_timeseries (
                        run_id,
                        ts,
                        equity,
                        cash,
                        gross_exposure,
                        net_exposure,
                        drawdown
                    ) values {values_str}
                    on conflict (run_id, ts) do update
                    set equity = excluded.equity,
                        cash = excluded.cash,
                        gross_exposure = excluded.gross_exposure,
                        net_exposure = excluded.net_exposure,
                        drawdown = excluded.drawdown
                    """
                )
            )

    def insert_debug_traces(
        self,
        connection: Connection,
        *,
        run_id: int,
        debug_traces: Sequence[BacktestDebugTraceRecord],
        order_id_map: dict[str, int] | None = None,
        fill_id_map: dict[str, int] | None = None,
    ) -> list[int]:
        persisted_ids: list[int] = []
        order_id_map = order_id_map or {}
        fill_id_map = fill_id_map or {}
        instrument_cache: dict[tuple[str, str], int] = {}
        json_payload_cache: dict[int, str] = {}
        prepared_rows: list[dict[str, object]] = []
        for trace in debug_traces:
            cache_key = (trace.exchange_code, trace.unified_symbol)
            instrument_id = instrument_cache.get(cache_key)
            if instrument_id is None:
                instrument_id = resolve_instrument_id(connection, trace.exchange_code, trace.unified_symbol)
                instrument_cache[cache_key] = instrument_id
            resolved_order_ids = [order_id_map[order_id] for order_id in trace.created_order_ids if order_id in order_id_map]
            resolved_fill_ids = [fill_id_map[fill_id] for fill_id in trace.fill_ids if fill_id in fill_id_map]
            prepared_rows.append(
                {
                    "run_id": run_id,
                    "instrument_id": instrument_id,
                    "step_index": trace.step_index,
                    "bar_time": trace.bar_time,
                    "close_price": trace.close_price,
                    "current_position_qty": trace.current_position_qty,
                    "position_qty_delta": trace.position_qty_delta,
                    "signal_count": trace.signal_count,
                    "intent_count": trace.intent_count,
                    "blocked_intent_count": trace.blocked_intent_count,
                    "blocked_codes_json": self._serialize_json_payload(
                        trace.blocked_codes,
                        cache=json_payload_cache,
                        empty_json=self._EMPTY_JSON_ARRAY,
                    ),
                    "created_order_count": trace.created_order_count,
                    "sim_order_ids_json": self._serialize_json_payload(
                        resolved_order_ids,
                        cache=json_payload_cache,
                        empty_json=self._EMPTY_JSON_ARRAY,
                    ),
                    "fill_count": trace.fill_count,
                    "sim_fill_ids_json": self._serialize_json_payload(
                        resolved_fill_ids,
                        cache=json_payload_cache,
                        empty_json=self._EMPTY_JSON_ARRAY,
                    ),
                    "cash": trace.cash,
                    "cash_delta": trace.cash_delta,
                    "equity": trace.equity,
                    "equity_delta": trace.equity_delta,
                    "gross_exposure": trace.gross_exposure,
                    "net_exposure": trace.net_exposure,
                    "drawdown": trace.drawdown,
                    "market_context_json": self._serialize_json_payload(
                        trace.market_context_json,
                        cache=json_payload_cache,
                        empty_json=self._JSON_NULL,
                    ),
                    "decision_json": self._serialize_json_payload(
                        trace.decision_json,
                        cache=json_payload_cache,
                        empty_json=self._EMPTY_JSON_OBJECT,
                    ),
                    "risk_outcomes_json": self._serialize_json_payload(
                        trace.risk_outcomes_json,
                        cache=json_payload_cache,
                        empty_json=self._EMPTY_JSON_ARRAY,
                    ),
                }
            )

        for i in range(0, len(prepared_rows), self._BATCH_WRITE_CHUNK_SIZE):
            chunk = prepared_rows[i : i + self._BATCH_WRITE_CHUNK_SIZE]
            params = {
                "run_ids": [row["run_id"] for row in chunk],
                "instrument_ids": [row["instrument_id"] for row in chunk],
                "step_indexes": [row["step_index"] for row in chunk],
                "bar_times": [row["bar_time"] for row in chunk],
                "close_prices": [row["close_price"] for row in chunk],
                "current_position_qtys": [row["current_position_qty"] for row in chunk],
                "position_qty_deltas": [row["position_qty_delta"] for row in chunk],
                "signal_counts": [row["signal_count"] for row in chunk],
                "intent_counts": [row["intent_count"] for row in chunk],
                "blocked_intent_counts": [row["blocked_intent_count"] for row in chunk],
                "blocked_codes_json_texts": [row["blocked_codes_json"] for row in chunk],
                "created_order_counts": [row["created_order_count"] for row in chunk],
                "sim_order_ids_json_texts": [row["sim_order_ids_json"] for row in chunk],
                "fill_counts": [row["fill_count"] for row in chunk],
                "sim_fill_ids_json_texts": [row["sim_fill_ids_json"] for row in chunk],
                "cash_values": [row["cash"] for row in chunk],
                "cash_deltas": [row["cash_delta"] for row in chunk],
                "equity_values": [row["equity"] for row in chunk],
                "equity_deltas": [row["equity_delta"] for row in chunk],
                "gross_exposures": [row["gross_exposure"] for row in chunk],
                "net_exposures": [row["net_exposure"] for row in chunk],
                "drawdowns": [row["drawdown"] for row in chunk],
                "market_context_json_texts": [row["market_context_json"] for row in chunk],
                "decision_json_texts": [row["decision_json"] for row in chunk],
                "risk_outcomes_json_texts": [row["risk_outcomes_json"] for row in chunk],
            }
            rows = connection.execute(self._INSERT_DEBUG_TRACES_SQL, params).scalars().all()
            persisted_ids.extend(int(row) for row in rows)
        return persisted_ids

    @staticmethod
    def _serialize_json_payload(
        payload: object,
        *,
        cache: dict[int, str],
        empty_json: str,
    ) -> str:
        if payload is None:
            return empty_json
        if isinstance(payload, (list, tuple, dict)) and not payload:
            return empty_json
        cache_key = id(payload)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        serialized = json.dumps(payload, default=str)
        cache[cache_key] = serialized
        return serialized

    def _build_params_json(
        self,
        run_config: BacktestRunConfig,
        *,
        runtime_metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        selected_assumption_bundle = run_config.resolve_selected_assumption_bundle()
        resolved_session_risk_policy = run_config.resolve_session_risk_policy()
        effective_risk_policy = run_config.build_effective_risk_policy()
        effective_assumptions = run_config.build_effective_assumption_snapshot()
        return {
            "session_code": run_config.session.session_code,
            "environment": run_config.session.environment,
            "trading_timezone": run_config.session.trading_timezone,
            "netting_mode": run_config.session.netting_mode,
            "bar_interval": run_config.bar_interval,
            "initial_cash": str(run_config.initial_cash),
            "assumption_bundle_code": run_config.assumption_bundle_code,
            "assumption_bundle_version": run_config.assumption_bundle_version,
            "debug_trace_options": {
                "level": run_config.debug_trace_level,
                "stride": run_config.debug_trace_stride,
                "activity_only": run_config.debug_trace_activity_only,
            },
            "assumption_bundle": (
                selected_assumption_bundle.model_dump(mode="json", by_alias=True)
                if selected_assumption_bundle is not None
                else {}
            ),
            "assumption_overrides": run_config.build_assumption_overrides(),
            "effective_assumptions": effective_assumptions.model_dump(mode="json", by_alias=True),
            "strategy_params": run_config.strategy_params_json,
            "run_metadata": run_config.metadata_json,
            "runtime_metadata": runtime_metadata or {},
            "session_metadata": run_config.session.metadata_json,
            "execution_policy": run_config.session.execution_policy.model_dump(mode="json", by_alias=True),
            "protection_policy": run_config.session.protection_policy.model_dump(mode="json", by_alias=True),
            "session_risk_policy": resolved_session_risk_policy.model_dump(mode="json", by_alias=True),
            "risk_overrides": run_config.risk_overrides.as_patch_dict(),
            "risk_policy": effective_risk_policy.model_dump(mode="json", by_alias=True),
        }

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

    def list_debug_trace_records(
        self,
        connection: Connection,
        *,
        run_id: int,
        limit: int | None = None,
        unified_symbol: str | None = None,
        bar_time_from: object | None = None,
        bar_time_to: object | None = None,
        blocked_only: bool = False,
        risk_code: str | None = None,
        cooldown_state_only: bool = False,
        signals_only: bool = False,
        fills_only: bool = False,
        orders_only: bool = False,
    ) -> list[dict[str, object]]:
        filters = ["trace.run_id = :run_id"]
        params: dict[str, object] = {"run_id": run_id}
        if unified_symbol is not None:
            filters.append("instrument.unified_symbol = :unified_symbol")
            params["unified_symbol"] = unified_symbol
        if bar_time_from is not None:
            filters.append("trace.bar_time >= :bar_time_from")
            params["bar_time_from"] = bar_time_from
        if bar_time_to is not None:
            filters.append("trace.bar_time <= :bar_time_to")
            params["bar_time_to"] = bar_time_to
        if blocked_only:
            filters.append("trace.blocked_intent_count > 0")
        if risk_code is not None:
            filters.append("trace.blocked_codes_json ? :risk_code")
            params["risk_code"] = risk_code
        if cooldown_state_only:
            filters.append(
                """(
                    trace.blocked_codes_json ? 'cooldown_active'
                    or coalesce((trace.decision_json->'risk_state'->>'cooldown_active')::boolean, false)
                    or coalesce((trace.decision_json->'risk_state'->>'cooldown_activated_this_step')::boolean, false)
                )"""
            )
        if signals_only:
            filters.append("trace.signal_count > 0")
        if fills_only:
            filters.append("trace.fill_count > 0")
        if orders_only:
            filters.append("trace.created_order_count > 0")

        where_clause = " and ".join(filters)
        base_select = f"""
            select
                trace.debug_trace_id,
                trace.step_index,
                instrument.unified_symbol,
                trace.bar_time,
                trace.close_price,
                trace.current_position_qty,
                trace.position_qty_delta,
                trace.signal_count,
                trace.intent_count,
                trace.blocked_intent_count,
                trace.blocked_codes_json,
                trace.created_order_count,
                trace.sim_order_ids_json,
                trace.fill_count,
                trace.sim_fill_ids_json,
                trace.cash,
                trace.cash_delta,
                trace.equity,
                trace.equity_delta,
                trace.gross_exposure,
                trace.net_exposure,
                trace.drawdown,
                trace.market_context_json,
                trace.decision_json,
                trace.risk_outcomes_json,
                coalesce(
                    (
                        select jsonb_agg(
                            jsonb_build_object(
                                'anchor_id', a.anchor_id,
                                'debug_trace_id', a.debug_trace_id,
                                'scenario_id', a.scenario_id,
                                'expected_behavior', a.expected_behavior,
                                'observed_behavior', a.observed_behavior,
                                'created_at', a.created_at,
                                'updated_at', a.updated_at
                            ) order by a.created_at asc
                        )
                        from research.trace_investigation_anchors a
                        where a.debug_trace_id = trace.debug_trace_id
                    ),
                    '[]'::jsonb
                ) as investigation_anchors_json
            from backtest.debug_traces trace
            join ref.instruments instrument on instrument.instrument_id = trace.instrument_id
            where {where_clause}
        """
        if limit is None:
            query = f"""
                {base_select}
                order by trace.step_index asc
            """
        else:
            params["limit"] = limit
            query = f"""
                select *
                from (
                    {base_select}
                    order by trace.step_index desc
                    limit :limit
                ) sliced
                order by step_index asc
            """

        rows = connection.execute(text(query), params).mappings().all()
        return [dict(row) for row in rows]

    def count_debug_traces(self, connection: Connection, *, run_id: int) -> int:
        return int(
            connection.execute(
                text("select count(*) from backtest.debug_traces where run_id = :run_id"),
                {"run_id": run_id},
            ).scalar_one()
        )

    def get_debug_trace_run_id(self, connection: Connection, *, debug_trace_id: int) -> int | None:
        row = connection.execute(
            text(
                """
                select run_id
                from backtest.debug_traces
                where debug_trace_id = :debug_trace_id
                """
            ),
            {"debug_trace_id": debug_trace_id},
        ).first()
        if row is None:
            return None
        return int(row[0])

    def get_debug_trace_record(
        self,
        connection: Connection,
        *,
        run_id: int,
        debug_trace_id: int,
    ) -> dict[str, object] | None:
        row = connection.execute(
            text(
                """
                select
                    trace.run_id,
                    trace.debug_trace_id,
                    trace.step_index,
                    instrument.unified_symbol,
                    trace.bar_time,
                    trace.close_price,
                    trace.signal_count,
                    trace.intent_count,
                    trace.blocked_intent_count,
                    trace.created_order_count,
                    trace.fill_count,
                    trace.blocked_codes_json,
                    trace.market_context_json,
                    trace.decision_json,
                    trace.risk_outcomes_json,
                    coalesce(
                        (
                            select jsonb_agg(
                                jsonb_build_object(
                                    'anchor_id', a.anchor_id,
                                    'debug_trace_id', a.debug_trace_id,
                                    'scenario_id', a.scenario_id,
                                    'expected_behavior', a.expected_behavior,
                                    'observed_behavior', a.observed_behavior,
                                    'created_at', a.created_at,
                                    'updated_at', a.updated_at
                                ) order by a.created_at asc
                            )
                            from research.trace_investigation_anchors a
                            where a.debug_trace_id = trace.debug_trace_id
                        ),
                        '[]'::jsonb
                    ) as investigation_anchors_json
                from backtest.debug_traces trace
                join ref.instruments instrument on instrument.instrument_id = trace.instrument_id
                where trace.run_id = :run_id
                  and trace.debug_trace_id = :debug_trace_id
                """
            ),
            {
                "run_id": run_id,
                "debug_trace_id": debug_trace_id,
            },
        ).mappings().first()
        return dict(row) if row is not None else None

    def upsert_investigation_anchor(
        self,
        connection: Connection,
        *,
        debug_trace_id: int,
        scenario_id: str | None,
        expected_behavior: str | None,
        observed_behavior: str | None,
        actor_name: str,
    ) -> dict[str, object]:
        row = connection.execute(
            text(
                """
                insert into research.trace_investigation_anchors (
                    debug_trace_id,
                    scenario_id,
                    expected_behavior,
                    observed_behavior,
                    created_by,
                    updated_by
                ) values (
                    :debug_trace_id,
                    :scenario_id,
                    :expected_behavior,
                    :observed_behavior,
                    :actor_name,
                    :actor_name
                )
                returning *
                """
            ),
            {
                "debug_trace_id": debug_trace_id,
                "scenario_id": scenario_id,
                "expected_behavior": expected_behavior,
                "observed_behavior": observed_behavior,
                "actor_name": actor_name,
            },
        ).mappings().one()
        return dict(row)
