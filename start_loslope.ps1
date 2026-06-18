<#
  LoSLOPE launcher
  ----------------
  Starts the backend (if it isn't already running) and a Cloudflare quick
  tunnel, then prints the current public dashboard URL. Keep the window open;
  press Ctrl+C to stop the tunnel.

  Run it:  right-click > "Run with PowerShell", or from a terminal:
           powershell -ExecutionPolicy Bypass -File .\start_loslope.ps1
#>
$ErrorActionPreference = "Stop"
$root   = $PSScriptRoot
$python = Join-Path $root "backend\.venv\Scripts\python.exe"
$cf     = Join-Path $root "tools\cloudflared.exe"
$dist   = Join-Path $root "frontend\dist"

Write-Host "=== LoSLOPE launcher ===" -ForegroundColor Cyan

if (-not (Test-Path $dist)) {
  Write-Host "WARNING: frontend\dist not found - the dashboard UI won't be served." -ForegroundColor Yellow
  Write-Host "         Build it once:  cd frontend ; npm run build" -ForegroundColor Yellow
}

# 1) Backend on :8000 (skip if already listening) -----------------------------
$up = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($up) {
  Write-Host "Backend already running on :8000" -ForegroundColor Green
} else {
  Write-Host "Starting backend..." -ForegroundColor Cyan
  Start-Process -FilePath $python `
    -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000" `
    -WorkingDirectory (Join-Path $root "backend") -WindowStyle Minimized | Out-Null
  $deadline = (Get-Date).AddSeconds(40)
  do {
    Start-Sleep -Seconds 1
    $up = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
  } until ($up -or (Get-Date) -gt $deadline)
  if ($up) { Write-Host "Backend is up." -ForegroundColor Green }
  else { Write-Host "Backend did not start in time - check the backend window." -ForegroundColor Red; exit 1 }
}

# 2) Cloudflare quick tunnel ---------------------------------------------------
$log = Join-Path $env:TEMP "loslope_tunnel.log"
Remove-Item $log,"$log.out" -ErrorAction SilentlyContinue
Write-Host "Starting Cloudflare tunnel..." -ForegroundColor Cyan
$proc = Start-Process -FilePath $cf `
  -ArgumentList "tunnel","--url","http://localhost:8000" `
  -RedirectStandardError $log -RedirectStandardOutput "$log.out" `
  -PassThru -WindowStyle Hidden

# 3) Wait for and print the public URL ----------------------------------------
$url = $null
$deadline = (Get-Date).AddSeconds(30)
do {
  Start-Sleep -Seconds 1
  $m = Select-String -Path $log,"$log.out" -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" `
        -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($m) { $url = $m.Matches[0].Value }
} until ($url -or (Get-Date) -gt $deadline)

Write-Host ""
if ($url) {
  Write-Host "=======================================================" -ForegroundColor Green
  Write-Host "  LoSLOPE dashboard is ONLINE at:"                       -ForegroundColor Green
  Write-Host "  $url"                                                  -ForegroundColor White
  Write-Host "=======================================================" -ForegroundColor Green
  Write-Host "Keep this window open. Press Ctrl+C to stop the tunnel."
} else {
  Write-Host "Could not detect the tunnel URL. Check $log" -ForegroundColor Red
}

# 4) Block until the tunnel exits (Ctrl+C) ------------------------------------
Wait-Process -Id $proc.Id
