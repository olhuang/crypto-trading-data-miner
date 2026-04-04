# AI Memory and Handoff Workflow Spec

## Purpose

This document defines a practical memory workflow for AI coding agents working in
this repository.

The goal is not to make the model "remember everything".
The goal is to make long-running repository work:
- resumable
- compact
- verifiable
- handoff-friendly across sessions
- aligned with this project's existing spec / phase / tracker structure

This spec is intended for:
- Codex-style coding-agent workflows
- long-running Phase 5-8 implementation tasks
- repo self-review and follow-up cleanup
- strategy/research/backtest/replay workbench tasks that span multiple sessions

It complements:
- `README.md`
- `docs/spec-index.md`
- `docs/implementation-plan.md`
- `docs/phases-2-to-9-checklists.md`
- `docs/strategy-workbench-spec.md`
- `docs/strategy-research-and-evaluation-spec.md`
- `docs/repo-self-review-tracker.md`

---

## 1. Design Principles

### 1.1 Do Not Rely on Chat History Alone

Chat history is useful for short-term continuity, but it is not a trustworthy
source of long-term project memory.

The workflow should assume that:
- long transcripts will be compacted
- middle-context details can be lost
- a future session may begin with only a partial summary

### 1.2 Separate Thinking Memory From Project Memory

The model may use transient reasoning internally, but project memory must live in
repo-visible artifacts.

The repository should preserve:
- durable project state
- active task state
- decisions
- handoff packet
- session summary

### 1.3 Keep Memory Layered

The memory system should preserve three layers:

- `stable memory`
  - low-frequency facts about the project
- `task memory`
  - what is currently being worked on
- `session memory`
  - what just happened in the last work slice

### 1.4 Favor Short, Verified, Structured Records

Memory artifacts should prefer:
- short bullets over transcripts
- `verified` findings over speculation
- explicit assumptions instead of hidden guesses
- references to files / specs / commits instead of free-form narration

### 1.5 Handoffs Must Be Runnable

A cross-session handoff is good only if the next agent can:
- understand the current focus quickly
- identify what is already verified
- know what file/spec to read next
- continue with a concrete next action

---

## 2. Memory Layers for This Project

### 2.1 Stable Memory

Stable memory should capture low-frequency, high-value facts such as:
- current repo maturity
- phase status
- architecture guardrails
- canonical source-of-truth docs
- durable implementation constraints

For this repository, stable memory should draw from:
- `README.md`
- `docs/spec-index.md`
- `docs/implementation-plan.md`
- `docs/phases-2-to-9-checklists.md`

### 2.2 Task Memory

Task memory should capture:
- what is currently in progress
- what is blocked
- what is next
- what was just completed

Task memory should not duplicate every detail from the full phase checklists.
It should act as the focused working board for the currently active slice.

### 2.3 Session Memory

Session memory should capture:
- what this session tried to do
- what changed
- what was verified
- what remains risky
- what the next session should do first

This is the main handoff layer.

---

## 3. Canonical Memory Artifacts

The repository should use the following file set under `docs/agent-memory/`.

### 3.1 `docs/agent-memory/PROJECT_STATE.md`

Purpose:
- stable project state
- current repo maturity
- current implementation baseline
- key source-of-truth docs

Update frequency:
- low
- only when project state changes materially

### 3.2 `docs/agent-memory/TASK_BOARD.md`

Purpose:
- active working board for the current repo slice

Sections should include:
- `Current Focus`
- `In Progress`
- `Blocked`
- `Next`
- `Recently Done`

Update frequency:
- whenever the active task focus changes

### 3.3 `docs/agent-memory/DECISION_LOG.md`

Purpose:
- durable technical decisions
- confirmed root causes
- accepted tradeoffs

Should include:
- date
- decision
- reason
- impact

Should not include:
- trivial implementation chatter
- temporary debugging noise

### 3.4 `docs/agent-memory/HANDOFF.md`

Purpose:
- cross-session handoff packet

Must include:
- current focus
- verified findings
- open problems
- exact files/specs to inspect next
- recommended next action

This is the most important resume file.

### 3.5 `docs/agent-memory/SESSION_SUMMARY.md`

Purpose:
- compact rolling session summary

Should include:
- goal
- done
- files changed
- decisions
- risks
- next

This file may be overwritten or kept as a rolling latest summary.

---

## 4. Memory Workflow

The intended workflow is:

```text
Load Stable Memory
  -> Restate Current State
  -> Pick One Subtask
  -> Work One Milestone
  -> Compress Into Session Summary
  -> Update Task Board / Decision Log
  -> Write Handoff
  -> Stop or Continue
```

### 4.1 Session Start

At the start of a session, the agent should read:
- `README.md`
- `docs/spec-index.md`
- `docs/implementation-plan.md`
- `docs/phases-2-to-9-checklists.md`
- `docs/repo-self-review-tracker.md`
- `docs/agent-memory/PROJECT_STATE.md`
- `docs/agent-memory/TASK_BOARD.md`
- `docs/agent-memory/DECISION_LOG.md`
- `docs/agent-memory/HANDOFF.md`

Then it should produce:
- one short current-state summary
- one explicitly chosen subtask

### 4.2 Single-Subtask Rule

One session should ideally focus on:
- one bug
- one spec cleanup
- one implementation slice
- one review/fix batch

The memory workflow should explicitly avoid:
- mixing unrelated modules
- carrying too many parallel changes
- storing giant transcripts as memory

### 4.3 Milestone Update Rule

After each meaningful milestone, the agent should update:
- `SESSION_SUMMARY.md`
- `TASK_BOARD.md`
- `DECISION_LOG.md` when applicable

