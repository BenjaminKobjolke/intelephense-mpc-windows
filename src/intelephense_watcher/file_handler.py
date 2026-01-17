"""File system event handler for PHP file watching."""

import os
import threading
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler

from intelephense_watcher.config.constants import CONSTANTS
from intelephense_watcher.lsp_client import LspClient


def is_php_file(path: str) -> bool:
    """Check if the path is a PHP file.

    Args:
        path: File path to check.

    Returns:
        True if the file has a PHP extension.
    """
    return any(path.lower().endswith(ext) for ext in CONSTANTS.PHP_EXTENSIONS)


def scan_php_files(directory: str) -> list[str]:
    """Recursively find all PHP files in a directory.

    Args:
        directory: Root directory to scan.

    Returns:
        List of absolute paths to PHP files.
    """
    php_files: list[str] = []
    for root, dirs, files in os.walk(directory):
        # Skip common vendor/cache directories
        dirs[:] = [d for d in dirs if d not in CONSTANTS.SKIP_DIRECTORIES]
        for file in files:
            if is_php_file(file):
                php_files.append(os.path.join(root, file))
    return php_files


class PhpFileHandler(FileSystemEventHandler):
    """Watches for PHP file changes."""

    def __init__(self, lsp_client: LspClient, debounce_delay: float = 0.3):
        self.lsp_client = lsp_client
        self.debounce_delay = debounce_delay
        self.debounce_timers: dict[str, threading.Timer] = {}
        self.lock = threading.Lock()

    def _debounced_action(self, path: str, action: Callable[[], None]) -> None:
        """Debounce file change events."""
        with self.lock:
            if path in self.debounce_timers:
                self.debounce_timers[path].cancel()

            timer = threading.Timer(self.debounce_delay, action)
            self.debounce_timers[path] = timer
            timer.start()

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if event.is_directory or not is_php_file(str(event.src_path)):
            return
        self._debounced_action(
            str(event.src_path), lambda: self.lsp_client.open_document(str(event.src_path))
        )

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if event.is_directory or not is_php_file(str(event.src_path)):
            return
        self._debounced_action(
            str(event.src_path), lambda: self.lsp_client.change_document(str(event.src_path))
        )

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion events."""
        if event.is_directory or not is_php_file(str(event.src_path)):
            return
        self.lsp_client.close_document(str(event.src_path))
