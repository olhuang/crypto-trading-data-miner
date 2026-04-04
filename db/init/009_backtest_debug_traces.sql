create table if not exists backtest.debug_traces (
    debug_trace_id        bigserial primary key,
    run_id                bigint not null references backtest.runs(run_id) on delete cascade,
    instrument_id         bigint not null references ref.instruments(instrument_id),
    step_index            bigint not null,
    bar_time              timestamptz not null,
    close_price           numeric(30, 12),
    current_position_qty  numeric(30, 12),
    signal_count          integer not null default 0,
    intent_count          integer not null default 0,
    blocked_intent_count  integer not null default 0,
    created_order_count   integer not null default 0,
    fill_count            integer not null default 0,
    cash                  numeric(30, 12),
    equity                numeric(30, 12),
    drawdown              numeric(20, 10),
    decision_json         jsonb not null default '{}'::jsonb,
    risk_outcomes_json    jsonb not null default '[]'::jsonb,
    created_at            timestamptz not null default now(),
    unique (run_id, step_index)
);

create index if not exists idx_backtest_debug_traces_run_bar_time
    on backtest.debug_traces(run_id, bar_time asc, step_index asc);

create index if not exists idx_backtest_debug_traces_run_instrument
    on backtest.debug_traces(run_id, instrument_id, step_index asc);
