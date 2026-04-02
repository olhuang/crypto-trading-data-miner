# Numeric Precision and Rounding Policy

## Purpose

This document defines the numeric precision, scale, and rounding rules used across the trading platform.

It exists to prevent divergence between:
- API boundary payloads
- Python Decimal behavior
- PostgreSQL numeric columns
- PnL, fee, and funding calculations
- backtest, paper, and live execution outputs

This spec complements:
- `docs/api-contracts.md`
- `docs/pnl-and-accounting-spec.md`
- `docs/contract-to-schema-mapping.md`
- `docs/peer-review-followups.md`

---

## 1. Core Policy

### 1.1 API Boundary Rule

All numeric values crossing JSON/API boundaries must be encoded as strings.

Examples:
- `price`
- `qty`
- `notional`
- `fee`
- `funding_rate`
- `maker_fee_bps`
- `taker_fee_bps`

### 1.2 Internal Arithmetic Rule

All arithmetic that affects trading state, accounting, or persisted financial results must use `Decimal`, not floating-point types.

### 1.3 Persistence Rule

Persist financial and market numeric values using PostgreSQL `numeric`, not floating-point column types.

---

## 2. Decimal Behavior

## 2.1 Python Decimal Context

Recommended initial rule:
- use `Decimal` everywhere for canonical numeric handling
- do not rely on ambient/global decimal context for business correctness
- explicitly quantize values before persistence where the field has a defined precision policy

## 2.2 Business Rule

The platform should prefer:
- exact decimal parsing
- explicit quantization at business boundaries
- deterministic rounding behavior

---

## 3. Numeric Categories

## 3.1 Price-Like Fields
Examples:
- `price`
- `mark_price`
- `index_price`
- `avg_entry_price`

## 3.2 Quantity-Like Fields
Examples:
- `qty`
- `position_qty`
- `lot_size`
- `min_qty`

## 3.3 Monetary / Notional Fields
Examples:
- `notional`
- `wallet_balance`
- `available_balance`
- `equity`
- `realized_pnl`
- `unrealized_pnl`
- `fee`
- `funding_payment`

## 3.4 Rate / Ratio Fields
Examples:
- `funding_rate`
- `maker_fee_bps`
- `taker_fee_bps`
- `target_weight`
- `score`

---

## 4. Recommended Initial Precision Policy

These are implementation defaults for the first wave.

## 4.1 Prices

Recommended internal/persistence support:
- up to **18 total digits, 8 decimal places** as a safe default general policy

Use case:
- crypto spot/perp prices
- mark/index prices

## 4.2 Quantities

Recommended internal/persistence support:
- up to **28 total digits, 12 decimal places** as a safe default general policy

Use case:
- base asset quantities
- contract quantities where venue precision may vary

## 4.3 Monetary / Notional Amounts

Recommended internal/persistence support:
- up to **28 total digits, 8 decimal places** as a safe default general policy

Use case:
- notional
- balances
- PnL
- fees
- funding payments

## 4.4 Rates and BPS

Recommended internal/persistence support:
- up to **18 total digits, 10 decimal places** as a safe default general policy

Use case:
- funding rates
- basis-like rates
- weighted scores when represented as decimal fractions

## 4.5 Integer-Like Counts

Examples:
- `trade_count`
- `depth_levels`

These should use integer types, not Decimal.

---

## 5. Rounding Policy

## 5.1 General Rule

Use **ROUND_HALF_UP** as the default business rounding mode when a value must be rounded for persistence or reporting, unless a field requires explicit floor/truncate behavior due to exchange trading-rule compliance.

## 5.2 Venue Compliance Exception

When normalizing order quantities and prices to venue rules:
- qty and price must respect exchange filters exactly
- rounding behavior may need to be **floor/truncate to valid increment** rather than standard reporting rounding

This is a trading-rule normalization step, not a generic accounting/reporting step.

## 5.3 Reporting Rule

Displayed/reporting values may be formatted differently for UI readability, but stored/accounting values must preserve the canonical rounded/quantized form used for business calculations.

---

## 6. Quantization Rules by Category

## 6.1 Market Data Ingestion

Do not over-quantize raw exchange numeric values beyond what is needed for safe parsing and DB persistence.
Preserve the provided precision as far as practical within the chosen column scale.

## 6.2 Order Requests

Before sending an order:
- normalize `price` to exchange tick size
- normalize `qty` to exchange lot size and min qty constraints
- use venue-compliant truncation/floor behavior where required

## 6.3 Fills and Fees

Persist fills and fees using canonical Decimal values.
Do not convert to float for intermediate calculations.

## 6.4 PnL and Balance Outputs

PnL and balance values should be quantized consistently at the business boundary used for persistence/reporting.
Avoid inconsistent per-codepath formatting.

---

## 7. PostgreSQL Alignment Guidance

## 7.1 Rule

For first implementation, DB column definitions should align with the category-level defaults in this spec.

## 7.2 Practical Guidance

If an existing column is already defined in SQL with a specific numeric precision/scale, implementation should obey the SQL schema.
If the schema lacks explicit precision strategy for a new field, use the defaults in this document.

This means:
- SQL remains implemented-state authority
- this document provides forward implementation defaults and normalization rules

---

## 8. Cross-Environment Consistency Rule

Backtest, paper, and live must all use:
- the same Decimal parsing policy
- the same business rounding policy
- the same field-category quantization rules

Differences in numeric outcomes should come from data or execution behavior, not from inconsistent rounding code paths.

---

## 9. Field-Level Guidance Examples

### Funding Rate
- parse as Decimal
- persist with high fractional precision
- do not cast to float for analytics or PnL application

### Fee BPS
- preserve high fractional precision
- convert to actual fee amount using Decimal arithmetic only

### Qty
- normalize to venue lot size before order submission
- preserve canonical fill qty exactly as received/normalized

### PnL
- compute with Decimal
- quantize using reporting/persistence policy consistently

---

## 10. Validation Rules

Validation should reject:
- non-string numeric fields at API boundary when canonical contract expects strings
- malformed decimal strings
- values exceeding allowed field precision if enforcement is configured at model or DB layer

---

## 11. Deferred Topics

These are intentionally deferred for later refinement:
- per-exchange precision overrides beyond venue rule filters
- UI formatting precision per screen
- tax/reporting-specific rounding variants
- cross-currency portfolio reporting precision policy

---

## 12. Minimum Acceptance Criteria

This policy is sufficiently specified when:
- all API numeric fields are string-encoded
- all financial arithmetic uses Decimal
- default field-category precision/scale guidance exists
- default rounding policy exists
- exchange-rule normalization is explicitly separated from generic business rounding

---

## 13. Final Summary

The locked implementation defaults are:
- numeric values cross API boundaries as strings
- business arithmetic uses Decimal
- PostgreSQL persists numeric values using numeric types
- ROUND_HALF_UP is the default business rounding mode
- exchange trading-rule normalization may use stricter truncation/floor behavior
- price, qty, monetary amounts, and rates follow category-specific default scales

This is the minimum precision policy needed to avoid hidden divergence during implementation.