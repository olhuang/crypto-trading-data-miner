# Execution and Risk Engine Spec

## Purpose

This document defines the behavioral semantics of the execution and risk engine.

It focuses on:
- signal-to-order flow
- target position handling
- pre-trade and post-trade risk checks
- order lifecycle responsibilities
- paper/live consistency rules
- emergency and protective controls

This spec complements:
- `docs/api-contracts.md`
- `docs/backend-system-design.md`
- `docs/backtest-risk-guardrails-spec.md`
- `docs/security-and-secrets-spec.md`

---

## 1. Goals

The execution and risk system must:
1. turn strategy outputs into controlled orders
2. enforce risk checks before risky actions reach execution
3. preserve a canonical order/fill lifecycle across paper and live
4. keep paper and live behavior aligned where possible
5. support emergency and protective controls for safe operations

---

## 2. Core Flow

Recommended high-level flow:
1. market state is available
2. strategy emits signal and/or target position
3. portfolio/execution logic determines desired order action
4. pre-trade risk checks are applied
5. order request is created
6. order is simulated (paper/backtest) or routed to exchange (live)
7. order events and fills are persisted
8. positions and balances update
9. post-trade risk and monitoring checks run

---

## 3. Strategy Output Semantics

## 3.1 Signal vs Target Position

Signals and target positions have different semantics.

### Signal
Represents an actionable strategy decision or recommendation.
Examples:
- entry long
- exit
- reduce
- rebalance

### Target Position
Represents the desired resulting exposure.
Examples:
- target qty = 0.5 BTC
- target weight = 25%

## 3.2 Preferred Rule

If both signal and target position exist, the execution engine should treat target position as the desired state and signal as supporting context.

---

## 4. Execution Responsibilities

The execution engine is responsible for:
- turning desired exposure change into one or more orders
- applying venue trading rules
- applying pre-trade risk checks
- maintaining canonical order lifecycle records
- updating positions and balances from fills
- emitting latency and audit records

The execution engine is not responsible for defining strategy alpha logic itself.

---

## 5. Order Generation Semantics

## 5.1 Position Delta Rule

Orders should normally be generated from the delta between:
- current position state
- desired target position state

## 5.2 Order Splitting

The engine may split one desired adjustment into multiple orders for:
- size control
- venue trading-rule compliance
- execution strategy purposes

## 5.3 Trading Rule Validation

Before submission or simulation, validate:
- symbol/instrument is tradable
- qty meets lot size and min qty
- notional meets minimum notional
- price conforms to tick size where relevant
- account/environment is allowed to trade the symbol

---

## 6. Pre-Trade Risk Checks

## 6.1 Required Pre-Trade Checks

Minimum checks should include:
- max position qty
- max notional
- max leverage
- max daily loss threshold
- symbol/account trading eligibility
- session/runtime status (for example, emergency stop active)

## 6.2 Optional Later Checks

- concentration limits
- order rate limits
- venue-specific margin health thresholds
- correlation/exposure concentration checks

## 6.3 Pre-Trade Decision Outcomes

A pre-trade check should end in one of:
- `allow`
- `modify` (only if policy explicitly allows size clipping or safe transformation)
- `block`

Blocking should generate `risk.risk_events` with enough context for later review.

---

## 7. Post-Trade Risk Checks

Post-trade checks should monitor:
- realized and unrealized loss thresholds
- leverage state
- margin health
- exposure against configured limits after fills
- unusual rejection or exception patterns

Post-trade checks may trigger:
- warnings
- new order blocking
- session pause
- emergency control escalation

---

## 8. Order Lifecycle Semantics

## 8.1 Canonical Lifecycle States

Use a consistent normalized lifecycle such as:
- `new`
- `submitted`
- `acknowledged`
- `partial`
- `filled`
- `canceled`
- `rejected`
- `expired`

## 8.2 Lifecycle Recording Rules

