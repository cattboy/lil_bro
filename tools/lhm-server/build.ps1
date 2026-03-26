# tools/lhm-server/build.ps1
# Builds lhm-server.exe as a self-contained single-file Windows x64 binary.
# Requires .NET 8 SDK.  Run from repo root or from this directory.

$ErrorActionPreference = "Stop"
$OutDir = Join-Path $PSScriptRoot "dist"

# ── PawnIO.sys prerequisite ───────────────────────────────────────────────────
# lhm-server.exe embeds PawnIO.sys so it can auto-install the thermal driver on
# first run.  Build PawnIO.sys from source if it is not already present.

$PawnIOSys = Resolve-Path (Join-Path $PSScriptRoot "..\..\tools\PawnIO\dist\PawnIO.sys") `
             -ErrorAction SilentlyContinue

if (-not $PawnIOSys) {
    Write-Host ""
    Write-Host "PawnIO.sys not found - attempting auto-build from tools/PawnIO/..." `
               -ForegroundColor Yellow
    $PawnIOBuild = Join-Path $PSScriptRoot "..\..\tools\PawnIO\build.ps1"
    if (Test-Path $PawnIOBuild) {
        & $PawnIOBuild
        if ($LASTEXITCODE -ne 0) {
            Write-Warning (
                "PawnIO build failed.  lhm-server.exe will be built WITHOUT embedded " +
                "PawnIO.sys - temperature monitoring will not work until PawnIO is " +
                "installed separately.  See tools/PawnIO/build.ps1 for requirements."
            )
        }
    } else {
        Write-Warning "tools/PawnIO/build.ps1 not found - skipping PawnIO embed."
    }
} else {
    Write-Host "PawnIO.sys found - will embed in lhm-server.exe." -ForegroundColor Green
}
Write-Host ""

# ── .NET SDK check ────────────────────────────────────────────────────────────

if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
    Write-Error ".NET 8 SDK is required to build lhm-server.  Download from https://dot.net/download"
    exit 1
}

$sdkVersion = (dotnet --version 2>$null)
Write-Host "dotnet SDK: $sdkVersion"

Write-Host "Building lhm-server (self-contained win-x64)..."
dotnet publish "$PSScriptRoot\LhmServer.csproj" `
    -r win-x64 `
    -c Release `
    --self-contained `
    -p:PublishSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -p:EnableCompressionInSingleFile=true `
    -o "$OutDir"

$exe = Join-Path $OutDir "lhm-server.exe"
if (-not (Test-Path $exe)) {
    Write-Error "Build succeeded but lhm-server.exe not found in $OutDir"
    exit 1
}

$sizeMb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "Built: lhm-server.exe ($sizeMb MB) -> $exe"
