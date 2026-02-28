"""MCP Server for Intelephense PHP diagnostics."""

import atexit
import json
import logging
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from mcp.server.fastmcp import FastMCP

from watchdog.observers import Observer

from intelephense_watcher.config.constants import CONSTANTS
from intelephense_watcher.file_handler import PhpFileHandler, scan_php_files
from intelephense_watcher.lsp_client import LspClient
from intelephense_watcher.utils import normalize_uri, path_to_uri, uri_to_path

# Configure logging
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "mcp.log")

# Create logger
logger = logging.getLogger("intelephense-mcp")
logger.setLevel(logging.INFO)

# File handler - writes to mcp.log in project root
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
logger.addHandler(file_handler)

# Stderr handler (for MCP stdio compatibility)
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.WARNING)  # Only warnings and errors to stderr
stderr_handler.setFormatter(logging.Formatter(LOG_FORMAT))
logger.addHandler(stderr_handler)

# Global registry of LSP clients and file observers by project path
_lsp_clients: dict[str, LspClient] = {}
_file_observers: dict[str, Observer] = {}
_clients_lock = threading.Lock()


def get_lsp_client(project_path: str) -> LspClient:
    """Get or create an LSP client for a project.

    Args:
        project_path: Absolute path to the PHP project root.

    Returns:
        An initialized LSP client for the project.

    Raises:
        RuntimeError: If the LSP client fails to start or initialize.
    """
    with _clients_lock:
        if project_path not in _lsp_clients:
            logger.info(f"Creating new LSP client for: {project_path}")
            client = LspClient(project_path)

            if not client.start():
                raise RuntimeError(
                    "Failed to start Intelephense. "
                    "Please ensure it is installed: npm install -g intelephense"
                )

            if not client.initialize():
                client.stop()
                raise RuntimeError("Failed to initialize LSP connection")

            # Index all PHP files
            php_files = scan_php_files(project_path)
            logger.info(f"Indexing {len(php_files)} PHP files...")
            for file_path in php_files:
                client.open_document(file_path)

            # Wait for diagnostics to be ready
            time.sleep(CONSTANTS.DIAGNOSTICS_DELAY)
            logger.info("LSP client ready")

            _lsp_clients[project_path] = client

            # Start file watcher for new/modified/deleted PHP files
            event_handler = PhpFileHandler(client, debounce_delay=CONSTANTS.DEBOUNCE_DELAY)
            observer = Observer()
            observer.schedule(event_handler, project_path, recursive=True)
            observer.daemon = True
            observer.start()
            _file_observers[project_path] = observer
            logger.info(f"File watcher started for: {project_path}")

        return _lsp_clients[project_path]


def cleanup_all_clients() -> None:
    """Stop all file observers and LSP clients on shutdown."""
    with _clients_lock:
        for project_path, observer in _file_observers.items():
            logger.info(f"Stopping file observer for: {project_path}")
            observer.stop()
        for observer in _file_observers.values():
            observer.join(timeout=5)
        _file_observers.clear()

        for project_path, client in _lsp_clients.items():
            logger.info(f"Stopping LSP client for: {project_path}")
            client.stop()
        _lsp_clients.clear()


# Register cleanup with atexit
atexit.register(cleanup_all_clients)

# Create MCP server
mcp = FastMCP("intelephense")


def _severity_to_name(severity: int) -> str:
    """Convert severity number to name."""
    severity_map = {1: "error", 2: "warning", 3: "info", 4: "hint"}
    return severity_map.get(severity, "unknown")


def _severity_to_number(severity_name: str) -> int:
    """Convert severity name to number."""
    return CONSTANTS.SEVERITY_NAMES.get(severity_name.lower(), CONSTANTS.SEVERITY_HINT)


