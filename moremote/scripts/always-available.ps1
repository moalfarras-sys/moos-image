# Keeps the PC awake and unlocked so Mo Remote stays reachable even when you're away.
# Run once. No admin needed for the power settings.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\always-available.ps1
$ErrorActionPreference = "SilentlyContinue"

Write-Host "==> Preventing sleep / display-off / screensaver..." -ForegroundColor Cyan
powercfg /change monitor-timeout-ac 0
powercfg /change monitor-timeout-dc 0
powercfg /change standby-timeout-ac 0
powercfg /change standby-timeout-dc 0
powercfg /change hibernate-timeout-ac 0
powercfg /change hibernate-timeout-dc 0

Write-Host "==> Not requiring a password when the display wakes..." -ForegroundColor Cyan
powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_NONE CONSOLELOCK 0
powercfg /SETDCVALUEINDEX SCHEME_CURRENT SUB_NONE CONSOLELOCK 0
powercfg /SETACTIVE SCHEME_CURRENT

Write-Host "==> Disabling the screensaver..." -ForegroundColor Cyan
Set-ItemProperty 'HKCU:\Control Panel\Desktop' -Name ScreenSaveActive -Value 0 -ErrorAction SilentlyContinue
Set-ItemProperty 'HKCU:\Control Panel\Desktop' -Name ScreenSaverIsSecure -Value 0 -ErrorAction SilentlyContinue

Write-Host "==> Fully disabling Workstation lock (needs admin once; approve the UAC prompt)..." -ForegroundColor Cyan
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$cmd = "New-Item -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Policies\System' -Force | Out-Null; Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Policies\System' -Name DisableLockWorkstation -Value 1 -Type DWord"
try {
  if ($isAdmin) { Invoke-Expression $cmd }
  else { Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile", "-Command", $cmd -Wait }
} catch { Write-Host "  (skipped lock-disable; idle-lock is already prevented above)" -ForegroundColor Yellow }

Write-Host ""
Write-Host "Done. The PC will stay awake and won't lock while you're away." -ForegroundColor Green
Write-Host ""
Write-Host "To control the PC right after it BOOTS (before any login screen), enable auto sign-in:" -ForegroundColor Yellow
Write-Host "  1) Press Win+R, type:  netplwiz   then press Enter"
Write-Host "  2) Uncheck: 'Users must enter a user name and password to use this computer'"
Write-Host "  3) Apply -> enter your Windows password once."
Write-Host "  Now the PC boots straight to the desktop where Mo Remote is already running,"
Write-Host "  so you can connect from your iPhone without touching the computer."
Write-Host ""
Write-Host "Note: the Windows lock/login screen itself cannot be captured by any normal app"
Write-Host "(Windows security). Auto sign-in above is the supported way to be reachable at boot."
