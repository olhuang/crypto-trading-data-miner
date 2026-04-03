# Strategy Taxonomy and Versioning Spec

## Purpose

This document defines the long-lived strategy identity model for:
- strategy classification
- research grouping
- version promotion
- stable code and database identity

The repository already uses:
- `strategy_code`
- `strategy_version`

However, those keys are not sufficient unless the project is explicit about what they mean.
Without that clarity, strategy seed data, backtest runs, research comparison, and future paper/live deployment can drift into conflicting interpretations.

This spec exists to freeze the intended meaning of:
- `family`
- `variant`
- `version`
- experiment and parameter-set boundaries

It complements:
- `docs/implementation-plan.md`
- `docs/position-management-spec.md`
- `docs/strategy-input-and-feature-pipeline-spec.md`
- `docs/strategy-research-and-evaluation-spec.md`
- `docs/internal-id-resolution-spec.md`

---

## 1. Core Rule

The platform should distinguish these levels:

1. `family`
2. `variant`
3. `version`

And it should not overload one level to mean another.

The practical rule is:
- `family` = broad research thesis or alpha category
- `variant` = stable deployable strategy identity
- `version` = immutable release of one variant

---

## 2. Definitions

### 2.1 Family

A `family` is the broad strategy idea class.

Examples:
- `momentum`
- `mean_reversion`
- `carry`
- `market_making`
- `stat_arb`

Family answers:
- what kind of alpha hypothesis is this
- what broad behavior does it represent

Family does not answer:
- which exact tradable implementation is deployed
- which exact parameterization is active

### 2.2 Variant

A `variant` is a stable named implementation line inside a family.

Examples:
- `btc_momentum`
- `btc_momentum_breakout`
- `eth_mean_reversion_zscore`
- `btc_perp_basis_carry`

Variant answers:
- which concrete strategy line is being researched, backtested, or deployed
- which implementation branch should be compared against its previous versions

Variant is the level that should usually map to:
- strategy registration
- research comparison identity
- backtest run ownership
- promotion to paper/live

### 2.3 Version

A `version` is an immutable released snapshot of one variant.

Examples:
- `v1.0.0`
- `v1.1.0`
- `v2.0.0`

Version answers:
- which exact code/config contract was used
- which release should be promoted, compared, or rolled back

Version should be immutable once published for research or deployment use.

### 2.4 Parameter Set

A parameter set is not the same thing as a version.

Parameter sets represent:
- tunable knobs
- research experiments
- local iteration candidates

Examples:
- `short_window=10, long_window=30`
- `tp_bps=80, sl_bps=40`

Parameter sweeps should usually be tracked as:
- run configuration
- experiment metadata

They should only become a new `version` when the project intentionally freezes them into a named promoted release.

### 2.5 Experiment

An experiment is a research grouping across:
- windows
- symbols
- parameter sets
- assumptions

Experiments compare runs.
They do not replace family, variant, or version identity.

---

## 3. Canonical Identity Rule for the Current Repo

The current schema and codebase already rely on:
- `strategy.strategies(strategy_code)`
- `strategy.strategy_versions(version_code)`
- code registry keys of `(strategy_code, strategy_version)`

To avoid breaking Phase 2-5 work, the canonical rule for the current repository is:

- current `strategy_code` should be interpreted as the stable `variant_code`
- current `strategy_version` should be interpreted as the immutable `version_code`
- `family` should currently be treated as metadata and planning context, not yet a required normalized DB key

This means:
- `strategy.strategies` currently behaves as a variant registry
- `strategy.strategy_versions` behaves as a version registry within each variant

---

## 4. Example Mapping

Current seeded strategy:
- `strategy_code = btc_momentum`
- `strategy_version = v1.0.0`

Recommended interpretation:
- `family = momentum`
- `variant = btc_momentum`
- `version = v1.0.0`

Possible future siblings inside the same family:
- `btc_momentum_breakout`
- `btc_momentum_ma_cross`
- `multi_asset_momentum_rank`

This allows:
- version comparison within `btc_momentum`
- variant comparison inside the `momentum` family
- family comparison against `mean_reversion` or `carry`

---

## 5. How to Decide What Counts as a New Family, Variant, or Version

### 5.1 New Family

Create a new family when the alpha thesis materially changes.

Examples:
- trend following -> mean reversion
- directional momentum -> basis carry
- single-asset alpha -> market making

### 5.2 New Variant

Create a new variant when the strategy remains in the same family but becomes a distinct research and deployment line.

Typical reasons:
- materially different signal construction
- materially different holding horizon
- materially different tradable universe
- materially different execution/protection style
- materially different portfolio construction logic

Practical question:
- would researchers want to compare and promote this line separately from the old one

