create table if not exists md.global_long_short_account_ratios (
    instrument_id          bigint not null references ref.instruments(instrument_id),
    ts                     timestamptz not null,
    period_code            text not null,
    long_short_ratio       numeric(30, 12) not null,
    long_account_ratio     numeric(30, 12),
    short_account_ratio    numeric(30, 12),
    ingest_time            timestamptz not null default now(),
    primary key (instrument_id, ts, period_code)
);

create index if not exists idx_global_long_short_account_ratios_instrument_period_ts
    on md.global_long_short_account_ratios(instrument_id, period_code, ts desc);

create table if not exists md.top_trader_long_short_account_ratios (
    instrument_id          bigint not null references ref.instruments(instrument_id),
    ts                     timestamptz not null,
    period_code            text not null,
    long_short_ratio       numeric(30, 12) not null,
    long_account_ratio     numeric(30, 12),
    short_account_ratio    numeric(30, 12),
    ingest_time            timestamptz not null default now(),
    primary key (instrument_id, ts, period_code)
);

create index if not exists idx_top_trader_long_short_account_ratios_instrument_period_ts
    on md.top_trader_long_short_account_ratios(instrument_id, period_code, ts desc);

create table if not exists md.top_trader_long_short_position_ratios (
    instrument_id          bigint not null references ref.instruments(instrument_id),
    ts                     timestamptz not null,
    period_code            text not null,
    long_short_ratio       numeric(30, 12) not null,
    long_account_ratio     numeric(30, 12),
    short_account_ratio    numeric(30, 12),
    ingest_time            timestamptz not null default now(),
    primary key (instrument_id, ts, period_code)
);

create index if not exists idx_top_trader_long_short_position_ratios_instrument_period_ts
    on md.top_trader_long_short_position_ratios(instrument_id, period_code, ts desc);

create table if not exists md.taker_long_short_ratios (
    instrument_id          bigint not null references ref.instruments(instrument_id),
    ts                     timestamptz not null,
    period_code            text not null,
    buy_sell_ratio         numeric(30, 12) not null,
    buy_vol                numeric(30, 12),
    sell_vol               numeric(30, 12),
    ingest_time            timestamptz not null default now(),
    primary key (instrument_id, ts, period_code)
);

create index if not exists idx_taker_long_short_ratios_instrument_period_ts
    on md.taker_long_short_ratios(instrument_id, period_code, ts desc);
