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


def main():
    print("lil_bro build pipeline")
    print("=" * 40)

    if "--clean" in sys.argv:
        print("\n[1/3] Cleaning...")
        clean()
    else:
        print("\n[1/3] Clean skipped (use --clean to force)")

    print("\n[2/3] Building with PyInstaller...")
    exe_path = run_pyinstaller()

    print("\n[3/3] Generating integrity manifest...")
    generate_manifest(exe_path)

    print("\n" + "=" * 40)
    print("Build complete!")
    print(f"  Portable exe: {DIST_DIR / EXE_NAME}")
    print(f"  Manifest:     {DIST_DIR / MANIFEST_NAME}")
    print(f"\nCopy both files to distribute.")


if __name__ == "__main__":
    main()
