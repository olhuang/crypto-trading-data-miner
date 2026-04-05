alter table backtest.debug_traces
    add column if not exists market_context_json jsonb;
