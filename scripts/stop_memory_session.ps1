param(
    [string]$SuggestedNextAction = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot

$ChecklistPath = Join-Path $RepoRoot "docs/agent-memory/SESSION_STOP_CHECKLIST.md"
$HandoffPath = Join-Path $RepoRoot "docs/agent-memory/HANDOFF.md"
$SummaryPath = Join-Path $RepoRoot "docs/agent-memory/SESSION_SUMMARY.md"
$TaskBoardPath = Join-Path $RepoRoot "docs/agent-memory/TASK_BOARD.md"
$DecisionLogPath = Join-Path $RepoRoot "docs/agent-memory/DECISION_LOG.md"

function Write-Section([string]$Title) {
    Write-Host ""
    Write-Host ("=" * 78)
    Write-Host $Title
    Write-Host ("=" * 78)
}

Write-Section "Repo Memory Workflow: Session Stop"
Write-Host "Update these files before stopping:"
Write-Host ("- {0}" -f $SummaryPath.Replace($RepoRoot + "\", ""))
Write-Host ("- {0}" -f $TaskBoardPath.Replace($RepoRoot + "\", ""))
Write-Host ("- {0}" -f $DecisionLogPath.Replace($RepoRoot + "\", ""))
Write-Host ("- {0}" -f $HandoffPath.Replace($RepoRoot + "\", ""))

Write-Section "Stop Checklist"
Get-Content $ChecklistPath

Write-Section "Current Handoff"
Get-Content $HandoffPath

Write-Section "Suggested Stop Prompt"
Write-Host "Before stopping, follow docs/agent-memory/SESSION_STOP_CHECKLIST.md."
Write-Host "Make sure docs/agent-memory/HANDOFF.md includes:"
Write-Host "- current focus"
Write-Host "- verified findings"
Write-Host "- open problems"
Write-Host "- exact files/specs to inspect next"
Write-Host "- recommended next action"

if ($SuggestedNextAction.Trim()) {
    Write-Host ""
    Write-Host ("Suggested next action: {0}" -f $SuggestedNextAction)
}
