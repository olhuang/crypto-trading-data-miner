-- Phase 1 seed data
--
-- Seed design principles:
-- 1. This file must be safe to re-run in development.
-- 2. Natural keys are preferred over hardcoded FK ids.
-- 3. `unified_symbol` is exchange-agnostic and represents the canonical system symbol.
-- 4. Spot instruments use settlement asset = quote asset for consistent accounting semantics.
-- 5. Perp instruments use settlement asset = quote asset for USDT-settled contracts.
-- 6. Trading-rule values below are starter defaults for local bootstrap and should later be
--    refreshed from exchange instrument metadata sync jobs in Phase 3.

begin;

-- -----------------------------------------------------------------------------
-- Exchanges
-- -----------------------------------------------------------------------------
insert into ref.exchanges (exchange_code, exchange_name, timezone)
values
    ('binance', 'Binance', 'UTC'),
    ('bybit', 'Bybit', 'UTC')
on conflict (exchange_code) do nothing;

-- -----------------------------------------------------------------------------
-- Assets
-- -----------------------------------------------------------------------------
insert into ref.assets (asset_code, asset_name, asset_type)
values
    ('BTC', 'Bitcoin', 'coin'),
    ('ETH', 'Ether', 'coin'),
    ('USDT', 'Tether USD', 'stablecoin'),
    ('USDC', 'USD Coin', 'stablecoin')
on conflict (asset_code) do nothing;

-- -----------------------------------------------------------------------------
-- Spot Instruments
-- -----------------------------------------------------------------------------
insert into ref.instruments (
    exchange_id,
    venue_symbol,
    unified_symbol,
    instrument_type,
    base_asset_id,
    quote_asset_id,
    settlement_asset_id,
    tick_size,
    lot_size,
    min_qty,
    min_notional,
    contract_size,
    status
)
select
    e.exchange_id,
    'BTCUSDT',
    'BTCUSDT_SPOT',
    'spot',
    ba.asset_id,
    qa.asset_id,
    qa.asset_id,
    0.01,
    0.00001,
    0.00001,
    10,
    null,
    'trading'
from ref.exchanges e
join ref.assets ba on ba.asset_code = 'BTC'
join ref.assets qa on qa.asset_code = 'USDT'
where e.exchange_code = 'binance'
on conflict (exchange_id, venue_symbol, instrument_type) do nothing;

insert into ref.instruments (
    exchange_id,
    venue_symbol,
    unified_symbol,
    instrument_type,
    base_asset_id,
    quote_asset_id,
    settlement_asset_id,
    tick_size,
    lot_size,
    min_qty,
    min_notional,
    contract_size,
    status
)
select
    e.exchange_id,
    'ETHUSDT',
    'ETHUSDT_SPOT',
    'spot',
    ba.asset_id,
    qa.asset_id,
    qa.asset_id,
    0.01,
    0.0001,
    0.0001,
    10,
    null,
    'trading'
from ref.exchanges e
join ref.assets ba on ba.asset_code = 'ETH'
join ref.assets qa on qa.asset_code = 'USDT'
where e.exchange_code = 'binance'
on conflict (exchange_id, venue_symbol, instrument_type) do nothing;

insert into ref.instruments (
    exchange_id,
    venue_symbol,
    unified_symbol,
    instrument_type,
    base_asset_id,
    quote_asset_id,
    settlement_asset_id,
    tick_size,
    lot_size,
    min_qty,
    min_notional,
    contract_size,
    status
)
select
    e.exchange_id,
    'BTCUSDT',
    'BTCUSDT_SPOT',
    'spot',
    ba.asset_id,
    qa.asset_id,
    qa.asset_id,
    0.01,
    0.00001,
    0.00001,
    10,
    null,
    'trading'
from ref.exchanges e
join ref.assets ba on ba.asset_code = 'BTC'
join ref.assets qa on qa.asset_code = 'USDT'
where e.exchange_code = 'bybit'
on conflict (exchange_id, venue_symbol, instrument_type) do nothing;

insert into ref.instruments (
    exchange_id,
    venue_symbol,
    unified_symbol,
    instrument_type,
    base_asset_id,
    quote_asset_id,
    settlement_asset_id,
    tick_size,
    lot_size,
    min_qty,
    min_notional,
    contract_size,
    status
)
select
    e.exchange_id,
    'ETHUSDT',
    'ETHUSDT_SPOT',
    'spot',
    ba.asset_id,
    qa.asset_id,
    qa.asset_id,
    0.01,
    0.0001,
    0.0001,
    10,
    null,
    'trading'
from ref.exchanges e
join ref.assets ba on ba.asset_code = 'ETH'
join ref.assets qa on qa.asset_code = 'USDT'
where e.exchange_code = 'bybit'
on conflict (exchange_id, venue_symbol, instrument_type) do nothing;

