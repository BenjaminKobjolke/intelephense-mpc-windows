"""Diagnostics display for terminal output."""

import csv
import fnmatch
import io
import os
import re
from typing import Any

from intelephense_watcher.config.constants import COLORS, CONSTANTS
from intelephense_watcher.utils import uri_to_path

# Pattern to match unused underscore-prefixed symbol hints
# e.g., "Symbol '$_response' is declared but not used." (variable)
# e.g., "Symbol '_createFriendship' is declared but not used." (method/function)
# The \$? makes the dollar sign optional to match both variables and methods
UNUSED_UNDERSCORE_SYMBOL_PATTERN = re.compile(
    r"^Symbol '\$?_[^']*' is declared but not used\.$"
)

# Pattern to match unused underscore-prefixed function/method hints
# e.g., "Method '_createFriendship' is declared but never used."
# e.g., "Function '_myHelper' is declared but never used."
UNUSED_UNDERSCORE_FUNC_PATTERN = re.compile(
    r"^(?:Method|Function) '_[^']*' is declared but never used\.$"
)

# Keep old name as alias for backward compatibility
UNUSED_UNDERSCORE_VAR_PATTERN = UNUSED_UNDERSCORE_SYMBOL_PATTERN


def filter_diagnostics_by_severity(
    diagnostics: dict[str, list[dict[str, Any]]], min_severity: int
) -> dict[str, list[dict[str, Any]]]:
    """Filter diagnostics to only include those at or above minimum severity.

    Args:
        diagnostics: Dictionary mapping URIs to lists of diagnostic objects.
        min_severity: Maximum severity level to include (1=Error, 4=Hint).

    Returns:
        Filtered diagnostics dictionary.
    """
    filtered: dict[str, list[dict[str, Any]]] = {}
    for uri, diags in diagnostics.items():
        filtered_diags = [d for d in diags if d.get("severity", 1) <= min_severity]
        if filtered_diags:
            filtered[uri] = filtered_diags
    return filtered


def _is_unused_underscore_symbol(diagnostic: dict[str, Any]) -> bool:
    """Check if diagnostic is an unused underscore-prefixed symbol hint.

    This matches:
    - Variables: "Symbol '$_response' is declared but not used."
    - Methods as Symbol: "Symbol '_createFriendship' is declared but not used."
    - Methods: "Method '_createFriendship' is declared but never used."
    - Functions: "Function '_myHelper' is declared but never used."

    Args:
        diagnostic: A diagnostic object from the LSP.

    Returns:
        True if this is an unused hint for an underscore-prefixed symbol.
    """
    # Only apply to hints (severity 4)
    if diagnostic.get("severity", 1) != CONSTANTS.SEVERITY_HINT:
        return False
    message = diagnostic.get("message", "")
    return bool(
        UNUSED_UNDERSCORE_SYMBOL_PATTERN.match(message)
        or UNUSED_UNDERSCORE_FUNC_PATTERN.match(message)
    )


# Keep the old function name as an alias for backward compatibility
_is_unused_underscore_variable = _is_unused_underscore_symbol


def filter_unused_underscore_variables(
    diagnostics: dict[str, list[dict[str, Any]]],
    enabled: bool = True,
) -> dict[str, list[dict[str, Any]]]:
    """Filter out unused hints for underscore-prefixed symbols.

    This filters hints for intentionally unused symbols:
    - Variables: "Symbol '$_response' is declared but not used."
    - Methods: "Method '_createFriendship' is declared but never used."
    - Functions: "Function '_myHelper' is declared but never used."

    The underscore prefix indicates the symbol is intentionally unused.

    Args:
        diagnostics: Dictionary mapping URIs to lists of diagnostic objects.
        enabled: Whether filtering is enabled (False = return unchanged).

    Returns:
        Filtered diagnostics dictionary.
    """
    if not enabled:
        return diagnostics

    filtered: dict[str, list[dict[str, Any]]] = {}
    for uri, diags in diagnostics.items():
        filtered_diags = [d for d in diags if not _is_unused_underscore_symbol(d)]
        if filtered_diags:
            filtered[uri] = filtered_diags
    return filtered


