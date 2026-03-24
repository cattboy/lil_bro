"""Main menu loop and AI model setup."""

import sys
from colorama import Fore, Style

from src.llm.model_loader import load_model, get_model_status
from src.utils.formatting import (
    print_header, print_info, print_warning, print_error,
    print_success, print_key_value, print_prompt,
)
from src.pipeline._state import get_llm, set_llm
from src.pipeline.phases import run_optimization_pipeline


def menu_loop():
    """3-option main menu: Pipeline, AI Setup, Exit."""
    while True:
        print_header("Main Menu")

        if get_llm() is not None:
            print_key_value("AI Model", "ready", value_color=Fore.GREEN)
        else:
            print_key_value("AI Model", "not loaded", value_color=Fore.YELLOW)

        print(f"  {Fore.CYAN}1.{Style.RESET_ALL} Run Full Esports Optimization Pipeline")
        print(f"  {Fore.CYAN}2.{Style.RESET_ALL} Setup AI Model")
        print(f"  {Fore.CYAN}3.{Style.RESET_ALL} Exit")

        print()
        print_prompt("Select an option [1-3]: ")
        choice = input().strip()

        if choice == '1':
            run_optimization_pipeline()
        elif choice == '2':
            setup_ai_model()
        elif choice == '3':
            print_info("shutting down, stay sweaty lil_bro.")
            sys.exit(0)
        else:
            print_error("Invalid choice. Try again.")


def setup_ai_model():
    """Interactive AI model management -- shows status, offers download, loads model."""
    print_header("AI Model Setup")

    status = get_model_status()

    if status["llama_installed"]:
        print_success("llama-cpp-python installed")
    else:
        print_warning("llama-cpp-python is not installed")
        print_info("Install with:  uv pip install llama-cpp-python")
        print_info(
            "\nThe optimization pipeline works without it -- "
            "you'll get standard recommendations instead of AI-generated ones.\n"
        )
        return

    if status["model_downloaded"]:
        print_success(f"Model downloaded: {status['model_path']}")
    else:
        print_info("Model not yet downloaded")
        print_info(f"Expected path: {status['model_path']}")

    if get_llm() is not None:
        print_success("Model loaded and ready")
        print_info("\nNothing to do -- AI model is already set up.")
        return

    print()
    result = load_model()
    set_llm(result)

    if get_llm() is not None:
        print_success("\nAI model is ready. The pipeline will use AI-powered explanations.")
    else:
        print_info(
            "\nThe pipeline works without the AI model -- "
            "you'll get standard recommendations."
        )
