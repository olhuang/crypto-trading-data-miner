# BTC 4H Breakout Perp Research Spec

## Purpose

This document translates a discretionary research idea into a repository-aligned
implementation plan for:
- one new strategy variant
- one first research assumption bundle line
- one staged feature-input extension path
- one clear separation between strategy logic, shared risk guardrails, and execution assumptions

It is intentionally scoped for the current Phase 5 backtest foundation.
It does **not** assume the full later replay, protection-lifecycle, or paper/live stack already exists.

This spec complements:
- `docs/strategy-input-and-feature-pipeline-spec.md`
- `docs/strategy-risk-assumption-management-spec.md`
- `docs/strategy-research-and-evaluation-spec.md`
- `docs/backtest-risk-guardrails-spec.md`
- `docs/strategy-workbench-spec.md`

---

## 1. Research Goal

Define a first research-grade BTC perpetual breakout prototype that is:
- simple enough to backtest honestly on the current bars-based engine
- modular enough to support ablation testing
- explicit about which parts are alpha logic versus risk/session controls

The source idea is:
- market: `BTCUSDT_PERP` first
- decision frame: `4h`
- trend filter: `20 EMA` vs `50 EMA`
- breakout trigger: break prior `20` bars high/low
- volatility filter: require elevated but not extreme volatility
- perp context filter: funding / OI / funding-settlement proximity
- stop / trailing / EMA exit
- per-trade risk sizing
- session stop rules after repeated losses

The implementation rule for this repo is:
- start with a realistic `v0.1` that the current runner can support cleanly
- defer anything that would require intrabar path assumptions or a full protection engine redesign

---

## 2. Recommended First Variant

Recommended first variant identity:
- `strategy_code`: `btc_4h_breakout_perp`
- `strategy_version`: `v0.1.0`

Recommended first-slice scope:
- market: `BTCUSDT_PERP`
- direction: `long-only`
- execution convention: evaluate on 4H close, enter/exit through the existing bars-based next-step market-fill path
- feature input baseline: extend the current perp-context line rather than inventing a separate raw-table read path

Why this first:
- the current repo already supports 1m-driven higher-timeframe strategy logic through the hourly example pattern
- long-only avoids immediate complexity around short borrow, trend inversion edge cases, and asymmetrical perp behavior
- next-step market-fill convention is more honest on the current engine than pretending exact intrabar breakout-stop entry fidelity

Explicit non-goals for `v0.1`:
- dated futures
- intrabar stop-entry breakout simulation
- full dual-side production-ready version
- full TP/SL/protection lifecycle reuse

---

## 3. Strategy Layer

## 3.1 Core Alpha Logic

The strategy should be responsible for:
- aggregating or maintaining 4H decision bars from the current 1m stream
- computing trend regime
- computing breakout condition
- computing volatility eligibility
- evaluating perp-context entry filters
- deciding desired target position
- deciding strategy-owned exits for the first research slice

The strategy should **not** be responsible for:
- shared session leverage limits
- shared daily-loss stop semantics for the account/session layer
- shared gross-exposure blocking
- fee/slippage/fill model selection

## 3.2 Trend Filter

Long-side rule:
- only allow long breakout entries when `ema_20 > ema_50`

Future short-side extension:
- only allow short breakout entries when `ema_20 < ema_50`

Implementation note:
- `ema_20` and `ema_50` should be computed on 4H closes, not on raw 1m closes

## 3.3 Breakout Trigger

Long-side rule:
- require current 4H close to finish above the highest high of the prior `20` completed 4H bars

Future short-side mirror:
- require current 4H close to finish below the lowest low of the prior `20` completed 4H bars

Important implementation rule:
- use completed 4H bars only for the breakout reference window
- do not include the current decision bar inside the lookback high/low set

## 3.4 Volatility Filter

Recommended `v0.1` choice:
- use `ATR%` instead of `20-day realized volatility`

Reason:
- ATR is directly compatible with the current bars-based strategy foundation
- ATR is also needed for stop distance, trailing distance, and risk sizing

Recommended rule:
- compute `atr_pct = atr_14 / close`
- require `atr_pct` to be above a configured lower regime threshold
- require `atr_pct` to remain below a configured upper extreme threshold

