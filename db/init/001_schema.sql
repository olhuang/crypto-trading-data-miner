create schema if not exists ref;
create schema if not exists md;
create schema if not exists strategy;
create schema if not exists execution;
create schema if not exists backtest;
create schema if not exists risk;
create schema if not exists ops;

create table if not exists ref.exchanges (
    exchange_id       smallserial primary key,
    exchange_code     text not null unique,
    exchange_name     text not null,
    timezone          text,
    created_at        timestamptz not null default now()
);

create table if not exists ref.assets (
    asset_id           bigserial primary key,
    asset_code         text not null unique,
    asset_name         text,
    asset_type         text,
    created_at         timestamptz not null default now()
);

create table if not exists ref.instruments (
    instrument_id          bigserial primary key,
    exchange_id            smallint not null references ref.exchanges(exchange_id),
    venue_symbol           text not null,
    unified_symbol         text not null,
    instrument_type        text not null,
    base_asset_id          bigint not null references ref.assets(asset_id),
    quote_asset_id         bigint not null references ref.assets(asset_id),
    settlement_asset_id    bigint references ref.assets(asset_id),
    tick_size              numeric(30, 12),
    lot_size               numeric(30, 12),
    min_qty                numeric(30, 12),
    min_notional           numeric(30, 12),
    contract_size          numeric(30, 12),
    status                 text not null default 'trading',
    launch_time            timestamptz,
    delist_time            timestamptz,
    created_at             timestamptz not null default now(),
    unique(exchange_id, venue_symbol, instrument_type)
);

create table if not exists ref.fee_schedules (
    fee_schedule_id      bigserial primary key,
    exchange_id          smallint not null references ref.exchanges(exchange_id),
    instrument_type      text not null,
    vip_tier             text,
    maker_fee_bps        numeric(12, 6),
    taker_fee_bps        numeric(12, 6),
    effective_from       timestamptz not null,
    effective_to         timestamptz,
    created_at           timestamptz not null default now()
);

create table if not exists md.bars_1m (
    instrument_id        bigint not null references ref.instruments(instrument_id),
    bar_time             timestamptz not null,
    open                 numeric(30, 12) not null,
    high                 numeric(30, 12) not null,
    low                  numeric(30, 12) not null,
    close                numeric(30, 12) not null,
    volume               numeric(30, 12) not null,
    quote_volume         numeric(30, 12),
    trade_count          integer,
    created_at           timestamptz not null default now(),
    primary key (instrument_id, bar_time)
);

create table if not exists md.trades (
    instrument_id        bigint not null references ref.instruments(instrument_id),
    exchange_trade_id    text not null,
    event_time           timestamptz not null,
    ingest_time          timestamptz not null default now(),
    price                numeric(30, 12) not null,
    qty                  numeric(30, 12) not null,
    aggressor_side       text,
    primary key (instrument_id, exchange_trade_id)
);

create table if not exists md.funding_rates (
    instrument_id         bigint not null references ref.instruments(instrument_id),
    funding_time          timestamptz not null,
    funding_rate          numeric(20, 10) not null,
    mark_price            numeric(30, 12),
    index_price           numeric(30, 12),
    created_at            timestamptz not null default now(),
    primary key (instrument_id, funding_time)
);

create table if not exists md.open_interest (
    instrument_id         bigint not null references ref.instruments(instrument_id),
    ts                    timestamptz not null,
    open_interest         numeric(30, 12) not null,
    created_at            timestamptz not null default now(),
    primary key (instrument_id, ts)
);

create table if not exists strategy.strategies (
    strategy_id          bigserial primary key,
    strategy_code        text not null unique,
    strategy_name        text not null,
    description          text,
    created_at           timestamptz not null default now()
);

create table if not exists strategy.strategy_versions (
    strategy_version_id   bigserial primary key,
    strategy_id           bigint not null references strategy.strategies(strategy_id),
    version_code          text not null,
    params_json           jsonb not null,
    feature_version       text,
    execution_version     text,
    risk_version          text,
    is_active             boolean not null default false,
    created_at            timestamptz not null default now(),
    unique(strategy_id, version_code)
);

