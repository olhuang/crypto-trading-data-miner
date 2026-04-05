param(
    [string]$Symbol = "BTCUSDT",
    [string]$UnifiedSymbol = "BTCUSDT_PERP",
    [string]$StartTime = "2026-04-04T23:55:00+00:00",
    [string]$EndTime = "2026-04-05T00:12:59+00:00",
    [string]$RequestedBy = "repair_mark_index_gap_ps1",
    [string]$PythonExe = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PythonScript = Join-Path $PSScriptRoot "repair_mark_index_gap.py"

function Resolve-PythonExe() {
    if ($PythonExe.Trim()) {
        return $PythonExe
    }

    $VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (Test-Path $VenvPython) {
        return $VenvPython
    }

    return "python"
}

$Python = Resolve-PythonExe
$Args = @(
    $PythonScript,
    "--symbol", $Symbol,
    "--unified-symbol", $UnifiedSymbol,
    "--start-time", $StartTime,
    "--end-time", $EndTime,
    "--requested-by", $RequestedBy
)

if ($DryRun) {
    $Args += "--dry-run"
}

Write-Host ""
Write-Host ("=" * 78)
Write-Host "Binance Mark/Index Gap Repair"
Write-Host ("=" * 78)
Write-Host ("Repo Root: {0}" -f $RepoRoot)
Write-Host ("Python: {0}" -f $Python)
Write-Host ("Command: {0} {1}" -f $Python, ($Args -join " "))

& $Python @Args
exit $LASTEXITCODE
