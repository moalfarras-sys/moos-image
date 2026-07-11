# Installs the built app to %LOCALAPPDATA%\MoRemotePersonal\app, adds a Start Menu
# shortcut, enables start-with-Windows, and launches it. No admin rights required.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\install.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist"
$exeName = "MoRemotePersonal.exe"

if (-not (Test-Path (Join-Path $dist $exeName))) {
  Write-Host "==> No build found, building first..." -ForegroundColor Yellow
  & (Join-Path $PSScriptRoot "build.ps1")
}

# Validate the build output before touching the system.
$exeSrc = Join-Path $dist $exeName
if (-not (Test-Path $exeSrc -PathType Leaf) -or (Get-Item $exeSrc).Length -eq 0) {
  throw "Build output is missing or empty: $exeSrc. Run scripts\build.ps1 and check for errors."
}

$dest = Join-Path $env:LOCALAPPDATA "MoRemotePersonal\app"

Write-Host "==> Stopping any running instance" -ForegroundColor Cyan
Stop-Process -Name "MoRemotePersonal" -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 600

Write-Host "==> Copying to $dest" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item (Join-Path $dist "*") $dest -Recurse -Force
$exe = Join-Path $dest $exeName

Write-Host "==> Creating shortcuts" -ForegroundColor Cyan
$iconFile = Join-Path $dest "app.ico"
$iconLoc = if (Test-Path $iconFile) { "$iconFile,0" } else { "$exe,0" }
$ws = New-Object -ComObject WScript.Shell
foreach ($loc in @([Environment]::GetFolderPath("Programs"), [Environment]::GetFolderPath("Desktop"))) {
  $lnk = $ws.CreateShortcut((Join-Path $loc "Mo Remote.lnk"))
  $lnk.TargetPath = $exe
  $lnk.WorkingDirectory = $dest
  $lnk.IconLocation = $iconLoc
  $lnk.Save()
}

Write-Host "==> Enabling start-with-Windows" -ForegroundColor Cyan
$run = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
Set-ItemProperty -Path $run -Name "MoRemotePersonal" -Value "`"$exe`""

Write-Host "==> Allowing the app through Windows Firewall (approve the UAC prompt)" -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "allow-firewall.ps1") -ExePath $exe

Write-Host "==> Launching" -ForegroundColor Cyan
Start-Process $exe

Write-Host ""
Write-Host "Installed and running. Look for the tray icon near the clock." -ForegroundColor Green
Write-Host "Right-click the tray icon -> 'Copy access URL', then open that URL on your iPhone."
