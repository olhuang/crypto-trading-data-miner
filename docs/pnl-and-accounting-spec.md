# PnL and Accounting Spec

## Purpose

This document defines the accounting and PnL semantics for the trading platform.

It focuses on:
- realized and unrealized PnL
- fee and funding treatment
- ledger behavior
- balance/equity semantics
- position accounting conventions
- consistency across backtest, paper, and live

This spec complements:
- `docs/execution-and-risk-engine-spec.md`
- `docs/data-catalog.md`
- `docs/data-catalog-addendum.md`

---

## 1. Goals

The accounting layer must ensure:
1. fills and balances reconcile to a coherent financial view
2. backtest, paper, and live use compatible accounting language
3. fees, funding, and transfers are not mixed ambiguously
4. PnL can be explained and traced
5. equity and margin-related views are consistent enough for risk and UI use

---

## 2. Core Accounting Objects

The accounting model uses these primary concepts:
- positions
- fills
- balances
- account ledger entries
- funding PnL events
- performance summary/time series

## 2.1 System of Record Principle

For operational accounting truth:
- `execution.fills`
- `execution.account_ledger`
- `execution.funding_pnl`
- `execution.balances`
- `execution.positions`

must collectively explain the account state.

---

## 3. PnL Categories

## 3.1 Realized Trading PnL

Realized PnL is produced when position exposure is reduced or closed in a way that crystallizes profit/loss.

Examples:
- closing a long above entry price
- covering a short below entry price

## 3.2 Unrealized PnL

Unrealized PnL is mark-to-market PnL on currently open exposure.
It depends on:
- current position quantity
- average entry basis or chosen accounting basis
- mark price (preferred for derivatives)
- current reference price for spot where appropriate

## 3.3 Fee Cost

Trading fees are not part of price improvement itself. They should be tracked separately and then reflected in net PnL/equity views.

## 3.4 Funding PnL

Funding payments/receipts for perpetual instruments should be tracked separately from trade price PnL.

## 3.5 Other Cashflow Adjustments

Examples:
- rebates
- deposit/withdrawal activity
- borrow interest
- manual adjustments

These must not be conflated with trading alpha PnL.

---

## 4. Position Accounting Method

## 4.1 Recommended Initial Method

Use **weighted average cost / average entry price** as the primary position accounting method for the first implementation.

Why:
- simpler to implement consistently across backtest, paper, and live
- aligns well with position snapshot semantics already present in the schema

## 4.2 Future Extension

If tax or advanced accounting requirements arise later, FIFO/LIFO-style views can be added as derived analytical methods, not necessarily as the operational primary method.

## 4.3 Position State Fields

Operational position state should support:
- current position quantity
- average entry price
- realized PnL cumulative view
- last mark/reference price where needed
- last update time

---

## 5. Realized PnL Rules

## 5.1 Realization Trigger

Realized PnL occurs when a fill reduces existing exposure.

Examples:
- long 1 BTC -> sell 0.4 BTC: realized on 0.4 BTC
- short 1 BTC -> buy 1 BTC: realized on full 1 BTC

## 5.2 Directional Semantics

For long exposure:
- favorable exit above average entry = positive realized PnL

For short exposure:
- favorable buyback below average entry = positive realized PnL

## 5.3 Net vs Gross Realized PnL

Recommended definitions:
- **gross realized PnL**: price-based trading PnL before fees/funding
- **net realized PnL**: gross realized PnL after fees and other realized execution costs as presented in a net view

Both views may be useful, but naming must remain explicit.

---

## 6. Unrealized PnL Rules

## 6.1 Reference Price

Preferred reference prices:
- perpetuals: mark price
- spot: latest trade/close/mark equivalent according to chosen valuation policy

## 6.2 Formula Semantics

Unrealized PnL should be derived from:
- open quantity
- valuation price
- position basis

The exact numeric formula is implementation-specific, but the reference price source must be explicit and consistent.

## 6.3 UI Rule

Any displayed unrealized PnL should indicate the valuation basis used.

---

## 7. Fee Accounting Rules

## 7.1 Fee Event Treatment

Each fill may generate a fee event with:
- fee amount
- fee asset
- liquidity flag where available

## 7.2 Ledger Recording

Trading fees should be represented as ledger events, typically with `ledger_type = trade_fee`.

