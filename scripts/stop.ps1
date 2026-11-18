$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = if ($env:TIANQIONG_DATA_DIR) { [IO.Path]::GetFullPath($env:TIANQIONG_DATA_DIR) } else { Join-Path $env:LOCALAPPDATA 'TianqiongDemo' }
$recordPath = Join-Path $runtimeRoot 'processes.json'
if (-not (Test-Path -LiteralPath $recordPath)) { Write-Output 'No recorded project processes.'; exit 0 }
$record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
if ($record.project -ne $projectRoot) { throw 'Recorded project path does not match this checkout.' }
foreach ($service in @($record.backend, $record.frontend)) {
    $process = Get-Process -Id $service.pid -ErrorAction SilentlyContinue
    if ($process) {
        $expectedTicks = if ($service.started_ticks) { [long]$service.started_ticks } else { ([datetime]$service.started_at).ToUniversalTime().Ticks }
        $timeDifference = [Math]::Abs($process.StartTime.ToUniversalTime().Ticks - $expectedTicks)
        if ($process.Path -ne $service.executable -or $timeDifference -gt [TimeSpan]::TicksPerSecond) { Write-Warning "PID $($service.pid) no longer matches the recorded service; skipped."; continue }
        # A Windows virtualenv launcher has a child interpreter which owns the port.
        & taskkill.exe /PID $process.Id /T /F | Out-Null
        Write-Output "Stopped project process $($process.Id)"
    }
}
