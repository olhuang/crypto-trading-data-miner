param(
    [string]$Subtask = "",
    [int]$MaxLinesPerMemoryFile = 120
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot

$StableDocs = @(
    "README.md",
    "docs/spec-index.md",
    "docs/implementation-plan.md",
    "docs/phases-2-to-9-checklists.md",
    "docs/repo-self-review-tracker.md"
)

$MemoryDocs = @(
    "docs/agent-memory/PROJECT_STATE.md",
    "docs/agent-memory/TASK_BOARD.md",
    "docs/agent-memory/DECISION_LOG.md",
    "docs/agent-memory/HANDOFF.md"
)

function Write-Section([string]$Title) {
    Write-Host ""
    Write-Host ("=" * 78)
    Write-Host $Title
    Write-Host ("=" * 78)
}

function Show-FilePreview([string]$RelativePath, [int]$MaxLines) {
    $FullPath = Join-Path $RepoRoot $RelativePath
    Write-Host ""
    Write-Host ("--- {0} ---" -f $RelativePath)
    if (-not (Test-Path $FullPath)) {
        Write-Host "Missing file."
        return
    }
    Get-Content $FullPath | Select-Object -First $MaxLines
}

Write-Section "Repo Memory Workflow: Session Start"
Write-Host "Read the stable docs first:"
foreach ($Path in $StableDocs) {
    Write-Host ("- {0}" -f $Path)
}

Write-Section "Repo Memory Files"
foreach ($Path in $MemoryDocs) {
    Show-FilePreview -RelativePath $Path -MaxLines $MaxLinesPerMemoryFile
}

Write-Section "Required Next Actions"
Write-Host "1. Summarize the current repo state in 8 bullets or fewer."
Write-Host "2. Pick exactly one highest-value subtask."
Write-Host "3. State which files/specs you will inspect first."
Write-Host "4. Do not begin editing before the current state is clear."
Write-Host "5. Update docs/agent-memory/SESSION_SUMMARY.md after each milestone."

if ($Subtask.Trim()) {
    Write-Host ""
    Write-Host ("Requested subtask: {0}" -f $Subtask)
}

Write-Section "Suggested Prompt Block"
Write-Host "Read docs/agent-memory/SESSION_START_PROMPT.md and follow it strictly."
if ($Subtask.Trim()) {
    Write-Host ""
    Write-Host "After restating the current state, work only on this subtask:"
    Write-Host $Subtask
}
