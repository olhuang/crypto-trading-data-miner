# Position Management Spec

## Purpose

This document defines the long-lived architecture plan for:
- position management
- lot and fill attribution
- strategy-vs-account book separation
- execution policy handling
- TP / SL / trailing protection semantics
- portfolio reporting and auditability

It exists to prevent later phases from drifting into ad hoc patching as backtest, paper, live, and reconciliation capabilities expand.

This spec complements:
- `docs/execution-and-risk-engine-spec.md`
- `docs/pnl-and-accounting-spec.md`
- `docs/api-contracts.md`
- `docs/implementation-plan.md`

---

## 1. Goals

The position-management backbone must:
1. support backtest, paper, and live with the same core lifecycle language
2. separate strategy intent from account reality
3. preserve fill-level truth for audit and reconciliation
4. support add/reduce/reverse logic without losing attribution
5. support TP / SL and future protective logic as first-class state
6. support per-strategy reporting even when strategies share an account later
7. allow phased rollout without painting the repo into a corner

---

## 2. Source-of-Truth Alignment

This spec is additive to existing design rules:
- `docs/execution-and-risk-engine-spec.md` remains the source of truth for canonical order/fill lifecycle semantics
- `docs/pnl-and-accounting-spec.md` remains the source of truth for initial accounting vocabulary and the current weighted-average operational projection

This spec extends those documents by defining the architecture needed to support:
- multi-strategy position ownership
- future lot-aware accounting
- strategy/account fill allocation
- protection-rule lifecycle
- reporting/audit flows that survive beyond the Phase 5 MVP

---

## 3. Core Design Principles

### 3.1 Fill-Level Truth
- `fills` are the canonical execution fact
- positions, balances, and reports are projections derived from facts

### 3.2 Strategy Book and Account Book Must Be Separate
- a strategy's desired exposure is not the same as the account's net exposure
- this separation is required even if Phase 5 initially runs one strategy at a time

### 3.3 Aggregate Positions Are Projections
- `execution.positions` and similar aggregate state are useful and should remain
- they must not be the only source of truth once fills and lots exist

### 3.4 Protective State Is First-Class
- TP / SL / trailing behavior must not live only in transient strategy memory
- protection rules need explicit persisted lifecycle state

### 3.5 One Lifecycle Across Environments
- backtest, paper, and live should differ in data source and routing behavior
- they should not differ in internal order/fill/position language

### 3.6 Reporting Is Derived, Not Hand-Maintained
- reporting should be built from persisted facts and stable projections
- it should not depend on UI state or fragile in-memory bookkeeping

---

## 4. Books and Ownership Model

The system should think in three books:

### 4.1 Strategy Book
Represents what one strategy owns or intends.

Examples:
- strategy A is long 0.75 BTC
- strategy B is flat
- strategy C wants to reduce by 0.25 BTC

### 4.2 Account Book
Represents what the exchange account actually holds.

Examples:
- the exchange account is net long 0.50 BTC
- the account has one open order and two partial fills

### 4.3 Portfolio Book
Represents the higher-level aggregation across strategies/accounts for monitoring and reporting.

Examples:
- total exposure by environment
- total risk by account
- strategy attribution across a shared account

### 4.4 Rule
- all strategy decisions originate in the strategy book
- all real fills land in the account book
- allocation logic maps account-book fills back into strategy-book ownership

---

## 5. Canonical Facts and Projections

### 5.1 Canonical Facts
The architecture should preserve these as long-lived facts:
- strategy intents
- orders
- order events
- fills
- protection-rule events
- ledger events

### 5.2 Derived Projections
The architecture should derive these from facts:
- open position state
- average entry / exposure state
- position snapshots
- balance snapshots
- realized / unrealized PnL views
- run/session/account reports

### 5.3 Planned Future Tables / Models
The following are recommended additions or explicit future slices:
- `strategy.strategy_sessions`
- `execution.execution_policies`
- `execution.strategy_intents`
- `execution.fill_allocations`
- `execution.position_lots`
- `execution.lot_closures`
- `execution.protection_rules`
- `execution.protection_rule_events`
- `backtest.run_position_snapshots`
- `backtest.run_lot_events`
- `backtest.run_protection_events`
- `backtest.run_reports`

These names are planning-oriented and may evolve slightly, but the functional roles should remain.

---

## 6. Strategy Intent and Execution Policy

### 6.1 Strategy Output
Strategies may emit:
- `signal`
- `target_position`
- both, where target position is the desired state and signal is supporting context

### 6.2 Execution Policy
Every strategy/session should be associated with an execution policy that defines:
- preferred order types
- urgency / aggressiveness
- maker vs taker bias
- slicing behavior
- max participation / max child-order size
- allowed reduce-only behavior
- TP / SL style
- whether account-level netting is allowed

### 6.3 Rule
- strategies should not hard-code routing behavior directly into reporting/accounting logic
- execution policy must sit between strategy output and order creation

