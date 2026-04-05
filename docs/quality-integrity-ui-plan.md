# Quality Integrity UI Plan

## Purpose

This document defines how the current internal `/monitoring` console should expose:
- dataset-integrity validation
- bounded validation windows
- post-backfill integrity review
- future BTC backfill status visibility

It focuses on the near-term `evolve` path for the existing internal Quality workspace.
It does not attempt to define the final long-term frontend architecture.

This plan complements:
- `docs/ui-api-spec.md`
- `docs/ui-phase-checklists.md`
- `docs/frontend-ui-usability-improvement-plan.md`
- `docs/frontend-keep-evolve-replace-strategy.md`

---

## Current State

The repo already has a working Phase 4 integrity-validation backend:
- `POST /api/v1/quality/integrity`
- `scripts/validate_dataset_integrity.py`
- `scripts/validate_dataset_integrity.ps1`

The validator can check:
- `gap`
- `duplicate`
- `missing`
- `corrupt`

It already supports the current BTC backfill footprint:
- `BTCUSDT_SPOT`
  - default: `bars_1m`
- `BTCUSDT_PERP`
  - default: `bars_1m`, `funding_rates`, `open_interest`, `mark_prices`, `index_prices`

The `/monitoring` Quality page now exposes an initial Integrity slice with:
- bounded validation form
- quick ranges
- dataset summary table
- selected dataset summary/detail
- raw JSON as collapsible secondary detail

The rest of the Quality page currently shows:
- quality checks
- open gaps

It does not yet expose:
- BTC backfill status
- stronger segmented Quality workspace navigation
- deeper dataset-detail polish for gap/future-row evidence

---

## Problem Summary

The current operator flow for integrity work is still too manual:

1. run a CLI/PowerShell command
2. inspect JSON output in terminal
3. separately inspect quality checks/gaps in `/monitoring`
4. separately inspect BTC backfill status from the status file

This makes post-backfill validation harder than it should be.

---

## Design Principles

1. Window-first validation
- integrity validation should always operate over an explicit time window
- the UI should require or derive a bounded `start_time` and `end_time`

2. Quick ranges over free-form only
- explicit timestamps should remain supported
- but common ranges should be one click away

3. Summary first, evidence second
- top-level status cards should appear before raw JSON
- dataset-level counts should appear before detailed finding payloads

4. Keep validation and quality related
- integrity validation belongs in the existing `Quality` workspace
- do not create a separate top-level nav item just for integrity

5. Post-backfill flow should be obvious
- the UI should make it natural to:
  - inspect current BTC backfill coverage/status
  - validate the newly backfilled window
  - inspect gaps/findings

---

## Recommended Quality Workspace Evolution

The current `Quality` page should evolve into 4 sub-surfaces:

1. `Checks`
- existing quality checks

2. `Gaps`
- existing open gaps explorer

3. `Integrity`
- new bounded validation form and result viewer

4. `Backfill Status`
- future BTC bootstrap/incremental status summary

This can be implemented inside the current `Quality` page using:
- internal tabs
- or segmented buttons

Do not add a new top-level nav item yet.

---

## Integrity Validation UX

## Form Inputs

The Integrity panel should include:
- `exchange_code`
  - default `binance`
- `unified_symbol`
  - initial target usage: `BTCUSDT_SPOT` / `BTCUSDT_PERP`
- `start_time`
- `end_time`
- `persist_findings`
  - checkbox
- `data_types`
  - optional multi-select / checklist
- `raw_event_channel`
  - optional, shown only when `raw_market_events` is selected

## Quick Ranges

The form should also provide one-click ranges:
- `Last 24h`
- `Last 7d`
- `Last 30d`
- `This Month`
- `YTD`
- `Latest BTC Backfill Tail`

Notes:
- explicit timestamps remain editable
- quick ranges should fill the timestamp inputs, not replace them

## Default Behavior

If the user only picks a symbol and time window:
- `_SPOT` should default to `bars_1m`
- `_PERP` should default to `bars_1m`, `funding_rates`, `open_interest`, `mark_prices`, `index_prices`

If the user manually selects datasets:
- the UI should submit only those explicit `data_types`

---

## Integrity Result Layout

## Top Summary

At the top of the result panel, show:
- symbol
- validated window
- observed_at
- persisted or not
- overall status
- total dataset count
- total findings count
- total gap segments

