param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = if ($env:TIANQIONG_DATA_DIR) { [IO.Path]::GetFullPath($env:TIANQIONG_DATA_DIR) } else { Join-Path $env:LOCALAPPDATA 'TianqiongDemo' }
$webUrl = 'http://127.0.0.1:5173'
$logPath = Join-Path $runtimeRoot 'desktop-launcher.log'
$startupLock = New-Object System.Threading.Mutex($false, 'Local\TianhengSKYDOME.DesktopLauncher')
$hasLock = $false
function Test-SkydomeReady {
    try {
        $recordPath = Join-Path $runtimeRoot 'processes.json'
        if (-not (Test-Path -LiteralPath $recordPath)) { return $false }
        $record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($record.project -ne $projectRoot) { return $false }
        # Windows PowerShell 5.1 otherwise decodes charset-less UTF-8 responses as ANSI.
        $systemResponse = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/v1/system/status' -UseBasicParsing -TimeoutSec 3
        $system = [Text.Encoding]::UTF8.GetString($systemResponse.RawContentStream.ToArray()) | ConvertFrom-Json
        $web = Invoke-WebRequest -Uri $webUrl -UseBasicParsing -TimeoutSec 3
        $html = [Text.Encoding]::UTF8.GetString($web.RawContentStream.ToArray())
        return ($system.app_name -eq '天亨 · 空天地人智能安全协同平台' -and $system.database -eq 'connected' -and $web.StatusCode -eq 200 -and $html -match '<title>天亨')
    } catch { return $false }
}
try {
    try { $hasLock = $startupLock.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $hasLock = $true }
    if (-not $hasLock) { exit 0 }
    New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
    $reused = Test-SkydomeReady
    if (-not $reused) {
        & (Join-Path $PSScriptRoot 'start.ps1') | Out-File -LiteralPath $logPath -Encoding utf8 -Append
        if (-not (Test-SkydomeReady)) { throw '服务尚未就绪，请检查后端和前端日志。若仅部分服务在运行，请运行 scripts\stop.ps1 后重试。' }
    }
    $result = if ($reused) { 'Reused existing services' } else { 'Started services' }
    Add-Content -LiteralPath $logPath -Encoding utf8 -Value ("{0} {1}: {2}" -f (Get-Date -Format o), $result, $webUrl)
    if (-not $NoBrowser) { Start-Process -FilePath $webUrl }
    Write-Output "$result. $webUrl"
} catch {
    $message = "启动失败：$($_.Exception.Message)`r`n`r`n日志：$logPath`r`n项目：$projectRoot"
    try { Add-Content -LiteralPath $logPath -Encoding utf8 -Value $message } catch { }
    if (-not $NoBrowser) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show($message, '天亨 SKYDOME 启动提示', 'OK', 'Error') | Out-Null
    }
    Write-Error $message -ErrorAction Continue
    exit 1
} finally {
    if ($hasLock) { $startupLock.ReleaseMutex() }
    $startupLock.Dispose()
}
