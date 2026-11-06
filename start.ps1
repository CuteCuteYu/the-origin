# ============================================================
#  "Beneath the Faint Light" - One-Click Launcher
#  Starts the FastAPI backend (port 8000) and the Vite
#  frontend (port 5173), then opens the browser.
#
#  Usage (keep this file in the project root, e.g. code\):
#    powershell -ExecutionPolicy Bypass -File .\start.ps1
#  or: right-click this file -> "Run with PowerShell"
#
#  NOTE: This script is ASCII-only on purpose (no CJK characters),
#  so it can be parsed correctly no matter which code page the
#  console uses. All paths are resolved from $PSScriptRoot.
# ============================================================

$host.UI.RawUI.WindowTitle = "VigaNex Launcher"

$root     = $PSScriptRoot
$backend  = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"

Write-Host "=============================================="
Write-Host " VigaNex Game - One-Click Launcher"
Write-Host " project root: $root"
Write-Host "=============================================="

# ---------- sanity checks ----------
$problems = $false

if (-not (Test-Path (Join-Path $backend "main.py"))) {
    Write-Host "[ERROR] backend\main.py not found. Keep this script in the project root (code\)." -ForegroundColor Red
    $problems = $true
}
if (-not (Test-Path (Join-Path $frontend "package.json"))) {
    Write-Host "[ERROR] frontend\package.json not found. Keep this script in the project root (code\)." -ForegroundColor Red
    $problems = $true
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] 'uv' is not in PATH. Install it first: https://docs.astral.sh/uv/" -ForegroundColor Red
    $problems = $true
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] 'npm' is not in PATH. Install Node.js first: https://nodejs.org/" -ForegroundColor Red
    $problems = $true
}
if ($problems) {
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not (Test-Path Env:OPENAI_API_KEY)) {
    Write-Host "[WARN] OPENAI_API_KEY is not set in this session."
    Write-Host "       The game can still start, but NPC chat will fail until the key is configured."
    Write-Host "       See README - Quick Start - step 1 (set the environment variable, then reopen terminals)."
}

# ---------- helpers ----------
function Test-PortOpen([int]$Port) {
    $client = $null
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $client.Connect("127.0.0.1", $Port)
        return $true
    } catch {
        return $false
    } finally {
        if ($client) { $client.Close() }
    }
}

function Wait-Port([int]$Port, [int]$Seconds) {
    $loops = $Seconds * 2
    for ($i = 0; $i -lt $loops; $i++) {
        if (Test-PortOpen $Port) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

# ---------- first-time dependency install ----------
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "[SETUP] frontend\node_modules not found. Running 'npm install' (first time only, please wait)..."
    Start-Process -FilePath "powershell.exe" -WorkingDirectory $frontend `
        -ArgumentList "-NoProfile", "-Command", "npm install" -Wait
    if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
        Write-Host "[ERROR] 'npm install' failed. Please run it manually inside the frontend folder." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}
# backend: 'uv run' below auto-creates .venv and syncs dependencies when missing

# ---------- backend ----------
Write-Host ""
Write-Host "[1/3] Backend (FastAPI, port 8000)"
if (Test-PortOpen 8000) {
    Write-Host "      Port 8000 is already in use - assuming the backend is already running." -ForegroundColor Yellow
} else {
    Start-Process -FilePath "powershell.exe" -WorkingDirectory $backend `
        -ArgumentList "-NoProfile", "-NoExit", "-Command", "uv run python -m uvicorn main:app --port 8000"
    if (Wait-Port 8000 60) {
        Write-Host "      Backend is up: http://127.0.0.1:8000" -ForegroundColor Green
    } else {
        Write-Host "      [WARN] Backend did not open port 8000 within 60s." -ForegroundColor Yellow
        Write-Host "             Check the backend window for errors (the very first run may need extra time)."
    }
}

# ---------- frontend ----------
Write-Host "[2/3] Frontend (Vite dev server, port 5173)"
if (Test-PortOpen 5173) {
    Write-Host "      Port 5173 is already in use - assuming the frontend is already running." -ForegroundColor Yellow
} else {
    Start-Process -FilePath "powershell.exe" -WorkingDirectory $frontend `
        -ArgumentList "-NoProfile", "-NoExit", "-Command", "npm run dev"
    if (Wait-Port 5173 30) {
        Write-Host "      Frontend is up: http://localhost:5173" -ForegroundColor Green
    } else {
        Write-Host "      [WARN] Frontend did not open port 5173 within 30s. Check its window for errors." -ForegroundColor Yellow
    }
}

# ---------- open the game ----------
Write-Host "[3/3] Opening the game in your default browser..."
Start-Process "http://localhost:5173"
Write-Host "      AI frontend (autonomous): http://127.0.0.1:8000/ai/" -ForegroundColor Cyan

Write-Host ""
Write-Host "=============================================="
Write-Host " Done. Two new windows have been opened:"
Write-Host "   - Backend  (FastAPI  - port 8000)"
Write-Host "   - Frontend (Vite dev - port 5173)"
Write-Host ""
Write-Host " AI auto-play UI is served by the backend:"
Write-Host "   http://127.0.0.1:8000/ai/"
Write-Host ""
Write-Host " To STOP the game: close those two windows,"
Write-Host " or press Ctrl+C inside each of them."
Write-Host " This launcher window can be closed now."
Write-Host "=============================================="
