# Repo Self-Review Tracker

## Purpose

This document tracks issues found during deep-dive self-review passes across:
- specs
- implementation plans
- phase checklists
- API/UI contracts
- runtime code

The intent is to keep one explicit place for:
- findings that were fixed in the current pass
- follow-up items that remain intentionally open

---

## Review Pass: 2026-04-04

### Fixed In This Pass

| ID | Area | Finding | Resolution | Status |
|---|---|---|---|---|
| `SR-2026-04-04-01` | Backtest diagnostics API | The Stage A diagnostics API exposed only high-level flags while richer risk breakdown and state snapshot were only buried inside `run_detail.runtime_metadata_json`. | Added a typed `risk_summary` section to the diagnostics projector and API resource, including `block_counts_by_code`, `outcome_counts_by_code`, and `state_snapshot`. | `fixed` |
| `SR-2026-04-04-02` | Phase 5 checklist consistency | `Task 5.6` still showed drawdown as incomplete even though max drawdown is already computed and persisted; the report-output wording was also stale relative to the current API/UI surfaces. | Split the checklist into explicit `Sharpe` vs `max drawdown`, marked drawdown complete, and updated summary-output wording to match the current persisted/API/UI reality. | `fixed` |
| `SR-2026-04-04-03` | Assumption bundle semantics | `stress_costs@v1` looked like a real higher-cost runtime bundle even though current Phase 5 foundation does not yet alter fee/slippage behavior from that bundle. | Clarified the bundle display/description as a placeholder lineage bundle so UI/API users are not misled into thinking runtime costs already change. | `fixed` |
| `SR-2026-04-04-04` | Daily loss guardrail | `max_daily_loss_pct` used UTC day boundaries, which would drift from the intended session semantics for non-UTC research runs. | Added `session.trading_timezone`, switched daily-loss trading-day resets to session-local dates, exposed the chosen timezone in run detail/runtime metadata, and updated the launch UI surface. | `fixed` |
| `SR-2026-04-04-06` | Diagnostics depth | Stage A diagnostics now exposes richer risk summary, and Level 1 backend debug traces now exist, but there was still no internal debug-trace UI surface. | Added the Level 1 internal trace table/detail slice in `/monitoring`, including run-detail fetch wiring and compact trace JSON inspection. | `fixed` |

### Open Follow-Ups

| ID | Area | Finding | Planned Direction | Status |
|---|---|---|---|---|
| `SR-2026-04-04-05` | Cooldown semantics | `cooldown_bars_after_stop` currently uses a realized losing close as the first stop-like proxy. It is not yet linked to explicit protection-trigger events. | Rebind cooldown to TP/SL/protection events once the fuller protection lifecycle exists. | `open` |
| `SR-2026-04-04-07` | Compare/analyze maturity | Compare currently focuses on assumptions and KPI deltas, but not yet on richer runtime risk-state deltas or persisted compare-set workflows. | Extend compare-set persistence and runtime-risk diff views in later Phase 5 workbench stages. | `open` |
| `SR-2026-04-04-08` | Diagnostics trace drill-down | The internal trace table now exists, but diagnostics flags still do not jump directly to matching trace ranges or prefiltered trace views. | Add diagnostics-to-trace anchors after Level 2 richer trace linkage is in place. | `open` |

## Review Pass: 2026-04-11

### Fixed In This Pass

| ID | Area | Finding | Resolution | Status |
|---|---|---|---|---|
| `SR-2026-04-04-07` | Compare/analyze maturity | Compare currently focuses on assumptions and KPI deltas, but not yet on richer runtime risk-state deltas or persisted compare-set workflows. | Extended compare-set projection, persisted snapshot facts, API resources, UI tables, and regression coverage so compare now exposes diagnostics/risk diffs, blocked-intent counts, guardrail-state deltas, and surfaced diagnostic-flag differences per run. | `fixed` |

---

## References

- `docs/backtest-risk-guardrails-spec.md`
- `docs/strategy-risk-assumption-management-spec.md`
- `docs/phases-2-to-9-checklists.md`
- `docs/ui-api-spec.md`
- `docs/api-resource-contracts.md`