---

## 7. Position and Lot Management

### 7.1 Recommended Long-Term Backbone
The long-term canonical model should be:
- fill-level truth
- lot-aware position ownership
- aggregate position projections for convenience

### 7.2 Initial Accounting Alignment
To stay aligned with `docs/pnl-and-accounting-spec.md`:
- the Phase 5 MVP may continue to expose weighted-average position projections
- but the architecture should keep room for lot-aware extensions without redesigning the core lifecycle

### 7.3 Add / Reduce / Reverse Rules
- add: new fill increases exposure and may create or extend open lot state
- reduce: new fill closes part of existing exposure
- reverse: old direction is closed first, then new direction opens

### 7.4 Closing Policy
The system should reserve support for:
- weighted average operational projection
- future FIFO/LIFO-style derived views

Recommended rollout:
- Phase 5/6: weighted-average operational projection for simplicity
- schema/model/repository design: do not block future lot-aware derived reporting

### 7.5 Minimum Required Position Fields
At minimum, projections should support:
- signed quantity
- average entry
- realized PnL cumulative
- unrealized PnL basis
- last mark / valuation price
- last update time
- owning strategy/session where applicable

---

## 8. TP / SL / Protection Architecture

### 8.1 Protection Rules Must Be Persisted
Protection should be represented explicitly, not just recomputed from current strategy code.

Minimum rule categories:
- take profit
- stop loss
- trailing stop
- time-based exit

### 8.2 Scope Modes
The design should support:
- `position-level` protection
- `lot-level` protection

Recommended rollout:
- Phase 5 MVP: position-level only
- later phases: optional lot-level expansion

### 8.3 Trigger Basis
Protection evaluation should allow explicit trigger basis such as:
- mark price
- index price
- last trade
- bar high/low for backtest mode

### 8.4 Trigger Outcome
A triggered protection rule should produce:
- a protection event
- an execution intent or order request
- updated rule status (`triggered`, `canceled`, `expired`)

### 8.5 Same-Bar Ambiguity Rule for Backtest
In bars-only backtest mode, the engine must define a deterministic rule for:
- same-bar TP and SL touches
- same-bar entry and exit ambiguity

Recommended initial rule:
- explicit conservative ordering documented in code and reports

---

## 9. Multi-Strategy Coordination

### 9.1 The Real Problem
Different strategies may:
- trade the same symbol
- hold opposite directions
- use different execution styles
- use different TP / SL logic

Therefore, the engine must not assume one symbol equals one strategy-owned position.

### 9.2 Recommended Operating Modes

#### Mode A: Isolated Strategy Session
- one strategy effectively owns one position book
- simplest and best for Phase 5 MVP

#### Mode B: Shared Account with Virtual Strategy Books
- multiple strategies share one account
- account fills must be allocated back to strategies
- required before serious multi-strategy live trading

#### Mode C: Fully Netted Portfolio Mode
- central portfolio engine may intentionally net or offset strategy exposures
- defer until the earlier modes are stable

### 9.3 Recommended Rollout
- Phase 5: build with Mode A assumptions
- schema and interfaces: remain compatible with later Mode B
- Phase 6/7: introduce explicit fill allocation and strategy/account separation if shared-account execution is needed

### 9.4 Recommended Code Architecture
Different strategies should not each implement their own private position/accounting engine.

Instead, future code should separate:
- strategy logic
- session configuration
- execution policy
- protection policy
- shared lifecycle services

Recommended module boundaries:
- `src/strategy/`
  - strategy signal or target-position generation
- `src/session/`
  - strategy session config, ownership, runtime identity
- `src/execution/`
  - execution planning, order lifecycle, routing, fill handling
- `src/protection/`
  - TP / SL / trailing state, triggers, rule events
- `src/portfolio/`
  - position projection, equity, exposure, portfolio state
- `src/reporting/`
  - run/session/account/portfolio reporting and attribution

Recommended long-lived services:
- `StrategyRunner`
  - asks one strategy/session for its next intent
- `ExecutionPlanner`
  - turns target position changes into order plans using execution policy
- `OrderLifecycleService`
  - manages canonical order and order-event transitions
- `FillAccountingService`
  - turns fills into position, lot, balance, and ledger updates
- `ProtectionService`
  - manages protection rules and trigger outcomes
- `FillAllocationService`
  - maps account-book fills back into strategy ownership when accounts are shared
- `PortfolioProjector`
  - derives position and portfolio snapshots
- `ReportingProjector`
  - derives strategy/account/portfolio reports from persisted facts

### 9.5 Recommended Multi-Strategy Data Flow
The intended architecture should look like this:

```text
Strategy
  -> StrategySession
  -> ExecutionPolicy / ProtectionPolicy
  -> ExecutionIntent
  -> ExecutionPlanner
  -> Orders / OrderEvents
  -> Fills
  -> FillAllocationService (when needed)
  -> Strategy Book update
  -> Account Book update
  -> ProtectionService update
  -> PortfolioProjector / ReportingProjector
```

