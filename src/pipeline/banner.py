"""ASCII art banner and tagline."""

from colorama import Fore, Style
from src.utils.formatting import print_accent, print_dim


def print_banner():
    """Prints the lil_bro ASCII art banner with tagline and privacy notice."""
    banner = f"""{Fore.MAGENTA}{Style.BRIGHT}
  _   _    __  _            ___
 | | (_)  / / | |__   _ __ / _ \\
 | | | | / /  | '_ \\ | '__| | | |
 | | | |/ /   | |_) || |  | |_| |
 |_| |_/_/    |_.__/ |_|   \\___/
{Style.RESET_ALL}"""
    print(banner)
    print_accent("  Your Local AI PC Optimization Agent")
    print_dim("  Privacy Guarantee: 100% Offline Analysis. No data leaves your machine.\n")
