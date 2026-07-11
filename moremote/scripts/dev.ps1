# Dev mode: runs the agent (localhost:8765) + the Vite dev server (localhost:5173)
# in two windows. The dev server proxies /api and /ws to the agent.
# Open http://localhost:5173 in a browser (or from your phone over Tailscale: use the agent URL).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Push-Location (Join-Path $root "controller")
if (-not (Test-Path "node_modules")) { npm install }
npm run gen-icons
Pop-Location

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\agent'; Write-Host 'AGENT (http://localhost:8765)' -ForegroundColor Green; dotnet run"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\controller'; Write-Host 'DEV UI (http://localhost:5173)' -ForegroundColor Green; npm run dev"

Write-Host "Agent:  http://localhost:8765"
Write-Host "Dev UI: http://localhost:5173  (talks to the agent via proxy)"