create table if not exists strategy.signals (
    signal_id              bigserial primary key,
    strategy_version_id    bigint not null references strategy.strategy_versions(strategy_version_id),
    instrument_id          bigint not null references ref.instruments(instrument_id),
    signal_time            timestamptz not null,
    signal_type            text not null,
    direction              text,
    score                  numeric(20, 10),
    target_qty             numeric(30, 12),
    target_notional        numeric(30, 12),
    reason_code            text,
    metadata_json          jsonb,
    created_at             timestamptz not null default now()
);

create table if not exists strategy.target_positions (
    target_position_id      bigserial primary key,
    strategy_version_id     bigint not null references strategy.strategy_versions(strategy_version_id),
    instrument_id           bigint not null references ref.instruments(instrument_id),
    target_time             timestamptz not null,
    target_qty              numeric(30, 12),
    target_weight           numeric(20, 10),
    target_notional         numeric(30, 12),
    created_at              timestamptz not null default now()
);

create table if not exists execution.accounts (
    account_id             bigserial primary key,
    account_code           text not null unique,
    exchange_id            smallint not null references ref.exchanges(exchange_id),
    account_type           text not null,
    base_currency_id       bigint references ref.assets(asset_id),
    is_active              boolean not null default true,
    created_at             timestamptz not null default now()
);

create table if not exists execution.orders (
    order_id                bigserial primary key,
    account_id              bigint not null references execution.accounts(account_id),
    strategy_version_id     bigint references strategy.strategy_versions(strategy_version_id),
    signal_id               bigint references strategy.signals(signal_id),
    instrument_id           bigint not null references ref.instruments(instrument_id),
    environment             text not null,
    client_order_id         text,
    exchange_order_id       text,
    side                    text not null,
    order_type              text not null,
    time_in_force           text,
    price                   numeric(30, 12),
    qty                     numeric(30, 12) not null,
    status                  text not null,
    reject_reason           text,
    event_time              timestamptz,
    submit_time             timestamptz,
    ack_time                timestamptz,
    cancel_time             timestamptz,
    created_at              timestamptz not null default now()
);

create index if not exists idx_orders_account_time on execution.orders(account_id, created_at desc);
create index if not exists idx_orders_instrument_time on execution.orders(instrument_id, created_at desc);
create index if not exists idx_orders_strategy_time on execution.orders(strategy_version_id, created_at desc);

create table if not exists execution.fills (
    fill_id                 bigserial primary key,
    order_id                bigint not null references execution.orders(order_id),
    instrument_id           bigint not null references ref.instruments(instrument_id),
    exchange_trade_id       text,
    fill_time               timestamptz not null,
    price                   numeric(30, 12) not null,
    qty                     numeric(30, 12) not null,
    notional                numeric(30, 12),
    fee                     numeric(30, 12),
    fee_asset_id            bigint references ref.assets(asset_id),
    liquidity_flag          text,
    created_at              timestamptz not null default now()
);

create table if not exists execution.positions (
    account_id               bigint not null references execution.accounts(account_id),
    instrument_id            bigint not null references ref.instruments(instrument_id),
    position_qty             numeric(30, 12) not null default 0,
    avg_entry_price          numeric(30, 12),
    realized_pnl             numeric(30, 12) not null default 0,
    unrealized_pnl           numeric(30, 12) not null default 0,
    mark_price               numeric(30, 12),
    liquidation_price        numeric(30, 12),
    updated_at               timestamptz not null default now(),
    primary key (account_id, instrument_id)
);

create table if not exists execution.position_snapshots (
    account_id               bigint not null references execution.accounts(account_id),
    instrument_id            bigint not null references ref.instruments(instrument_id),
    snapshot_time            timestamptz not null,
    position_qty             numeric(30, 12) not null,
    avg_entry_price          numeric(30, 12),
    mark_price               numeric(30, 12),
    unrealized_pnl           numeric(30, 12),
    realized_pnl             numeric(30, 12),
    primary key (account_id, instrument_id, snapshot_time)
);

