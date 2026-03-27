#Requires -RunAsAdministrator

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "    OK: $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "    WARN: $Message" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# 1. Git
# ---------------------------------------------------------------------------
Write-Step "Installing Git..."
$git = Get-Command git -ErrorAction SilentlyContinue
if ($git) {
    Write-Success "Git already installed at $($git.Source)"
} else {
    winget install --id Git.Git --silent --accept-package-agreements --accept-source-agreements
    Write-Success "Git installed"
}

# ---------------------------------------------------------------------------
# 2. CMake
# ---------------------------------------------------------------------------
Write-Step "Installing CMake 3.25+..."
$cmake = Get-Command cmake -ErrorAction SilentlyContinue
if ($cmake) {
    Write-Success "CMake already installed at $($cmake.Source)"
} else {
    winget install --id Kitware.CMake --silent --accept-package-agreements --accept-source-agreements
    Write-Success "CMake installed"
}

# ---------------------------------------------------------------------------
# 3. Visual Studio 2022 Community (Desktop C++ workload)
# ---------------------------------------------------------------------------
Write-Step "Installing Visual Studio 2022 Community with C++ workload..."
$vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vsInstalled = $false
if (Test-Path $vsWhere) {
    $vsPath = & $vsWhere -version "[17,18)" -property installationPath 2>$null
    if ($vsPath) {
        $vsInstalled = $true
        Write-Success "Visual Studio 2022 already installed at $vsPath"
        Write-Step "Ensuring NativeDesktop workload is present..."
        $installer = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\setup.exe"
        & $installer modify `
            --installPath $vsPath `
            --add Microsoft.VisualStudio.Workload.NativeDesktop `
            --includeRecommended `
            --quiet --norestart
        Write-Success "Workload verified/added"
    }
}
if (-not $vsInstalled) {
    winget install --id Microsoft.VisualStudio.2022.Community `
        --silent --accept-package-agreements --accept-source-agreements `
        --override "--add Microsoft.VisualStudio.Workload.NativeDesktop --includeRecommended --quiet --norestart"
    Write-Success "Visual Studio 2022 installed"
}

# ---------------------------------------------------------------------------
# 4. Windows SDK 10.0.26100 (required by WDK and provides kernel32.lib)
# ---------------------------------------------------------------------------
Write-Step "Installing Windows SDK 10.0.26100..."
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkLibDir = "$sdkRoot\Lib\10.0.26100.0"
if (Test-Path $sdkLibDir) {
    Write-Success "Windows SDK 10.0.26100 already installed at $sdkRoot"
} else {
    winget install --id Microsoft.WindowsSDK.10.0.26100 --silent --accept-package-agreements --accept-source-agreements
    Write-Success "Windows SDK 10.0.26100 installed"
}

# ---------------------------------------------------------------------------
# 5. Windows Driver Kit (WDK) 10.0.26100
# ---------------------------------------------------------------------------
Write-Step "Installing Windows Driver Kit 10.0.26100..."
$wdkRoot = $sdkRoot
$wdkIncKm = "$wdkRoot\Include\10.0.26100.0\km"
if (Test-Path $wdkIncKm) {
    Write-Success "WDK 10.0.26100 already installed at $wdkRoot"
} else {
    winget install --id Microsoft.WindowsWDK.10.0.26100 --silent --accept-package-agreements --accept-source-agreements
    Write-Success "WDK 10.0.26100 installed"
}

# ---------------------------------------------------------------------------
# 6. WDK Visual Studio Extension
# ---------------------------------------------------------------------------
Write-Step "Installing WDK Visual Studio extension..."
$vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vsPath = & $vsWhere -version "[17,18)" -property installationPath 2>$null
$vsixInstaller = "$vsPath\Common7\IDE\VSIXInstaller.exe"

if (-not (Test-Path $vsixInstaller)) {
    Write-Warn "VSIXInstaller not found at expected path. Skipping extension install."
} else {
    $vsix = Get-ChildItem "$wdkRoot\Vsix\VS2022\" -Recurse -Filter "WDK.vsix" -ErrorAction SilentlyContinue |
        Sort-Object -Property FullName |
        Select-Object -Last 1

    if (-not $vsix) {
        Write-Warn "WDK.vsix not found under $wdkRoot\Vsix\VS2022\ — skipping extension install."
        Write-Warn "You may need to install it manually after WDK setup completes."
    } else {
        Write-Host "    Found: $($vsix.FullName)"
        & $vsixInstaller /quiet $vsix.FullName
        Write-Success "WDK VS extension installed"
    }
}

# ---------------------------------------------------------------------------
# 7. Reload PATH
# ---------------------------------------------------------------------------
Write-Step "Reloading PATH..."
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("PATH", "User")
Write-Success "PATH reloaded"

# ---------------------------------------------------------------------------
# 8. Git submodules (including PawnIO's PawnPP)
# ---------------------------------------------------------------------------
Write-Step "Initializing git submodules..."
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $repoRoot
try {
    git submodule update --init --recursive
    # PawnIO has its own submodule (PawnPP) not tracked by the root repo
    $pawnIODir = Join-Path $repoRoot "tools\PawnIO"
    if (Test-Path "$pawnIODir\.gitmodules") {
        Push-Location $pawnIODir
        git submodule update --init --recursive
        Pop-Location
    }
    Write-Success "Submodules initialized (including PawnIO/PawnPP)"
} finally {
    Pop-Location
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host "`n==> All dependencies installed successfully." -ForegroundColor Green
Write-Host ""
Write-Host "To build PawnIO + lhm-server, run:" -ForegroundColor White
Write-Host "    powershell -ExecutionPolicy Bypass -File tools/lhm-server/build.ps1" -ForegroundColor Gray
Write-Host ""