Recommended first implementation:
- thresholds are explicit strategy params
- do **not** first depend on dynamic rolling cross-history quantiles inside the strategy

This keeps the first run reproducible and easier to compare.

## 3.5 Perp Context Filters

Recommended `v0.1` filters:

### Funding Heat Filter
- block new longs when latest funding rate is above a configured positive threshold

### OI Push / Weak Price Progress Filter
- block new longs when OI rises too quickly but price progress over the same context window is weak

### Funding Proximity Filter
- block new longs inside a configured time window before the next funding settlement

Implementation note:
- these belong in strategy logic or strategy-ready feature context, not in shared session risk
- they are alpha-adjacent entry filters, not universal guardrails

## 3.6 First Exit Model

Recommended `v0.1` exit ownership:
- keep exits inside strategy-local logic

First-slice exit rules:
- initial stop distance reference: `2 ATR`
- trailing reference: `1.5 ATR` to `2 ATR`
- additional trend exit: close below `20 EMA`

Why strategy-local first:
- current repo guardrails are shared session controls, not a full trade protection engine
- pushing ATR trailing directly into shared protection too early would mix research prototyping with unfinished protection architecture

---

## 4. Risk Layer

## 4.1 Shared Risk Guardrails

These should continue using the existing shared session model:
- `max_drawdown_pct`
- `max_daily_loss_pct`
- `max_leverage`
- `max_gross_exposure_multiple`
- reduce-only behavior when blocked

Rule:
- shared risk guardrails remain account/session envelope controls
- they should not encode this strategy's alpha-specific entry logic

## 4.2 Strategy-Local Risk Rules

These should begin as strategy-local or strategy-runtime rules in `v0.1`:
- per-trade risk target = `0.5%` of current equity
- initial stop distance = `2 ATR`
- derived size from `risk_budget / stop_distance`
- strategy-level stop-trading after `3` consecutive losing trades
- strategy-level stop-trading after `-2R` for the current trading day

Reason:
- these are tightly coupled to this strategy's entry/exit structure and `R` definition
- the current shared guardrail layer is not yet built around realized-trade-sequence state or strategy-specific stop distance math

## 4.3 Recommended Future Promotion Path

If this strategy proves useful, later migration can be:
- keep `0.5% risk per trade` as strategy-local sizing policy
- consider moving daily stop-trading semantics into reusable session guardrail only after multiple strategies need the same `R`-based stop model

---

## 5. Execution Layer

## 5.1 Recommended First Execution Assumption

Use:
- current deterministic bars-based fill path
- next-step market-style fill convention already used by the baseline Phase 5 research line

Do not first implement:
- stop-entry intrabar breakout orders
- same-bar breakout trigger/fill claims
- detailed maker/taker path optimization

## 5.2 Why This Is The Honest First Choice

This strategy idea is naturally breakout-oriented, but the current engine is still bars-based.

If the repo pretends:
- breakout triggered inside the bar
- stop-entry was placed optimally
- fill occurred without path ambiguity

then the first result will overstate fidelity.

So the first honest rule should be:
- decision confirmed on 4H close
- position established through the current next-step bars-based execution convention

## 5.3 First Assumption Bundle Direction

Recommended first bundle line:
- `breakout_perp_research_v1`

Recommended contents:
- `market_data_version = md.bars_1m`
- `feature_input_version = bars_perp_breakout_context_v1`
- `fee_model_version = ref_fee_schedule_v1`
- `slippage_model_version = fixed_bps_v1`
- `fill_model_version = deterministic_bars_v1`
- `latency_model_version = bars_next_open_v1`
- `benchmark_set_code = btc_perp_breakout_baseline_v1`
- `risk_policy = perp_medium_v1` as the shared default envelope

---

## 6. Feature Input Plan

## 6.1 Recommended New Feature Input Version

Recommended new feature-input line:
- `bars_perp_breakout_context_v1`

This should extend, not replace, the current perp-context baseline.

