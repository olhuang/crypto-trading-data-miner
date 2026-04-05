param(
    [ValidateSet("bootstrap", "resume", "incremental")]
    [string]$Mode = "incremental",

    [string]$StartDate = "2020-01-01",
    [string]$EndDate = "",
    [string]$StatusFile = "",
    [string]$RequestedBy = "binance_btc_history_backfill_ps1",
    [string]$PythonExe = "",
    [string[]]$Dataset = @(),

    [switch]$StatusOnly,
    [switch]$WatchStatus,
    [int]$RefreshSeconds = 5,
    [switch]$NoExecute
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PythonScript = Join-Path $PSScriptRoot "binance_btc_history_backfill.py"
$DefaultStatusFile = Join-Path $RepoRoot "tmp\binance_btc_history_backfill_status.json"

if (-not $StatusFile.Trim()) {
    $StatusFile = $DefaultStatusFile
}

function Write-Section([string]$Title) {
    Write-Host ""
    Write-Host ("=" * 78)
    Write-Host $Title
    Write-Host ("=" * 78)
}

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

function Format-Value($Value) {
    if ($null -eq $Value) {
        return "-"
    }
    if ($Value -is [System.Collections.IEnumerable] -and -not ($Value -is [string])) {
        return ($Value | ConvertTo-Json -Compress -Depth 6)
    }
    return [string]$Value
}

function Show-StatusSnapshot([string]$Path) {
    Write-Section "Binance BTC Backfill Status"
    Write-Host ("Status file: {0}" -f $Path)

    if (-not (Test-Path $Path)) {
        Write-Host "Status file not found."
        return
    }

    $Status = Get-Content $Path -Raw | ConvertFrom-Json
    $Overall = $Status.overall
    $CurrentTask = $Status.current_task

    Write-Host ("State: {0}" -f (Format-Value $Status.state))
    Write-Host ("Mode: {0}" -f (Format-Value $Status.mode))
    Write-Host ("Updated At: {0}" -f (Format-Value $Status.updated_at))
    Write-Host ("Progress: {0}/{1} ({2}%)" -f (Format-Value $Overall.tasks_completed), (Format-Value $Overall.tasks_total), (Format-Value $Overall.progress_pct))

    if ($CurrentTask) {
        Write-Host ""
        Write-Host "Current Task:"
        Write-Host ("- dataset: {0}" -f (Format-Value $CurrentTask.dataset_key))
        Write-Host ("- label: {0}" -f (Format-Value $CurrentTask.label))
        Write-Host ("- task: {0}/{1}" -f (Format-Value $CurrentTask.task_number), (Format-Value $CurrentTask.task_total))
        Write-Host ("- chunk: {0}/{1}" -f (Format-Value $CurrentTask.chunk_index), (Format-Value $CurrentTask.chunk_total))
        Write-Host ("- window: {0} -> {1}" -f (Format-Value $CurrentTask.window_start), (Format-Value $CurrentTask.window_end))
    }

    if ($Status.last_result) {
        Write-Host ""
        Write-Host "Last Result:"
        Write-Host ("- dataset: {0}" -f (Format-Value $Status.last_result.dataset_key))
        Write-Host ("- status: {0}" -f (Format-Value $Status.last_result.status))
        Write-Host ("- rows_written: {0}" -f (Format-Value $Status.last_result.rows_written))
    }

    if ($Status.datasets) {
        Write-Host ""
        Write-Host "Datasets:"
        foreach ($Dataset in $Status.datasets.PSObject.Properties) {
            $Payload = $Dataset.Value
            Write-Host ("- {0}: chunks {1}/{2}, rows_written={3}" -f $Payload.dataset_key, $Payload.chunks_completed, $Payload.chunk_total, $Payload.rows_written)
        }
    }

    if ($Status.coverage_summary) {
        Write-Host ""
        Write-Host "Coverage Summary Present: yes"
        foreach ($Symbol in $Status.coverage_summary.PSObject.Properties) {
            foreach ($Dataset in $Symbol.Value.PSObject.Properties) {
                $Payload = $Dataset.Value
                $SafeTo = $Payload.safe_available_to
                $FutureRows = $Payload.future_row_count
                Write-Host ("- {0}.{1}: safe_available_to={2}, future_row_count={3}" -f $Symbol.Name, $Dataset.Name, (Format-Value $SafeTo), (Format-Value $FutureRows))
            }
        }
    }

    if ($Status.error) {
        Write-Host ""
        Write-Host "Error:"
        Write-Host ("- message: {0}" -f (Format-Value $Status.error.message))
        Write-Host ("- failed_at: {0}" -f (Format-Value $Status.error.failed_at))
    }
}

function Watch-StatusSnapshot([string]$Path, [int]$Seconds) {
    while ($true) {
        Clear-Host
        Show-StatusSnapshot -Path $Path
        Start-Sleep -Seconds $Seconds
    }
}

if ($StatusOnly) {
    Show-StatusSnapshot -Path $StatusFile
    exit 0
}

if ($WatchStatus) {
    Watch-StatusSnapshot -Path $StatusFile -Seconds $RefreshSeconds
    exit 0
}

$Python = Resolve-PythonExe
$Args = @($PythonScript, "--status-file", $StatusFile, "--requested-by", $RequestedBy)

if ($Mode -eq "resume") {
    $Args += "--resume-from-status"
    if ($PSBoundParameters.ContainsKey("StartDate")) {
        $Args += @("--start-date", $StartDate)
    }
    if ($PSBoundParameters.ContainsKey("EndDate") -and $EndDate.Trim()) {
        $Args += @("--end-date", $EndDate)
    }
}
elseif ($Mode -eq "incremental") {
    $Args += "--incremental"
    $Args += @("--start-date", $StartDate)
    foreach ($DatasetName in $Dataset) {
        if ($DatasetName.Trim()) {
            $Args += @("--dataset", $DatasetName.Trim())
        }
    }
    if ($EndDate.Trim()) {
        $Args += @("--end-date", $EndDate)
    }
}
else {
    $Args += @("--start-date", $StartDate)
    if ($EndDate.Trim()) {
        $Args += @("--end-date", $EndDate)
    }
}

Write-Section "Binance BTC Backfill Launcher"
Write-Host ("Repo Root: {0}" -f $RepoRoot)
Write-Host ("Python: {0}" -f $Python)
Write-Host ("Mode: {0}" -f $Mode)
Write-Host ("Status File: {0}" -f $StatusFile)
Write-Host ("Command: {0} {1}" -f $Python, ($Args -join " "))

if ($NoExecute) {
    Write-Host ""
    Write-Host "NoExecute is set. Command not started."
    exit 0
}

& $Python @Args
$ExitCode = $LASTEXITCODE

Write-Section "Post-Run Status"
Show-StatusSnapshot -Path $StatusFile

exit $ExitCode
