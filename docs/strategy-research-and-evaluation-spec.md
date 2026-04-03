# Strategy Research and Evaluation Spec

## Purpose

This document defines the long-lived plan for:
- strategy development workflow
- research iteration workflow
- strategy testing expectations
- multi-window evaluation
- multi-strategy comparison
- experiment analysis and reporting

It exists because a usable trading platform needs more than a single backtest runner.
Researchers need a repeatable way to:
- create new strategies
- test them safely
- compare them across multiple windows
- compare multiple strategies and parameter sets
- understand why one run is better or worse than another

This spec complements:
- `docs/implementation-plan.md`
- `docs/position-management-spec.md`
- `docs/strategy-taxonomy-and-versioning-spec.md`
- `docs/strategy-input-and-feature-pipeline-spec.md`
- `docs/testing-strategy-spec.md`
- `docs/ui-spec.md`
- `docs/ui-api-spec.md`

---

## 1. Core Goal

The platform should eventually support a full strategy research lifecycle:

```text
idea
  -> strategy implementation
  -> local validation
  -> repeatable backtest runs
  -> multi-window evaluation
  -> multi-strategy / multi-parameter comparison
  -> research review and reporting
  -> paper/live promotion decision
```

The intent is to make new strategy research:
- reproducible
- comparable
- auditable
- scalable beyond one-off scripts

---

## 2. Design Principles

### 2.1 Strategy Research Must Be Reproducible
Every run should be attributable to:
- strategy code/version
- parameter set
- data window
- market-data assumptions
- fee/slippage assumptions
- feature/input version

### 2.2 One Run Is Never Enough
Single-window success is not sufficient.

The platform should explicitly support:
- multiple windows
- multiple symbols
- multiple parameter sets
- multiple strategy versions

### 2.3 Research and Testing Are Separate But Linked
- research asks whether an idea works
- testing asks whether the implementation is correct and stable

Both must exist.

### 2.4 Comparison Must Be First-Class
The platform should not treat run comparison as an afterthought.

Users should be able to compare:
- same strategy across windows
- same strategy across parameter sets
- different strategies on the same window
- performance against baselines/benchmarks

### 2.5 Promotion Requires Structured Evidence
Moving from research to paper/live should depend on:
- repeated evaluation
- documented assumptions
- explicit comparison results

### 2.6 Strategy Identity Must Be Stable
Research comparison depends on a stable strategy taxonomy.

The project should distinguish:
- `family`
- `variant`
- `version`

And should follow:
- `docs/strategy-taxonomy-and-versioning-spec.md`

For the current repository, the practical rule is:
- current `strategy_code` means stable variant identity
- current `strategy_version` means immutable version identity

---

## 3. Strategy Development Workflow

The intended long-term workflow for a new strategy is:

1. create strategy code and metadata
2. define inputs/features required by the strategy
3. validate strategy contract locally
4. run a small deterministic smoke backtest
5. run broader backtests across windows
6. compare against:
   - previous strategy version
   - baseline strategy
   - benchmark asset behavior
7. inspect diagnostics
8. decide whether to:
   - iterate
   - archive
   - promote to paper trading

This means strategy work should eventually include:
- implementation
- experiment registration
- evaluation
- comparison
- review

---

## 4. Research Objects the System Should Support

The platform should eventually think in these objects:

### 4.1 Strategy Version
The versioned implementation and parameterizable logic.

Already partially represented by:
- `strategy.strategies`
- `strategy.strategy_versions`

### 4.2 Backtest Run
One concrete execution of a strategy version over one configuration/window.

Already partially represented by:
- `backtest.runs`
- `backtest.simulated_orders`
- `backtest.simulated_fills`
- `backtest.performance_summary`
- `backtest.performance_timeseries`

### 4.3 Research Experiment
A grouping object above individual runs.

Example:
- “BTC momentum v1.0.0, compare parameters across 2020–2021, 2022, and 2023–2024”

Suggested future role:
- group many backtest runs under one experiment or research question

### 4.4 Comparison Set
A collection of runs intentionally compared against each other.

Example:
- same strategy, different windows
- same window, different strategies
- same strategy, different fee/slippage assumptions

### 4.5 Promotion Candidate
A run group or strategy version that has passed enough checks to move to paper trading.

---

## 5. Multi-Window Evaluation Plan

The system should explicitly support multiple window types.

### 5.1 Fixed Historical Windows
Examples:
- `2020-01-01` to `2020-12-31`
- `2022-01-01` to `2022-06-30`

Use for:
- baseline regime evaluation
- targeted historical comparison

### 5.2 Rolling Windows
Examples:
- 90-day rolling windows
- 180-day rolling windows

Use for:
- stability checks
- performance drift analysis

### 5.3 Regime Windows
Examples:
- bull market windows
- crash windows
- sideways windows
- funding-heavy periods

Use for:
- understanding where a strategy actually works

### 5.4 In-Sample / Out-of-Sample Splits
Examples:
- train or tune on one window
- validate on a later untouched window

Use for:
- guarding against overfitting

### 5.5 Walk-Forward Style Evaluation
The platform should eventually support:
- repeated retune/re-evaluate cycles across consecutive windows

This is not required in the first Phase 5 slice, but the research model should preserve room for it.

---

## 6. Multi-Strategy and Multi-Parameter Comparison

The platform should support at least these comparison modes:

### 6.1 Same Strategy, Different Parameters
Examples:
- different moving-average windows
- different stop-loss sizes
- different target sizing rules

### 6.2 Same Strategy, Different Windows
Examples:
- compare 2021 vs 2022 vs 2023
- compare high-volatility vs low-volatility windows

