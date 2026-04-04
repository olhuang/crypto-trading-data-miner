# Object-Level Notes and Annotations Spec

## Purpose

This document defines how the platform should manage durable notes and
annotations attached to concrete research/runtime objects rather than only to
the repository as a whole.

The goal is to make:
- backtest compare/review work
- replay investigation work
- future workbench annotation UI

resumable, reviewable, and traceable without relying only on chat memory or
repo-level handoff files.

This spec complements:
- `docs/ai-memory-and-handoff-spec.md`
- `docs/strategy-workbench-spec.md`
- `docs/backtest-and-replay-diagnostics-spec.md`
- `docs/strategy-risk-assumption-management-spec.md`
- `docs/ui-api-spec.md`
- `docs/api-resource-contracts.md`

---

## 1. Core Goal

The platform should eventually support two levels of working memory:

1. `repo-level memory`
   - project-wide working context
   - current focus, decisions, handoff
   - currently handled through `docs/agent-memory/`

2. `object-level notes`
   - notes tied to one concrete object such as:
     - a backtest run
     - a compare set
     - a replay run
     - a replay scenario

The rule is:
- repo-level memory tells the next session what overall line of work is active
- object-level notes tell the next session what has already been learned about a
  specific research/runtime object

---

## 2. Why Object-Level Notes Are Needed

Repo-level memory alone is not enough once the platform supports:
- many backtest runs
- many compare sets
- many replay investigations
- promotion/review workflows

Without object-level notes, important research memory tends to drift into:
- chat transcripts
- ad hoc markdown
- screenshots
- spreadsheet side notes

That makes it hard to answer:
- why this compare result mattered
- what was already verified in a replay investigation
- which open questions remain for a specific run or scenario
- what the next reviewer or agent should inspect first

---

## 3. Supported Object Types

The annotation model should eventually support at least:

- `backtest_run`
- `compare_set`
- `replay_run`
- `replay_scenario`

It should preserve room for future expansion to:
- `run_group`
- `experiment`
- `strategy_variant`
- `promotion_review`
- `incident_review`

---

## 4. Canonical Note Types

The object-level note system should support a small stable vocabulary.

Recommended `annotation_type` values:
- `note`
- `review`
- `promotion_decision`
- `investigation`
- `expected_vs_observed`
- `bookmark`
- `follow_up`

Recommended `status` values:
- `draft`
- `in_review`
- `confirmed`
- `follow_up`
- `accepted`
- `rejected`
- `resolved`
- `unresolved`

Recommended `note_source` values:
- `system`
- `agent`
- `human`

Recommended `verification_state` values:
- `system_fact`
- `assumption`
- `verified`

---

## 5. Canonical Annotation Resource Shape

The system should eventually converge on one generic annotation object with
object-specific templates layered on top.

Recommended base shape:

```json
{
  "annotation_id": 9001,
  "entity_type": "compare_set",
  "entity_id": "cmp_20260404_001",
  "annotation_type": "review",
  "status": "draft",
  "title": "BTC momentum compare review",
  "summary": "Initial comparison note for two BTCUSDT_PERP runs.",
  "note_source": "system",
  "verification_state": "system_fact",
  "verified_findings_json": [],
  "open_questions_json": [],
  "next_action": "Review KPI and assumption diffs before promoting.",
  "source_refs_json": {
    "run_ids": [5001, 5002],
    "trace_refs": [],
    "file_refs": []
  },
  "facts_snapshot_json": {},
  "created_by": "system",
  "updated_by": "system",
  "created_at": "2026-04-04T12:00:00Z",
  "updated_at": "2026-04-04T12:00:00Z"
}
```

This base shape should be reused by all object types even if the UI later
renders different note forms.

---

## 6. How Notes Should Be Generated

Object-level notes should not begin as free-form AI prose.

They should be generated in three layers.

### 6.1 Seed Note

When a supported object is created, the system should be able to create a note
draft with:
- object identity
- object type
- stable title
- initial status
- object references

Examples:
- compare-set creation seeds a `review` note draft
- replay-run creation seeds an `investigation` note draft
- replay-scenario creation seeds an `expected_vs_observed` or `bookmark` note

### 6.2 System Enrichment

After seed creation, the system should enrich the note with machine-verifiable
facts.

Examples:
- compare-set KPI diff
- compare-set assumption diff
- compare-set benchmark delta
- replay-run warnings
- replay timeline anchors
- diagnostics flags

This layer should be clearly marked as `system_fact`.

### 6.3 Agent/Human Enrichment

Only after the fact layer exists should an agent or human add:
- verified findings
- open questions
- next action
- review decision
- root-cause hypothesis

This keeps:
- facts
- assumptions
- conclusions

distinct from each other.

---

## 7. Compare and Review Notes

Compare/review notes are the first recommended implementation slice.

### 7.1 Trigger

