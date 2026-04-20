"""
build.py — Automated build pipeline for lil_bro.

Usage:
    python build.py          # Full build + integrity manifest
    python build.py --clean  # Clean dist/ and build/ first

Steps:
    [1/5] Clean (optional, --clean flag)
    [2/5] Fetch latest signed PawnIO.sys from GitHub (update_pawnio.ps1)
          Falls back to WDK source build if offline / rate-limited / 7-Zip absent.
    [3/5] Build lhm-server.exe (requires .NET 8 SDK; embeds PawnIO.sys)
    [4/5] Build lil_bro.exe with PyInstaller
    
Requires: pyinstaller (listed in [project.optional-dependencies] dev)
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DIST_DIR = ROOT / "dist"
EXE_NAME = "lil_bro.exe"


def clean():
    for d in ["build", "dist"]:
        p = ROOT / d
        if p.exists():
            shutil.rmtree(p)
            print(f"  Cleaned {p}")


def run_pyinstaller():
    spec = ROOT / "lil_bro.spec"
    if not spec.exists():
        print(f"ERROR: {spec} not found")
        sys.exit(1)

    cmd = [sys.executable, "-m", "PyInstaller", str(spec), "--noconfirm"]
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print("ERROR: PyInstaller build failed!")
        sys.exit(1)

    exe_path = DIST_DIR / EXE_NAME
    if not exe_path.exists():
        print(f"ERROR: Expected output not found at {exe_path}")
        sys.exit(1)

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"  Built: {exe_path} ({size_mb:.1f} MB)")
    return exe_path





def run_pawnio_update():
    """Try to fetch the latest signed PawnIO.sys from GitHub releases.

    Runs tools/PawnIO_Latest_Check/update_pawnio.ps1, which:
      1. Checks namazso/PawnIO.Setup for a newer release
      2. Downloads + SHA256-verifies PawnIO_setup.exe if newer
      3. Extracts the signed PawnIO.sys to tools/PawnIO/dist/PawnIO.sys

    Non-fatal: network failures, rate limits, and missing 7-Zip all exit 0
    from the script.  If PawnIO.sys is already up to date, this is a no-op.
    On any failure the lhm-server build falls back to WDK source compilation.
    """
    script = ROOT / "tools" / "PawnIO_Latest_Check" / "update_pawnio.ps1"
    if not script.exists():
        print("  SKIP: tools/PawnIO_Latest_Check/update_pawnio.ps1 not found")
        return

    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        cwd=str(script.parent),
    )

    target_sys = ROOT / "tools" / "PawnIO" / "dist" / "PawnIO.sys"
    if result.returncode != 0:
        print(
            "  WARNING: PawnIO update script failed — "
            "lhm-server build will fall back to WDK source compilation."
        )
    elif target_sys.exists():
        size_kb = target_sys.stat().st_size / 1024
        print(f"  PawnIO.sys ready: {target_sys} ({size_kb:.1f} KB)")
    else:
        print(
            "  WARNING: update_pawnio.ps1 exited cleanly but PawnIO.sys not found — "
            "lhm-server build will fall back to WDK source compilation."
        )


def build_lhm_server():
    """Build the custom thermal sensor server (requires .NET 8 SDK + WDK).

    Runs tools/lhm-server/build.ps1, which first auto-builds PawnIO.sys from
    tools/PawnIO/build.ps1 (WDK + CMake) if not already present, then embeds
    it inside lhm-server.exe.  The resulting exe auto-installs the PawnIO
    kernel driver on first run (admin required once; persists across reboots).

    Failure is non-fatal — the main build continues and thermal monitoring
    falls back to a user-installed LibreHardwareMonitor if available.
    """
    script = ROOT / "tools" / "lhm-server" / "build.ps1"
    if not script.exists():
        print("  SKIP: tools/lhm-server/build.ps1 not found")
        return
    

    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        cwd=str(script.parent),
    )

    lhm_exe = ROOT / "tools" / "lhm-server" / "dist" / "lhm-server.exe"
    if result.returncode != 0 or not lhm_exe.exists():
        print(
            "  WARNING: lhm-server build failed — thermals will require a manual "
            "LibreHardwareMonitor install.  Install .NET 8 SDK and re-run the build."
        )
    else:
        size_mb = lhm_exe.stat().st_size / (1024 * 1024)
        print(f"  Built: {lhm_exe} ({size_mb:.1f} MB)")


def build_npi():
    """Build NVIDIA Profile Inspector from source (requires .NET SDK + net48 targeting pack).

    Compiles the modified NPI fork via dotnet build and copies the exe to
    tools/nvidiaProfileInspector/nvidiaProfileInspector.exe where lil_bro.spec
    and _NPI_SEARCH_PATHS expect it.

    Failure is non-fatal — the main build continues and GPU profile
    optimization (G-Sync, VSync, DLSS, FPS cap) will be unavailable.
    """
    npi_exe = ROOT / "tools" / "nvidiaProfileInspector" / "nvidiaProfileInspector.exe"
    if npi_exe.exists():
        size_mb = npi_exe.stat().st_size / (1024 * 1024)
        print(f"  Found: {npi_exe} ({size_mb:.1f} MB)")
        return

    csproj = (
        ROOT / "tools" / "nvidiaProfileInspector" / "nvidiaProfileInspector"
        / "nvidiaProfileInspector.csproj"
    )
    if not csproj.exists():
        print(f"  SKIP: {csproj} not found")
        return

    try:
        result = subprocess.run(
            ["dotnet", "build", str(csproj), "-c", "Release"],
            cwd=str(csproj.parent),
        )
    except FileNotFoundError:
        print(
            "  WARNING: dotnet not found on PATH — install the .NET SDK to build NPI.\n"
            "  GPU profile optimization will be unavailable."
        )
        return

    build_output = csproj.parent / "bin" / "Release" / "net48" / "nvidiaProfileInspector.exe"
    if result.returncode != 0 or not build_output.exists():
        print(
            "  WARNING: NPI build failed — GPU profile optimization will be unavailable.\n"
            "  Ensure the .NET SDK and .NET Framework 4.8 Targeting Pack are installed,\n"
            "  then re-run the build."
        )
        return

    shutil.copy2(build_output, npi_exe)
    size_mb = npi_exe.stat().st_size / (1024 * 1024)
    print(f"  Built: {npi_exe} ({size_mb:.1f} MB)")


def main():
    print("lil_bro build pipeline")
    print("=" * 40)

    if "--clean" in sys.argv:
        print("\n[1/4] Cleaning...")
        clean()
    else:
        print("\n[1/4] Clean skipped (use --clean to force)")

    print("\n[2/4] Building NPI (GPU profile optimizer)...")
    build_npi()
    print("\n[2/4] Fetching latest signed PawnIO.sys from GitHub...")
    run_pawnio_update()

    print("\n[3/4] Building lhm-server (thermal sensor server)...")
    build_lhm_server()

    print("\n[4/4] Building with PyInstaller...")
    run_pyinstaller()

    print("\n" + "=" * 40)
    print("Build complete!")
    print(f"  Portable exe: {DIST_DIR / EXE_NAME}")
    print("\nReady to distribute.")


if __name__ == "__main__":
    main()
