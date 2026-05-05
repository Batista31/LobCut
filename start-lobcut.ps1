param(
    [switch]$NoElectron,
    [switch]$NoDashboard,
    [switch]$WithOpenClaw,
    [switch]$NoBuild,
    [switch]$Rebuild,
    [switch]$Logs,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "    $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "    $Message" -ForegroundColor Yellow
}

function Test-Command {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-CommandPath {
    param([string]$Name)
    return (Get-Command $Name -ErrorAction Stop).Source
}

function Wait-ForDocker {
    param([int]$TimeoutSeconds = 120)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            docker info *> $null
            return $true
        }
        catch {
            Start-Sleep -Seconds 2
        }
    } while ((Get-Date) -lt $deadline)

    return $false
}

function Wait-ForHttp {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 90
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5 *> $null
            return $true
        }
        catch {
            Start-Sleep -Seconds 2
        }
    } while ((Get-Date) -lt $deadline)

    return $false
}

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "LobCut launcher" -ForegroundColor Magenta
Write-Host "Project: $ProjectRoot"

if (-not (Test-Path (Join-Path $ProjectRoot "docker-compose.yml"))) {
    throw "docker-compose.yml was not found. Run this script from the LobCut project folder."
}

if ($Stop) {
    Write-Step "Stopping LobCut services"
    docker compose --profile dev --profile openclaw down
    Write-Ok "Docker services stopped."
    exit 0
}

Write-Step "Checking required tools"
if (-not (Test-Command "docker")) {
    throw "Docker was not found. Install Docker Desktop, start it once, then run this script again."
}
Write-Ok "Docker command is available."

if (-not (Test-Command "npm.cmd")) {
    throw "Node.js/npm was not found. Install Node.js 20 or newer, then run this script again."
}
$npmCommand = Get-CommandPath "npm.cmd"
Write-Ok "npm is available."

Write-Step "Preparing local folders"
$folders = @(
    "input",
    "input/images",
    "input/videos",
    "output",
    "data",
    "logs",
    "temp"
)
foreach ($folder in $folders) {
    New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot $folder) *> $null
}
Write-Ok "Input, output, data, logs, and temp folders are ready."

if (-not (Test-Path (Join-Path $ProjectRoot ".env"))) {
    if (Test-Path (Join-Path $ProjectRoot ".env.example")) {
        Copy-Item -Path (Join-Path $ProjectRoot ".env.example") -Destination (Join-Path $ProjectRoot ".env")
        Write-Warn ".env was missing, so I created one from .env.example. Add your API keys there when needed."
    }
    else {
        New-Item -ItemType File -Path (Join-Path $ProjectRoot ".env") *> $null
        Write-Warn ".env was missing, so I created an empty one. Add your API keys there when needed."
    }
}
else {
    Write-Ok ".env exists."
}

Write-Step "Starting Docker Desktop if needed"
if (-not (Wait-ForDocker -TimeoutSeconds 5)) {
    $dockerDesktop = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerDesktop) {
        Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
        Write-Warn "Docker Desktop was not running. Starting it now..."
    }
    else {
        Write-Warn "Docker Desktop executable was not found in the default location."
    }
}

if (-not (Wait-ForDocker -TimeoutSeconds 120)) {
    throw "Docker is still not responding. Open Docker Desktop, wait until it says it is running, then run this script again."
}
Write-Ok "Docker is running."

