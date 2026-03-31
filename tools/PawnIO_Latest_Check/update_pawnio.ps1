<#
.SYNOPSIS
    Checks for the latest PawnIO.Setup release on GitHub, downloads if newer,
    verifies SHA256, and extracts PawnIO.sys for the build pipeline.

.DESCRIPTION
    0. Check if PawnIO.sys already exists in dist
    1. Queries GitHub API for the latest namazso/PawnIO.Setup release
    2. Compares against locally tracked version
    3. Downloads new release if available, archives the old one
    4. Verifies SHA256 against GitHub's asset.digest
    5. Extracts PawnIO.sys via 7-Zip and places it at tools/PawnIO/dist/PawnIO.sys

    Requires: 7-Zip installed at "C:\Program Files\7-Zip\7z.exe"
    Requires: Internet access to api.github.com and github.com
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Helpers ───────────────────────────────────────────────────────────────────

# Read the PE Machine field (offset 4 into the PE header) to determine CPU arch.
# Returns the COFF machine type as a UInt16 (0x8664 = AMD64, 0xAA64 = ARM64, etc.)
function Get-PEMachineType([string]$Path) {
    $bytes    = [System.IO.File]::ReadAllBytes($Path)
    $peOffset = [System.BitConverter]::ToInt32($bytes, 0x3C)
    return    [System.BitConverter]::ToUInt16($bytes, $peOffset + 4)
}

$AMD64 = [uint16]0x8664   # x64 / AMD64 machine type

# ── Paths ────────────────────────────────────────────────────────────────────

$ScriptDir   = $PSScriptRoot
$RepoRoot    = Resolve-Path (Join-Path $ScriptDir "..\..")
$ResourceDir = Join-Path $ScriptDir "resources"
$ArchiveDir  = Join-Path $ResourceDir "archive"
$VersionFile = Join-Path $ScriptDir "version.json"
$SetupExe    = Join-Path $ResourceDir "PawnIO_setup.exe"
$PawnIODist  = Join-Path (Join-Path (Join-Path $RepoRoot "tools") "PawnIO") "dist"
$TargetSys   = Join-Path $PawnIODist "PawnIO.sys"
$SevenZip    = "C:\Program Files\7-Zip\7z.exe"

$GitHubAPI   = "https://api.github.com/repos/namazso/PawnIO.Setup/releases/latest"

# ── Step 0: Check if PawnIO.sys already exists in dist ──────────────────────

if (Test-Path $TargetSys) {
    $existingMachine = Get-PEMachineType $TargetSys
    if ($existingMachine -eq $AMD64) {
        Write-Host "PawnIO.sys (x64) already present in dist - skipping update check." -ForegroundColor Green
        Write-Host "  $TargetSys" -ForegroundColor DarkGray
        exit 0
    }
    # Wrong architecture (e.g. ARM64 was extracted on a previous run) - re-extract.
    Write-Host ("PawnIO.sys in dist is wrong architecture " +
                ("(0x{0:X4} - expected 0x8664 x64). Re-extracting..." -f $existingMachine)) `
               -ForegroundColor Yellow
}
else {
    Write-Host "PawnIO.sys not found in dist - running update check." -ForegroundColor Yellow
}

# ── Prerequisite: 7-Zip ─────────────────────────────────────────────────────

if (-not (Test-Path $SevenZip)) {
    Write-Error ("7-Zip not found at '$SevenZip'.`n" +
                 "  Install from https://7-zip.org and re-run this script.")
}
Write-Host "7-Zip: found" -ForegroundColor DarkGray

# ── Step 1: Query GitHub API for latest release ─────────────────────────────

Write-Host ""
Write-Host "Checking GitHub for latest PawnIO.Setup release..." -ForegroundColor Cyan

try {
    $headers = @{ "User-Agent" = "lil_bro-PawnIO-Updater" }
    $response = Invoke-RestMethod -Uri $GitHubAPI -Headers $headers -TimeoutSec 15
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    if ($statusCode -eq 403 -or $statusCode -eq 429) {
        Write-Warning "GitHub API rate limit hit. Try again later or set GH_TOKEN env var."
    } else {
        Write-Warning "Failed to reach GitHub API: $_"
    }
    Write-Host "Skipping PawnIO update check." -ForegroundColor Yellow
    exit 0
}

$latestVersion = $response.tag_name
$asset         = $response.assets | Select-Object -First 1

if (-not $asset) {
    Write-Error "No assets found in the latest release ($latestVersion)."
}

$downloadUrl   = $asset.browser_download_url
$expectedSize  = $asset.size
$digestRaw     = $asset.digest   # format: "sha256:<hex>"

if (-not $digestRaw -or -not $digestRaw.StartsWith("sha256:")) {
    Write-Error "Unexpected digest format from GitHub: '$digestRaw'"
}
$expectedSHA = $digestRaw.Substring(7).ToLower()

