# BTC 4H Breakout Perp Implementation Checklist

## Purpose

This checklist turns:
- `docs/btc-4h-breakout-perp-research-spec.md`

into an implementation-ready sequence for the current repository.

It is intentionally scoped for the current Phase 5 backtest architecture.

---

## 1. First Delivery Goal

Deliver one research-usable first slice with:
- `BTCUSDT_PERP`
- `long-only`
- 4H decision logic derived from current 1m bars
- trend + breakout + ATR volatility gating
- first perp-context filters
- current bars-based next-step execution assumptions
- compare/analyze-compatible metadata

Recommended first implementation identity:
- `strategy_code = btc_4h_breakout_perp`
- `strategy_version = v0.1.0`

---

## 2. Files To Touch First

## Strategy
- `src/strategy/examples.py`
- `src/strategy/registry.py`
- `src/strategy/base.py`

## Backtest / Data Loading
- `src/backtest/data.py`
- `src/backtest/runner.py`

## Assumptions / Models
- `src/backtest/assumption_registry.py`
- `src/models/backtest.py`

## API / UI Surface
- `src/api/app.py`
- `frontend/monitoring/app.js`
- `frontend/monitoring/index.html`

## Seed / Bootstrap
- `db/init/` next ordered seed migration for strategy/version row
- `tests/test_seed_defaults.py`

## Tests
- `tests/test_phase5_foundation.py`
- `tests/test_api_models.py`

---

## 3. Phase 1: Strategy Skeleton

### Tasks
- [ ] add a new strategy class in `src/strategy/examples.py`
- [ ] register `btc_4h_breakout_perp@v0.1.0` in `src/strategy/registry.py`
- [ ] validate required params and defaults
- [ ] keep first version `long-only`

### Required First Params
- [ ] `trend_fast_ema`
- [ ] `trend_slow_ema`
- [ ] `breakout_lookback_bars`
- [ ] `atr_window`
- [ ] `initial_stop_atr`
- [ ] `trailing_stop_atr`
- [ ] `exit_on_ema20_cross`
- [ ] `risk_per_trade_pct`
- [ ] `volatility_floor_atr_pct`
- [ ] `volatility_ceiling_atr_pct`
- [ ] `max_funding_rate_long`
- [ ] `oi_change_pct_window`
- [ ] `min_price_change_pct_for_oi_confirmation`
- [ ] `skip_entries_within_minutes_of_funding`
- [ ] `max_consecutive_losses`
- [ ] `max_daily_r_multiple_loss`

### Acceptance Checks
- [ ] strategy instantiates from registry
- [ ] invalid params fail clearly
- [ ] strategy can return `None` without side effects when requirements are not met

---

## 4. Phase 2: 4H Aggregation and Core Logic

### Tasks
- [ ] reuse the incremental higher-timeframe aggregation pattern from `btc_hourly_momentum`
- [ ] derive 4H close series from 1m stream
- [ ] compute 20 EMA and 50 EMA on 4H closes
- [ ] compute prior-20-bar breakout high for long entries
- [ ] compute 14 ATR and ATR%
- [ ] gate entries on:
  - [ ] trend filter
  - [ ] breakout confirmation on 4H close
  - [ ] ATR% floor
  - [ ] ATR% ceiling

### Acceptance Checks
- [ ] 4H strategy works with 1m input bars
- [ ] breakout window excludes current bar
- [ ] ATR / EMA calculations are based on 4H bars, not raw 1m bars

---

## 5. Phase 3: First Perp Context Filters

### Tasks
- [ ] extend strategy evaluation to read perp context from `StrategyMarketContext`
- [ ] add funding heat filter for long entries
- [ ] add OI rise / weak price progress filter
- [ ] add funding proximity filter

### Required Feature Fields
- [ ] latest funding rate
- [ ] latest open interest
- [ ] minutes to next funding settlement
- [ ] OI change over one explicit context window
- [ ] price change over the same explicit context window

### Implementation Rule
- [ ] if a field is missing, entry should be skipped rather than guessed

### Acceptance Checks
- [ ] strategy behaves deterministically with identical context inputs
- [ ] context filters do not require direct table access from strategy code

---

## 6. Phase 4: Feature Input Version

### Tasks
- [ ] define a new feature-input line: `bars_perp_breakout_context_v1`
- [ ] extend the backtest data-loading path so the required context can be passed into the strategy snapshot
- [ ] keep the existing `bars_perp_context_v1` behavior unchanged for current strategies

