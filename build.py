"""
build.py — Automated build pipeline for lil_bro.

Usage:
    python build.py          # Full build + integrity manifest
    python build.py --clean  # Clean dist/ and build/ first

Requires: pyinstaller (listed in [project.optional-dependencies] dev)
"""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DIST_DIR = ROOT / "dist"
EXE_NAME = "lil_bro.exe"
MANIFEST_NAME = "integrity.json"


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


def generate_manifest(exe_path: Path):
    """Generate integrity.json with the SHA-256 hash of the .exe."""
    # Read version from source
    version = "unknown"
    version_file = ROOT / "src" / "_version.py"
    if version_file.exists():
        ns = {}
        exec(version_file.read_text(), ns)
        version = ns.get("__version__", "unknown")

    exe_hash = hashlib.sha256(exe_path.read_bytes()).hexdigest()

    manifest = {
        "version": version,
        "algorithm": "sha256",
        "exe_hash": exe_hash,
        "exe_name": EXE_NAME,
    }

    manifest_path = DIST_DIR / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"  Manifest: {manifest_path}")
    print(f"  SHA-256:  {exe_hash[:32]}...")


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


def check_npi_binary():
    """Warn if nvidiaProfileInspector.exe is missing from the expected location."""
    npi_exe = ROOT / "tools" / "nvidiaProfileInspector" / "nvidiaProfileInspector" / "bin" / "Release" / "net48" / "nvidiaProfileInspector.exe"
    if npi_exe.exists():
        size_mb = npi_exe.stat().st_size / (1024 * 1024)
        print(f"  Found: {npi_exe} ({size_mb:.1f} MB)")
    else:
        print(
            "  WARNING: tools/nvidiaProfileInspector/nvidiaProfileInspector.exe not found.\n"
            "  GPU profile optimization (G-Sync, VSync, DLSS, FPS cap) will be unavailable.\n"
            "  Build the modified NPI fork and place the exe at that path."
            # TODO CLAUDE this should build the code from source in C:\1_Coding\2026\lil_bro\tools\nvidiaProfileInspector\nvidiaProfileInspector using "dotnet build -c Release"
        )


def main():
    print("lil_bro build pipeline")
    print("=" * 40)

    if "--clean" in sys.argv:
        print("\n[1/5] Cleaning...")
        clean()
    else:
        print("\n[1/5] Clean skipped (use --clean to force)")

    print("\n[2/5] Checking NPI binary (GPU profile optimizer)...")
    check_npi_binary()

    print("\n[3/5] Building lhm-server (thermal sensor server)...")
    build_lhm_server()

    print("\n[4/5] Building with PyInstaller...")
    exe_path = run_pyinstaller()

    print("\n[5/5] Generating integrity manifest...")
    generate_manifest(exe_path)

    print("\n" + "=" * 40)
    print("Build complete!")
    print(f"  Portable exe: {DIST_DIR / EXE_NAME}")
    print(f"  Manifest:     {DIST_DIR / MANIFEST_NAME}")
    print(f"\nCopy both files to distribute.")


if __name__ == "__main__":
    main()
