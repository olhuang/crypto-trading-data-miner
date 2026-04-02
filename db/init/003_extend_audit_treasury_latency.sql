create table if not exists strategy.deployments (
    deployment_id            bigserial primary key,
    strategy_version_id      bigint not null references strategy.strategy_versions(strategy_version_id),
    environment              text not null,
    deployment_status        text not null,
    deployed_by              text,
    rollout_time             timestamptz not null default now(),
    stop_time                timestamptz,
    git_commit_sha           text,
    image_tag                text,
    config_snapshot_json     jsonb,
    reason_code              text,
    created_at               timestamptz not null default now()
);

create index if not exists idx_strategy_deployments_strategy_env_time
    on strategy.deployments(strategy_version_id, environment, rollout_time desc);

create table if not exists strategy.config_change_audit (
    config_change_id         bigserial primary key,
    strategy_version_id      bigint references strategy.strategy_versions(strategy_version_id),
    deployment_id            bigint references strategy.deployments(deployment_id),
    changed_by               text,
    change_time              timestamptz not null default now(),
    change_type              text not null,
    old_config_json          jsonb,
    new_config_json          jsonb,
    reason_code              text,
    metadata_json            jsonb
);

create index if not exists idx_strategy_config_change_time
    on strategy.config_change_audit(change_time desc);

create table if not exists execution.deposits_withdrawals (
    treasury_event_id        bigserial primary key,
    account_id               bigint not null references execution.accounts(account_id),
    asset_id                 bigint not null references ref.assets(asset_id),
    event_type               text not null,
    network                  text,
    tx_hash                  text,
    wallet_address           text,
    address_tag              text,
    amount                   numeric(30, 12) not null,
    fee_amount               numeric(30, 12),
    fee_asset_id             bigint references ref.assets(asset_id),
    requested_at             timestamptz,
    completed_at             timestamptz,
    status                   text not null,
    external_reference_id    text,
    detail_json              jsonb,
    created_at               timestamptz not null default now()
);

create index if not exists idx_deposits_withdrawals_account_status_time
    on execution.deposits_withdrawals(account_id, status, created_at desc);

create table if not exists execution.borrow_lend_rates (
    rate_id                  bigserial primary key,
    exchange_id              smallint not null references ref.exchanges(exchange_id),
    asset_id                 bigint not null references ref.assets(asset_id),
    margin_mode              text,
    ts                       timestamptz not null,
    borrow_rate              numeric(20, 10),
    lend_rate                numeric(20, 10),
    ingest_time              timestamptz not null default now(),
    unique (exchange_id, asset_id, margin_mode, ts)
);

create index if not exists idx_borrow_lend_rates_asset_time
    on execution.borrow_lend_rates(asset_id, ts desc);

create table if not exists execution.borrow_lend_events (
    borrow_event_id          bigserial primary key,
    account_id               bigint not null references execution.accounts(account_id),
    asset_id                 bigint not null references ref.assets(asset_id),
    event_time               timestamptz not null,
    event_type               text not null,
    principal_amount         numeric(30, 12),
    interest_amount          numeric(30, 12),
    outstanding_amount       numeric(30, 12),
    external_reference_id    text,
    detail_json              jsonb,
    created_at               timestamptz not null default now()
);

create index if not exists idx_borrow_lend_events_account_asset_time
    on execution.borrow_lend_events(account_id, asset_id, event_time desc);

create table if not exists execution.execution_latency_metrics (
    latency_metric_id        bigserial primary key,
    environment              text not null,
    account_id               bigint references execution.accounts(account_id),
    strategy_version_id      bigint references strategy.strategy_versions(strategy_version_id),
    order_id                 bigint references execution.orders(order_id),
    instrument_id            bigint references ref.instruments(instrument_id),
    signal_time              timestamptz,
    order_submit_time        timestamptz,
    exchange_ack_time        timestamptz,
    first_fill_time          timestamptz,
    final_fill_time          timestamptz,
    ws_receive_time          timestamptz,
    local_process_time_ms    integer,
    signal_to_submit_ms      integer,
    submit_to_ack_ms         integer,
    ack_to_first_fill_ms     integer,
    submit_to_final_fill_ms  integer,
    metadata_json            jsonb,
    created_at               timestamptz not null default now()
);

create index if not exists idx_execution_latency_metrics_order
    on execution.execution_latency_metrics(order_id);

create index if not exists idx_execution_latency_metrics_time
    on execution.execution_latency_metrics(created_at desc);

create table if not exists risk.exchange_status_events (
    exchange_status_event_id bigserial primary key,
    exchange_id              smallint not null references ref.exchanges(exchange_id),
    instrument_id            bigint references ref.instruments(instrument_id),
    event_time               timestamptz not null,
    event_type               text not null,
    status                   text,
    detail_json              jsonb,
    created_at               timestamptz not null default now()
);

create index if not exists idx_exchange_status_events_time
    on risk.exchange_status_events(event_time desc);

create table if not exists risk.forced_reduction_events (
    forced_reduction_event_id bigserial primary key,
    account_id               bigint references execution.accounts(account_id),
    instrument_id            bigint references ref.instruments(instrument_id),
    event_time               timestamptz not null,
    event_type               text not null,
    qty                      numeric(30, 12),
    price                    numeric(30, 12),
    amount                   numeric(30, 12),
    external_reference_id    text,
    detail_json              jsonb,
    created_at               timestamptz not null default now()
);

create index if not exists idx_forced_reduction_events_time
    on risk.forced_reduction_events(event_time desc);

create table if not exists backtest.universe_snapshots (
    run_id                   bigint not null references backtest.runs(run_id),
    snapshot_time            timestamptz not null,
    universe_json            jsonb not null,
    primary key (run_id, snapshot_time)
);

create table if not exists backtest.portfolio_allocation_history (
    allocation_id            bigserial primary key,
    run_id                   bigint references backtest.runs(run_id),
    strategy_version_id      bigint references strategy.strategy_versions(strategy_version_id),
    snapshot_time            timestamptz not null,
    account_id               bigint references execution.accounts(account_id),
    instrument_id            bigint references ref.instruments(instrument_id),
    target_weight            numeric(20, 10),
    actual_weight            numeric(20, 10),
    target_notional          numeric(30, 12),
    actual_notional          numeric(30, 12),
    cash_weight              numeric(20, 10),
    hedge_weight             numeric(20, 10),
    reason_code              text,
    metadata_json            jsonb,
    created_at               timestamptz not null default now()
);

create index if not exists idx_portfolio_allocation_history_time
    on backtest.portfolio_allocation_history(snapshot_time desc);