def _format_diagnostics(
    diagnostics: dict[str, list[dict[str, Any]]],
    min_severity: int,
    ignore_unused_underscore: bool = True,
    ignore_patterns: list[str] | None = None,
    workspace_path: str = "",
) -> str:
    """Format diagnostics as a readable string.

    Args:
        diagnostics: Dictionary of URI -> list of diagnostic objects.
        min_severity: Minimum severity level to include (1=error, 4=hint).
        ignore_unused_underscore: Filter out unused $_xxx variable hints.
        ignore_patterns: List of glob patterns to ignore.
        workspace_path: Absolute path to workspace root.

    Returns:
        Formatted string of diagnostics.
    """
    from intelephense_watcher.diagnostics import (
        filter_by_ignore_patterns,
        filter_unused_underscore_variables,
    )

    # Apply ignore patterns filter
    if ignore_patterns and workspace_path:
        diagnostics = filter_by_ignore_patterns(diagnostics, ignore_patterns, workspace_path)

    # Apply underscore filter
    diagnostics = filter_unused_underscore_variables(diagnostics, ignore_unused_underscore)

    lines: list[str] = []

    for uri, diags in sorted(diagnostics.items()):
        file_path = uri_to_path(uri)
        file_diags = [d for d in diags if d.get("severity", 4) <= min_severity]

        if not file_diags:
            continue

        lines.append(f"\n{file_path}:")
        for diag in file_diags:
            start = diag.get("range", {}).get("start", {})
            line_num = start.get("line", 0) + 1
            col = start.get("character", 0) + 1
            severity = _severity_to_name(diag.get("severity", 4))
            message = diag.get("message", "Unknown error")
            lines.append(f"  {line_num}:{col} [{severity}] {message}")

    if not lines:
        return "No diagnostics found."

    total = sum(len(d) for d in diagnostics.values())
    filtered = sum(
        1
        for diags in diagnostics.values()
        for d in diags
        if d.get("severity", 4) <= min_severity
    )
    lines.insert(0, f"Found {filtered} diagnostic(s) (of {total} total):")

    return "\n".join(lines)


def _sync_new_files(client: LspClient, project_path: str) -> list[str]:
    """Detect and index PHP files not yet known to the LSP client.

    Scans the project for all PHP files, compares against the client's
    opened URIs set, and opens+notifies for any new files.

    Args:
        client: The LSP client instance.
        project_path: Absolute path to the project root.

    Returns:
        List of newly indexed file paths.
    """
    current_php_files = scan_php_files(project_path)
    new_files = []

    for fp in current_php_files:
        uri = path_to_uri(fp)
        if uri not in client._opened_uris:
            new_files.append(fp)

    if not new_files:
        return []

    # Send didChangeWatchedFiles for all new files in a batch (type 1 = Created)
    changes = [{"uri": path_to_uri(fp), "type": 1} for fp in new_files]
    client.notify_files_changed(changes)

    # Open each new file in the LSP
    for fp in new_files:
        client.open_document(fp)

    return new_files


@mcp.tool()
def get_diagnostics(
    project_path: str,
    file_path: str | None = None,
    min_severity: str = "hint",
    ignore_unused_underscore: bool = True,
) -> str:
    """Get PHP diagnostics for a project or specific file.

    Args:
        project_path: Absolute path to the PHP project root.
        file_path: Optional specific file to check (returns all if omitted).
        min_severity: Minimum severity level (error, warning, info, hint).
        ignore_unused_underscore: Filter out unused $_xxx variable hints (default: True).

    Returns:
        Formatted string of diagnostics.
    """
    from intelephense_watcher.config.config_file import get_ignore_patterns, load_config_file

    logger.info(
        f"TOOL CALL: get_diagnostics(project_path={project_path!r}, "
        f"file_path={file_path!r}, min_severity={min_severity!r})"
    )
    try:
        # Load config for this project
        config = load_config_file(project_path)
        ignore_patterns = get_ignore_patterns(config)

        client = get_lsp_client(project_path)
        severity_num = _severity_to_number(min_severity)

        # Detect and index any new PHP files not yet known to the LSP
        new_files = _sync_new_files(client, project_path)
        if new_files:
            logger.info(f"Found {len(new_files)} new PHP file(s) to index")

        # Refresh file(s) to get latest diagnostics
        if file_path:
            # Refresh single file (opens it if not yet known to LSP)
            logger.info(f"Refreshing file: {file_path}")
            client.ensure_document_open(file_path)
        else:
            # Refresh all PHP files in project
            logger.info("Refreshing all PHP files...")
            php_files = scan_php_files(project_path)
            for fp in php_files:
                client.ensure_document_open(fp)

        # Wait for LSP to process; extra time if new files were indexed
        delay = CONSTANTS.DIAGNOSTICS_DELAY
        if new_files:
            delay += CONSTANTS.NEW_FILE_EXTRA_DELAY
        time.sleep(delay)

        with client.diagnostics_lock:
            # Log all diagnostics for debugging
            logger.info(f"Total files with diagnostics: {len(client.diagnostics)}")
            for uri, diags in client.diagnostics.items():
                logger.info(f"  {uri}: {len(diags)} diagnostic(s)")

            if file_path:
                target_uri = normalize_uri(path_to_uri(file_path))
                logger.info(f"Looking for target URI: {target_uri}")
                filtered = {
                    uri: diags
                    for uri, diags in client.diagnostics.items()
                    if normalize_uri(uri) == target_uri
                }
            else:
                filtered = dict(client.diagnostics)

        return _format_diagnostics(
            filtered, severity_num, ignore_unused_underscore, ignore_patterns, project_path
        )

    except Exception as e:
        logger.exception("Error getting diagnostics")
        return f"Error: {e}"