## 7.3 PnL Presentation

Fee costs should be separable in analytics, but included in net economic outcomes.

---

## 8. Funding Accounting Rules

## 8.1 Funding Event Treatment

Funding must be recorded as:
- explicit `execution.funding_pnl` event
- corresponding ledger effect where appropriate

## 8.2 Funding Classification

Funding should be reported separately from trade PnL.
It is part of strategy economics, but not the same as execution edge.

## 8.3 Net Strategy PnL View

A net strategy performance view may include:
- realized trade PnL
- unrealized PnL
- fees
- funding
- borrow interest if applicable

But each component must remain separately attributable.

---

## 9. Ledger Semantics

## 9.1 Ledger Role

`execution.account_ledger` is the normalized cashflow/event ledger for:
- deposits
- withdrawals
- fees
- funding
- realized PnL-related balance effects where applicable
- transfers
- rebates
- adjustments

## 9.2 Ledger Rules

- ledger entries should be append-only in logical behavior
- corrections should be represented as explicit correcting entries where practical
- reference ids should link ledger entries back to source events when possible

## 9.3 Ledger vs Balance Relationship

Balances are snapshot state.
Ledger is event history.
Balances should be explainable through prior balances plus ledger-affecting events and valuation effects depending on product type.

---

## 10. Balance and Equity Semantics

## 10.1 Wallet / Cash-Like Balance

Represents base cash or wallet holdings excluding some unrealized effects depending on venue semantics.

## 10.2 Available Balance

Represents balance available for new orders or margin use according to venue/account model.

## 10.3 Margin Balance

Represents balance adjusted for margin-related effects where relevant.

## 10.4 Equity

Equity should reflect the account's total economic value under the chosen valuation method, typically including unrealized PnL.

## 10.5 Rule

Displayed balance/equity fields must state or imply the venue/account interpretation being used if there is ambiguity.

---

## 11. Spot vs Perpetual Semantics

## 11.1 Spot

For spot trading:
- balances directly reflect held assets
- position semantics may be simpler or derived from asset holdings
- no funding by default

## 11.2 Perpetuals

For perpetuals:
- unrealized PnL should generally use mark price
- funding affects economics independently of fill price PnL
- margin and leverage semantics matter for risk views

---

## 12. Backtest / Paper / Live Consistency Rules

## 12.1 Common Semantics Required

All environments should share:
- same naming of realized/unrealized PnL
- same fee/funding classification
- same position basis method unless explicitly configured otherwise

## 12.2 Allowed Differences

Differences may arise from:
- fill realism
- timing differences
- missing venue-specific private data in paper/backtest

But accounting vocabulary and ledger semantics should remain aligned.

---

## 13. Performance Summary Component Breakdown

Backtest/paper/live summary views should ideally break PnL into components such as:
- gross trading PnL
- fee cost
- funding PnL
- borrow interest cost if applicable
- rebates/other adjustments
- net PnL

This is required for useful strategy attribution.

---

## 14. Reconciliation Expectations

Accounting consistency should support checks such as:
- fills align with position changes
- fee totals align with fill fee fields and ledger entries
- funding history aligns with `execution.funding_pnl` and ledger entries
- balance snapshots are not inconsistent with known cashflow events and valuation changes

---

## 15. Open Methodology Choices Reserved for Later

The following may be extended later if needed:
- multi-collateral valuation models
- cross vs isolated margin-specific derived equity models
- tax-lot accounting views
- portfolio-level attribution across strategies and accounts

These do not block the initial operational accounting model.

---

## 16. Minimum Acceptance Criteria

The accounting/PnL model is sufficiently specified when:
- realized vs unrealized PnL semantics are explicit
- fee and funding are explicit separate components
- ledger role is defined
- balance/equity terminology is defined
- average-cost position accounting is chosen for initial implementation
- environment consistency rules are explicit

---

## 17. Final Summary

The recommended initial accounting model is:
- average-cost position basis
- explicit separation of realized trade PnL, unrealized PnL, fees, funding, and other cashflows
- ledger as normalized event history
- balances as snapshots
- equity as valuation-based total account state
- shared accounting vocabulary across backtest, paper, and live

This is the minimum foundation needed for trustworthy performance reporting and reconciliation.