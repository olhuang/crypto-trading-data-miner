# Session Start Prompt

Use this prompt at the start of a new long-running coding session for this
repository.

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
- state which files/specs will be inspected first
- do not begin coding before the current state is clear

While working:
- update docs/agent-memory/SESSION_SUMMARY.md after each meaningful milestone
- update docs/agent-memory/TASK_BOARD.md when task state changes
- append to docs/agent-memory/DECISION_LOG.md only for durable decisions
- keep summaries short and verified
```

## Operator Notes
- This prompt is for session start only.
- If the session becomes noisy, re-run this prompt and restate the current
  state before continuing.
- Treat repo-visible docs as the source of truth, not transcript memory.
