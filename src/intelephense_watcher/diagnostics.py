"""Diagnostics display for terminal output."""

import os
from typing import Any

from intelephense_watcher.config.constants import COLORS, CONSTANTS
from intelephense_watcher.utils import uri_to_path


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


class DiagnosticsDisplay:
    """Handles pretty-printing of diagnostics."""

    SEVERITY_MAP: dict[int, tuple[str, str]] = {
        CONSTANTS.SEVERITY_ERROR: ("Error", COLORS.RED),
        CONSTANTS.SEVERITY_WARNING: ("Warning", COLORS.YELLOW),
        CONSTANTS.SEVERITY_INFO: ("Info", COLORS.BLUE),
        CONSTANTS.SEVERITY_HINT: ("Hint", COLORS.CYAN),
    }

    def __init__(self, workspace_path: str, min_severity: int = 4):
        self.workspace_path = os.path.abspath(workspace_path)
        self.min_severity = min_severity

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

        # Filter diagnostics by severity
        filtered_diagnostics = filter_diagnostics_by_severity(diagnostics, self.min_severity)

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

        # Filter diagnostics by severity
        filtered_diagnostics = filter_diagnostics_by_severity(diagnostics, self.min_severity)

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
