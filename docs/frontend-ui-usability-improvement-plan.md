# Frontend UI Usability Improvement Plan

## Purpose

This document tracks how to turn the current internal `/monitoring` console from a useful-but-dense engineering surface into a clearer research workbench for:
- backtest launch
- run inspection
- compare/review
- debug trace investigation
- future replay investigation

It is intentionally focused on usability and information architecture, not backend capability planning.

This plan complements:
- `docs/ui-spec.md`
- `docs/ui-phase-checklists.md`
- `docs/strategy-workbench-spec.md`
- `docs/object-level-notes-and-annotations-spec.md`
- `docs/debug-trace-rollout-plan.md`

---

## Current Problem Summary

The current `/monitoring` UI is functionally rich but not yet user-friendly enough for repeated daily research work.

The main issues are:

1. Too many workflows are mixed into one long Backtests page
- launch
- registry/reference lookup
- compare
- review notes
- run list
- run detail
- diagnostics
- signals/orders/fills/timeseries
- debug traces

2. The launch form relies too heavily on placeholders instead of durable labels
- once a field has a value, the field meaning becomes hard to see
- boolean/string toggles are easy to misread
- advanced fields visually compete with core fields

3. The page hierarchy is weak
- everything is visually a panel
- primary tasks and secondary details are not clearly separated
- the user is forced to scroll and remember where each function lives

4. Raw JSON is still too prominent
- structured drill-down has improved trace inspection
- but other areas still rely on JSON blocks as the first reading surface instead of summary-first presentation

5. Selected-run investigation is not yet a true workspace
- no strong run summary header
- no tabbed separation between overview/performance/execution/trace/notes
- signals/orders/fills/timeseries/debug traces compete in one vertical stack

6. Compare/review is still coupled too tightly to the launch surface
- compare is now usable
- but it still feels like a sidecar bolted onto the same page rather than a dedicated research workspace

---

## Design Principles

The UI should move toward these principles:

1. One primary job per visible surface
- launch
- inspect runs
- compare/review
- investigate traces

2. Summary first, payload second
- cards, key stats, and structured summaries should appear before JSON or raw payload views

3. Core fields first, advanced fields later
- the common path should be obvious
- advanced assumptions/risk/debug options should be grouped and collapsible

4. Stable labels over placeholder-only forms
- field labels must remain visible even when values are populated

5. Master-detail over long scrolling stacks
- the user should select an object on the left/top and inspect it in a focused workspace on the right/below

6. Investigation surfaces should preserve context
- selected run
- selected compare set
- selected trace
- selected note

7. Internal tool does not mean visually chaotic
- the current internal console can stay pragmatic
- but it still needs stronger grouping, spacing, and navigational clarity

---

## Recommended Information Architecture

## Backtests View Should Become a Workspace

Instead of one long page, the current Backtests section should evolve into 4 sub-surfaces:

1. `Launch`
- backtest run builder
- named risk policy / assumption bundle reference

2. `Runs`
- run list
- selected run summary
- run detail tabs

3. `Compare`
- compare-set builder
- compare result tables
- compare review notes

4. `Investigate`
- diagnostics anchors
- targeted trace filters
- selected trace detail
- future replay/investigation notes

This can be implemented as:
- segmented navigation within the Backtests page
- or a tab bar inside the Backtests workspace

Do not create separate top-level app navigation items yet unless the internal console itself is being restructured more broadly.

---

## Proposed Run Workspace Layout

### Selected Run Summary Header

Show at the top:
- run id / run name
- strategy code/version
- symbol/universe
- time window
- status
- total return
- max drawdown
- turnover
- fee/slippage cost

This should replace the current pattern where the first thing the user sees is a JSON blob.

### Run Detail Tabs

Recommended tabs:

1. `Overview`
- run metadata summary
- assumption/risk snapshot summary
- diagnostics summary
- artifacts summary

2. `Performance`
- equity curve
- drawdown chart
- month/quarter/year breakdown

3. `Execution`
- signals
- orders
- fills
- selected execution detail

4. `Trace`
- diagnostics anchors
- targeted trace filters
- trace table
- selected trace detail

5. `Notes`
- future run-level annotations
- compare/replay-linked notes where relevant

The current page already has most of this data; the main missing work is layout and prioritization.

---

## Proposed Compare Workspace Layout

The compare flow should be separated from launch.

Recommended structure:

### Compare Builder
- choose run ids
- choose benchmark
- create compare set

### Compare Summary
- top KPI delta cards
- best/worst differences
- summary flags

### Compare Detail Tabs
- `Runs`
- `Assumption Diffs`
- `Benchmark`
- `Review Notes`

This will make compare feel like a proper research object rather than a one-off form sitting beside launch.

---

