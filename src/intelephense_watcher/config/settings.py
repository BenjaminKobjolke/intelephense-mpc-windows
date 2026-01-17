"""Runtime settings for Intelephense Watcher."""

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    """Runtime settings configured from CLI and environment."""

    workspace_path: str = ""
    min_severity: int = 4  # Default: show all (hint and above)
    timeout: int | None = None  # None = watch forever, int = seconds
    output_file: str | None = None  # None = console, str = file path
    debug: bool = field(default_factory=lambda: os.environ.get("DEBUG", "").lower() in ("1", "true"))
    request_timeout: float = field(
        default_factory=lambda: float(os.environ.get("LSP_TIMEOUT", "30"))
    )

    def __post_init__(self) -> None:
        """Validate and normalize settings."""
        if self.workspace_path:
            self.workspace_path = os.path.abspath(self.workspace_path)