@mcp.tool()
def find_references(
    project_path: str, file_path: str, line: int, column: int
) -> str:
    """Find all references to a symbol at a specific position.

    Args:
        project_path: Absolute path to the PHP project root.
        file_path: Absolute path to the PHP file.
        line: 0-indexed line number.
        column: 0-indexed column number.

    Returns:
        Formatted list of reference locations or error message.
    """
    logger.info(
        f"TOOL CALL: find_references(project_path={project_path!r}, "
        f"file_path={file_path!r}, line={line}, column={column})"
    )
    try:
        client = get_lsp_client(project_path)

        refs = client.find_references(file_path, line, column)
        if not refs:
            return "No references found."

        lines = [f"Found {len(refs)} reference(s):"]
        for ref in refs:
            ref_path = uri_to_path(ref["uri"])
            start = ref["range"]["start"]
            ref_line = start["line"] + 1
            ref_col = start["character"] + 1
            lines.append(f"  {ref_path}:{ref_line}:{ref_col}")

        return "\n".join(lines)

    except Exception as e:
        logger.exception("Error finding references")
        return f"Error: {e}"


@mcp.tool()
def get_capabilities(project_path: str) -> str:
    """Get LSP server capabilities for a project.

    Args:
        project_path: Absolute path to the PHP project root.

    Returns:
        JSON string of server capabilities.
    """
    import json

    logger.info(f"TOOL CALL: get_capabilities(project_path={project_path!r})")
    try:
        client = get_lsp_client(project_path)
        return json.dumps(client.server_capabilities, indent=2)

    except Exception as e:
        logger.exception("Error getting capabilities")
        return f"Error: {e}"


@mcp.tool()
def go_to_definition(
    project_path: str, file_path: str, line: int, column: int
) -> str:
    """Go to definition of symbol at position.

    Args:
        project_path: Absolute path to PHP project root.
        file_path: Absolute path to PHP file.
        line: 0-indexed line number.
        column: 0-indexed column number.

    Returns:
        Definition location(s) or error message.
    """
    logger.info(
        f"TOOL CALL: go_to_definition(project_path={project_path!r}, "
        f"file_path={file_path!r}, line={line}, column={column})"
    )
    try:
        client = get_lsp_client(project_path)

        result = client.go_to_definition(file_path, line, column)
        if not result:
            return "No definition found."

        # Handle single Location or list of Locations
        locations = result if isinstance(result, list) else [result]

        lines = [f"Found {len(locations)} definition(s):"]
        for loc in locations:
            loc_path = uri_to_path(loc["uri"])
            start = loc["range"]["start"]
            loc_line = start["line"] + 1
            loc_col = start["character"] + 1
            lines.append(f"  {loc_path}:{loc_line}:{loc_col}")

        return "\n".join(lines)

    except Exception as e:
        logger.exception("Error going to definition")
        return f"Error: {e}"


@mcp.tool()
def get_hover(
    project_path: str, file_path: str, line: int, column: int
) -> str:
    """Get hover information (documentation, type) for symbol.

    Args:
        project_path: Absolute path to PHP project root.
        file_path: Absolute path to PHP file.
        line: 0-indexed line number.
        column: 0-indexed column number.

    Returns:
        Hover content or error message.
    """
    logger.info(
        f"TOOL CALL: get_hover(project_path={project_path!r}, "
        f"file_path={file_path!r}, line={line}, column={column})"
    )
    try:
        client = get_lsp_client(project_path)

        result = client.get_hover(file_path, line, column)
        if not result:
            return "No hover information available."

        contents = result.get("contents", {})

        # Handle MarkupContent
        if isinstance(contents, dict):
            return contents.get("value", str(contents))

        # Handle MarkedString or array of MarkedString
        if isinstance(contents, list):
            parts = []
            for item in contents:
                if isinstance(item, dict):
                    parts.append(item.get("value", str(item)))
                else:
                    parts.append(str(item))
            return "\n\n".join(parts)

        return str(contents)

    except Exception as e:
        logger.exception("Error getting hover")
        return f"Error: {e}"


