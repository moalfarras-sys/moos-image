# Removes the EXPERIMENTAL Mo Remote SYSTEM service and restores the normal per-user autostart.
# Requires admin (self-elevates below).
$ErrorActionPreference = "SilentlyContinue"

# --- self-elevate ---
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File","`"$PSCommandPath`""
  return
}

$svc = "MoRemotePersonal"
Write-Host "==> Stopping and deleting the service" -ForegroundColor Cyan
sc.exe stop $svc 2>$null | Out-Null
Start-Sleep -Milliseconds 500
sc.exe delete $svc 2>$null | Out-Null

# Kill any leftover SYSTEM worker.
Stop-Process -Name "MoRemotePersonal" -Force -ErrorAction SilentlyContinue

Write-Host "==> Restoring normal per-user autostart" -ForegroundColor Cyan
$exe = Join-Path $env:LOCALAPPDATA "MoRemotePersonal\app\MoRemotePersonal.exe"
if (Test-Path $exe) {
  Set-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name $svc -Value "`"$exe`""
  Start-Process $exe
}

Write-Host ""
Write-Host "Service removed. Back to normal (with the on-screen banner)." -ForegroundColor Green
