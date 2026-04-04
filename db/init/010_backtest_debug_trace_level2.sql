alter table backtest.debug_traces
    add column if not exists position_qty_delta numeric(30, 12),
    add column if not exists blocked_codes_json jsonb not null default '[]'::jsonb,
    add column if not exists sim_order_ids_json jsonb not null default '[]'::jsonb,
    add column if not exists sim_fill_ids_json jsonb not null default '[]'::jsonb,
    add column if not exists cash_delta numeric(30, 12),
    add column if not exists equity_delta numeric(30, 12),
    add column if not exists gross_exposure numeric(30, 12),
    add column if not exists net_exposure numeric(30, 12);