## Dataset Summary Table

For each dataset, show one row with:
- `data_type`
- `status`
- `available_from`
- `available_to`
- `expected_points`
- `actual_points`
- `missing_count`
- `duplicate_count`
- `corrupt_count`
- `future_row_count`

This should be the main scanning surface.

## Selected Dataset Detail

When a dataset row is selected, show:
- headline counts
- missing segments / gap segments
- duplicate profile
- corrupt profile
- future-row profile
- persisted finding refs where available

## Raw JSON

Raw JSON should still be available, but only as a collapsible debug detail.

---

## Backfill Status UX

This should be a separate sub-surface under `Quality`.

The UI should show:
- current mode
  - bootstrap / resume / incremental
- current state
  - running / finished / failed
- updated_at
- task progress
- dataset chunk progress
- last result
- coverage summary

For BTC-specific local tooling, the UI can start with:
- a read-only status view

Later it may add:
- a launch button for local wrappers
- status refresh polling

---

## API / Data Dependencies

## Existing APIs Already Available

- `GET /api/v1/quality/checks`
- `GET /api/v1/quality/summary`
- `GET /api/v1/quality/gaps`
- `POST /api/v1/quality/integrity`

## Future API Recommended

For backfill status, add a lightweight read endpoint such as:
- `GET /api/v1/quality/backfill-status/binance-btc`

Recommended response shape:
- current status-file state
- per-dataset progress
- coverage summary
- last result

This should be read-only.

---

## Phased UI Implementation

## UI Slice 4A: Integrity Form + Result Summary

Status:
- completed

Scope:
- add `Integrity` panel to current Quality page
- bounded validation form
- quick ranges
- summary cards
- dataset summary table
- raw JSON detail

Acceptance:
- operator can validate one symbol/window without leaving `/monitoring`
- operator can quickly understand whether the window is clean or not

## UI Slice 4B: Dataset Detail Drill-Down

Scope:
- selected dataset detail
- gap segments
- duplicate/corrupt/future summaries
- cleaner summary-first presentation

Acceptance:
- operator can identify which dataset failed and why without reading raw JSON first

## UI Slice 4C: BTC Backfill Status Panel

Scope:
- show current BTC bootstrap/incremental status
- show dataset chunk progress
- show latest coverage summary

Acceptance:
- operator can see current backfill state without opening the status file manually

## UI Slice 4D: Quality Workspace Restructure

Scope:
- segmented `Checks / Gaps / Integrity / Backfill Status`
- stronger separation within the Quality page

Acceptance:
- integrity validation no longer feels bolted onto a flat quality page

---

## Recommended Immediate Slice

The safest next move is:

### Slice
`UI Slice 4A: Integrity Form + Result Summary`

### Why
- the backend already exists
- it gives immediate operator value
- it stays inside the current `Quality` page instead of widening scope
- it keeps the first step summary-first and workflow-friendly

This slice is now landed in `/monitoring` and should be treated as the baseline integrity workspace.

### Explicitly Defer
- backfill-launch controls
- long-running progress orchestration inside the UI
- generic multi-symbol integrity workspace
- product-grade charts

### Next Recommended Slice
- `UI Slice 4C: BTC Backfill Status Panel`
- optional follow-up: polish the current selected-dataset detail into the fuller `UI Slice 4B` presentation

---

## Resume Checklist

When resuming this work:
- inspect `frontend/monitoring/index.html`
- inspect `frontend/monitoring/app.js`
- inspect `frontend/monitoring/styles.css`
- inspect `src/api/app.py`
- inspect `src/jobs/data_quality.py`
- confirm whether the next slice is:
  - `UI Slice 4A` integrity form/result
  - or `UI Slice 4C` backfill-status panel
- keep it inside the current `Quality` page first

---

## Summary

The integrity workflow should be exposed in `/monitoring` as part of the existing Quality workspace.

The best short-term UX is:
- explicit time window
- quick range helpers
- symbol-first validation
- summary cards
- dataset summary table
- selected dataset detail
- raw JSON only as secondary detail

The immediate next move should be:
- add `Integrity` to the current Quality page
- let operators validate a bounded window directly from UI
- then add BTC backfill status as a companion quality/coverage surface
