from src.utils.formatting import print_info


def verify_integrity(silent_pass: bool = True) -> bool:
    """Remind users to download only from the official release page."""
    if not silent_pass:
        print_info(
            "lil_bro should only be downloaded from "
            "https://github.com/cattboy/lil_bro/releases"
        )
    return True
