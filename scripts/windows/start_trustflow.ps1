param(
    [int]$ApiPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$ForceBackend
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Set-Location $Root

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Administrator permission is required so FastAPI can start WSL/Mininet. Requesting elevation..."
    $elevatedArgs = @("-ExecutionPolicy", "Bypass", "-File", $PSCommandPath,
        "-ApiPort", "$ApiPort", "-FrontendPort", "$FrontendPort")
    if ($ForceBackend) { $elevatedArgs += "-ForceBackend" }
    Start-Process powershell.exe -Verb RunAs -WorkingDirectory $Root -ArgumentList $elevatedArgs | Out-Null
    exit 0
}

function Test-TrustFlowApi {
    try {
        $health = Invoke-RestMethod "http://127.0.0.1:$ApiPort/api/health" -TimeoutSec 3
        $scenarios = Invoke-RestMethod "http://127.0.0.1:$ApiPort/api/scenarios" -TimeoutSec 3
        $live = Invoke-RestMethod "http://127.0.0.1:$ApiPort/api/live/preflight" -TimeoutSec 5
        return ($health.ok -eq $true -and $scenarios.scenarios.Count -gt 0 -and $live.ok -eq $true)
    } catch {
        return $false
    }
}

if (Test-TrustFlowApi) {
    Write-Host "TrustFlow backend is already running on http://127.0.0.1:$ApiPort"
} else {
    $listeners = @(Get-NetTCPConnection -LocalPort $ApiPort -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
    if ($listeners.Count -gt 0 -and -not $ForceBackend) {
        $details = $listeners | ForEach-Object {
            $p = Get-Process -Id $_ -ErrorAction SilentlyContinue
            if ($p) { "$($p.ProcessName) (PID $_)" } else { "PID $_" }
        }
        throw "Port $ApiPort is occupied by $($details -join ', ') and is not the TrustFlow API. Stop that service or rerun with -ForceBackend after verifying it is safe."
    }
    if ($ForceBackend) {
        foreach ($pid in $listeners) {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Milliseconds 500
    }

    $python = Join-Path $Root ".venv/Scripts/python.exe"
    if (-not (Test-Path $python)) { throw "Missing $python. Create the Windows virtual environment first." }
    $backendLog = Join-Path $Root "logs-backend.out.log"
    $backendErr = Join-Path $Root "logs-backend.err.log"
    Start-Process -FilePath $python -WorkingDirectory $Root `
        -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "$ApiPort") `
        -RedirectStandardOutput $backendLog -RedirectStandardError $backendErr -WindowStyle Hidden

    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 500
        if (Test-TrustFlowApi) { break }
    }
    if (-not (Test-TrustFlowApi)) {
        throw "TrustFlow backend did not become ready. Check $backendErr."
    }
    Write-Host "TrustFlow backend started on http://127.0.0.1:$ApiPort"
}

$frontendUrl = "http://127.0.0.1:$FrontendPort"
try {
    Invoke-WebRequest $frontendUrl -UseBasicParsing -TimeoutSec 2 | Out-Null
    Write-Host "Frontend is already running on $frontendUrl"
} catch {
    # Prefer npm.cmd so PowerShell execution policy does not block npm.ps1.
    $npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
    if (-not $npm) { throw "npm was not found. Install Node.js before starting the frontend." }
    $frontendDir = Join-Path $Root "frontend"
    # Launch through cmd.exe so npm.cmd and its child Vite process remain alive
    # after this PowerShell launcher exits.
    Start-Process -FilePath "cmd.exe" -WorkingDirectory $frontendDir `
        -ArgumentList @("/c", "npm.cmd run dev -- --host 127.0.0.1 --port $FrontendPort") `
        -WindowStyle Hidden
    $frontendReady = $false
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            Invoke-WebRequest $frontendUrl -UseBasicParsing -TimeoutSec 2 | Out-Null
            $frontendReady = $true
            break
        } catch { }
    }
    if (-not $frontendReady) {
        throw "Frontend did not become ready. Run 'npm.cmd run dev' in $frontendDir and inspect the Vite output."
    }
    Write-Host "Frontend starting at $frontendUrl"
}

Write-Host "Open $frontendUrl"
Write-Host "For real WSL data, start scripts/wsl/start_live.sh separately after this script reports the backend is ready."