The intended strategy snapshot should include:
- latest 1m bar
- recent 1m history
- internal 4H aggregation state or derived 4H bar history
- latest funding snapshot
- latest OI snapshot
- latest mark/index snapshots
- derived funding-settlement proximity
- derived OI momentum / OI push metric
- derived price progress metric over the same OI context window

## 6.2 Minimum Required Derived Fields

Recommended `v0.1` feature fields:
- `ema_20_4h`
- `ema_50_4h`
- `highest_high_20_4h`
- `lowest_low_20_4h`
- `atr_14_4h`
- `atr_pct_14_4h`
- `latest_funding_rate`
- `minutes_to_next_funding`
- `oi_change_pct_window`
- `price_change_pct_window`
- `oi_price_divergence_flag`

## 6.3 No-Look-Ahead Rules

All perp context must obey:
- latest known value with timestamp `<= decision_time`

Funding proximity rule should be derived from:
- the next expected funding boundary after current decision time
- not from future funding values

---

## 7. Parameters

Recommended first parameter set fields:
- `trend_fast_ema = 20`
- `trend_slow_ema = 50`
- `breakout_lookback_bars = 20`
- `atr_window = 14`
- `initial_stop_atr = 2.0`
- `trailing_stop_atr = 1.5`
- `exit_on_ema20_cross = true`
- `risk_per_trade_pct = 0.005`
- `volatility_floor_atr_pct`
- `volatility_ceiling_atr_pct`
- `max_funding_rate_long`
- `oi_change_pct_window`
- `min_price_change_pct_for_oi_confirmation`
- `skip_entries_within_minutes_of_funding`
- `max_consecutive_losses = 3`
- `max_daily_r_multiple_loss = 2.0`

Recommended `v0.1` simplification:
- fix most structural windows at the canonical values from the idea
- expose only the most decision-relevant thresholds for early ablation

---

## 8. Research Matrix

The first ablation matrix should be explicit.

Recommended order:

### Run Family A
- breakout only

### Run Family B
- breakout + trend filter

### Run Family C
- breakout + trend filter + volatility filter

### Run Family D
- breakout + trend filter + volatility filter + funding heat filter

### Run Family E
- full `v0.1` with funding proximity and OI-price divergence filter

Each run family should hold:
- same window
- same execution assumptions
- same shared session risk envelope
- same benchmark reference

This is necessary to answer:
- whether the context filters truly improve expectancy / drawdown structure
- or whether they only reduce trade count without adding robustness

---

## 9. Recommended First Implementation Sequence

1. add this strategy spec and freeze first-slice boundaries
2. implement new strategy variant as `long-only`
3. reuse the higher-timeframe aggregation pattern from the hourly example, extended to 4H
4. implement 4H EMA / breakout / ATR logic
5. add a new feature-input version for breakout-context fields
6. add a named assumption bundle for breakout perp research
7. run ablation set across at least:
   - one bull regime window
   - one high-volatility breakdown window
   - one mixed/chop window
8. only after that, consider:
   - short-side extension
   - richer trailing/stop lifecycle migration
   - dated futures adaptation

---

## 10. Recommended Explicit Deferrals

Defer these until after the first ablation results:
- short-side trading
- dated futures support
- dynamic percentile-based volatility gating
- full trade-level protection-engine integration
- intrabar breakout stop-order simulation
- richer execution urgency or maker-bias assumptions

These are good later enhancements, but they would blur the first research read.

---

## 11. Minimum Acceptance Criteria

This strategy line is ready for implementation when:
- one stable strategy identity is chosen
- the first execution convention is explicit
- the split between strategy-local logic and shared session risk is explicit
- the new feature-input needs are named clearly
- the first ablation matrix is defined before coding

---

## 12. Final Summary

The repository-aligned first implementation should be:
- `BTCUSDT_PERP`
- `4H`
- `long-only`
- `breakout + trend + ATR volatility + perp context filters`
- strategy-local ATR stop / trailing / risk-per-trade sizing
- shared session guardrails still enforced through the existing Phase 5 risk layer
- current deterministic bars-based execution assumptions used honestly

This keeps the first research slice:
- implementable on the current repo
- decomposable for ablation
- compatible with later Phase 5 compare/review work
- extensible toward replay, paper, and live without forcing an early redesign
