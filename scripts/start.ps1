param([int]$ApiPort = 8000, [int]$WebPort = 5173)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv-day2\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { $pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe' }
$frontendRoot = Join-Path $projectRoot 'frontend'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Python environment missing. Follow README setup instructions.' }
if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot 'node_modules\vite\bin\vite.js'))) { throw 'Frontend dependencies missing. Run npm ci in frontend.' }
if ($ApiPort -ne 8000) { throw 'This development proxy expects API port 8000. Change frontend proxy before using another port.' }
if (-not $env:TIANQIONG_DATA_DIR) { $env:TIANQIONG_DATA_DIR = Join-Path $env:LOCALAPPDATA 'TianqiongDemo' }
$runtimeRoot = [IO.Path]::GetFullPath($env:TIANQIONG_DATA_DIR)
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
$ports = @($ApiPort, $WebPort)
foreach ($port in $ports) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { throw "Port $port is already in use. Check the existing service; no process was stopped." }
}
$apiOut = Join-Path $runtimeRoot 'backend.stdout.log'
$apiErr = Join-Path $runtimeRoot 'backend.stderr.log'
$webOut = Join-Path $runtimeRoot 'frontend.stdout.log'
$webErr = Join-Path $runtimeRoot 'frontend.stderr.log'
$nodeExe = (Get-Command node -ErrorAction Stop).Source
$viteScript = Join-Path $frontendRoot 'node_modules\vite\bin\vite.js'
$quotedViteScript = '"' + $viteScript + '"'
$apiProcess = Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','app.main:app','--app-dir','backend','--host','127.0.0.1','--port',"$ApiPort") -WorkingDirectory $projectRoot -RedirectStandardOutput $apiOut -RedirectStandardError $apiErr -WindowStyle Hidden -PassThru
try {
    $webProcess = Start-Process -FilePath $nodeExe -ArgumentList @($quotedViteScript,'--host','127.0.0.1','--port',"$WebPort",'--strictPort') -WorkingDirectory $frontendRoot -RedirectStandardOutput $webOut -RedirectStandardError $webErr -WindowStyle Hidden -PassThru
} catch { Stop-Process -Id $apiProcess.Id -ErrorAction SilentlyContinue; throw }
$processRecord = @{
    backend = @{ pid = $apiProcess.Id; started_at = $apiProcess.StartTime.ToUniversalTime().ToString('o'); started_ticks = $apiProcess.StartTime.ToUniversalTime().Ticks; executable = $pythonExe }
    frontend = @{ pid = $webProcess.Id; started_at = $webProcess.StartTime.ToUniversalTime().ToString('o'); started_ticks = $webProcess.StartTime.ToUniversalTime().Ticks; executable = $nodeExe }
    project = $projectRoot
}
$processRecord | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $runtimeRoot 'processes.json') -Encoding utf8
$ready = $false
for ($attempt = 0; $attempt -lt 25; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/health" -TimeoutSec 2
        $web = Invoke-WebRequest -Uri "http://127.0.0.1:$WebPort/" -UseBasicParsing -TimeoutSec 2
        if ($health.status -eq 'ok' -and $web.StatusCode -eq 200) { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 400 }
}
if (-not $ready) { throw "Startup not confirmed. Inspect logs in $runtimeRoot. Use scripts/stop.ps1 to stop only this project's processes." }
Write-Output "Frontend: http://127.0.0.1:$WebPort"
Write-Output "API docs: http://127.0.0.1:$ApiPort/docs"
Write-Output "Runtime data: $runtimeRoot"
Write-Output 'Tianheng SKYDOME: local simulation with evidence analysis and coordinated execution. Closing the browser does not stop the services.'
