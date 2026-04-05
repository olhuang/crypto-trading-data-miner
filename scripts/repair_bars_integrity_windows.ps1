param(
    [string]$Symbol = "BTCUSDT",
    [string]$UnifiedSymbol = "BTCUSDT_PERP",
    [string]$Interval = "1m",
    [string]$RequestedBy = "repair_bars_integrity_windows_ps1",
    [string]$StartTime = "",
    [string]$EndTime = "",
    [string]$PythonExe = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PythonScript = Join-Path $PSScriptRoot "repair_bars_integrity_windows.py"

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
    "--interval", $Interval,
    "--requested-by", $RequestedBy
)

if ($StartTime.Trim() -and $EndTime.Trim()) {
    $Args += @("--start-time", $StartTime, "--end-time", $EndTime)
}
elseif ($StartTime.Trim() -or $EndTime.Trim()) {
    throw "StartTime and EndTime must be supplied together."
}

if ($DryRun) {
    $Args += "--dry-run"
}

Write-Host ""
Write-Host ("=" * 78)
Write-Host "Binance Bars Integrity Repair"
Write-Host ("=" * 78)
Write-Host ("Repo Root: {0}" -f $RepoRoot)
Write-Host ("Python: {0}" -f $Python)
Write-Host ("Command: {0} {1}" -f $Python, ($Args -join " "))

& $Python @Args
exit $LASTEXITCODE
