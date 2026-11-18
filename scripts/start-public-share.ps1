param([int]$Port = 8787)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$shareRoot = Join-Path $projectRoot '.runtime\share'
$pythonExe = Join-Path $projectRoot '.venv-day2\Scripts\python.exe'
$tunnelExe = Join-Path $shareRoot 'tools\cloudflared.exe'
if (-not (Test-Path -LiteralPath (Join-Path $shareRoot 'site\index.html'))) { throw 'Build the public preview first.' }
if (-not (Test-Path -LiteralPath $tunnelExe)) { throw 'Official cloudflared executable is missing.' }
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { throw "Port $Port already in use. No process was stopped." }
# Only this child process environment is affected; no key file is read or copied.
Remove-Item Env:ZHIPU_API_KEY,Env:ZAI_API_KEY -ErrorAction SilentlyContinue
$server = Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','app.public_share:app','--app-dir','backend','--host','127.0.0.1','--port',"$Port",'--no-server-header') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $shareRoot 'server.stdout.log') -RedirectStandardError (Join-Path $shareRoot 'server.stderr.log') -PassThru
$ready = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    try {
        $health = Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 2
        if ($health.status -eq 'ok') { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 300 }
}
if (-not $ready) { throw 'Public preview startup failed. Check .runtime/share/server.stderr.log.' }
Invoke-RestMethod "http://127.0.0.1:$Port/api/v1/demo-scenarios/evt-008/prepare" -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 10 | Out-Null
$tunnel = Start-Process -FilePath $tunnelExe -ArgumentList @('tunnel','--no-autoupdate','--protocol','http2','--url',"http://127.0.0.1:$Port") -WorkingDirectory $shareRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $shareRoot 'tunnel.stdout.log') -RedirectStandardError (Join-Path $shareRoot 'tunnel.stderr.log') -PassThru
@{ project=$projectRoot; port=$Port; server=@{pid=$server.Id;started_ticks=$server.StartTime.ToUniversalTime().Ticks}; tunnel=@{pid=$tunnel.Id;started_ticks=$tunnel.StartTime.ToUniversalTime().Ticks} } | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $shareRoot 'processes.json') -Encoding utf8
Write-Output "Public preview server PID: $($server.Id); Cloudflare PID: $($tunnel.Id)"
Write-Output 'Read .runtime/share/tunnel.stderr.log for the public URL.'
