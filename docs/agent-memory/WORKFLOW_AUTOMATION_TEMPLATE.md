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

## 2. Minimal VS Code Task Template

If you want a one-command launcher, create a local `.vscode/tasks.json` using a
task like this and adapt it to your own Codex/CLI setup:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Run Repo Memory Workflow",
      "type": "shell",
      "command": "codex",
      "args": [
        "Read docs/agent-memory/SESSION_START_PROMPT.md and follow it strictly. After restating the current state, work on exactly one subtask from docs/agent-memory/TASK_BOARD.md. Before stopping, follow docs/agent-memory/SESSION_STOP_CHECKLIST.md."
      ],
      "options": {
        "cwd": "${workspaceFolder}"
      },
      "problemMatcher": []
    }
  ]
}
```

This template is intentionally not auto-installed into the repo because:
- different machines may not have the same CLI path
- different contributors may use different local launch commands
- this repository should not force editor-specific behavior by default

---

## 3. Suggested Session Rhythm

### Start
- run the session-start prompt
- select one subtask
- inspect only the most relevant files/specs first

### During Work
- keep the active subtask small
- update `SESSION_SUMMARY.md` after meaningful milestones
- move task state in `TASK_BOARD.md` when the focus changes

### Stop
- run the stop checklist
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