### Suggested First Scope
- [ ] derive `minutes_to_next_funding`
- [ ] derive `oi_change_pct_window`
- [ ] derive `price_change_pct_window`
- [ ] derive a boolean or compact indicator for weak-price-vs-oi-push condition

### Acceptance Checks
- [ ] new feature-input version is opt-in
- [ ] existing strategies continue to work unchanged
- [ ] new context fields appear in persisted debug trace market context for explainability

---

## 7. Phase 5: Strategy-Local Trade Management

### Tasks
- [ ] implement ATR-based initial stop reference inside strategy-local state
- [ ] implement ATR trailing rule inside strategy-local state
- [ ] implement optional `close < 20EMA` exit rule
- [ ] implement risk-based target sizing from:
  - [ ] current equity
  - [ ] `risk_per_trade_pct`
  - [ ] ATR stop distance
- [ ] implement stop-trading after:
  - [ ] 3 consecutive losing trades
  - [ ] daily `-2R`

### Important Rule
- [ ] keep these rules out of shared guardrails in `v0.1`

### Acceptance Checks
- [ ] trade management can be explained from strategy-local metadata/debug traces
- [ ] strategy sizing and stop-trading state are reproducible across reruns

---

## 8. Phase 6: Assumption Bundle and Seed Path

### Tasks
- [ ] add `breakout_perp_research@v1` to `src/backtest/assumption_registry.py`
- [ ] set:
  - [ ] `market_data_version = md.bars_1m`
  - [ ] `feature_input_version = bars_perp_breakout_context_v1`
  - [ ] `fill_model_version = deterministic_bars_v1`
  - [ ] `latency_model_version = bars_next_open_v1`
  - [ ] `risk_policy = perp_medium_v1`
- [ ] add DB seed migration for `btc_4h_breakout_perp@v0.1.0`
- [ ] update seed-default coverage tests

### Acceptance Checks
- [ ] new strategy/version resolves through lookup-backed run creation
- [ ] new assumption bundle is visible in API/UI list surfaces

---

## 9. Phase 7: Backtests UI Surface

### Tasks
- [ ] expose the new strategy in the run-launch flow
- [ ] add a dedicated preset if useful
- [ ] expose the new bundle in assumption-bundle guidance
- [ ] label the strategy as `4H Breakout Perp`

### Acceptance Checks
- [ ] a user can launch the new strategy from `/monitoring`
- [ ] strategy-specific params are visible and understandable

---

## 10. First Tests To Write

## Unit / Foundation
- [ ] registry test: strategy is registered
- [ ] validation test: invalid param combinations fail
- [ ] logic test: trend false => no long entry
- [ ] logic test: breakout false => no long entry
- [ ] logic test: ATR% too low => no entry
- [ ] logic test: ATR% too high => no entry
- [ ] logic test: funding too hot => no entry
- [ ] logic test: close breakout + trend + acceptable ATR + acceptable funding => entry

## Context / Data
- [ ] feature-input test: `bars_perp_breakout_context_v1` provides required fields
- [ ] no-look-ahead test for funding / OI context alignment
- [ ] debug-trace test: selected context fields are visible in persisted trace evidence

## Persistence / API
- [ ] persisted run test for `btc_4h_breakout_perp`
- [ ] API create/detail integration test through `POST /api/v1/backtests/runs`
- [ ] seed-default test confirms strategy/version row exists

## Research-Ablation Sanity
- [ ] compare `breakout_only`
- [ ] compare `breakout + trend`
- [ ] compare `breakout + trend + atr`
- [ ] compare `breakout + trend + atr + funding`

---

## 11. Recommended First Coding Order

1. strategy class + registry
2. foundation tests for logic and registration
3. 4H aggregation + EMA / breakout / ATR
4. new feature-input version and context derivations
5. perp context filters
6. assumption bundle + DB seed migration
7. persisted run + API test
8. UI launch support
9. strategy-local trade-management refinements

---

## 12. Explicit Deferrals

- [ ] short-side version
- [ ] dated futures
- [ ] intrabar breakout stop-entry simulation
- [ ] shared guardrail migration for `R`-based stop-trading
- [ ] production-grade protection-engine integration
- [ ] dynamic percentile volatility regime engine

---

## 13. Done Criteria For `v0.1`

`v0.1` is done when:
- [ ] `btc_4h_breakout_perp@v0.1.0` can launch from the current API/UI
- [ ] one persisted run can complete end to end
- [ ] compare/analyze can distinguish the strategy from existing baselines
- [ ] debug traces show enough context to explain why entries were allowed or skipped
- [ ] at least the first ablation family can be run without ad hoc code changes
