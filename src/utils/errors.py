class LilBroError(Exception):
    """Base exception class for all lil_bro specific errors."""
    pass

class AdminRequiredError(LilBroError):
    """Raised when an operation requires administrative privileges but the script is not elevated."""
    pass

class ScannerError(LilBroError):
    """Raised when a system scanner encounters an unexpected error or missing component."""
    pass

class RestorePointError(LilBroError):
    """Raised when creating a System Restore Point fails."""
    pass

class SetterError(LilBroError):
    """Raised when a fix/setter operation fails to apply a system change."""
    pass



class NvapiInitError(SetterError):
    """Raised when NPI fails to initialize NVAPI -- typically no NVIDIA GPU present.

    Canonical signature: ``returncode == 3221225477`` (0xC0000005, access violation)
    with ``DrsSession`` NullRef in stderr. Callers can use this subclass to detect
    the AMD-only-system case without string-matching the formatted error message.
    """
    pass
