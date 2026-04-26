<#
.SYNOPSIS
    Checks for the latest PawnIO.Setup release on GitHub, downloads if newer,
    verifies SHA256, and copies pawnio_setup.exe to the build pipeline.

.DESCRIPTION
    0. Check if pawnio_setup.exe already exists in dist
    1. Queries GitHub API for the latest namazso/PawnIO.Setup release
    2. Compares against locally tracked version
    3. Downloads new release if available, archives the old one
    4. Verifies SHA256 against GitHub's asset.digest
    5. Copies pawnio_setup.exe to tools/PawnIO/dist/pawnio_setup.exe

    Requires: Internet access to api.github.com and github.com
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Paths ────────────────────────────────────────────────────────────────────

$ScriptDir   = $PSScriptRoot
$RepoRoot    = Resolve-Path (Join-Path $ScriptDir "..\..")
$ResourceDir = Join-Path $ScriptDir "resources"
$ArchiveDir  = Join-Path $ResourceDir "archive"
$VersionFile = Join-Path $ScriptDir "version.json"
$SetupExe    = Join-Path $ResourceDir "PawnIO_setup.exe"
$PawnIODist  = Join-Path (Join-Path (Join-Path $RepoRoot "tools") "PawnIO") "dist"
$TargetSetup = Join-Path $PawnIODist "pawnio_setup.exe"

$GitHubAPI   = "https://api.github.com/repos/namazso/PawnIO.Setup/releases/latest"

# ── Step 0: Check if pawnio_setup.exe already exists in dist ─────────────────

if (Test-Path $TargetSetup) {
    # Also check that cached version.json matches so we don't skip a pending update.
    if (Test-Path $VersionFile) {
        $versionData  = Get-Content $VersionFile -Raw | ConvertFrom-Json
        $localVersion = $versionData.version
        Write-Host "pawnio_setup.exe already in dist ($localVersion) - skipping update check." -ForegroundColor Green
        Write-Host "  $TargetSetup" -ForegroundColor DarkGray
        exit 0
    }
    Write-Host "pawnio_setup.exe in dist but no version file - running update check." -ForegroundColor Yellow
} else {
    Write-Host "pawnio_setup.exe not found in dist - running update check." -ForegroundColor Yellow
}

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
            Write-Host "Already up to date ($localVersion) - using cached installer..." -ForegroundColor Green
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

# ── Step 7: Copy pawnio_setup.exe to dist/ ───────────────────────────────────

New-Item -ItemType Directory -Force -Path $PawnIODist | Out-Null
Copy-Item -Path $SetupExe -Destination $TargetSetup -Force
$setupSize = [math]::Round((Get-Item $TargetSetup).Length / 1MB, 1)
Write-Host "  pawnio_setup.exe -> $TargetSetup ($($setupSize) MB)" -ForegroundColor Green

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
    Write-Host "PawnIO setup exe copied from cache ($localVersion)." -ForegroundColor Green
}

Write-Host "  Setup exe: $SetupExe" -ForegroundColor DarkGray
Write-Host "  Dist copy: $TargetSetup" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Next: run build.py or tools/lhm-server/build.ps1 to embed pawnio_setup.exe." -ForegroundColor DarkGray
