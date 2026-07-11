# Adds a Windows Firewall inbound allow rule so your iPhone can reach the agent over
# Tailscale. Firewall changes need admin, so this self-elevates (one UAC prompt).
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\allow-firewall.ps1
param([string]$ExePath)

$exe = if ($ExePath) { $ExePath } else { Join-Path $env:LOCALAPPDATA "MoRemotePersonal\app\MoRemotePersonal.exe" }

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
  Write-Host "Requesting administrator rights to add the firewall rule (approve the UAC prompt)..." -ForegroundColor Yellow
  Start-Process powershell -Verb RunAs -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"", "`"$exe`""
  ) -Wait
  return
}

# Admin from here on.
Remove-NetFirewallRule -DisplayName "Mo Remote Personal" -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName "Mo Remote Personal" `
  -Direction Inbound -Action Allow -Program $exe -Profile Any `
  -Description "Allow iPhone to reach Mo Remote Personal over Tailscale" | Out-Null
Write-Host "Firewall inbound rule added for: $exe" -ForegroundColor Green
