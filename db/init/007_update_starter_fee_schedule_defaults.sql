-- Update starter fee schedule defaults for local bootstrap and early backtests.
--
-- This migration keeps existing local databases aligned with the current
-- bootstrap assumptions without requiring a full volume reset.

begin;

update ref.fee_schedules
set
    maker_fee_bps = 7.5,
    taker_fee_bps = 7.5
where instrument_type = 'spot'
  and coalesce(vip_tier, '') = 'default'
  and effective_from = '2025-01-01 00:00:00+00'::timestamptz;

update ref.fee_schedules
set
    maker_fee_bps = 1.8,
    taker_fee_bps = 4.5
where instrument_type = 'perp'
  and coalesce(vip_tier, '') = 'default'
  and effective_from = '2025-01-01 00:00:00+00'::timestamptz;

commit;
