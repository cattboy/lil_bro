"""
model_loader.py — GGUF model loader for lil_bro.

Handles:
  - Resolving the cached model path (%APPDATA%\\lil_bro\\models\\)
  - First-run download prompt + download from HuggingFace Hub
  - Loading the Llama model (CPU-only, n_gpu_layers=0)

Returns a Llama instance on success, None on any failure (import missing,
download declined, load error). Callers must handle None gracefully.
"""
from __future__ import annotations
import os
import urllib.request
from pathlib import Path

from colorama import Fore, Style

MODEL_FILENAME = "Qwen2.5-Coder-7B-Instruct.Q4_K_M.gguf"
MODEL_HF_URL = (
    "https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
    "/resolve/main/Qwen2.5-Coder-7B-Instruct.Q4_K_M.gguf"
)
MODEL_SIZE_GB = 4.5


def get_model_path() -> Path:
    """Returns the expected local path for the cached GGUF model."""
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "lil_bro" / "models" / MODEL_FILENAME


def get_model_status() -> dict:
    """Returns the current state of the LLM toolchain for display in menus."""
    llama_installed = False
    try:
        import llama_cpp  # noqa: F401
        llama_installed = True
    except ImportError:
        pass

    model_path = get_model_path()
    return {
        "llama_installed": llama_installed,
        "model_downloaded": model_path.exists(),
        "model_path": str(model_path),
    }


def _download_model(dest: Path) -> bool:
    """Downloads the GGUF model to dest with a progress indicator. Returns True on success."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"{Fore.CYAN}Downloading {MODEL_FILENAME} (~{MODEL_SIZE_GB} GB){Style.RESET_ALL}")
    print(f"  Destination: {dest}")

    def _progress(block_num: int, block_size: int, total_size: int) -> None:
        if total_size > 0:
            pct = min(block_num * block_size * 100 // total_size, 100)
            print(f"\r  {pct:3d}% complete", end="", flush=True)

    try:
        urllib.request.urlretrieve(MODEL_HF_URL, dest, _progress)
        print()  # newline after progress bar
        return True
    except Exception as e:
        print(f"\n{Fore.RED}✗ Download failed: {e}{Style.RESET_ALL}")
        if dest.exists():
            dest.unlink(missing_ok=True)
        return False


def load_model():
    """
    Loads the GGUF model for CPU inference.

    First-run flow (model not yet cached):
      - Displays a privacy disclosure (no scan data sent; only IP visible to HuggingFace).
      - Asks the user before downloading.
      - Caches the model in %APPDATA%\\lil_bro\\models\\ for all future runs.

    Returns:
        llama_cpp.Llama on success, None if unavailable for any reason.
    """
    try:
        from llama_cpp import Llama  # type: ignore
    except ImportError:
        print(
            f"{Fore.YELLOW}⚠ llama-cpp-python not installed — "
            f"AI explanations unavailable this run.{Style.RESET_ALL}"
        )
        return None

    model_path = get_model_path()

    if not model_path.exists():
        print(f"\n{Fore.CYAN}{Style.BRIGHT}=== First Run: AI Model Download ==={Style.RESET_ALL}")
        print(
            f"lil_bro uses a local AI model ({MODEL_FILENAME}, ~{MODEL_SIZE_GB} GB)\n"
            "to explain findings and propose fixes in plain English.\n"
        )
        print(f"{Fore.YELLOW}Privacy note:{Style.RESET_ALL}")
        print("  • No system scan data or hardware info is transmitted.")
        print("  • Your IP will be visible to HuggingFace (the model host) during download only.")
        print("  • After the first run, lil_bro is fully offline.\n")

        response = input(
            f"{Fore.MAGENTA}Download model now? [y/N]: {Style.RESET_ALL}"
        ).strip().lower()

        if response not in ("y", "yes"):
            print(
                f"{Fore.YELLOW}⚠ Model download skipped — "
                f"AI explanations will not be available this run.{Style.RESET_ALL}"
            )
            return None

        if not _download_model(model_path):
            return None

        print(f"{Fore.GREEN}✓ Model cached at {model_path}{Style.RESET_ALL}\n")

    try:
        print(f"{Fore.BLUE}ℹ Loading AI model (CPU)...{Style.RESET_ALL}", end="", flush=True)
        llm = Llama(
            model_path=str(model_path),
            n_ctx=2048,
            n_gpu_layers=0,  # CPU-only for portability across all hardware
            verbose=False,
        )
        print(f" {Fore.GREEN}Ready.{Style.RESET_ALL}")
        return llm
    except Exception as e:
        print(f"\n{Fore.RED}✗ Failed to load model: {e}{Style.RESET_ALL}")
        return None
