-- Phase 5 BTC 4H breakout strategy bootstrap seed
--
-- Adds the seeded 4H breakout research strategy so persisted backtest runs
-- can resolve strategy/version ids without manual local inserts.

begin;

insert into strategy.strategies (
    strategy_code,
    strategy_name,
    description
)
values (
    'btc_4h_breakout_perp',
    'BTC 4H Breakout Perp',
    'seeded BTC perpetual 4H breakout strategy for Phase 5 research flows'
)
on conflict (strategy_code) do update
set
    strategy_name = excluded.strategy_name,
    description = excluded.description;

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
    'v0.1.0',
    '{}'::jsonb,
    'seed-v1',
    'seed-v1',
    'seed-v1',
    true
from strategy.strategies s
where s.strategy_code = 'btc_4h_breakout_perp'
on conflict (strategy_id, version_code) do update
set
    params_json = excluded.params_json,
    feature_version = excluded.feature_version,
    execution_version = excluded.execution_version,
    risk_version = excluded.risk_version,
    is_active = excluded.is_active;

commit;
