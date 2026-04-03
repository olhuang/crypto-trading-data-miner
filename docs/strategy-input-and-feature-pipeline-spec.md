# Strategy Input and Feature Pipeline Spec

## Purpose

This document defines the long-lived plan for how strategies should consume:
- bars
- trades
- funding rates
- open interest
- mark prices
- index prices
- future external features such as sentiment, on-chain, or macro inputs

The goal is to avoid coupling strategy code directly to raw database tables and to prevent future phases from drifting into inconsistent timestamp handling or look-ahead bias.

This spec complements:
- `docs/api-contracts.md`
- `docs/data-catalog.md`
- `docs/implementation-plan.md`
- `docs/position-management-spec.md`

---

## 1. Core Goal

Strategies should not read arbitrary raw tables ad hoc.

Instead, the system should evolve toward:
1. a stable data-loading layer
2. an explicit feature/alignment layer
3. a canonical strategy-input snapshot
4. a strategy interface that consumes that snapshot consistently across backtest, paper, and live

---

## 2. Why Bars-Only Is Not the Long-Term Model

Phase 5 begins with bars-based research because it is the fastest safe slice.

That does **not** mean strategies should be permanently limited to bars.

Future strategies may legitimately depend on:
- `md.funding_rates`
- `md.open_interest`
- `md.mark_prices`
- `md.index_prices`
- `md.trades`
- future order book views
- future external datasets such as sentiment or on-chain features

Therefore, the architecture must preserve a path from:
- bars-only MVP

to:
- multi-dataset, time-aligned strategy inputs

without rewriting the strategy interface from scratch.

---

## 3. Design Principles

### 3.1 Strategies Consume Snapshots, Not Raw Tables
- strategy code should consume a canonical input object
- it should not know SQL table layout details

### 3.2 Time Alignment Must Be Explicit
- each dataset has its own native cadence
- the engine must define what data is known at decision time
- timestamp alignment must be deterministic and reproducible

### 3.3 No Look-Ahead Bias
- at decision time `t`, the strategy may only access data available at or before `t`
- later-published values must not leak backward into the feature view

### 3.4 Feature Construction Is a Separate Responsibility
- feature engineering should not be hidden inside order execution or position accounting code
- raw ingestion and feature derivation should remain separate concerns

### 3.5 Backtest / Paper / Live Should Share Strategy Input Semantics
- the data source may differ
- the strategy-input contract should not

---

## 4. Recommended Layer Model

The intended long-term flow is:

```text
Raw data tables / external feeds
  -> dataset loaders
  -> time-alignment / feature builders
  -> StrategyInputSnapshot
  -> strategy evaluate(...)
  -> signal / target position
```

Recommended logical layers:

### 4.1 Dataset Loader Layer
Responsible for loading:
- bars
- funding
- OI
- mark/index
- trades
- future external datasets

This layer should:
- know where data comes from
- know how to query it efficiently
- not embed strategy-specific decision logic

### 4.2 Alignment and Feature Layer
Responsible for:
- windowing
- resampling
- as-of joins
- filling or not filling sparse values
- building derived features

This layer is where:
- funding gets aligned to a bar time
- latest OI is attached to a decision point
- mark/index values become available as-of the current step
- external sentiment values are attached only if published in time

### 4.3 Strategy Input Snapshot Layer
Responsible for producing a stable input object for strategies.

This layer should be the contract between:
- market/feature plumbing
- strategy logic

### 4.4 Strategy Layer
Responsible only for:
- reading the provided snapshot
- producing `Signal` or `TargetPosition`

---

## 5. Recommended Canonical Input Object

The long-term strategy interface should evolve toward a canonical snapshot object such as:

```text
StrategyInputSnapshot
- decision_time
- primary bar
- recent bars window
- latest funding snapshot
- latest open-interest snapshot
- latest mark/index snapshot
- optional recent trades window
- optional order book state
- optional external feature values
- current strategy/account state
```

This object does not need to be fully implemented in Phase 5.

However, future work should preserve space for it instead of hard-coding bars-only assumptions into the public strategy interface.

---

## 6. Dataset Families and Their Handling

### 6.1 Bars
Properties:
- regular cadence
- easiest to use for deterministic backtests

Best use:
- Phase 5 baseline strategy input

### 6.2 Funding Rates
Properties:
- sparse compared to bars
- discrete event times

Best use:
- perp carry features
- cost attribution
- context feature rather than bar replacement

Handling rule:
- attach the latest funding value known at decision time

### 6.3 Open Interest
Properties:
- sampled series
- cadence differs from bars

Best use:
- participation / crowding / positioning context

Handling rule:
- use as-of alignment to the decision timestamp

### 6.4 Mark and Index Prices
Properties:
- mark drives unrealized PnL/liquidation context
- index provides fair/reference context

