-- Phase 2 execution hardening:
-- keep exchange-originated fills idempotent when a venue trade id is present.

create unique index if not exists idx_execution_fills_order_trade_unique
    on execution.fills(order_id, exchange_trade_id)
    where exchange_trade_id is not null;
