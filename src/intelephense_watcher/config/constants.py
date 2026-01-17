"""Constants for Intelephense Watcher."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Colors:
    """ANSI color codes for terminal output."""

    RED: str = "\033[91m"
    YELLOW: str = "\033[93m"
    GREEN: str = "\033[92m"
    BLUE: str = "\033[94m"
    CYAN: str = "\033[96m"
    RESET: str = "\033[0m"
    BOLD: str = "\033[1m"


@dataclass(frozen=True)
class Constants:
    """Application constants."""

    # LSP command
    LSP_COMMAND: tuple[str, ...] = ("intelephense", "--stdio")

    # File extensions to watch
    PHP_EXTENSIONS: tuple[str, ...] = (".php",)

    # Directories to skip during scanning
    SKIP_DIRECTORIES: tuple[str, ...] = ("vendor", "node_modules", ".git", "cache")

    # Timing values (in seconds)
    DEBOUNCE_DELAY: float = 0.3
    REQUEST_TIMEOUT: float = 30.0
    INIT_DELAY: float = 1.0
    DIAGNOSTICS_DELAY: float = 2.0

    # Severity levels
    SEVERITY_ERROR: int = 1
    SEVERITY_WARNING: int = 2
    SEVERITY_INFO: int = 3
    SEVERITY_HINT: int = 4

    # Severity name mapping
    SEVERITY_NAMES: dict[str, int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        """Initialize mutable defaults."""
        object.__setattr__(
            self,
            "SEVERITY_NAMES",
            {
                "error": self.SEVERITY_ERROR,
                "warning": self.SEVERITY_WARNING,
                "info": self.SEVERITY_INFO,
                "hint": self.SEVERITY_HINT,
            },
        )


# Default instances for easy import
COLORS = Colors()
CONSTANTS = Constants()