If yes, it should usually be a new variant.

### 5.3 New Version

Create a new version when the same variant receives an intentional immutable release.

Typical reasons:
- logic changes
- default parameter changes
- feature-pipeline version changes
- protection/execution configuration changes
- bug fix that changes expected run results

Practical question:
- should this release be reproducibly distinguishable from the prior release under the same variant

If yes, it should usually be a new version.

### 5.4 Not a New Version

These should usually stay as experiment/run metadata instead of becoming a new version immediately:
- local exploratory parameter sweeps
- one-off notebook tweaks
- temporary debug settings
- alternate window selection
- alternate slippage assumptions for sensitivity analysis only

---

## 6. Naming Rules

### 6.1 Family Code

Recommended:
- lowercase snake_case
- short and generic

Examples:
- `momentum`
- `mean_reversion`
- `carry`

### 6.2 Variant Code

Recommended:
- lowercase snake_case
- specific enough to remain stable over time
- expressive enough to stand alone in run lists and research reports

Examples:
- `btc_momentum`
- `btc_perp_basis_carry`
- `eth_mean_reversion_zscore`

### 6.3 Version Code

Recommended:
- semantic-version style
- prefixed with `v`

Examples:
- `v1.0.0`
- `v1.1.0`
- `v2.0.0`

### 6.4 Display Names

Human-readable names should exist separately from stable keys.

Examples:
- family display name: `Momentum`
- variant display name: `BTC Momentum`
- version display name: `BTC Momentum v1.0.0`

---

## 7. Research and Comparison Implications

The system should support comparison at three levels:

### 7.1 Version Within Variant

Examples:
- `btc_momentum v1.0.0` vs `btc_momentum v1.1.0`

Use for:
- release regression
- promotion decisions
- implementation improvement tracking

### 7.2 Variant Within Family

Examples:
- `btc_momentum` vs `btc_momentum_breakout`

Use for:
- deciding which strategy line best expresses a shared alpha family

### 7.3 Family Across Families

Examples:
- `momentum` vs `mean_reversion`

Use for:
- research budgeting
- portfolio mix decisions
- long-term roadmap prioritization

---

## 8. Code Architecture Implications

### 8.1 Strategy Registry

Current registry keys should remain:
- `(strategy_code, strategy_version)`

But code should interpret them as:
- `(variant_code, version_code)`

Strategy classes may later expose:
- `strategy_family`
- `strategy_code`
- `strategy_version`

without breaking existing registry usage.

### 8.2 Strategy Session and Run Metadata

Backtest, paper, and live session metadata should eventually capture:
- family
- variant
- version
- parameter set or experiment context

The family field does not need to block Phase 5 implementation, but the architecture should preserve room for it.

### 8.3 Research UI and Reporting

Future compare/analyze tooling should support:
- group by family
- group by variant
- compare versions within variant

---

## 9. Database and Schema Evolution Plan

### 9.1 Short-Term Rule

Do not block Phase 5 by redesigning the current schema immediately.

Short-term canonical interpretation:
- `strategy.strategies` rows are variants
- `strategy.strategy_versions` rows are versions within variants

### 9.2 Mid-Term Metadata Expansion

When the project is ready, add family metadata in one of these ways:
- add `family_code` to `strategy.strategies`
- or add `strategy.strategy_families` and reference it from `strategy.strategies`

### 9.3 Long-Term Optional Normalization

If taxonomy becomes richer, the project may later introduce:
- `strategy.strategy_families`
- `strategy.strategy_variants`

with backward-compatible natural-key handling.

This is optional future hardening, not a blocker for current phases.

---

## 10. Seed and Promotion Guidance

Starter seed rows should use stable variant identities, not broad family names unless the variant is intentionally singular.

Current seed rule:
- `btc_momentum` is acceptable as a variant key
- its family should be interpreted as `momentum`

Promotion rule:
- only versions that are frozen, reproducible, and reviewable should become named promoted versions

---

## 11. Phase Guidance

### Phase 5
- keep `strategy_code` interpreted as `variant_code`
- keep `strategy_version` interpreted as immutable `version_code`
- preserve room for family metadata in session/run/report outputs

### Phase 6-7
- add family-aware reporting and grouping
- keep paper/live deployments bound to variant + version identity

### Phase 8+
- normalize family metadata if operational complexity justifies it

---

## 12. Final Summary

The long-lived rule is:
- `family` is the research category
- `variant` is the stable strategy identity
- `version` is the immutable release

For the current repository:
- `strategy_code` means `variant_code`
- `strategy_version` means `version_code`

This keeps current Phase 2-5 implementation compatible while preserving a clean path to future multi-strategy research, promotion, paper trading, live trading, and reporting.