With explicit ownership boundaries:

```text
strategy output        = what this strategy wants
execution policy       = how this strategy prefers to get filled
account fills          = what the venue actually filled
fill allocation        = how actual fills map back to strategies
position/protection    = shared canonical state engine
reporting              = derived views for strategy/account/portfolio
```

### 9.6 Rule for Future Extensibility
To preserve future multi-strategy flexibility:
- strategies may vary by signal logic, execution policy, and protection policy
- strategies must not vary by private accounting semantics
- shared lifecycle services should remain canonical for backtest, paper, and live
- if shared-account execution is added later, it should extend through fill allocation and strategy/account book separation rather than replacing the existing lifecycle

---

## 10. Fill Allocation

When multiple strategies may share an account later, the system should support:
- one account-level fill
- one or more strategy-level allocations for that fill

Minimum allocation fields should include:
- fill id
- strategy/session id
- allocated quantity
- allocated notional
- allocation reason / policy

This is what keeps:
- strategy reporting
- strategy PnL
- strategy protection behavior
- reconciliation

from collapsing into account-level ambiguity.

---

## 11. Reporting Model

Reporting should be layered.

### 11.1 Execution Reporting
- order timeline
- order-event history
- fill timeline
- rejection/cancel reasons

### 11.2 Position Reporting
- open exposure
- closed exposure history
- average entry
- realized / unrealized PnL
- hold time
- TP / SL event history

### 11.3 Portfolio Reporting
- equity curve
- drawdown
- turnover
- fee cost
- funding cost
- gross / net PnL
- per-symbol attribution
- per-strategy attribution
- per-account attribution

### 11.4 Rule
Reporting should remain possible even if future accounting method views expand.

---

## 12. Bars-Based Backtest Limitations

The Phase 5 MVP will likely use bars.

That is acceptable, but the architecture must acknowledge:
- it does not know true intrabar order-book path
- limit-order realism is approximate
- TP / SL trigger ordering within a bar is approximate
- slippage must be model-driven, not recovered from bars

Therefore:
- Phase 5 is a research baseline
- not a full execution simulator

This is acceptable as long as:
- assumptions are explicit
- fill simulation is deterministic
- protection trigger rules are documented
- reporting states the simulation basis clearly

---

## 13. Phase-Aligned Implementation Plan

### 13.1 Phase 5: Backtest MVP
Implement:
- strategy interface
- isolated strategy-session book
- bars-based execution simulation
- weighted-average operational position projection
- position-level TP / SL
- fill-level persistence
- backtest reporting baseline

Do not require yet:
- shared-account fill allocation
- lot-level TP / SL
- exchange-native order-management complexity

### 13.2 Phase 6: Paper Trading
Extend with:
- real-time session lifecycle
- shared canonical order/fill/protection services
- timing metrics
- paper session reporting

Keep:
- isolated strategy-session as the default safe path

### 13.3 Phase 7: Live Trading
Extend with:
- real exchange fills
- authenticated routing
- account-book updates from exchange state
- optional strategy/account fill allocation if shared accounts are enabled

### 13.4 Phase 8: Reconciliation and Audit
Add:
- fill allocation audit
- position/book reconciliation
- ledger/funding reconciliation
- protection action audit trail
- operator diagnostics

---

## 14. Required Early Decisions

These decisions should be treated as frozen before serious Phase 5 implementation:
- strategy book and account book are distinct concepts
- fills are the execution truth
- aggregate positions are projections, not the only source of truth
- protection rules are first-class persisted state
- Phase 5 starts with isolated strategy sessions
- future shared-account support requires explicit fill allocation

---

## 15. Anti-Patterns To Avoid

Do not:
- treat one account-level position as if it belonged to one strategy forever
- store TP / SL only inside strategy runtime memory
- rely only on aggregate positions with no durable fill history
- create a separate lifecycle vocabulary for backtest, paper, and live
- make reporting depend on mutable UI state or manual spreadsheets

---

## 16. Minimum Acceptance Criteria

This spec is sufficiently actionable when:
- strategy book vs account book separation is explicit
- execution policy responsibilities are explicit
- protection rules are modeled explicitly
- fill allocation is planned for future shared-account support
- reporting layers are defined
- Phase 5 through Phase 8 rollout is staged clearly

---

## 17. Final Summary

The extensible position-management plan for this repo is:
- strategy intent remains separate from account reality
- fills remain canonical execution truth
- positions, balances, and reports are projections from facts
- TP / SL and related controls are explicit protected state
- Phase 5 starts with isolated strategy sessions and position-level protection
- later phases extend into shared-account allocation, live execution, and reconciliation without redoing the core model

This should be treated as the planning backbone for all future backtest, paper, live, and reporting work.