def filter_by_ignore_patterns(
    diagnostics: dict[str, list[dict[str, Any]]],
    ignore_patterns: list[str],
    workspace_path: str,
) -> dict[str, list[dict[str, Any]]]:
    """Filter out diagnostics from paths matching ignore patterns.

    Args:
        diagnostics: Dictionary mapping URIs to lists of diagnostic objects.
        ignore_patterns: List of glob patterns to ignore (e.g., "vendor/**").
        workspace_path: Absolute path to the workspace root.

    Returns:
        Filtered diagnostics dictionary with ignored paths removed.
    """
    if not ignore_patterns:
        return diagnostics

    filtered: dict[str, list[dict[str, Any]]] = {}
    for uri, diags in diagnostics.items():
        file_path = uri_to_path(uri)
        rel_path = os.path.relpath(file_path, workspace_path)
        # Normalize to forward slashes for pattern matching
        rel_path = rel_path.replace("\\", "/")

        # Check if path matches any ignore pattern
        if not any(fnmatch.fnmatch(rel_path, p) for p in ignore_patterns):
            filtered[uri] = diags

    return filtered


class DiagnosticsDisplay:
    """Handles pretty-printing of diagnostics."""

    SEVERITY_MAP: dict[int, tuple[str, str]] = {
        CONSTANTS.SEVERITY_ERROR: ("Error", COLORS.RED),
        CONSTANTS.SEVERITY_WARNING: ("Warning", COLORS.YELLOW),
        CONSTANTS.SEVERITY_INFO: ("Info", COLORS.BLUE),
        CONSTANTS.SEVERITY_HINT: ("Hint", COLORS.CYAN),
    }

    def __init__(
        self,
        workspace_path: str,
        min_severity: int = 4,
        ignore_unused_underscore: bool = True,
        ignore_patterns: list[str] | None = None,
    ):
        self.workspace_path = os.path.abspath(workspace_path)
        self.min_severity = min_severity
        self.ignore_unused_underscore = ignore_unused_underscore
        self.ignore_patterns = ignore_patterns or []

    def display(self, diagnostics: dict[str, list[dict[str, Any]]]) -> None:
        """Display all diagnostics filtered by minimum severity."""
        # Clear screen and move cursor to top
        print("\033[2J\033[H", end="")

        print(f"{COLORS.BOLD}=== PHP Diagnostics ==={COLORS.RESET}")
        print(f"Watching: {self.workspace_path}")

        # Get filter name from severity level
        filter_name = next(
            (k for k, v in CONSTANTS.SEVERITY_NAMES.items() if v == self.min_severity),
            "unknown",
        )
        print(f"Filter: {filter_name} and above")
        print("-" * 60)

        # Apply filters
        filtered_diagnostics = filter_diagnostics_by_severity(diagnostics, self.min_severity)
        filtered_diagnostics = filter_by_ignore_patterns(
            filtered_diagnostics, self.ignore_patterns, self.workspace_path
        )
        filtered_diagnostics = filter_unused_underscore_variables(
            filtered_diagnostics, self.ignore_unused_underscore
        )

        if not filtered_diagnostics:
            print(f"{COLORS.GREEN}No issues found!{COLORS.RESET}")
            print("-" * 60)
            print("Press Ctrl+C to exit")
            return

        total_errors = 0
        total_warnings = 0
        total_info = 0
        total_hints = 0

        for uri, diags in sorted(filtered_diagnostics.items()):
            file_path = uri_to_path(uri)
            rel_path = os.path.relpath(file_path, self.workspace_path)

            print(f"\n{COLORS.BOLD}{rel_path}{COLORS.RESET}")

            for diag in sorted(
                diags, key=lambda d: d.get("range", {}).get("start", {}).get("line", 0)
            ):
                severity = diag.get("severity", 1)
                severity_name, color = self.SEVERITY_MAP.get(severity, ("Unknown", COLORS.RESET))

                if severity == CONSTANTS.SEVERITY_ERROR:
                    total_errors += 1
                elif severity == CONSTANTS.SEVERITY_WARNING:
                    total_warnings += 1
                elif severity == CONSTANTS.SEVERITY_INFO:
                    total_info += 1
                elif severity == CONSTANTS.SEVERITY_HINT:
                    total_hints += 1

                start = diag.get("range", {}).get("start", {})
                line = start.get("line", 0) + 1  # LSP lines are 0-indexed
                col = start.get("character", 0) + 1
                message = diag.get("message", "Unknown error")

                print(f"  {color}{severity_name}{COLORS.RESET} [{line}:{col}]: {message}")

        print("\n" + "-" * 60)
        summary_parts = []
        if total_errors:
            summary_parts.append(f"{COLORS.RED}{total_errors} error(s){COLORS.RESET}")
        if total_warnings:
            summary_parts.append(f"{COLORS.YELLOW}{total_warnings} warning(s){COLORS.RESET}")
        if total_info:
            summary_parts.append(f"{COLORS.BLUE}{total_info} info{COLORS.RESET}")
        if total_hints:
            summary_parts.append(f"{COLORS.CYAN}{total_hints} hint(s){COLORS.RESET}")

        if summary_parts:
            print("Summary: " + ", ".join(summary_parts))
        print("Press Ctrl+C to exit")

    def format_plain(self, diagnostics: dict[str, list[dict[str, Any]]]) -> str:
        """Format diagnostics as plain text without ANSI codes.

        Args:
            diagnostics: Dictionary mapping URIs to lists of diagnostic objects.

        Returns:
            Plain text string suitable for file output.
        """
        lines: list[str] = []
        lines.append("=== PHP Diagnostics ===")
        lines.append(f"Workspace: {self.workspace_path}")

        # Get filter name from severity level
        filter_name = next(
            (k for k, v in CONSTANTS.SEVERITY_NAMES.items() if v == self.min_severity),
            "unknown",
        )
        lines.append(f"Filter: {filter_name} and above")
        lines.append("-" * 60)

        # Apply filters
        filtered_diagnostics = filter_diagnostics_by_severity(diagnostics, self.min_severity)
        filtered_diagnostics = filter_by_ignore_patterns(
            filtered_diagnostics, self.ignore_patterns, self.workspace_path
        )
        filtered_diagnostics = filter_unused_underscore_variables(
            filtered_diagnostics, self.ignore_unused_underscore
        )

        if not filtered_diagnostics:
            lines.append("No issues found!")
            lines.append("-" * 60)
            return "\n".join(lines)

        total_errors = 0
        total_warnings = 0
        total_info = 0
        total_hints = 0

        for uri, diags in sorted(filtered_diagnostics.items()):
            file_path = uri_to_path(uri)
            rel_path = os.path.relpath(file_path, self.workspace_path)

            lines.append(f"\n{rel_path}")

            for diag in sorted(
                diags, key=lambda d: d.get("range", {}).get("start", {}).get("line", 0)
            ):
                severity = diag.get("severity", 1)
                severity_name = self.SEVERITY_MAP.get(severity, ("Unknown", ""))[0]

                if severity == CONSTANTS.SEVERITY_ERROR:
                    total_errors += 1
                elif severity == CONSTANTS.SEVERITY_WARNING:
                    total_warnings += 1
                elif severity == CONSTANTS.SEVERITY_INFO:
                    total_info += 1
                elif severity == CONSTANTS.SEVERITY_HINT:
                    total_hints += 1

                start = diag.get("range", {}).get("start", {})
                line = start.get("line", 0) + 1  # LSP lines are 0-indexed
                col = start.get("character", 0) + 1
                message = diag.get("message", "Unknown error")

                lines.append(f"  {severity_name} [{line}:{col}]: {message}")

        lines.append("\n" + "-" * 60)
        summary_parts = []
        if total_errors:
            summary_parts.append(f"{total_errors} error(s)")
        if total_warnings:
            summary_parts.append(f"{total_warnings} warning(s)")
        if total_info:
            summary_parts.append(f"{total_info} info")
        if total_hints:
            summary_parts.append(f"{total_hints} hint(s)")

        if summary_parts:
            lines.append("Summary: " + ", ".join(summary_parts))

        return "\n".join(lines)

    def format_csv(self, diagnostics: dict[str, list[dict[str, Any]]]) -> str:
        """Format diagnostics as CSV string.

        Columns: file,line,column,severity,message

        Args:
            diagnostics: Dictionary mapping URIs to lists of diagnostic objects.

        Returns:
            CSV formatted string with headers.
        """
        # Apply filters
        filtered_diagnostics = filter_diagnostics_by_severity(diagnostics, self.min_severity)
        filtered_diagnostics = filter_by_ignore_patterns(
            filtered_diagnostics, self.ignore_patterns, self.workspace_path
        )
        filtered_diagnostics = filter_unused_underscore_variables(
            filtered_diagnostics, self.ignore_unused_underscore
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["file", "line", "column", "severity", "message"])

        for uri, diags in sorted(filtered_diagnostics.items()):
            file_path = uri_to_path(uri)
            rel_path = os.path.relpath(file_path, self.workspace_path)
            # Normalize path separators
            rel_path = rel_path.replace("\\", "/")

            for diag in sorted(
                diags, key=lambda d: d.get("range", {}).get("start", {}).get("line", 0)
            ):
                severity = diag.get("severity", 1)
                severity_name = self.SEVERITY_MAP.get(severity, ("Unknown", ""))[0].lower()

                start = diag.get("range", {}).get("start", {})
                line = start.get("line", 0) + 1  # LSP lines are 0-indexed
                col = start.get("character", 0) + 1
                message = diag.get("message", "Unknown error")

                writer.writerow([rel_path, line, col, severity_name, message])

        return output.getvalue()