def _symbol_kind_name(kind: int) -> str:
    """Convert symbol kind number to name."""
    kinds = {
        1: "File", 2: "Module", 3: "Namespace", 4: "Package",
        5: "Class", 6: "Method", 7: "Property", 8: "Field",
        9: "Constructor", 10: "Enum", 11: "Interface", 12: "Function",
        13: "Variable", 14: "Constant", 15: "String", 16: "Number",
        17: "Boolean", 18: "Array", 19: "Object", 20: "Key",
        21: "Null", 22: "EnumMember", 23: "Struct", 24: "Event",
        25: "Operator", 26: "TypeParameter",
    }
    return kinds.get(kind, f"Kind{kind}")


def _format_document_symbols(symbols: list[dict], indent: int = 0) -> list[str]:
    """Format document symbols recursively."""
    lines = []
    prefix = "  " * indent

    for sym in symbols:
        name = sym.get("name", "?")
        kind = _symbol_kind_name(sym.get("kind", 0))

        # Get location info
        if "range" in sym:
            start = sym["range"]["start"]
            line_num = start["line"] + 1
            lines.append(f"{prefix}{kind}: {name} (line {line_num})")
        elif "location" in sym:
            start = sym["location"]["range"]["start"]
            line_num = start["line"] + 1
            lines.append(f"{prefix}{kind}: {name} (line {line_num})")
        else:
            lines.append(f"{prefix}{kind}: {name}")

        # Handle children (DocumentSymbol format)
        if "children" in sym:
            lines.extend(_format_document_symbols(sym["children"], indent + 1))

    return lines


@mcp.tool()
def get_document_symbols(project_path: str, file_path: str) -> str:
    """Get all symbols (classes, functions, variables) in a PHP file.

    Args:
        project_path: Absolute path to PHP project root.
        file_path: Absolute path to PHP file.

    Returns:
        Hierarchical list of symbols or error message.
    """
    logger.info(
        f"TOOL CALL: get_document_symbols(project_path={project_path!r}, "
        f"file_path={file_path!r})"
    )
    try:
        client = get_lsp_client(project_path)

        result = client.get_document_symbols(file_path)
        if not result:
            return "No symbols found in document."

        lines = [f"Found {len(result)} top-level symbol(s):"]
        lines.extend(_format_document_symbols(result))

        return "\n".join(lines)

    except Exception as e:
        logger.exception("Error getting document symbols")
        return f"Error: {e}"


@mcp.tool()
def search_symbols(project_path: str, query: str) -> str:
    """Search for symbols across the workspace.

    Args:
        project_path: Absolute path to PHP project root.
        query: Search query (partial name match).

    Returns:
        List of matching symbols with locations.
    """
    logger.info(
        f"TOOL CALL: search_symbols(project_path={project_path!r}, query={query!r})"
    )
    try:
        client = get_lsp_client(project_path)

        result = client.search_symbols(query)
        if not result:
            return f"No symbols found matching '{query}'."

        lines = [f"Found {len(result)} symbol(s) matching '{query}':"]
        for sym in result:
            name = sym.get("name", "?")
            kind = _symbol_kind_name(sym.get("kind", 0))
            loc = sym.get("location", {})
            loc_path = uri_to_path(loc.get("uri", ""))
            start = loc.get("range", {}).get("start", {})
            line_num = start.get("line", 0) + 1
            lines.append(f"  {kind}: {name} - {loc_path}:{line_num}")

        return "\n".join(lines)

    except Exception as e:
        logger.exception("Error searching symbols")
        return f"Error: {e}"


