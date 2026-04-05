# Binance Futures Sentiment Ratios Rollout

## Scope

Target initial collection for `BTCUSDT_PERP` from Binance USDT-M Futures:

- `globalLongShortAccountRatio`
- `topLongShortAccountRatio`
- `topLongShortPositionRatio`
- `takerlongshortRatio`

These are research/sentiment datasets, not execution-critical base market data.

## Collection Policy

- Treat all four endpoints as **recent-history datasets**
- Retention / availability assumption: **latest 30 days**
- Always send **both** `startTime` and `endTime`
- Initial symbol scope: `BTCUSDT_PERP`
- Initial period scope:
  - Phase A recommended default: `5m`
  - Optional Phase B expansion: `1h`, `4h`, `1d`

## Why Collect

These datasets are useful for:

- crowding / positioning features
- trend confirmation vs. contrarian signals
- liquidation / funding context
- regime labeling for research and replay analysis

## Why Not Treat As Core Base Data

These datasets are:

- exchange-derived aggregates
- recent-window only
- not required for order simulation or PnL accounting
- more suitable as feature/sentiment layers than canonical market facts

## Proposed Storage

Separate tables under `md.*`, keyed by `(instrument_id, ts, period_code)`:

- `md.global_long_short_account_ratios`
- `md.top_trader_long_short_account_ratios`
- `md.top_trader_long_short_position_ratios`
- `md.taker_long_short_ratios`

Suggested fields:

- `instrument_id`
- `ts`
- `period_code`
- `ingest_time`

Ratio tables:

- `long_short_ratio`
- `long_account_ratio`
- `short_account_ratio`

Taker table:

- `buy_sell_ratio`
- `buy_vol`
- `sell_vol`

## Recommended Rollout Order

### Slice 1: Backend Foundation

- schema migration
- market event models
- repositories
- Binance REST client fetch + normalize

### Slice 2: Snapshot / Backfill Integration

- wire into `market_snapshot_refresh`
- add recent-window incremental catch-up
- support dataset-scoped repair / backfill

### Slice 3: Quality / Monitoring

- integrity semantics should treat these as recent-retention datasets
- freshness / coverage summary in Quality UI
- optional dataset detail drill-down

### Slice 4: Research Consumption

- expose in feature pipelines
- join to backtest / replay research views
- optional compare-set diagnostics

## Notes

- `takerlongshortRatio` has known timestamp-filter quirks; pass both `startTime` and `endTime`
- Higher periods can be added later, but starting with `5m` keeps the first slice small
- Retention semantics should match current `open_interest` handling style rather than full-history continuity expectations