Milestones include:
- root cause confirmed
- spec aligned
- code change landed
- tests passed
- blocker discovered
- task boundary changed

### 4.4 Session End / Handoff Rule

Before stopping, the agent should always update:
- `HANDOFF.md`

Minimum handoff contents:
- what changed
- what is verified
- what is still open
- what file/spec to inspect first
- what action should happen next

---

## 5. Memory Writing Rules

### 5.1 Verified vs Assumption

Memory artifacts should distinguish:
- `verified`
- `assumption`
- `planned`

The agent should not silently promote assumptions into stable memory.

### 5.2 Source-of-Truth Linking

When recording important memory, prefer references to:
- file paths
- spec names
- task ids
- commit ids

Instead of vague phrases like:
- "the system was changed"

Prefer:
- "Phase 5 risk guardrail state snapshot now persists in `src/backtest/risk.py` and is exposed via `src/api/app.py`"

### 5.3 Compression Rule

Memory files should remain short.

Target style:
- bullets
- short paragraphs
- direct file references

Avoid:
- full transcripts
- repeated background
- giant copied logs

### 5.4 Rolling vs Stable Updates

Use this rule:
- stable facts go to `PROJECT_STATE.md`
- durable decisions go to `DECISION_LOG.md`
- current work state goes to `TASK_BOARD.md`
- latest session state goes to `SESSION_SUMMARY.md`
- cross-session continuation goes to `HANDOFF.md`

---

## 6. Project-Specific Source-of-Truth Order

When memory conflicts appear, the agent should use this order:

1. implemented code / SQL for current implementation reality
2. detailed topic spec
3. implementation plan
4. phase checklist
5. agent-memory files
6. chat history

This means:
- the memory workflow helps continuity
- it does not override actual source-of-truth docs or code

---

## 7. Project-Specific Recommended Session Start Prompt

For this repository, the recommended session-start behavior is:

1. read the current source-of-truth docs
2. read agent-memory files
3. summarize current state in 8 bullets or fewer
4. select one subtask
5. only then start changing code/specs

Recommended prompt shape:

```text
Before doing anything:
1. Read README.md
2. Read docs/spec-index.md
3. Read docs/implementation-plan.md
4. Read docs/phases-2-to-9-checklists.md
5. Read docs/repo-self-review-tracker.md
6. Read docs/agent-memory/PROJECT_STATE.md
7. Read docs/agent-memory/TASK_BOARD.md
8. Read docs/agent-memory/DECISION_LOG.md
9. Read docs/agent-memory/HANDOFF.md

Then:
- summarize the current repo state in <=8 bullets
- identify exactly one highest-value subtask
- do not begin coding before the current state is clear
```

The reusable file form of this prompt lives at:
- `docs/agent-memory/SESSION_START_PROMPT.md`

---

## 8. Project-Specific Recommended Session Stop Prompt

Recommended stop behavior:

```text
Before stopping:
1. Update docs/agent-memory/SESSION_SUMMARY.md
2. Update docs/agent-memory/TASK_BOARD.md
3. Append to docs/agent-memory/DECISION_LOG.md if a real decision was made
4. Update docs/agent-memory/HANDOFF.md

The handoff must include:
- current focus
- what is verified
- what remains open
- exact files/specs to inspect next
- recommended next action
```

The reusable stop checklist lives at:
- `docs/agent-memory/SESSION_STOP_CHECKLIST.md`

An operator-facing automation template for CLI / VS Code lives at:
- `docs/agent-memory/WORKFLOW_AUTOMATION_TEMPLATE.md`

---

## 9. Anti-Patterns

Do not:
- rely only on chat history as memory
- dump entire transcripts into memory files
- store unresolved speculation as a stable fact
- work on too many subtasks in one session
- let handoff be vague or non-actionable
- duplicate the entire implementation plan into task memory

---

## 10. Phased Implementation Plan

### Phase A: Manual File-Based Workflow

Implement:
- memory spec
- repo-local memory files
- explicit usage rules

This is the minimum viable and immediately useful version.

### Phase B: Workflow Discipline

Enforce by habit/process:
- session start reads memory files
- session stop writes handoff
- milestone updates keep task board fresh
- start/stop templates are easy to reuse from CLI / editor tooling

This can happen without new runtime code.

### Phase C: Workbench Integration

Later integrate with:
- strategy workbench
- compare/analyze
- artifact bundles
- replay scenarios

Examples:
- attach handoff packets to run groups
- store review notes and next-step memory with compare sets
- tie replay-scenario notes into durable memory

### Phase D: API / UI Support

Later add optional API/UI support for:
- structured notes
- run annotations
- handoff state
- memory-linked review workflow

### Phase E: Paper / Live Reuse

Later reuse the same memory/handoff model for:
- paper-session handoffs
- live incident investigation
- reconciliation review follow-through

---

## 11. Why This Workflow Fits This Project

This repository has:
- many layered specs
- long-running phased work
- backtest / replay / diagnostics work that spans sessions
- self-review / follow-up cleanup work

That means the repo needs more than generic chat continuity.

It needs:
- compact working memory
- explicit handoff
- spec-aware restart behavior
- project-visible state rather than hidden transcript memory

This workflow is intentionally designed to fit:
- design-first development
- Phase 5 research/backtest expansion
- repo-local start/stop tooling before any future UI-backed annotation system
- future paper/live/reconciliation handoff needs

---

## 12. Final Summary

The right memory model for this repository is:

- not "let the AI remember everything"
- but "let the AI read stable docs, maintain a small active task board, and leave a clean handoff packet"

The repository should treat AI memory as:
- structured repo state
- short summaries
- explicit decisions
- actionable handoff

That is the most practical path to robust long-horizon work without depending on fragile chat-history recall.
