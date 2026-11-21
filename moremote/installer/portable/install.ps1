# Portable installer for Mo Remote (bundled next to the 'app' folder).
# Installs to %LOCALAPPDATA%, adds Start-Menu + Desktop shortcuts, enables start-with-Windows,
# allows the app through the firewall, and launches it. No admin needed (except a one-time
# UAC prompt for the firewall rule).
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$appSrc = Join-Path $here "app"
$exeName = "MoRemotePersonal.exe"

if (-not (Test-Path (Join-Path $appSrc $exeName))) {
  Write-Host "ERROR: the 'app' folder is missing next to this installer." -ForegroundColor Red
  Read-Host "Press Enter to close"; exit 1
}

Write-Host "Installing Mawj..." -ForegroundColor Cyan
Stop-Process -Name "MoRemotePersonal" -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 700

$dest = Join-Path $env:LOCALAPPDATA "MoRemotePersonal\app"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item (Join-Path $appSrc "*") $dest -Recurse -Force
$exe = Join-Path $dest $exeName

Write-Host "Creating shortcuts..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "mawj-shortcuts.ps1") -Mode Install -Executable $exe

Write-Host "Enabling start-with-Windows..." -ForegroundColor Cyan
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "MoRemotePersonal" -Value "`"$exe`""

Write-Host "Allowing through Windows Firewall (approve the UAC prompt)..." -ForegroundColor Cyan
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$fw = "Remove-NetFirewallRule -DisplayName 'Mo Remote Personal' -ErrorAction SilentlyContinue; New-NetFirewallRule -DisplayName 'Mo Remote Personal' -Direction Inbound -Action Allow -Program '$exe' -Profile Any | Out-Null"
try {
  if ($isAdmin) { Invoke-Expression $fw }
  else { Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile", "-Command", $fw -Wait }
} catch { Write-Host "  (firewall step skipped — you can run allow-firewall later)" -ForegroundColor Yellow }

Start-Process $exe
Write-Host ""
Write-Host "Done! Mawj is running (look for the tray icon near the clock)." -ForegroundColor Green
Write-Host "Right-click the tray icon -> 'Copy access URL', then open it in Safari on your iPhone." -ForegroundColor Green
Read-Host "Press Enter to close"
