[CmdletBinding()]
param(
    [string]$ExchangeCode = "binance",
    [Parameter(Mandatory = $true)][string]$UnifiedSymbol,
    [Parameter(Mandatory = $true)][string]$StartTime,
    [Parameter(Mandatory = $true)][string]$EndTime,
    [string]$ObservedAt,
    [string[]]$DataType,
    [string]$RawEventChannel,
    [switch]$NoPersist,
    [string]$Output,
    [string]$PythonExe = ".\.venv\Scripts\python.exe"
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = if ([System.IO.Path]::IsPathRooted($PythonExe)) { $PythonExe } else { Join-Path $repoRoot $PythonExe }
$scriptPath = Join-Path $repoRoot "scripts\validate_dataset_integrity.py"

$arguments = @(
    $scriptPath,
    "--exchange-code", $ExchangeCode,
    "--unified-symbol", $UnifiedSymbol,
    "--start-time", $StartTime,
    "--end-time", $EndTime
)

if ($ObservedAt) {
    $arguments += @("--observed-at", $ObservedAt)
}
foreach ($value in ($DataType | Where-Object { $_ })) {
    $arguments += @("--data-type", $value)
}
if ($RawEventChannel) {
    $arguments += @("--raw-event-channel", $RawEventChannel)
}
if ($NoPersist) {
    $arguments += "--no-persist"
}
if ($Output) {
    $arguments += @("--output", $Output)
}

Write-Host ("=" * 78)
Write-Host "Dataset Integrity Validator"
Write-Host ("=" * 78)
Write-Host "Repo Root: $repoRoot"
Write-Host "Python: $pythonPath"
Write-Host "Unified Symbol: $UnifiedSymbol"
Write-Host "Window: $StartTime -> $EndTime"
if ($ObservedAt) {
    Write-Host "Observed At: $ObservedAt"
}
if ($DataType) {
    Write-Host ("Datasets: " + ($DataType -join ", "))
}
if ($RawEventChannel) {
    Write-Host "Raw Event Channel: $RawEventChannel"
}
Write-Host "Persist Findings: $([bool](-not $NoPersist))"
Write-Host ""
Write-Host ("Command: {0} {1}" -f $pythonPath, ($arguments -join " "))

& $pythonPath @arguments
exit $LASTEXITCODE
