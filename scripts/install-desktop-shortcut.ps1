$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $PSScriptRoot 'open-skydome.ps1'
$powershellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$shell = New-Object -ComObject WScript.Shell
$desktopPath = $shell.SpecialFolders.Item('Desktop')
if (-not $desktopPath -or -not (Test-Path -LiteralPath $desktopPath -PathType Container)) { throw 'Cannot locate the current Windows desktop.' }
$shortcutPath = Join-Path $desktopPath '天亨 SKYDOME.lnk'
if (Test-Path -LiteralPath $shortcutPath) {
    $existing = $shell.CreateShortcut($shortcutPath)
    if ($existing.Arguments -notlike ('*' + $launcher + '*')) { throw 'A different shortcut already has this name; it was not overwritten.' }
}
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $powershellExe
$shortcut.Arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $launcher + '"'
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = '启动天亨智能安全协同平台并打开浏览器；服务已运行时直接打开。'
$shortcut.IconLocation = (Join-Path $env:SystemRoot 'System32\shell32.dll') + ',13'
$shortcut.WindowStyle = 7
$shortcut.Save()
$check = $shell.CreateShortcut($shortcutPath)
[pscustomobject]@{Shortcut=$shortcutPath; Target=$check.TargetPath; Arguments=$check.Arguments; WorkingDirectory=$check.WorkingDirectory; Exists=(Test-Path -LiteralPath $shortcutPath)} | ConvertTo-Json