-- -----------------------------------------------------------------------------
-- Perpetual Instruments
-- -----------------------------------------------------------------------------
insert into ref.instruments (
    exchange_id,
    venue_symbol,
    unified_symbol,
    instrument_type,
    base_asset_id,
    quote_asset_id,
    settlement_asset_id,
    tick_size,
    lot_size,
    min_qty,
    min_notional,
    contract_size,
    status
)
select
    e.exchange_id,
    'BTCUSDT',
    'BTCUSDT_PERP',
    'perp',
    ba.asset_id,
    qa.asset_id,
    sa.asset_id,
    0.10,
    0.001,
    0.001,
    100,
    1,
    'trading'
from ref.exchanges e
join ref.assets ba on ba.asset_code = 'BTC'
join ref.assets qa on qa.asset_code = 'USDT'
join ref.assets sa on sa.asset_code = 'USDT'
where e.exchange_code = 'binance'
on conflict (exchange_id, venue_symbol, instrument_type) do nothing;

insert into ref.instruments (
    exchange_id,
    venue_symbol,
    unified_symbol,
    instrument_type,
    base_asset_id,
    quote_asset_id,
    settlement_asset_id,
    tick_size,
    lot_size,
    min_qty,
    min_notional,
    contract_size,
    status
)
select
    e.exchange_id,
    'ETHUSDT',
    'ETHUSDT_PERP',
    'perp',
    ba.asset_id,
    qa.asset_id,
    sa.asset_id,
    0.01,
    0.001,
    0.001,
    20,
    1,
    'trading'
from ref.exchanges e
join ref.assets ba on ba.asset_code = 'ETH'
join ref.assets qa on qa.asset_code = 'USDT'
join ref.assets sa on sa.asset_code = 'USDT'
where e.exchange_code = 'binance'
on conflict (exchange_id, venue_symbol, instrument_type) do nothing;

insert into ref.instruments (
    exchange_id,
    venue_symbol,
    unified_symbol,
    instrument_type,
    base_asset_id,
    quote_asset_id,
    settlement_asset_id,
    tick_size,
    lot_size,
    min_qty,
    min_notional,
    contract_size,
    status
)
select
    e.exchange_id,
    'BTCUSDT',
    'BTCUSDT_PERP',
    'perp',
    ba.asset_id,
    qa.asset_id,
    sa.asset_id,
    0.10,
    0.001,
    0.001,
    100,
    1,
    'trading'
from ref.exchanges e
join ref.assets ba on ba.asset_code = 'BTC'
join ref.assets qa on qa.asset_code = 'USDT'
join ref.assets sa on sa.asset_code = 'USDT'
where e.exchange_code = 'bybit'
on conflict (exchange_id, venue_symbol, instrument_type) do nothing;

insert into ref.instruments (
    exchange_id,
    venue_symbol,
    unified_symbol,
    instrument_type,
    base_asset_id,
    quote_asset_id,
    settlement_asset_id,
    tick_size,
    lot_size,
    min_qty,
    min_notional,
    contract_size,
    status
)
select
    e.exchange_id,
    'ETHUSDT',
    'ETHUSDT_PERP',
    'perp',
    ba.asset_id,
    qa.asset_id,
    sa.asset_id,
    0.01,
    0.001,
    0.001,
    20,
    1,
    'trading'
from ref.exchanges e
join ref.assets ba on ba.asset_code = 'ETH'
join ref.assets qa on qa.asset_code = 'USDT'
join ref.assets sa on sa.asset_code = 'USDT'
where e.exchange_code = 'bybit'
on conflict (exchange_id, venue_symbol, instrument_type) do nothing;

-- -----------------------------------------------------------------------------
-- Starter Fee Schedules
--
-- These are bootstrap defaults intended for local development and early backtests.
-- Production fee logic should later be sourced from exchange/account tier configuration.
-- -----------------------------------------------------------------------------
insert into ref.fee_schedules (
    exchange_id,
    instrument_type,
    vip_tier,
    maker_fee_bps,
    taker_fee_bps,
    effective_from
)
select
    e.exchange_id,
    'spot',
    'default',
    7.5,
    7.5,
    '2025-01-01 00:00:00+00'::timestamptz
from ref.exchanges e
where not exists (
    select 1
    from ref.fee_schedules f
    where f.exchange_id = e.exchange_id
      and f.instrument_type = 'spot'
      and coalesce(f.vip_tier, '') = 'default'
      and f.effective_from = '2025-01-01 00:00:00+00'::timestamptz
);

insert into ref.fee_schedules (
    exchange_id,
    instrument_type,
    vip_tier,
    maker_fee_bps,
    taker_fee_bps,
    effective_from
)
select
    e.exchange_id,
    'perp',
    'default',
    1.8,
    4.5,
    '2025-01-01 00:00:00+00'::timestamptz
from ref.exchanges e
where not exists (
    select 1
    from ref.fee_schedules f
    where f.exchange_id = e.exchange_id
      and f.instrument_type = 'perp'
      and coalesce(f.vip_tier, '') = 'default'
      and f.effective_from = '2025-01-01 00:00:00+00'::timestamptz
);

commit;
