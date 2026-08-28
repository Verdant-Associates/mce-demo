# Python Environment Setup Script
# This script installs uv, creates a virtual environment, and installs required packages

param(
    [string]$EnvName = "demo_venv",
    [string]$PythonVersion = "3.12"
)

# Set error action preference to stop on errors
$ErrorActionPreference = "Stop"

Write-Host "=== Python Environment Setup Script ===" -ForegroundColor Green
Write-Host "Environment Name: $EnvName" -ForegroundColor Cyan
Write-Host "Python Version: $PythonVersion" -ForegroundColor Cyan
Write-Host ""

# Function to check if a command exists
function Test-CommandExists {
    param($Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

# Function to install uv
function Install-UV {
    Write-Host "Installing uv..." -ForegroundColor Yellow
    
    try {
        # Download and install uv using the official installer
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
        
        # Refresh PATH for current session
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
        
        Write-Host "uv installed successfully!" -ForegroundColor Green
    }
    catch {
        Write-Error "Failed to install uv: $_"
        exit 1
    }
}

# Check if uv is already installed
Write-Host "Checking if uv is installed..." -ForegroundColor Yellow
if (-not (Test-CommandExists "uv")) {
    Write-Host "uv not found. Installing..." -ForegroundColor Yellow
    Install-UV
} else {
    Write-Host "uv is already installed!" -ForegroundColor Green
    # Update uv to latest version
    Write-Host "Updating uv to latest version..." -ForegroundColor Yellow
    uv self update
}

# Verify uv installation
Write-Host "Verifying uv installation..." -ForegroundColor Yellow
try {
    $uvVersion = uv --version
    Write-Host "uv version: $uvVersion" -ForegroundColor Green
}
catch {
    Write-Error "uv installation verification failed: $_"
    exit 1
}

# Remove existing environment if it exists
if (Test-Path $EnvName) {
    Write-Host "Removing existing environment '$EnvName'..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $EnvName
}

# Create virtual environment
Write-Host "Creating virtual environment '$EnvName' with Python $PythonVersion..." -ForegroundColor Yellow
try {
    uv venv $EnvName --python $PythonVersion
    Write-Host "Virtual environment created successfully!" -ForegroundColor Green
}
catch {
    Write-Error "Failed to create virtual environment: $_"
    exit 1
}

# Define your required packages here
# You can modify this array to include your specific packages and versions
$RequiredPackages = @(
	"pandas==3.0.2",
    "polars==1.39.0",
	"seaborn==0.13.2",
	"pyjanitor==0.31.0",
	"pyarrow==21.0.0",
	"great-tables==0.18.0",
	"statsmodels==0.14.5",
	"ipywidgets==8.1.7",
	"nbformat==5.10.4",
	"import-ipynb==0.2",
    "egnyte==0.5.3",
    "plotly==6.8.0",
    "pywin32==312",
    "ipykernel==7.3.0",
    "fastexcel==0.20.2",
    "holidays==0.103",
    "pytz==2026.3.post1"
    # Add more packages as needed
    # "package-name==version"
)

    # "PyMuPDF==1.27.2.3"
# Install packages
Write-Host "Installing required packages..." -ForegroundColor Yellow
Write-Host "Packages to install:" -ForegroundColor Cyan
$RequiredPackages | ForEach-Object { Write-Host "  - $_" -ForegroundColor Cyan }
Write-Host ""

try {
    foreach ($package in $RequiredPackages) {
        Write-Host "Installing $package..." -ForegroundColor Yellow
        uv pip install $package --python $EnvName
    }
    Write-Host "All packages installed successfully!" -ForegroundColor Green
}
catch {
    Write-Error "Failed to install packages: $_"
    exit 1
}

# opendsm is installed separately from GitHub master, not PyPI:
# v1.2.6 on PyPI has a stale test-data download URL/filename that 404s,
# already fixed on master but not yet released.
Write-Host "Installing opendsm from GitHub master..." -ForegroundColor Yellow
try {
    uv pip install "git+https://github.com/opendsm/opendsm.git@master" --python $EnvName
    Write-Host "opendsm installed successfully!" -ForegroundColor Green
}
catch {
    Write-Error "Failed to install opendsm: $_"
    exit 1
}

# Generate requirements.txt for future reference
Write-Host "Generating requirements.txt..." -ForegroundColor Yellow
try {
    uv pip freeze --python $EnvName | Out-File -FilePath "requirements.txt" -Encoding UTF8
    Write-Host "requirements.txt generated successfully!" -ForegroundColor Green
}
catch {
    Write-Warning "Failed to generate requirements.txt: $_"
}

# Display activation instructions
Write-Host ""
Write-Host "=== Setup Complete! ===" -ForegroundColor Green
Write-Host ""
Write-Host "To activate your virtual environment, run:" -ForegroundColor Yellow
Write-Host "  ./$EnvName/Scripts/Activate.ps1" -ForegroundColor White
Write-Host ""
Write-Host "To deactivate the environment later, run:" -ForegroundColor Yellow
Write-Host "  deactivate" -ForegroundColor White
Write-Host ""
Write-Host "To install additional packages in this environment:" -ForegroundColor Yellow
Write-Host "  uv pip install package-name --python $EnvName" -ForegroundColor White
Write-Host ""

# Optional: Activate the environment automatically
# $ActivateChoice = Read-Host "Would you like to activate the environment now? (y/n)"
# if ($ActivateChoice -eq "y" -or $ActivateChoice -eq "Y") {
#     Write-Host "Activating environment..." -ForegroundColor Yellow
#     & "./$EnvName/Scripts/Activate.ps1"
# }
