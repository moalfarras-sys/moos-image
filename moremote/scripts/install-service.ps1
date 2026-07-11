# EXPERIMENTAL: install Mo Remote as a full SYSTEM Windows Service so the phone can see and
# control even the Windows lock / login screen. Requires admin (self-elevates below).
#
# Tradeoffs (you accepted these): there is NO on-screen "control active" banner in service mode,
# and the service runs as LocalSystem. Service mode uses its OWN PIN (SYSTEM profile) — the first
# phone connection will ask you to create it. Remove any time with scripts\uninstall-service.ps1.
$ErrorActionPreference = "Stop"

# --- self-elevate ---
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File","`"$PSCommandPath`""
  return
}

$svc = "MoRemotePersonal"
$exe = Join-Path $env:LOCALAPPDATA "MoRemotePersonal\app\MoRemotePersonal.exe"
if (-not (Test-Path $exe)) { throw "Install the app first (scripts\install.ps1). Not found: $exe" }

Write-Host "==> Removing the normal per-user autostart (avoids duplicates)" -ForegroundColor Cyan
Stop-Process -Name "MoRemotePersonal" -Force -ErrorAction SilentlyContinue
Remove-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name $svc -ErrorAction SilentlyContinue
schtasks /Delete /F /TN "MoRemotePersonal Admin Autostart" 2>$null | Out-Null

Write-Host "==> Creating the service" -ForegroundColor Cyan
sc.exe stop $svc 2>$null | Out-Null
sc.exe delete $svc 2>$null | Out-Null
Start-Sleep -Milliseconds 600
New-Service -Name $svc -BinaryPathName "`"$exe`" --service" -DisplayName "Mo Remote Personal" -StartupType Automatic | Out-Null
sc.exe description $svc "Mo Remote Personal remote-control service (reachable across the lock/login screen)." | Out-Null
sc.exe failure $svc reset= 60 actions= restart/5000/restart/5000/restart/5000 | Out-Null

Write-Host "==> Starting the service" -ForegroundColor Cyan
Start-Service $svc

Write-Host ""
Write-Host "Service installed and started." -ForegroundColor Green
Write-Host "It now captures even the login/lock screen. Note: NO on-screen banner in this mode."
Write-Host "First phone connection in service mode will ask you to create a PIN."
Write-Host "To remove it:  powershell -ExecutionPolicy Bypass -File scripts\uninstall-service.ps1"