### 6.3 Different Strategies, Same Window
Examples:
- trend strategy vs mean-reversion strategy on the same BTCUSDT window

### 6.4 Same Strategy, Different Market Assumptions
Examples:
- fee model A vs fee model B
- low slippage vs high slippage
- bars-only input vs bars+funding context later

### 6.5 Strategy vs Benchmark
Examples:
- strategy return vs buy-and-hold
- strategy drawdown vs passive benchmark

---

## 7. Research Metrics and Diagnostics

Comparison should not stop at one Sharpe number.

The platform should eventually support:

### 7.1 Core KPIs
- total return
- annualized return
- Sharpe
- Sortino
- max drawdown
- turnover
- fee cost
- slippage cost

### 7.2 Stability Metrics
- consistency across windows
- win/loss distribution
- performance dispersion by regime
- sensitivity to parameter changes

### 7.3 Exposure and Risk Diagnostics
- gross/net exposure
- time in market
- long vs short contribution
- symbol concentration

### 7.4 Execution Diagnostics
- fill assumptions used
- cost assumptions used
- signal-to-fill lag assumptions

### 7.5 Strategy Diagnostics
- signal count
- average holding duration
- reason-code distribution
- contribution by feature/regime where available later

---

## 8. Testing Plan for Strategy Work

Strategy work should be tested at multiple layers.

### 8.1 Contract Tests
Verify:
- strategy can be instantiated
- strategy input contract is respected
- outputs are valid `Signal` / `TargetPosition`

### 8.2 Determinism Tests
Verify:
- same data + same config -> same outputs

### 8.3 Logic Tests
Verify:
- expected decisions on known synthetic patterns
- expected TP/SL or target-position behavior where applicable

### 8.4 Regression Tests
Verify:
- a new change does not unexpectedly change baseline run results

### 8.5 Research Validation Tests
Verify:
- a new strategy or parameter set is evaluated on multiple windows before promotion

This layer is not a unit test in the narrow sense; it is a research policy requirement.

---

## 9. Recommended Code Architecture

To support ongoing strategy research, future code should separate:

- `src/strategy/`
  - strategy implementations
- `src/backtest/`
  - runner, fill model, portfolio/projector, report generation
- `src/research/`
  - experiment definitions
  - comparison set definitions
  - multi-window orchestration
  - benchmark comparison helpers
- `src/features/`
  - input/feature pipeline defined by `docs/strategy-input-and-feature-pipeline-spec.md`
- `src/reporting/`
  - reusable research report builders and comparison projectors

The first Phase 5 slice does not need all of these directories immediately.
But the architecture should preserve room for them instead of collapsing everything into one backtest runner module.

---

## 10. Suggested Future Persistence Model

The current `backtest.*` tables are enough for the first runs.

For fuller research workflows, the platform should eventually consider planning-oriented objects such as:
- experiment metadata
- comparison groups
- benchmark result links
- parameter sweep definitions
- promotion-review records

Possible future concepts:
- `backtest.experiments`
- `backtest.run_groups`
- `backtest.run_comparisons`
- `backtest.benchmark_snapshots`

These names are planning-oriented and may evolve.
The important point is the functional role, not the exact table names today.

---

## 11. UI and Operator/Research Workflow Expectations

The future internal console should support:

### 11.1 Strategy Development
- inspect strategy versions
- inspect parameter sets
- inspect required inputs/features

### 11.2 Research Execution
- launch one backtest
- launch grouped multi-window backtests
- launch parameter comparisons

### 11.3 Comparison and Analysis
- compare multiple runs side by side
- compare runs across windows
- compare strategy vs benchmark
- inspect KPI diffs and assumption diffs

### 11.4 Promotion Review
- mark a strategy version as:
  - exploratory
  - candidate
  - paper-ready
  - rejected / archived

This should later connect to the UI docs rather than remain a purely backend concept.

---

## 12. Recommended Phase Rollout

### 12.1 Phase 5 MVP
Implement:
- one deterministic bars-based backtest run
- one simple strategy
- reproducible run metadata
- core KPI output

Do not require yet:
- experiment groups
- parameter sweeps
- cross-run compare UI

### 12.2 Phase 5 Expansion
Add:
- grouped runs across multiple windows
- grouped runs across multiple parameter sets
- basic comparison output

### 12.3 Phase 6 / Phase 7
Use research evidence for:
- paper-trading promotion decisions
- live-trading promotion decisions

### 12.4 Later Research Expansion
Add:
- walk-forward evaluation
- benchmark libraries
- richer attribution
- feature sensitivity analysis
- multi-strategy ranking/review workflows

---

## 13. Anti-Patterns To Avoid

Do not:
- evaluate a strategy only on one favorable window
- compare runs without preserving assumptions and config
- mix implementation-correctness tests with research-evidence decisions
- let strategy research depend on manual spreadsheets as the canonical comparison layer
- hide parameter or feature changes outside versioned metadata

---

## 14. Minimum Acceptance Criteria

This plan is actionable when:
- new strategy development has a defined path from code to evaluation
- multi-window evaluation is treated as a first-class requirement
- multi-strategy and multi-parameter comparison are explicitly planned
- strategy testing is separated into correctness, determinism, and research-validation layers
- promotion to paper/live is framed as an evidence-based step

---

## 15. Final Summary

The long-term strategy research plan for this repo is:
- strategy development should flow through repeatable backtest runs, not one-off scripts
- research should evaluate strategies across multiple windows and comparison sets
- testing should cover correctness, determinism, and regression
- comparison and analysis should become first-class platform behavior
- promotion to paper/live should rely on structured research evidence

This should be treated as the planning backbone for future strategy research, experiment management, and comparative analysis work.