Write-Host "  Latest release: $latestVersion" -ForegroundColor Green
Write-Host "  Asset:          $($asset.name)" -ForegroundColor DarkGray
Write-Host "  Size:           $expectedSize bytes" -ForegroundColor DarkGray
Write-Host "  SHA256:         $($expectedSHA.Substring(0,16))..." -ForegroundColor DarkGray

# ── Step 2: Read local version ───────────────────────────────────────────────

$localVersion = $null

if ((Test-Path $VersionFile) -and (Test-Path $SetupExe)) {
    $versionData  = Get-Content $VersionFile -Raw | ConvertFrom-Json
    $localVersion = $versionData.version
    Write-Host ""
    Write-Host "  Local version:  $localVersion" -ForegroundColor DarkGray
} else {
    Write-Host ""
    Write-Host "  No local version found (first run)." -ForegroundColor Yellow
}

# ── Step 3: Compare versions ────────────────────────────────────────────────

$skipDownload = $false

if ($localVersion) {
    try {
        $ghVer    = [System.Version]$latestVersion
        $localVer = [System.Version]$localVersion
        if ($ghVer -le $localVer) {
            Write-Host ""
            Write-Host "Already up to date ($localVersion) - extracting from cached installer..." -ForegroundColor Green
            $skipDownload = $true
        }
    } catch {
        Write-Host "  Version parse warning: $_ -- proceeding with download." -ForegroundColor Yellow
    }
}

if (-not $skipDownload) {
    Write-Host ""
    Write-Host "New version available: $localVersion -> $latestVersion" -ForegroundColor Cyan

    # ── Step 4: Archive old exe ─────────────────────────────────────────────

    if ((Test-Path $SetupExe) -and $localVersion) {
        New-Item -ItemType Directory -Force -Path $ArchiveDir | Out-Null
        $archiveName = "PawnIO_setup_${localVersion}.exe"
        $archivePath = Join-Path $ArchiveDir $archiveName
        Move-Item -Path $SetupExe -Destination $archivePath -Force
        Write-Host "  Archived: $archiveName" -ForegroundColor DarkGray
    }

    # ── Step 5: Download new release ────────────────────────────────────────

    New-Item -ItemType Directory -Force -Path $ResourceDir | Out-Null

    Write-Host ""
    Write-Host "Downloading PawnIO_setup.exe ($latestVersion)..." -ForegroundColor Cyan

    try {
        Invoke-WebRequest -Uri $downloadUrl -OutFile $SetupExe -Headers $headers -TimeoutSec 300
    } catch {
        Write-Error "Download failed: $_"
    }

    $actualSize = (Get-Item $SetupExe).Length
    if ($actualSize -ne $expectedSize) {
        Remove-Item -Force $SetupExe -ErrorAction SilentlyContinue
        Write-Error ("Size mismatch! Expected $expectedSize bytes, got $actualSize bytes.`n" +
                     "  Download may be corrupted. Deleted the file -- re-run to retry.")
    }

    Write-Host "  Downloaded: $actualSize bytes" -ForegroundColor Green

    # ── Step 6: SHA256 verification ──────────────────────────────────────────

    Write-Host ""
    Write-Host "Verifying SHA256..." -ForegroundColor Cyan

    $sha256    = [System.Security.Cryptography.SHA256]::Create()
    $stream    = [System.IO.File]::OpenRead($SetupExe)
    $hashBytes = $sha256.ComputeHash($stream)
    $stream.Close()
    $sha256.Dispose()
    $actualSHA = ([BitConverter]::ToString($hashBytes) -replace '-','').ToLower()

    if ($actualSHA -ne $expectedSHA) {
        # Restore archived copy if we have one
        if ($localVersion) {
            $archivePath = Join-Path $ArchiveDir "PawnIO_setup_${localVersion}.exe"
            if (Test-Path $archivePath) {
                Copy-Item -Path $archivePath -Destination $SetupExe -Force
                Write-Host "  Restored previous version from archive." -ForegroundColor Yellow
            }
        }
        Remove-Item -Force $SetupExe -ErrorAction SilentlyContinue
        Write-Error ("SHA256 MISMATCH!`n" +
                     "  Expected: $expectedSHA`n" +
                     "  Actual:   $actualSHA`n" +
                     "  The downloaded file has been deleted.")
    }

    Write-Host "  SHA256 verified: $($actualSHA.Substring(0,16))..." -ForegroundColor Green
}

# ── Step 7: Extract PawnIO.sys using 7-Zip ──────────────────────────────────
# PawnIO_setup.exe is a PE containing a zstd-compressed CAB in RCDATA resource 105.
# Extraction is two-step: PE -> zstd payload ("105~") -> CAB contents.
# The CAB contains multiple PawnIO.sys for different architectures (x64, ARM64).
# Using -aou (auto-rename) keeps all variants; the first "PawnIO.sys" is x64 signed.

Write-Host ""
Write-Host "Extracting PawnIO.sys..." -ForegroundColor Cyan

$tempExtract = Join-Path $ScriptDir "_extract_temp"
$step1Dir    = Join-Path $tempExtract "step1"
$step2Dir    = Join-Path $tempExtract "step2"