Create or seed a compare review note when:
- a `compare_set` is created
- a user explicitly opens a review workflow for compared runs

### 7.2 System-Filled Fields

The system should prefill at least:
- `compare_name`
- `run_ids`
- benchmark reference
- KPI comparison snapshot
- assumption diff snapshot
- diagnostics flag diff snapshot
- available period types

### 7.3 Human/Agent Review Fields

The reviewer should then fill:
- which result is more trustworthy
- whether the difference is alpha-driven or assumption-driven
- whether rerun is required
- whether a run is a candidate for promotion
- next recommended action

### 7.4 Why This Matters

This turns compare output from:
- one transient API response

into:
- a durable review object that another session can continue

---

## 8. Replay Investigation Notes

Replay investigation notes should be the second implementation slice.

### 8.1 Trigger

Create or seed a replay investigation note when:
- a `replay_run` is created
- a `replay_scenario` is saved
- a user starts an expected-vs-observed investigation

### 8.2 System-Filled Fields

The system should prefill at least:
- replay window
- symbol/universe
- scenario identity when present
- diagnostics flags
- warning timeline references
- trace/timeline anchors

### 8.3 Human/Agent Investigation Fields

The investigator should then fill:
- expected behavior
- observed behavior
- verified findings
- assumptions not yet confirmed
- next debugging step

### 8.4 Rule

Replay notes should preserve room for both:
- `expected`
- `observed`

without forcing premature root-cause conclusions.

---

## 9. Relationship to Repo-Level Memory

Repo-level handoff and object-level notes should work together.

Recommended rule:
- `docs/agent-memory/HANDOFF.md` should describe the overall active line of work
- when relevant, `HANDOFF.md` should point to the primary object note being
  continued next

In other words:
- repo-level memory handles session continuity
- object-level notes handle research-object continuity

This prevents `HANDOFF.md` from becoming a duplicate of every compare/replay
review body.

---

## 10. Storage Direction

The first real implementation should prefer one generic annotation store rather
than many narrowly specialized tables.

Recommended first direction:
- `research.annotations`

The store should preserve:
- entity identity
- note type
- status
- fact snapshot
- human/agent additions
- timestamps
- actor fields

Object-specific projections can be added later if needed.

---

## 11. API Direction

The system should preserve room for both:
- generic annotation APIs
- object-specific convenience APIs

Recommended generic endpoints:
- `GET /api/v1/annotations`
- `POST /api/v1/annotations`
- `PATCH /api/v1/annotations/{annotation_id}`

Recommended object-specific convenience endpoints:
- `GET /api/v1/backtests/compare-sets/{compare_set_id}/notes`
- `POST /api/v1/backtests/compare-sets/{compare_set_id}/notes`
- `GET /api/v1/replays/runs/{replay_run_id}/notes`
- `POST /api/v1/replays/runs/{replay_run_id}/notes`
- `GET /api/v1/replays/scenarios/{scenario_id}/notes`
- `POST /api/v1/replays/scenarios/{scenario_id}/notes`

The generic store should be the canonical backend abstraction even if the first
UI prefers object-specific routes.

---

## 12. UI Direction

The future workbench UI should expose notes where users actually work.

Recommended placements:

### 12.1 Backtest Run Detail
- optional run notes
- diagnostics-linked annotations

### 12.2 Compare View
- compare review panel
- next-action / rerun decision
- assumption-vs-alpha conclusion note

### 12.3 Replay View
- investigation panel
- expected-vs-observed note
- bookmark and trace-anchor notes

### 12.4 Workbench Overview
- note counts
- unresolved investigations
- pending review decisions
- follow-up queue

The UI should not force users to leave the workbench and write important review
state somewhere else.

---

## 13. Phased Rollout

### Phase A: Planning and Resource Freeze

Deliver:
- this spec
- resource shape
- generation lifecycle
- storage and API direction

### Phase B: Compare Review Note Foundation

Deliver:
- compare-set note draft generation
- system-enriched compare facts
- manual/agent update path
- compare review API baseline

### Phase C: Replay Investigation Note Foundation

Deliver:
- replay-run or replay-scenario note draft generation
- expected-vs-observed fields
- trace/timeline reference support
- replay note API baseline

### Phase D: Unified Annotation Service

Deliver:
- generic annotation repository/service
- entity-specific convenience APIs backed by the same store
- source/verification-state handling

### Phase E: Workbench Annotation UI

Deliver:
- compare review panel
- replay investigation panel
- annotation editing/history in the workbench UI
- handoff links from repo-level memory into concrete object notes

---

## 14. Final Summary

Object-level notes should be:
- generated from templates
- enriched with system facts
- completed by human/agent judgment

They should extend, not replace, the repo-level memory workflow.

The immediate best first slice is:
- compare/review note foundation

The next slice is:
- replay investigation notes

The long-term goal is:
- a unified workbench annotation system tied directly to backtest, compare, and
  replay objects.