## Proposed Launch Form Improvements

### Core Problems Today
- field meaning disappears once values are populated
- booleans are typed as text
- all parameters compete equally

### Recommended Changes

1. Replace placeholder-only inputs with visible labels

2. Group fields into sections:
- Session
- Market Window
- Strategy Parameters
- Risk Policy
- Advanced / Debug

3. Replace string booleans with controls better suited to the value:
- checkbox
- toggle
- select for true/false when explicitness matters

4. Put these in an advanced section by default:
- `persist_debug_traces`
- low-frequency risk overrides
- experimental overrides

5. Add preset helpers:
- `Baseline Perp`
- `Baseline Spot`
- `Aggressive Perp`

These presets can fill the form but still leave the values editable.

---

## Proposed Trace Investigation Improvements

The current trace viewer has enough backend power that the main UI work should now focus on making it feel investigative rather than tabular.

Recommended improvements:

1. Keep `Trace Anchors` close to trace filters and trace table
- they belong to the same mental workflow

2. Add filter chips / badges showing active filters
- so the user knows why rows are missing

3. Promote the selected trace identity
- step index
- bar time
- symbol
- signal/order/fill counts

4. Keep the structured detail layout
- `Step Summary`
- `Linkage`
- `State Delta`
- `Decision`
- `Risk`
- `Raw`

5. Future note action placement
- reserve room for:
  - `Create investigation note from selected trace`
  - `Attach to existing note`

---

## Visual/Interaction Recommendations

These are low-risk usability upgrades that preserve the current internal-console nature:

1. Use clearer section dividers and spacing
- the page currently reads as one long sequence of equal-weight blocks

2. Add sticky sub-navigation inside Backtests
- `Launch | Runs | Compare | Investigate`

3. Add selected-state highlighting
- selected run row
- selected compare note row
- selected trace row

4. Reduce JSON-first presentation
- make JSON a secondary detail surface
- not the primary reading surface

5. Use summary cards where the user needs orientation
- selected run
- selected compare set
- selected investigation

6. Preserve desktop-first density, but improve mobile fallback
- the current responsive grid collapse is good as a baseline
- but the information hierarchy should still hold after stacking

---

## Phased Implementation

## UI Phase A: Launch Form Cleanup

Scope:
- visible labels
- grouped sections
- checkbox/select treatment for booleans
- advanced/debug subsection

Acceptance:
- the user can identify `persist_debug_traces`, `allow_short`, and risk fields without guessing from values
- common run launch requires less scanning

## UI Phase B: Backtest Workspace Restructure

Scope:
- segmented navigation inside Backtests
- separate `Launch`, `Runs`, `Compare`, `Investigate`
- selected run summary header

Acceptance:
- the user no longer needs to scroll through compare and trace sections just to inspect run KPIs

## UI Phase C: Run Detail Tabs and Charts

Scope:
- run detail tabs
- summary cards
- equity/drawdown visualization
- cleaner execution/trace grouping

Acceptance:
- the selected run can be understood from summary-first surfaces before opening payload details

## UI Phase D: Compare Workspace Cleanup

Scope:
- dedicated compare builder/result area
- review notes integrated in the same compare workspace

Acceptance:
- compare no longer feels coupled to run launch

## UI Phase E: Investigation Workflow

Scope:
- better diagnostics/trace arrangement
- trace-linked note actions
- future replay investigation entry points

Acceptance:
- the user can move from diagnostic warning -> trace evidence -> note workflow without losing context

---

## Recommended Immediate Next Slice

The safest next UI slice is:

### Slice
`UI Phase A: Launch Form Cleanup`

### Why
- lowest risk
- most obvious usability pain
- fixes the specific confusion already observed in current use, such as not knowing which field is `persist_debug_traces`
- improves daily usability without requiring larger workspace restructuring first

### Explicitly Defer
- full tabbed run workspace
- chart-heavy redesign
- compare workspace split
- replay investigation UI

---

## Resume Checklist

When resuming this UI work:
- inspect `frontend/monitoring/index.html`
- inspect `frontend/monitoring/app.js`
- inspect `frontend/monitoring/styles.css`
- confirm whether the next slice is launch-form cleanup or broader workspace restructuring
- avoid mixing large UX restructure with replay-note backend work in the same slice
- update `docs/agent-memory/HANDOFF.md` before stopping

---

## Summary

The current internal UI is already functionally capable, but it is too dense and flat for repeated research use.

The right direction is:
- reduce placeholder-only forms
- separate launch / runs / compare / investigate flows
- move from JSON-first to summary-first presentation
- turn selected run and selected compare set into clearer workspaces

The immediate next move should be:
- clean up the launch form first
- then restructure the Backtests workspace
- then polish compare and investigation flows on top of that clearer layout
