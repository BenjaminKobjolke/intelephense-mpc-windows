"""Intelephense LSP Watcher - Watch PHP files and display diagnostics in real-time."""

__version__ = "1.0.0"

from intelephense_watcher.api import Diagnostic, get_diagnostics
from intelephense_watcher.diagnostics import DiagnosticsDisplay

__all__ = ["Diagnostic", "get_diagnostics", "DiagnosticsDisplay"]
