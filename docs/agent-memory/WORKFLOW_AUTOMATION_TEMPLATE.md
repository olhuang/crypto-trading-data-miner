# Workflow Automation Template

This file shows the minimum practical way to run the repo memory workflow from
CLI or VS Code.

The goal is not to automate everything immediately. The goal is to make it easy
to start every session with the same memory discipline.

---

## 1. Minimal CLI Pattern

Use the session-start prompt in:
- `docs/agent-memory/SESSION_START_PROMPT.md`

Then run your agent with one explicit subtask.

Example shape:

```text
Read docs/agent-memory/SESSION_START_PROMPT.md and follow it strictly.
After restating the current state, work only on this subtask:

<one concrete subtask here>
```

Recommended stop rule:

```text
Before stopping, follow docs/agent-memory/SESSION_STOP_CHECKLIST.md.
```

---

## 2. Repo-Provided VS Code Tasks

This repository now ships a minimal `.vscode/tasks.json` with:
- `Memory: Start Session`
- `Memory: Stop Session`

These tasks call:
- `scripts/start_memory_session.ps1`
- `scripts/stop_memory_session.ps1`

The default task flow is editor-agnostic enough to work without forcing any
specific AI CLI path. The tasks print the exact memory files and start/stop
instructions into the terminal so the next agent step can follow them.

If you want a more automated local launcher, you can still adapt the tasks to
your own CLI setup later.

---

## 3. Suggested Session Rhythm

### Start
- run `Memory: Start Session` from VS Code, or run `scripts/start_memory_session.ps1`
- select one subtask
- inspect only the most relevant files/specs first

### During Work
- keep the active subtask small
- update `SESSION_SUMMARY.md` after meaningful milestones
- move task state in `TASK_BOARD.md` when the focus changes

### Stop
- run `Memory: Stop Session` from VS Code, or run `scripts/stop_memory_session.ps1`
- make the next action in `HANDOFF.md` concrete enough that another agent can
  continue without rereading the whole transcript

---

## 4. Recommended Future Upgrades

Later, this repo can extend the workflow with:
- workbench annotations tied to backtest/replay runs
- compare/review notes tied to compare sets
- replay investigation notes tied to scenarios/incidents
- API/UI-backed handoff and review state

Until then, these repo-visible files are the durable memory layer.
