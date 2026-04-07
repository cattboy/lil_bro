"""ASCII art banner and tagline."""

from colorama import Fore, Style
from src.utils.formatting import print_accent, print_dim, print_info


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
    print_info("  Your Local AI PC Optimization Agent")
    print_dim("  Privacy Guarantee: 100% Offline Analysis. No data leaves your machine.\n")
    print_accent("  ALL changes lil_bro makes are LOGGED to lil_bro_actions.log (right next to lil_bro.exe) ")
    print_accent("  and temp files are removed on exit — o7")
    print_accent("  == support lil_bros future: ")
    print_accent("  ====================  ====================")
    print_accent("  ")