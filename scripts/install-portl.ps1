# Portl CLI Docker Wrapper Installer for Windows
# This script installs a lightweight wrapper that runs portl via Docker

param(
    [string]$Image = "ghcr.io/hebaghazali/portl:latest"
)

# Configuration
$RegistryRepo = if ($env:PORTL_REGISTRY) { $env:PORTL_REGISTRY } else { "ghcr.io/hebaghazali/portl" }
$DefaultImage = "$RegistryRepo:latest"
$Image = if ($env:PORTL_IMAGE) { $env:PORTL_IMAGE } else { $Image }
$InstallDir = "$env:USERPROFILE\.local\bin"
$WrapperPath = "$InstallDir\portl.bat"

# Helper functions
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# Check if Docker is installed and running
function Test-Docker {
    try {
        $null = Get-Command docker -ErrorAction Stop
    }
    catch {
        Write-Error "Docker is not installed. Please install Docker Desktop first."
        Write-Info "Visit: https://docs.docker.com/desktop/windows/install/"
        exit 1
    }

    try {
        $null = docker info 2>$null
    }
    catch {
        Write-Error "Docker is not running. Please start Docker Desktop first."
        exit 1
    }
}

# Create install directory if it doesn't exist
function New-InstallDirectory {
    if (-not (Test-Path $InstallDir)) {
        Write-Info "Creating directory: $InstallDir"
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }
}

# Create the wrapper script
function New-Wrapper {
    Write-Info "Creating portl wrapper script..."
    
    $WrapperContent = @"
@echo off
REM Portl CLI Docker Wrapper for Windows
REM This script runs portl via Docker with proper volume mounting and environment handling

set IMAGE=$Image
set WORK_DIR=%CD%

REM Check if we're in a TTY (interactive)
if "%TERM%"=="cygwin" (
    set TTY_FLAG=-it
) else if "%TERM%"=="xterm" (
    set TTY_FLAG=-it
) else (
    set TTY_FLAG=
)

REM Build Docker run command
set DOCKER_CMD=docker run --rm %TTY_FLAG%

REM Mount current directory as work directory
set DOCKER_CMD=%DOCKER_CMD% -v "%WORK_DIR%:/work" -w /work

REM Pass through PORTL_* environment variables
for /f "tokens=1 delims==" %%i in ('set PORTL_ 2^>nul') do (
    set DOCKER_CMD=!DOCKER_CMD! -e %%i
)

REM Add host networking for localhost access (useful for local databases)
set DOCKER_CMD=%DOCKER_CMD% --add-host host.docker.internal:host-gateway

REM Execute the command
%DOCKER_CMD% %IMAGE% %*
"@

    $WrapperContent | Out-File -FilePath $WrapperPath -Encoding ASCII
}

# Test the installation
function Test-Installation {
    Write-Info "Testing installation..."
    
    try {
        & $WrapperPath --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Installation test passed!"
        } else {
            Write-Warning "Installation test failed, but wrapper was created."
            Write-Info "You may need to pull the Docker image manually:"
            Write-Info "  docker pull $Image"
        }
    }
    catch {
        Write-Warning "Installation test failed, but wrapper was created."
        Write-Info "You may need to pull the Docker image manually:"
        Write-Info "  docker pull $Image"
    }
}

# Check PATH configuration
function Test-Path {
    $CurrentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($CurrentPath -notlike "*$InstallDir*") {
        Write-Warning "$InstallDir is not in your PATH."
        Write-Info "Adding $InstallDir to your PATH..."
        
        $NewPath = if ($CurrentPath) { "$CurrentPath;$InstallDir" } else { $InstallDir }
        [Environment]::SetEnvironmentVariable("PATH", $NewPath, "User")
        
        Write-Success "Added $InstallDir to your PATH."
        Write-Info "You may need to restart your terminal for the changes to take effect."
    } else {
        Write-Success "$InstallDir is already in your PATH."
    }
}

# Main installation process
function Install-Portl {
    Write-Info "Installing Portl CLI Docker wrapper..."
    Write-Info "Image: $Image"
    
    Test-Docker
    New-InstallDirectory
    New-Wrapper
    Test-Installation
    Test-Path
    
    Write-Success "Portl CLI wrapper installed successfully!"
    Write-Info "You can now run: portl --help"
    Write-Info "To update the image, run: docker pull $Image"
}

# Run installation
Install-Portl
