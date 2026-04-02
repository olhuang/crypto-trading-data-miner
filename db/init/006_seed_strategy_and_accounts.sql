-- Phase 2/5+ bootstrap convenience seed extension
--
-- This file adds the minimum strategy/version/account rows needed so later
-- strategy-driven phases can resolve identifiers without manual setup.

begin;

-- -----------------------------------------------------------------------------
-- Starter strategy
-- -----------------------------------------------------------------------------
insert into strategy.strategies (
    strategy_code,
    strategy_name,
    description
)
values (
    'btc_momentum',
    'BTC Momentum',
    'minimal seed strategy for early backtest/paper flows'
)
on conflict (strategy_code) do update
set
    strategy_name = excluded.strategy_name,
    description = excluded.description;

-- -----------------------------------------------------------------------------
-- Starter strategy version
-- -----------------------------------------------------------------------------
insert into strategy.strategy_versions (
    strategy_id,
    version_code,
    params_json,
    feature_version,
    execution_version,
    risk_version,
    is_active
)
select
    s.strategy_id,
    'v1.0.0',
    '{}'::jsonb,
    'seed-v1',
    'seed-v1',
    'seed-v1',
    true
from strategy.strategies s
where s.strategy_code = 'btc_momentum'
on conflict (strategy_id, version_code) do update
set
    params_json = excluded.params_json,
    feature_version = excluded.feature_version,
    execution_version = excluded.execution_version,
    risk_version = excluded.risk_version,
    is_active = excluded.is_active;

-- -----------------------------------------------------------------------------
-- Starter paper account
-- -----------------------------------------------------------------------------
insert into execution.accounts (
    account_code,
    exchange_id,
    account_type,
    base_currency_id,
    is_active
)
select
    'paper_main',
    e.exchange_id,
    'paper',
    a.asset_id,
    true
from ref.exchanges e
join ref.assets a on a.asset_code = 'USDT'
where e.exchange_code = 'binance'
on conflict (account_code) do update
set
    exchange_id = excluded.exchange_id,
    account_type = excluded.account_type,
    base_currency_id = excluded.base_currency_id,
    is_active = excluded.is_active;

-- -----------------------------------------------------------------------------
-- Starter live placeholder account
-- -----------------------------------------------------------------------------
insert into execution.accounts (
    account_code,
    exchange_id,
    account_type,
    base_currency_id,
    is_active
)
select
    'binance_live_placeholder',
    e.exchange_id,
    'live',
    a.asset_id,
    false
from ref.exchanges e
join ref.assets a on a.asset_code = 'USDT'
where e.exchange_code = 'binance'
on conflict (account_code) do update
set
    exchange_id = excluded.exchange_id,
    account_type = excluded.account_type,
    base_currency_id = excluded.base_currency_id,
    is_active = excluded.is_active;

commit;
