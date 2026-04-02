-- Phase 1 verification script
--
-- Run this after local database bootstrap to validate that:
-- 1. schemas exist
-- 2. exchanges are seeded
-- 3. assets are seeded
-- 4. spot and perp instruments exist per exchange
-- 5. starter fee schedules exist
-- 6. no obvious duplicate reference rows exist

\echo '=== Phase 1 Verification: Schemas ==='
select schema_name
from information_schema.schemata
where schema_name in ('ref', 'md', 'strategy', 'execution', 'backtest', 'risk', 'ops')
order by schema_name;

\echo '=== Phase 1 Verification: Exchanges ==='
select exchange_code, exchange_name, timezone
from ref.exchanges
order by exchange_code;

\echo '=== Phase 1 Verification: Assets ==='
select asset_code, asset_name, asset_type
from ref.assets
order by asset_code;

\echo '=== Phase 1 Verification: Instruments ==='
select e.exchange_code, i.venue_symbol, i.unified_symbol, i.instrument_type, i.status
from ref.instruments i
join ref.exchanges e on e.exchange_id = i.exchange_id
order by e.exchange_code, i.instrument_type, i.venue_symbol;

\echo '=== Phase 1 Verification: Instrument Counts By Exchange And Type ==='
select e.exchange_code, i.instrument_type, count(*) as instrument_count
from ref.instruments i
join ref.exchanges e on e.exchange_id = i.exchange_id
group by e.exchange_code, i.instrument_type
order by e.exchange_code, i.instrument_type;

\echo '=== Phase 1 Verification: Fee Schedules ==='
select e.exchange_code, f.instrument_type, f.vip_tier, f.maker_fee_bps, f.taker_fee_bps, f.effective_from
from ref.fee_schedules f
join ref.exchanges e on e.exchange_id = f.exchange_id
order by e.exchange_code, f.instrument_type, f.effective_from;

\echo '=== Phase 1 Verification: Duplicate Exchanges (should return no rows) ==='
select exchange_code, count(*)
from ref.exchanges
group by exchange_code
having count(*) > 1;

\echo '=== Phase 1 Verification: Duplicate Assets (should return no rows) ==='
select asset_code, count(*)
from ref.assets
group by asset_code
having count(*) > 1;

\echo '=== Phase 1 Verification: Duplicate Instruments (should return no rows) ==='
select exchange_id, venue_symbol, count(*)
from ref.instruments
group by exchange_id, venue_symbol
having count(*) > 1;

\echo '=== Phase 1 Verification: Missing Spot Or Perp By Exchange (should return no rows) ==='
with required_pairs as (
    select e.exchange_code, t.instrument_type
    from ref.exchanges e
    cross join (values ('spot'), ('perp')) as t(instrument_type)
), actual_pairs as (
    select e.exchange_code, i.instrument_type
    from ref.instruments i
    join ref.exchanges e on e.exchange_id = i.exchange_id
    group by e.exchange_code, i.instrument_type
)
select r.exchange_code, r.instrument_type
from required_pairs r
left join actual_pairs a
  on a.exchange_code = r.exchange_code
 and a.instrument_type = r.instrument_type
where a.exchange_code is null
order by r.exchange_code, r.instrument_type;

\echo '=== Phase 1 Verification: Base/Quote/Settlement Mapping ==='
select
    e.exchange_code,
    i.venue_symbol,
    i.unified_symbol,
    i.instrument_type,
    ba.asset_code as base_asset,
    qa.asset_code as quote_asset,
    sa.asset_code as settlement_asset
from ref.instruments i
join ref.exchanges e on e.exchange_id = i.exchange_id
join ref.assets ba on ba.asset_id = i.base_asset_id
join ref.assets qa on qa.asset_id = i.quote_asset_id
left join ref.assets sa on sa.asset_id = i.settlement_asset_id
order by e.exchange_code, i.instrument_type, i.venue_symbol;

\echo '=== Phase 1 Verification Complete ==='
