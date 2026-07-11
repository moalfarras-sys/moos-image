# Removes the installed app, the Start Menu shortcut, and the start-with-Windows entry.
# Your PIN/settings under %LOCALAPPDATA%\MoRemotePersonal are kept unless you pass -Purge.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\uninstall.ps1 [-Purge]
param([switch]$Purge)
$ErrorActionPreference = "SilentlyContinue"

Write-Host "==> Stopping app" -ForegroundColor Cyan
Stop-Process -Name "MoRemotePersonal" -Force
Start-Sleep -Milliseconds 500

Write-Host "==> Removing start-with-Windows entry" -ForegroundColor Cyan
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "MoRemotePersonal"

Write-Host "==> Removing Start Menu shortcut" -ForegroundColor Cyan
Remove-Item (Join-Path ([Environment]::GetFolderPath("Programs")) "Mo Remote Personal.lnk") -Force

$base = Join-Path $env:LOCALAPPDATA "MoRemotePersonal"
Write-Host "==> Removing app files" -ForegroundColor Cyan
Remove-Item (Join-Path $base "app") -Recurse -Force

if ($Purge) {
  Write-Host "==> Purging settings + PIN" -ForegroundColor Yellow
  Remove-Item $base -Recurse -Force
} else {
  Write-Host "Settings/PIN kept at $base (run with -Purge to delete them)."
}
Write-Host "Done." -ForegroundColor Green