@mcp.tool()
def reindex(project_path: str) -> str:
    """Force re-index all PHP files in the workspace.

    Scans for all PHP files, notifies the LSP about any new or removed files,
    and refreshes all open documents. Use after bulk file operations.

    Args:
        project_path: Absolute path to the PHP project root.

    Returns:
        Summary of reindexing results.
    """
    logger.info(f"TOOL CALL: reindex(project_path={project_path!r})")
    try:
        client = get_lsp_client(project_path)

        # Scan current PHP files
        current_files = scan_php_files(project_path)
        current_uris = {path_to_uri(fp) for fp in current_files}

        # Find new files (on disk but not opened in LSP)
        new_files = [fp for fp in current_files if path_to_uri(fp) not in client._opened_uris]

        # Find removed files (opened in LSP but no longer on disk)
        removed_uris = client._opened_uris - current_uris

        # Build batch notification
        changes: list[dict[str, Any]] = []
        for fp in new_files:
            changes.append({"uri": path_to_uri(fp), "type": 1})  # Created
        for uri in removed_uris:
            changes.append({"uri": uri, "type": 3})  # Deleted

        if changes:
            client.notify_files_changed(changes)

        # Open new files
        for fp in new_files:
            client.open_document(fp)

        # Close removed files
        for uri in removed_uris:
            file_path = uri_to_path(uri)
            client.close_document(file_path)

        # Refresh all existing open files
        for fp in current_files:
            if path_to_uri(fp) not in {path_to_uri(f) for f in new_files}:
                client.change_document(fp)

        time.sleep(CONSTANTS.DIAGNOSTICS_DELAY + CONSTANTS.NEW_FILE_EXTRA_DELAY)

        return (
            f"Reindex complete: {len(current_files)} total files, "
            f"{len(new_files)} new, {len(removed_uris)} removed."
        )

    except Exception as e:
        logger.exception("Error during reindex")
        return f"Error: {e}"


class DiagnosticsHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for diagnostics endpoint."""

    def log_message(self, format: str, *args: Any) -> None:
        """Route HTTP server logs to our logger instead of stderr."""
        logger.info(f"HTTP: {format % args}")

    def do_POST(self) -> None:
        """Handle POST requests."""
        if self.path != "/diagnostics":
            self._send_json(404, {"error": f"Not found: {self.path}"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            params = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError) as e:
            self._send_json(400, {"error": f"Invalid JSON: {e}"})
            return

        project_path = params.get("project_path", "")
        file_path = params.get("file_path")
        min_severity = params.get("min_severity", "warning")

        if not project_path:
            self._send_json(400, {"error": "project_path is required"})
            return

        logger.info(
            f"HTTP diagnostics request: project={project_path!r}, "
            f"file={file_path!r}, severity={min_severity!r}"
        )

        try:
            output = get_diagnostics(
                project_path=project_path,
                file_path=file_path,
                min_severity=min_severity,
            )

            has_errors = "[error]" in output.lower()
            has_warnings = "[warning]" in output.lower()

            self._send_json(200, {
                "diagnostics": output,
                "has_errors": has_errors,
                "has_warnings": has_warnings,
                "output": output,
            })
        except Exception as e:
            logger.exception("HTTP diagnostics error")
            self._send_json(500, {"error": str(e)})

    def _send_json(self, status: int, data: dict) -> None:
        """Send a JSON response."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _start_http_server() -> HTTPServer | None:
    """Start the HTTP diagnostics server in a daemon thread.

    Returns:
        The HTTPServer instance, or None if it failed to start.
    """
    port = int(os.environ.get("INTELEPHENSE_HTTP_PORT", "19850"))

    try:
        server = HTTPServer(("127.0.0.1", port), DiagnosticsHTTPHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"HTTP diagnostics server listening on http://127.0.0.1:{port}")
        return server
    except OSError as e:
        logger.warning(f"Failed to start HTTP server on port {port}: {e}")
        return None


def main() -> None:
    """Run the MCP server."""
    logger.info("=" * 60)
    logger.info("MCP SERVER STARTING")
    logger.info(f"Log file: {LOG_FILE}")
    logger.info(f"Process ID: {os.getpid()}")
    logger.info("Waiting for Claude Code connection...")
    logger.info("=" * 60)

    # Start HTTP diagnostics server in background
    http_server = _start_http_server()

    mcp.run(transport="stdio")

    # Cleanup HTTP server on exit
    if http_server:
        http_server.shutdown()


if __name__ == "__main__":
    main()
