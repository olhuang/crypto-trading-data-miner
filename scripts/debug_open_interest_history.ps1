param(
  [string]$Symbol = "BTCUSDT",
  [Parameter(Mandatory = $true)][string]$StartTime,
  [Parameter(Mandatory = $true)][string]$EndTime,
  [string]$Period = "5m",
  [int]$ChunkDays = 1,
  [int]$Limit = 500,
  [switch]$OutputJson,
  [string]$PythonExe = ".\.venv\Scripts\python.exe"
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Resolve-Path -LiteralPath $PythonExe
$scriptPath = Join-Path $repoRoot "scripts\debug_open_interest_history.py"

$arguments = @(
  $scriptPath,
  "--symbol", $Symbol,
  "--start-time", $StartTime,
  "--end-time", $EndTime,
  "--period", $Period,
  "--chunk-days", $ChunkDays,
  "--limit", $Limit
)

if ($OutputJson) {
  $arguments += "--output-json"
}

Write-Host "=============================================================================="
Write-Host "Open Interest History Debug"
Write-Host "=============================================================================="
Write-Host "Repo Root: $repoRoot"
Write-Host "Python: $pythonPath"
Write-Host "Command: $pythonPath $($arguments -join ' ')"

& $pythonPath @arguments
exit $LASTEXITCODE