Write-Step "Preparing Docker path mappings"
$projectRootForward = $ProjectRoot.Replace("\", "/")
$defaultWatchInput = (Join-Path $ProjectRoot "input").Replace("\", "/")
$requiredMappings = @(
    "$ProjectRoot=/app",
    "$projectRootForward=/app"
)

$existingMappings = @()
if (-not [string]::IsNullOrWhiteSpace($env:WATCH_PATH_MAPPINGS)) {
    $existingMappings = $env:WATCH_PATH_MAPPINGS.Split(";") |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
}

$mergedMappings = @()
$mergedMappings += $requiredMappings
$mergedMappings += $existingMappings
$env:WATCH_PATH_MAPPINGS = ($mergedMappings | Select-Object -Unique) -join ";"

if ([string]::IsNullOrWhiteSpace($env:WATCH_HOST_INPUT)) {
    $env:WATCH_HOST_INPUT = $defaultWatchInput
}

Write-Ok "Project watchers can resolve $ProjectRoot to /app inside Docker."
Write-Ok "Default extra watch mount: $env:WATCH_HOST_INPUT -> /watch/user-input"

if (-not $NoBuild) {
    Write-Step "Building dashboard files for the desktop app"
    Push-Location (Join-Path $ProjectRoot "dashboard")
    try {
        $esbuildBinary = Join-Path (Get-Location) "node_modules\@esbuild\win32-x64\esbuild.exe"
        if (-not (Test-Path "node_modules")) {
            & $npmCommand install
            if ($LASTEXITCODE -ne 0) {
                throw "Dashboard dependency install failed."
            }
        }
        if (Test-Path $esbuildBinary) {
            $env:ESBUILD_BINARY_PATH = $esbuildBinary
        }
        & $npmCommand run build
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "Dashboard production build failed. Continuing because the live dashboard runs at http://localhost:3000."
        }
        else {
            Write-Ok "Dashboard build is ready."
        }
    }
    finally {
        Pop-Location
    }
}

Write-Step "Starting LobCut containers"
$composeArgs = @("compose")
if (-not $NoDashboard) {
    $composeArgs += @("--profile", "dev")
}
if ($WithOpenClaw) {
    $composeArgs += @("--profile", "openclaw")
}
$composeArgs += @("up", "-d")
if ($Rebuild) {
    $composeArgs += @("--build", "--force-recreate")
}
elseif (-not $NoBuild) {
    $composeArgs += @("--build", "--force-recreate")
}

& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed to start LobCut."
}
Write-Ok "Containers are starting."

Write-Step "Waiting for the backend"
if (Wait-ForHttp -Url "http://localhost:8000/health" -TimeoutSeconds 120) {
    Write-Ok "Backend is healthy at http://localhost:8000/health"
}
else {
    Write-Warn "Backend did not answer before the timeout. Check logs with: docker compose logs api"
}

if (-not $NoDashboard) {
    Write-Step "Waiting for the dashboard"
    if (Wait-ForHttp -Url "http://localhost:3000" -TimeoutSeconds 120) {
        Write-Ok "Dashboard is ready at http://localhost:3000"
    }
    else {
        Write-Warn "Dashboard did not answer before the timeout. Check logs with: docker compose logs dashboard"
    }
}

if (-not $NoElectron) {
    Write-Step "Starting the desktop app"
    Get-Process -Name "electron" -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -like "$ProjectRoot\electron-app\*" } |
        Stop-Process -Force

    Push-Location (Join-Path $ProjectRoot "electron-app")
    try {
        if (-not (Test-Path "node_modules")) {
            & $npmCommand install
            if ($LASTEXITCODE -ne 0) {
                throw "Electron dependency install failed."
            }
        }

        $env:LOBCUT_SKIP_DOCKER = "1"
        $env:LOBCUT_DASHBOARD_URL = "http://localhost:3000"
        Start-Process -FilePath $npmCommand -ArgumentList "start" -WorkingDirectory (Get-Location)
        Write-Ok "Electron app launched."
    }
    finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "LobCut is starting up." -ForegroundColor Green
if (-not $NoDashboard) {
    Write-Host "Dashboard: http://localhost:3000"
}
Write-Host "API:       http://localhost:8000"
Write-Host "Drop images into: $ProjectRoot\input\images"
Write-Host ""
Write-Host "Useful commands:"
Write-Host "  .\start-lobcut.ps1 -Stop"
Write-Host "  docker compose logs -f"

if ($Logs) {
    Write-Host ""
    Write-Host "Following LobCut service logs. Press Ctrl+C to stop viewing logs." -ForegroundColor Cyan
    docker compose logs -f orchestrator api dashboard
}