- every state change should create an order event
- paper and live should both persist order events and fills through the same canonical model
- exchange-native statuses must be normalized, but raw/native status may be preserved in detail metadata

## 8.3 Client vs Exchange IDs

- internal `order_id` identifies the canonical record
- `client_order_id` identifies the outbound request intent
- `exchange_order_id` identifies the venue-side object when available

---

## 9. Paper vs Live Consistency Rules

## 9.1 Consistency Goal

Paper and live must share:
- canonical order request shape
- canonical order lifecycle model
- canonical fill model
- common risk checks where applicable

## 9.2 Allowed Differences

Paper may differ in:
- fill realism
- latency source
- partial fill behavior detail
- venue-side error variety

## 9.3 Consistency Rule

Differences between paper and live must be caused by explicit execution environment differences, not by incompatible internal contracts.

---

## 10. Fill and Position Update Rules

## 10.1 Fill Processing

Each fill should update:
- order filled quantity/status
- position state
- balances or margin-affecting state
- realized fee records
- related latency data if applicable

## 10.2 Position State

At minimum, position state should track:
- current quantity
- average entry price according to accounting policy
- realized PnL reference path
- last update time

## 10.3 Balance State

Balance state should reflect:
- wallet/cash-like balance changes
- fee deductions
- funding payments/receipts
- realized PnL movements where appropriate

---

## 11. Execution Controls

## 11.1 Pause

Pause should:
- stop new strategy-driven order creation
- leave existing open orders under policy-defined handling

## 11.2 Stop

Stop should:
- stop the runtime session
- define whether open orders remain or are canceled by policy

## 11.3 Cancel All Open Orders

A cancel-all action should:
- be explicit in scope
- be auditable
- affect open orders only

## 11.4 Emergency Stop

Emergency stop should:
- immediately prevent new live order submission
- define whether open orders are canceled automatically
- be highly restricted and auditable

---

## 12. Reduce-Only and Protective Order Semantics

The engine should preserve explicit flags when supported:
- `reduce_only`
- `post_only`
- time-in-force semantics

Reduce-only rules must ensure the order cannot expand exposure beyond intended reduction semantics.

---

## 13. Order Rejection and Exception Handling

## 13.1 Rejections

Rejections should:
- update canonical order state to `rejected`
- record reason code and detail metadata
- optionally trigger operational or risk review depending on severity/frequency

## 13.2 Exception Events

Examples:
- exchange reject
- order disappears and needs reconciliation
- forced reduction event
- margin issue causing venue-side intervention

These must be recordable through order events, risk events, or specialized exception tables.

---

## 14. Latency Semantics

The engine should capture or derive:
- signal time
- submit time
- ack time
- first fill time
- final fill time

This is necessary for:
- paper/live comparison
- execution analysis
- operator debugging

---

## 15. Reconciliation Expectations

The execution engine should assume reconciliation exists and must support it by:
- preserving raw identifiers
- writing order events and fills promptly
- making current state derivable from persisted records
- allowing exchange state comparison later

---

## 16. Safety Rules for Live Trading

Before a live order is submitted, the engine must know:
- environment is live intentionally
- account is authorized for live trading
- runtime is not paused/stopped/emergency-stopped
- actor or strategy session has permission to act
- pre-trade risk checks passed

---

## 17. Minimum Acceptance Criteria

This execution and risk behavior is sufficiently specified when:
- signal/target-to-order semantics are defined
- pre-trade and post-trade risk checks are defined
- order lifecycle normalization is defined
- paper/live consistency rules are explicit
- emergency and protective controls are explicit
- position and balance update responsibilities are explicit

---

## 18. Final Summary

The execution and risk engine should behave as a controlled pipeline:
- strategy intent becomes target exposure or signal
- execution converts intent to canonical orders
- pre-trade risk decides allow/modify/block
- order events and fills define lifecycle truth
- positions and balances update from fills
- post-trade risk and controls supervise resulting exposure

This is the backbone required for safe paper trading and live trading.
