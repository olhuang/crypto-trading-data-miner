-- Phase 5 sentiment strategy bootstrap seed
--
-- Adds the seeded sentiment-aware research strategy so persisted backtest runs
-- can resolve strategy/version ids without manual local inserts.

begin;

insert into strategy.strategies (
    strategy_code,
    strategy_name,
    description
)
values (
    'btc_sentiment_momentum',
    'BTC Sentiment Momentum',
    'seeded sentiment-aware BTC momentum strategy for backtest research flows'
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
    'v1.0.0',
    '{}'::jsonb,
    'seed-v1',
    'seed-v1',
    'seed-v1',
    true
from strategy.strategies s
where s.strategy_code = 'btc_sentiment_momentum'
on conflict (strategy_id, version_code) do update
set
    params_json = excluded.params_json,
    feature_version = excluded.feature_version,
    execution_version = excluded.execution_version,
    risk_version = excluded.risk_version,
    is_active = excluded.is_active;

commit;
