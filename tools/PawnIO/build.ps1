<#
.SYNOPSIS
    Builds PawnIO.sys from source using WDK + CMake.
    Output: tools/PawnIO/dist/PawnIO.sys

.DESCRIPTION
    Requires:
      - CMake 3.25+  (https://cmake.org)
      - Windows Driver Kit (WDK) for the matching Windows SDK version
      - MSVC with C++20 support

    NOTE ON SIGNING:
      Binaries built from source are unsigned (or test-signed only).
      Test-signing mode must be enabled to load unsigned drivers:
        bcdedit /set testsigning on   (then reboot)
      For production builds, replace dist/PawnIO.sys with the officially
      signed release binary from pawnio.eu before building lhm-server.exe.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root    = $PSScriptRoot
$DistDir = Join-Path $Root "dist"
$OutSys  = Join-Path $DistDir "PawnIO.sys"

# ── Prerequisite checks ───────────────────────────────────────────────────────

if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
    Write-Error "cmake not found. Install CMake 3.25+ and add it to PATH."
}
Write-Host "cmake: $(cmake --version | Select-Object -First 1)" -ForegroundColor DarkGray

# WDK presence is checked by FindWdk.cmake; CMake configure will fail with a
# clear message if WDK is absent.

# ── CMake configure ───────────────────────────────────────────────────────────

$BuildDir = Join-Path $Root "cmake-build-release"

Write-Host ""
Write-Host "Configuring PawnIO (Release/x64)..." -ForegroundColor Cyan
cmake -S $Root -B $BuildDir -DCMAKE_BUILD_TYPE=Release -A x64
if ($LASTEXITCODE -ne 0) {
    Write-Error (
        "CMake configure failed.`n" +
        "  Ensure Windows Driver Kit is installed and WDK version matches your Windows SDK.`n" +
        "  WDK download: https://learn.microsoft.com/windows-hardware/drivers/download-the-wdk"
    )
}

# ── CMake build ───────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "Building PawnIO.sys..." -ForegroundColor Cyan
cmake --build $BuildDir --config Release
if ($LASTEXITCODE -ne 0) {
    Write-Error "CMake build failed. See output above for details."
}

# ── Locate output .sys ────────────────────────────────────────────────────────

# CMakeLists sets OUTPUT_NAME to "PawnIO_unsigned"; CMake may also produce "PawnIO.sys"
# if a signing step ran.  Accept either.
$SysFile = Get-ChildItem -Path $BuildDir -Filter "PawnIO.sys" -Recurse -ErrorAction SilentlyContinue |
           Select-Object -First 1

if (-not $SysFile) {
    $SysFile = Get-ChildItem -Path $BuildDir -Filter "PawnIO_unsigned.sys" -Recurse -ErrorAction SilentlyContinue |
               Select-Object -First 1
}

if (-not $SysFile) {
    Write-Error "PawnIO*.sys not found in build output at '$BuildDir'. Build may have produced a different filename."
}

# ── Copy to dist/ ─────────────────────────────────────────────────────────────

New-Item -ItemType Directory -Force -Path $DistDir | Out-Null
Copy-Item -Path $SysFile.FullName -Destination $OutSys -Force

$SizeMB = [math]::Round((Get-Item $OutSys).Length / 1KB, 1)
Write-Host ""
Write-Host "PawnIO.sys  →  $OutSys  (${SizeMB} KB)" -ForegroundColor Green
Write-Host ""
Write-Host "Next: run tools/lhm-server/build.ps1 to embed PawnIO.sys in lhm-server.exe." -ForegroundColor DarkGray
