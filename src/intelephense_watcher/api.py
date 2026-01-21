"""Library API for programmatic access to Intelephense diagnostics."""

import time
from dataclasses import dataclass
from typing import Any

from intelephense_watcher.config.constants import CONSTANTS
from intelephense_watcher.diagnostics import (
    filter_by_ignore_patterns,
    filter_diagnostics_by_severity,
    filter_unused_underscore_variables,
)
from intelephense_watcher.file_handler import scan_php_files
from intelephense_watcher.lsp_client import LspClient
from intelephense_watcher.utils import uri_to_path


@dataclass
class Diagnostic:
    """Represents a single diagnostic from Intelephense."""

    file_path: str  # Relative path from workspace
    line: int  # 1-indexed
    column: int  # 1-indexed
    severity: str  # "error", "warning", "info", "hint"
    message: str


def _severity_to_name(severity: int) -> str:
    """Convert severity number to name."""
    severity_map = {1: "error", 2: "warning", 3: "info", 4: "hint"}
    return severity_map.get(severity, "unknown")


def _severity_to_number(severity_name: str) -> int:
    """Convert severity name to number."""
    return CONSTANTS.SEVERITY_NAMES.get(severity_name.lower(), CONSTANTS.SEVERITY_HINT)


def _convert_to_diagnostics(
    raw_diagnostics: dict[str, list[dict[str, Any]]],
    workspace_path: str,
) -> list[Diagnostic]:
    """Convert raw LSP diagnostics to Diagnostic objects.

    Args:
        raw_diagnostics: Dictionary mapping URIs to lists of diagnostic objects.
        workspace_path: Absolute path to the workspace root.

    Returns:
        List of Diagnostic objects.
    """
    import os

    results: list[Diagnostic] = []

    for uri, diags in raw_diagnostics.items():
        file_path = uri_to_path(uri)
        try:
            rel_path = os.path.relpath(file_path, workspace_path)
        except ValueError:
            rel_path = file_path

        for diag in diags:
            start = diag.get("range", {}).get("start", {})
            line = start.get("line", 0) + 1  # Convert to 1-indexed
            column = start.get("character", 0) + 1  # Convert to 1-indexed
            severity = _severity_to_name(diag.get("severity", 4))
            message = diag.get("message", "Unknown error")

            results.append(
                Diagnostic(
                    file_path=rel_path.replace("\\", "/"),
                    line=line,
                    column=column,
                    severity=severity,
                    message=message,
                )
            )

    return results


def get_diagnostics(
    project_path: str,
    min_severity: str = "hint",
    ignore_unused_underscore: bool = True,
    ignore_patterns: list[str] | None = None,
    timeout: float = 3.0,
) -> list[Diagnostic]:
    """Get PHP diagnostics for a project.

    This function creates an LSP client, indexes all PHP files in the project,
    collects diagnostics, and returns them as structured Diagnostic objects.

    Args:
        project_path: Absolute path to the PHP project root.
        min_severity: Minimum severity level to include ("error", "warning", "info", "hint").
        ignore_unused_underscore: Filter out unused $_xxx variable hints (default: True).
        ignore_patterns: List of glob patterns to ignore (e.g., ["vendor/**", "node_modules/**"]).
        timeout: Time to wait for diagnostics after indexing (default: 3.0 seconds).

    Returns:
        List of Diagnostic objects containing file path, line, column, severity, and message.

    Raises:
        RuntimeError: If the LSP client fails to start or initialize.
    """
    import os

    # Normalize project path
    project_path = os.path.abspath(project_path)

    # Create and initialize LSP client
    client = LspClient(project_path)

    try:
        if not client.start():
            raise RuntimeError(
                "Failed to start Intelephense. "
                "Please ensure it is installed: npm install -g intelephense"
            )

        if not client.initialize():
            raise RuntimeError("Failed to initialize LSP connection")

        # Index all PHP files
        php_files = scan_php_files(project_path)
        for file_path in php_files:
            client.open_document(file_path)

        # Wait for diagnostics to be ready
        time.sleep(timeout)

        # Get diagnostics with lock
        with client.diagnostics_lock:
            raw_diagnostics = dict(client.diagnostics)

        # Apply filters
        severity_num = _severity_to_number(min_severity)
        filtered = filter_diagnostics_by_severity(raw_diagnostics, severity_num)
        if ignore_patterns:
            filtered = filter_by_ignore_patterns(filtered, ignore_patterns, project_path)
        filtered = filter_unused_underscore_variables(filtered, ignore_unused_underscore)

        # Convert to Diagnostic objects
        return _convert_to_diagnostics(filtered, project_path)

    finally:
        # Always clean up the client
        client.stop()