Best use:
- perp context
- basis or spread features
- protection trigger context in later phases

Handling rule:
- attach latest known mark/index view as-of the decision point

### 6.5 Trades
Properties:
- high volume
- closer to microstructure

Best use:
- later higher-fidelity feature models
- replay and execution realism

Handling rule:
- not required for Phase 5 baseline
- should enter through explicit windows or aggregations, not raw ad hoc scans from inside strategy code

### 6.6 Future External Features
Examples:
- news sentiment
- social sentiment
- on-chain metrics
- macro/calendar features

Handling rule:
- must carry explicit publish time / effective time
- must join into strategy inputs using no-look-ahead rules

---

## 7. Time Alignment Rules

### 7.1 Decision Time
Each backtest or runtime step should have an explicit `decision_time`.

For Phase 5 bars-based work, this will usually be:
- bar close time
- or the next-bar-open decision convention, depending on the runner design

### 7.2 As-Of Join Rule
For sparse or lower-frequency datasets:
- use the latest value with timestamp `<= decision_time`
- do not use later values

### 7.3 Publication-Time Rule
If a dataset has both:
- event time
- publish/arrival time

the strategy should only see the data when the publish/arrival condition is satisfied.

This is especially important for:
- external sentiment
- delayed reference data
- any dataset where event time and known time may differ

### 7.4 Missing-Data Rule
The engine should define per dataset whether missing values are:
- disallowed
- carried forward
- defaulted to `None`
- or block strategy evaluation

This must be explicit and reproducible.

---

## 8. Feature Engineering Plan

Feature engineering should be layered:

### 8.1 Raw Feature Inputs
Examples:
- bar OHLCV
- last funding
- latest OI
- current mark/index

### 8.2 Derived Features
Examples:
- returns
- rolling volatility
- moving averages
- volume imbalance
- funding basis
- mark-vs-index spread
- OI momentum

### 8.3 Strategy-Ready Feature Bundle
Examples:
- trend bundle
- perp basis bundle
- crowding/context bundle
- sentiment bundle

This allows:
- feature reuse across strategies
- easier testing
- easier future model/version tracking

---

## 9. Recommended Code Architecture

Recommended future code boundaries:

- `src/datafeed/` or `src/features/loaders/`
  - dataset loaders and read adapters
- `src/features/aligners/`
  - time alignment, windowing, as-of joins
- `src/features/builders/`
  - derived features
- `src/features/snapshots/`
  - canonical snapshot assembly
- `src/strategy/`
  - strategy logic consuming the assembled snapshot

If these paths are introduced later, they should remain consistent with:
- `src/strategy/`
- `src/backtest/`
- `src/execution/`
- `docs/position-management-spec.md`

---

## 10. Recommended Phase Rollout

### 10.1 Phase 5 MVP
Use:
- bars only

Implement:
- deterministic bar iteration
- recent bars window
- strategy evaluation on bar-derived inputs

Do not require yet:
- funding/OI/mark/index in every strategy input
- trades/order book
- external sentiment

### 10.2 Phase 5 Expansion
Add:
- optional latest funding/OI/mark/index snapshots to strategy input
- simple derived context features

This is the first recommended extension after the bars-only MVP is stable.

### 10.3 Phase 6 / Phase 7
Extend the same strategy-input contract to:
- paper trading
- live trading

The input source changes, but strategy code should still read the same logical snapshot contract.

### 10.4 Later Research Expansion
Add:
- trades-derived features
- order-book-derived features
- external sentiment/on-chain/macro features

Only after:
- timestamp handling
- no-look-ahead behavior
- feature versioning

are all explicit.

---

## 11. Anti-Patterns To Avoid

Do not:
- let strategies query raw DB tables directly
- hide as-of alignment rules inside arbitrary strategy helper code
- mix feature engineering with execution accounting logic
- treat event time and publish time as interchangeable
- hard-code bars-only assumptions into the long-term public strategy interface

---

## 12. Minimum Acceptance Criteria

This plan is actionable when:
- strategy input is clearly separated from raw table access
- time alignment rules are explicit
- no-look-ahead expectations are explicit
- future non-bar datasets have a place in the architecture
- Phase 5 through Phase 7 rollout is staged clearly

---

## 13. Final Summary

The long-term strategy-input plan for this repo is:
- Phase 5 starts with bars-only strategy inputs for the first deterministic backtest slice
- later phases extend the same interface with aligned funding/OI/mark/index context
- higher-frequency or external datasets are added through explicit loader/alignment/feature layers
- strategy code should ultimately consume a canonical `StrategyInputSnapshot`, not raw tables

This should be treated as the planning backbone for future strategy-input, feature-engineering, and multi-dataset strategy work.