create table if not exists execution.balances (
    account_id               bigint not null references execution.accounts(account_id),
    asset_id                 bigint not null references ref.assets(asset_id),
    snapshot_time            timestamptz not null,
    wallet_balance           numeric(30, 12) not null default 0,
    available_balance        numeric(30, 12) not null default 0,
    margin_balance           numeric(30, 12),
    equity                   numeric(30, 12),
    primary key (account_id, asset_id, snapshot_time)
);

create table if not exists backtest.runs (
    run_id                    bigserial primary key,
    strategy_version_id       bigint not null references strategy.strategy_versions(strategy_version_id),
    account_id                bigint references execution.accounts(account_id),
    run_name                  text,
    universe_json             jsonb,
    start_time                timestamptz not null,
    end_time                  timestamptz not null,
    market_data_version       text,
    fee_model_version         text,
    slippage_model_version    text,
    latency_model_version     text,
    params_json               jsonb,
    status                    text not null default 'finished',
    created_at                timestamptz not null default now()
);

create table if not exists backtest.simulated_orders (
    sim_order_id              bigserial primary key,
    run_id                    bigint not null references backtest.runs(run_id),
    signal_id                 bigint references strategy.signals(signal_id),
    instrument_id             bigint not null references ref.instruments(instrument_id),
    order_time                timestamptz not null,
    side                      text not null,
    order_type                text not null,
    price                     numeric(30, 12),
    qty                       numeric(30, 12) not null,
    status                    text not null,
    created_at                timestamptz not null default now()
);

create table if not exists backtest.simulated_fills (
    sim_fill_id               bigserial primary key,
    run_id                    bigint not null references backtest.runs(run_id),
    sim_order_id              bigint not null references backtest.simulated_orders(sim_order_id),
    instrument_id             bigint not null references ref.instruments(instrument_id),
    fill_time                 timestamptz not null,
    price                     numeric(30, 12) not null,
    qty                       numeric(30, 12) not null,
    fee                       numeric(30, 12),
    slippage_cost             numeric(30, 12),
    created_at                timestamptz not null default now()
);

create table if not exists backtest.performance_summary (
    run_id                    bigint primary key references backtest.runs(run_id),
    total_return              numeric(20, 10),
    annualized_return         numeric(20, 10),
    sharpe                    numeric(20, 10),
    sortino                   numeric(20, 10),
    max_drawdown              numeric(20, 10),
    turnover                  numeric(20, 10),
    win_rate                  numeric(20, 10),
    avg_holding_seconds       numeric(20, 2),
    fee_cost                  numeric(30, 12),
    slippage_cost             numeric(30, 12),
    created_at                timestamptz not null default now()
);

create table if not exists backtest.performance_timeseries (
    run_id                    bigint not null references backtest.runs(run_id),
    ts                        timestamptz not null,
    equity                    numeric(30, 12) not null,
    cash                      numeric(30, 12),
    gross_exposure            numeric(30, 12),
    net_exposure              numeric(30, 12),
    drawdown                  numeric(20, 10),
    primary key (run_id, ts)
);

create table if not exists risk.risk_limits (
    risk_limit_id             bigserial primary key,
    account_id                bigint not null references execution.accounts(account_id),
    instrument_id             bigint references ref.instruments(instrument_id),
    max_position_qty          numeric(30, 12),
    max_notional              numeric(30, 12),
    max_leverage              numeric(20, 10),
    max_daily_loss            numeric(30, 12),
    is_active                 boolean not null default true,
    created_at                timestamptz not null default now()
);

create table if not exists risk.risk_events (
    risk_event_id             bigserial primary key,
    account_id                bigint references execution.accounts(account_id),
    instrument_id             bigint references ref.instruments(instrument_id),
    event_time                timestamptz not null,
    event_type                text not null,
    severity                  text,
    detail_json               jsonb,
    created_at                timestamptz not null default now()
);

create table if not exists ops.system_logs (
    log_id                    bigserial primary key,
    service_name              text not null,
    log_time                  timestamptz not null default now(),
    level                     text not null,
    message                   text not null,
    context_json              jsonb
);
