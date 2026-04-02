create table if not exists md.orderbook_snapshots (
    instrument_id          bigint not null references ref.instruments(instrument_id),
    snapshot_time          timestamptz not null,
    ingest_time            timestamptz not null default now(),
    depth_levels           integer not null,
    bids_json              jsonb not null,
    asks_json              jsonb not null,
    checksum               text,
    source                 text,
    primary key (instrument_id, snapshot_time)
);

create index if not exists idx_orderbook_snapshots_ingest_time
    on md.orderbook_snapshots(ingest_time desc);

create table if not exists md.orderbook_deltas (
    delta_id               bigserial primary key,
    instrument_id          bigint not null references ref.instruments(instrument_id),
    event_time             timestamptz not null,
    ingest_time            timestamptz not null default now(),
    first_update_id        bigint,
    final_update_id        bigint,
    bids_json              jsonb,
    asks_json              jsonb,
    checksum               text,
    source                 text
);

create index if not exists idx_orderbook_deltas_instrument_event_time
    on md.orderbook_deltas(instrument_id, event_time desc);

create table if not exists md.mark_prices (
    instrument_id          bigint not null references ref.instruments(instrument_id),
    ts                     timestamptz not null,
    mark_price             numeric(30, 12) not null,
    funding_basis_bps      numeric(20, 10),
    ingest_time            timestamptz not null default now(),
    primary key (instrument_id, ts)
);

create table if not exists md.index_prices (
    instrument_id          bigint not null references ref.instruments(instrument_id),
    ts                     timestamptz not null,
    index_price            numeric(30, 12) not null,
    ingest_time            timestamptz not null default now(),
    primary key (instrument_id, ts)
);

create table if not exists md.liquidations (
    liquidation_id         bigserial primary key,
    instrument_id          bigint not null references ref.instruments(instrument_id),
    event_time             timestamptz not null,
    ingest_time            timestamptz not null default now(),
    side                   text,
    price                  numeric(30, 12),
    qty                    numeric(30, 12),
    notional               numeric(30, 12),
    source                 text,
    metadata_json          jsonb
);

create index if not exists idx_liquidations_instrument_event_time
    on md.liquidations(instrument_id, event_time desc);

create table if not exists md.raw_market_events (
    raw_event_id           bigserial primary key,
    exchange_id            smallint not null references ref.exchanges(exchange_id),
    instrument_id          bigint references ref.instruments(instrument_id),
    channel                text not null,
    event_type             text,
    event_time             timestamptz,
    ingest_time            timestamptz not null default now(),
    source_message_id      text,
    payload_json           jsonb not null
);

create index if not exists idx_raw_market_events_exchange_channel_ingest
    on md.raw_market_events(exchange_id, channel, ingest_time desc);

create table if not exists execution.order_events (
    order_event_id         bigserial primary key,
    order_id               bigint not null references execution.orders(order_id),
    event_type             text not null,
    event_time             timestamptz not null,
    status_before          text,
    status_after           text,
    exchange_order_id      text,
    client_order_id        text,
    reason_code            text,
    detail_json            jsonb,
    created_at             timestamptz not null default now()
);

create index if not exists idx_order_events_order_time
    on execution.order_events(order_id, event_time asc);

create table if not exists execution.account_ledger (
    ledger_id              bigserial primary key,
    account_id             bigint not null references execution.accounts(account_id),
    asset_id               bigint not null references ref.assets(asset_id),
    event_time             timestamptz not null,
    ledger_type            text not null,
    amount                 numeric(30, 12) not null,
    balance_after          numeric(30, 12),
    reference_type         text,
    reference_id           text,
    external_reference_id  text,
    detail_json            jsonb,
    created_at             timestamptz not null default now()
);

create index if not exists idx_account_ledger_account_asset_time
    on execution.account_ledger(account_id, asset_id, event_time desc);

create table if not exists execution.funding_pnl (
    funding_pnl_id         bigserial primary key,
    account_id             bigint not null references execution.accounts(account_id),
    instrument_id          bigint not null references ref.instruments(instrument_id),
    funding_time           timestamptz not null,
    position_qty           numeric(30, 12) not null,
    funding_rate           numeric(20, 10) not null,
    funding_payment        numeric(30, 12) not null,
    asset_id               bigint references ref.assets(asset_id),
    created_at             timestamptz not null default now()
);

create index if not exists idx_funding_pnl_account_time
    on execution.funding_pnl(account_id, funding_time desc);

create table if not exists risk.margin_tiers (
    margin_tier_id         bigserial primary key,
    instrument_id          bigint not null references ref.instruments(instrument_id),
    tier_no                integer not null,
    notional_floor         numeric(30, 12),
    notional_cap           numeric(30, 12),
    initial_margin_ratio   numeric(20, 10),
    maintenance_margin_ratio numeric(20, 10),
    max_leverage           numeric(20, 10),
    effective_from         timestamptz not null default now(),
    effective_to           timestamptz,
    unique (instrument_id, tier_no, effective_from)
);

create table if not exists ops.ingestion_jobs (
    ingestion_job_id       bigserial primary key,
    service_name           text not null,
    exchange_id            smallint references ref.exchanges(exchange_id),
    instrument_id          bigint references ref.instruments(instrument_id),
    data_type              text not null,
    schedule_type          text,
    window_start           timestamptz,
    window_end             timestamptz,
    status                 text not null,
    records_expected       bigint,
    records_written        bigint,
    started_at             timestamptz not null default now(),
    finished_at            timestamptz,
    error_message          text,
    metadata_json          jsonb
);

create index if not exists idx_ingestion_jobs_status_started_at
    on ops.ingestion_jobs(status, started_at desc);

create table if not exists ops.data_quality_checks (
    check_id               bigserial primary key,
    exchange_id            smallint references ref.exchanges(exchange_id),
    instrument_id          bigint references ref.instruments(instrument_id),
    data_type              text not null,
    check_time             timestamptz not null default now(),
    check_name             text not null,
    severity               text not null,
    status                 text not null,
    expected_value         text,
    observed_value         text,
    detail_json            jsonb
);

create index if not exists idx_data_quality_checks_time
    on ops.data_quality_checks(check_time desc);

create table if not exists ops.data_gaps (
    gap_id                 bigserial primary key,
    exchange_id            smallint references ref.exchanges(exchange_id),
    instrument_id          bigint references ref.instruments(instrument_id),
    data_type              text not null,
    gap_start              timestamptz not null,
    gap_end                timestamptz not null,
    expected_count         bigint,
    actual_count           bigint,
    status                 text not null default 'open',
    detected_at            timestamptz not null default now(),
    resolved_at            timestamptz,
    detail_json            jsonb
);

create index if not exists idx_data_gaps_status_detected_at
    on ops.data_gaps(status, detected_at desc);

create table if not exists ops.ws_connection_events (
    ws_event_id            bigserial primary key,
    service_name           text not null,
    exchange_id            smallint references ref.exchanges(exchange_id),
    channel                text,
    event_time             timestamptz not null default now(),
    event_type             text not null,
    connection_id          text,
    detail_json            jsonb
);

create index if not exists idx_ws_connection_events_time
    on ops.ws_connection_events(event_time desc);