# Clean up any leftover temp dir
if (Test-Path $tempExtract) {
    Remove-Item -Recurse -Force $tempExtract
}

# Step 7a: Extract PE resources (produces zstd-compressed "105~")
New-Item -ItemType Directory -Force -Path $step1Dir | Out-Null
& $SevenZip x $SetupExe "-o$step1Dir" -y 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Remove-Item -Recurse -Force $tempExtract -ErrorAction SilentlyContinue
    Write-Error "7-Zip PE extraction failed (exit code $LASTEXITCODE)."
}

# Find the zstd payload (7z auto-decompresses zstd, producing the inner file)
$payload = Get-ChildItem -Path $step1Dir -Recurse -File -ErrorAction SilentlyContinue |
           Select-Object -First 1

if (-not $payload) {
    Remove-Item -Recurse -Force $tempExtract -ErrorAction SilentlyContinue
    Write-Error "No payload found after PE extraction."
}
Write-Host "  Payload: $($payload.Name) ($([math]::Round($payload.Length / 1MB, 1)) MB)" -ForegroundColor DarkGray

# Step 7b: Extract CAB contents with -aou to preserve all architecture variants
New-Item -ItemType Directory -Force -Path $step2Dir | Out-Null
& $SevenZip x $payload.FullName "-o$step2Dir" -aou -y 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Remove-Item -Recurse -Force $tempExtract -ErrorAction SilentlyContinue
    Write-Error "7-Zip CAB extraction failed (exit code $LASTEXITCODE)."
}

# PawnIO_setup.exe is a multi-arch installer — the CAB contains both x64 and
# ARM64 drivers.  7-Zip -aou renames duplicates (PawnIO.sys, PawnIO_1.sys …)
# so the first file is NOT guaranteed to be x64.  Select explicitly by PE
# machine type (0x8664 = AMD64/x64) to avoid embedding the ARM64 variant on
# x64 Windows, which causes a silent sc-start failure (wrong architecture).
$allSys = Get-ChildItem -Path $step2Dir -Filter "PawnIO*.sys" -ErrorAction SilentlyContinue

# Log what was extracted so the CI log makes arch selection transparent
foreach ($f in $allSys) {
    $mt = Get-PEMachineType $f.FullName
    $archLabel = if ($mt -eq $AMD64) { "x64" } elseif ($mt -eq 0xAA64) { "ARM64" } else { "0x{0:X4}" -f $mt }
    Write-Host "  Found: $($f.Name) ($($f.Length) bytes, $archLabel)" -ForegroundColor DarkGray
}

$x64Sys = $allSys | Where-Object { (Get-PEMachineType $_.FullName) -eq $AMD64 } | Select-Object -First 1

if ($x64Sys) {
    $foundSys = $x64Sys.FullName
    Write-Host "  Selected x64 driver: $($x64Sys.Name)" -ForegroundColor Green
} elseif ($allSys) {
    # No x64 variant found — warn and fall back to the largest file
    $fallback = $allSys | Sort-Object Length -Descending | Select-Object -First 1
    $foundSys = $fallback.FullName
    Write-Warning ("No x64 (0x8664) PawnIO.sys found in extracted contents.`n" +
                   "  Falling back to: $($fallback.Name) ($($fallback.Length) bytes).`n" +
                   "  This may fail on x64 Windows if the wrong architecture is selected.")
} else {
    Write-Host "  Extracted contents:" -ForegroundColor Yellow
    Get-ChildItem -Path $step2Dir | ForEach-Object {
        Write-Host "    $($_.Name) ($($_.Length) bytes)" -ForegroundColor DarkGray
    }
    Remove-Item -Recurse -Force $tempExtract -ErrorAction SilentlyContinue
    Write-Error ("PawnIO.sys not found in extracted contents.`n" +
                 "  The installer format may have changed -- manual extraction required.")
}

# Copy to build pipeline target
New-Item -ItemType Directory -Force -Path $PawnIODist | Out-Null
Copy-Item -Path $foundSys -Destination $TargetSys -Force

$sysSize = [math]::Round((Get-Item $TargetSys).Length / 1KB, 1)
Write-Host "  PawnIO.sys -> $TargetSys ($($sysSize) KB)" -ForegroundColor Green

# Clean up temp dir
Remove-Item -Recurse -Force $tempExtract

# ── Step 8: Update version tracking (only when a new version was downloaded) ─

if (-not $skipDownload) {
    $versionInfo = @{
        version    = $latestVersion
        sha256     = $actualSHA
        updated_at = (Get-Date -Format "o")
    } | ConvertTo-Json -Depth 2

    Set-Content -Path $VersionFile -Value $versionInfo -Encoding UTF8

    Write-Host ""
    Write-Host "PawnIO updated to $latestVersion successfully." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "PawnIO extracted from cached installer ($localVersion)." -ForegroundColor Green
}

Write-Host "  Setup exe: $SetupExe" -ForegroundColor DarkGray
Write-Host "  Driver:    $TargetSys" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Next: run build.py or tools/lhm-server/build.ps1 to embed the new PawnIO.sys." -ForegroundColor DarkGray
