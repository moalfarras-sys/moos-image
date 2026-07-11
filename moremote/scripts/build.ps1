# Builds the PWA + a self-contained Windows app into .\dist
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\build.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# $ErrorActionPreference="Stop" does NOT stop on a failing native exe (npm/dotnet) —
# only $LASTEXITCODE reflects that. This helper makes those failures fatal.
function Assert-LastExit($what) {
  if ($LASTEXITCODE -ne 0) { throw "$what failed (exit $LASTEXITCODE)" }
}

Write-Host "==> Building Mo Remote Personal" -ForegroundColor Cyan

# 1) Frontend (PWA) -> agent\wwwroot, and icons -> agent\app.ico
Push-Location (Join-Path $root "controller")
if (-not (Test-Path "node_modules")) {
  Write-Host "==> npm install" -ForegroundColor Cyan
  npm install; Assert-LastExit "npm install"
}
Write-Host "==> Generating icons from Logo.png" -ForegroundColor Cyan
npm run gen-icons; Assert-LastExit "npm run gen-icons"
Write-Host "==> Building PWA" -ForegroundColor Cyan
npm run build; Assert-LastExit "npm run build"
Pop-Location

# 2) Agent -> self-contained single folder (no .NET install needed to run)
#    NOTE: We publish the Debug configuration on purpose. On Windows 11 with
#    "Smart App Control" enabled, the Release-optimized unsigned binary is blocked,
#    while the Debug-config build runs fine. For a personal, unsigned tool this is the
#    most reliable choice. (If you code-sign the binary, you can switch to Release.)
$out = Join-Path $root "dist"
if (Test-Path $out) { Remove-Item $out -Recurse -Force }
Push-Location (Join-Path $root "agent")
Write-Host "==> Publishing agent (self-contained win-x64)" -ForegroundColor Cyan
dotnet publish -c Debug -o $out; Assert-LastExit "dotnet publish"
Pop-Location

if (-not (Test-Path (Join-Path $out "MoRemotePersonal.exe"))) {
  throw "Publish finished but MoRemotePersonal.exe is missing in $out"
}

Write-Host ""
Write-Host "Build complete." -ForegroundColor Green
Write-Host "Run it:  $out\MoRemotePersonal.exe"
