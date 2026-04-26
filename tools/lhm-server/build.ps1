# tools/lhm-server/build.ps1
# Builds lhm-server.exe as a self-contained single-file Windows x64 binary.
# Requires .NET 8 SDK.  Run from repo root or from this directory.

$ErrorActionPreference = "Stop"
$OutDir = Join-Path $PSScriptRoot "dist"

# ── pawnio_setup.exe prerequisite ────────────────────────────────────────────
# lhm-server.exe embeds pawnio_setup.exe so it can install PawnIO via the
# Driver Store on first run.  Run update_pawnio.ps1 first if not present.

$PawnIOSetup = Join-Path $PSScriptRoot "..\..\tools\PawnIO\dist\pawnio_setup.exe"
if (Test-Path $PawnIOSetup) {
    Write-Host "pawnio_setup.exe found - will embed in lhm-server.exe." -ForegroundColor Green
} else {
    Write-Host "pawnio_setup.exe not found - run tools/PawnIO_Latest_Check/update_pawnio.ps1 first." `
               -ForegroundColor Yellow
    Write-Host "  lhm-server.exe will be built WITHOUT embedded PawnIO installer." -ForegroundColor Yellow
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
# Clean first — incremental builds can miss newly-added EmbeddedResource files
# (the Condition guard means MSBuild doesn't track PawnIO.sys as an input until
# it exists, so a stale cache silently omits it).
dotnet clean "$PSScriptRoot\LhmServer.csproj" -c Release -r win-x64 --nologo 2>$null
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
