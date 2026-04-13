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
