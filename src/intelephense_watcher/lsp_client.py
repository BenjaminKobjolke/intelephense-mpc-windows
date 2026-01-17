"""LSP client for communicating with Intelephense."""

import json
import os
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Optional

from intelephense_watcher.config.constants import COLORS, CONSTANTS
from intelephense_watcher.utils.uri import normalize_uri, path_to_uri, uri_to_path

# Re-export for backwards compatibility
__all__ = ["LspClient", "path_to_uri", "uri_to_path", "normalize_uri"]


class LspClient:
    """LSP client for communicating with Intelephense."""

    def __init__(self, workspace_path: str, request_timeout: float = 30.0):
        self.workspace_path = os.path.abspath(workspace_path)
        self.request_timeout = request_timeout
        self.process: Optional[subprocess.Popen[bytes]] = None
        self.request_id = 0
        self.pending_requests: dict[int, threading.Event] = {}
        self.responses: dict[int, Any] = {}
        self.lock = threading.Lock()
        self.reader_thread: Optional[threading.Thread] = None
        self.running = False
        self.diagnostics: dict[str, list[dict[str, Any]]] = {}
        self.diagnostics_lock = threading.Lock()
        self.on_diagnostics_updated: Optional[Callable[[], None]] = None
        self.server_capabilities: dict[str, Any] = {}

    def start(self) -> bool:
        """Start the Intelephense process."""
        try:
            # On Windows, use shell=True to find .cmd scripts in PATH
            use_shell = os.name == "nt"
            self.process = subprocess.Popen(
                list(CONSTANTS.LSP_COMMAND),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                shell=use_shell,
            )
            self.running = True
            self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self.reader_thread.start()
            return True
        except FileNotFoundError:
            print(f"{COLORS.RED}Error: intelephense not found.{COLORS.RESET}", file=sys.stderr)
            print("Please install it with: npm install -g intelephense", file=sys.stderr)
            return False

    def stop(self) -> None:
        """Stop the LSP client."""
        self.running = False
        if self.process:
            self.process.terminate()
            self.process.wait()

    def _send_message(self, message: dict[str, Any]) -> None:
        """Send a JSON-RPC message to the LSP server."""
        if not self.process or not self.process.stdin:
            return

        content = json.dumps(message)
        header = f"Content-Length: {len(content)}\r\n\r\n"
        full_message = header + content

        try:
            self.process.stdin.write(full_message.encode("utf-8"))
            self.process.stdin.flush()
        except (BrokenPipeError, OSError):
            self.running = False

    def send_request(self, method: str, params: dict[str, Any]) -> Optional[Any]:
        """Send a request and wait for response."""
        with self.lock:
            self.request_id += 1
            req_id = self.request_id
            event = threading.Event()
            self.pending_requests[req_id] = event

        message = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }
        self._send_message(message)

        # Wait for response with timeout
        if event.wait(timeout=self.request_timeout):
            with self.lock:
                return self.responses.pop(req_id, None)
        return None

    def send_notification(self, method: str, params: dict[str, Any]) -> None:
        """Send a notification (no response expected)."""
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        self._send_message(message)

    def _read_message(self) -> Optional[dict[str, Any]]:
        """Read a single LSP message from stdout."""
        if not self.process or not self.process.stdout:
            return None

        try:
            # Read headers
            headers: dict[str, str] = {}
            while True:
                line = self.process.stdout.readline().decode("utf-8")
                if not line or line == "\r\n":
                    break
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip()] = value.strip()

            if "Content-Length" not in headers:
                return None

            # Read content
            content_length = int(headers["Content-Length"])
            content = self.process.stdout.read(content_length).decode("utf-8")
            return json.loads(content)
        except (json.JSONDecodeError, ValueError, OSError):
            return None

    def _reader_loop(self) -> None:
        """Background thread to read LSP messages."""
        while self.running:
            message = self._read_message()
            if not message:
                continue

            # Handle response to a request
            if "id" in message and "result" in message:
                req_id = message["id"]
                with self.lock:
                    if req_id in self.pending_requests:
                        self.responses[req_id] = message.get("result")
                        self.pending_requests[req_id].set()
                        del self.pending_requests[req_id]

            # Handle notifications (like diagnostics)
            elif "method" in message:
                self._handle_notification(message)

    def _handle_notification(self, message: dict[str, Any]) -> None:
        """Handle incoming notifications from the server."""
        method = message.get("method", "")
        params = message.get("params", {})

        if method == "textDocument/publishDiagnostics":
            uri = params.get("uri", "")
            diagnostics = params.get("diagnostics", [])

            with self.diagnostics_lock:
                if diagnostics:
                    self.diagnostics[uri] = diagnostics
                elif uri in self.diagnostics:
                    del self.diagnostics[uri]

            if self.on_diagnostics_updated:
                self.on_diagnostics_updated()

    def initialize(self) -> bool:
        """Perform LSP initialization handshake."""
        workspace_uri = path_to_uri(self.workspace_path)

        init_params = {
            "processId": os.getpid(),
            "rootUri": workspace_uri,
            "rootPath": self.workspace_path,
            "capabilities": {
                "textDocument": {
                    "publishDiagnostics": {
                        "relatedInformation": True,
                    },
                    "synchronization": {
                        "didSave": True,
                        "willSave": False,
                        "willSaveWaitUntil": False,
                    },
                },
                "workspace": {
                    "workspaceFolders": True,
                },
            },
            "workspaceFolders": [
                {"uri": workspace_uri, "name": os.path.basename(self.workspace_path)}
            ],
        }

        result = self.send_request("initialize", init_params)
        if result is None:
            return False

        # Store server capabilities
        self.server_capabilities = result.get("capabilities", {})

        # Send initialized notification
        self.send_notification("initialized", {})
        return True

    def open_document(self, file_path: str) -> None:
        """Open a document in the LSP server."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (IOError, OSError):
            return

        uri = path_to_uri(file_path)
        self.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": "php",
                    "version": 1,
                    "text": content,
                }
            },
        )

    def change_document(self, file_path: str) -> None:
        """Notify server of document change."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (IOError, OSError):
            return

        uri = path_to_uri(file_path)
        self.send_notification(
            "textDocument/didChange",
            {
                "textDocument": {
                    "uri": uri,
                    "version": int(time.time()),
                },
                "contentChanges": [{"text": content}],
            },
        )

    def close_document(self, file_path: str) -> None:
        """Close a document in the LSP server."""
        uri = path_to_uri(file_path)
        self.send_notification("textDocument/didClose", {"textDocument": {"uri": uri}})

        # Remove diagnostics for closed file
        with self.diagnostics_lock:
            if uri in self.diagnostics:
                del self.diagnostics[uri]

    def find_references(
        self, file_path: str, line: int, character: int, include_declaration: bool = True
    ) -> Optional[list[dict[str, Any]]]:
        """Find all references to symbol at position.

        Args:
            file_path: Path to the PHP file
            line: 0-indexed line number
            character: 0-indexed column position
            include_declaration: Whether to include the declaration itself

        Returns:
            List of Location objects or None on error
        """
        uri = path_to_uri(file_path)
        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
            "context": {"includeDeclaration": include_declaration},
        }
        return self.send_request("textDocument/references", params)

    def go_to_definition(
        self, file_path: str, line: int, character: int
    ) -> Optional[list[dict[str, Any]]]:
        """Get definition location for symbol at position.

        Args:
            file_path: Path to the PHP file
            line: 0-indexed line number
            character: 0-indexed column position

        Returns:
            List of Location objects or None on error
        """
        uri = path_to_uri(file_path)
        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        }
        return self.send_request("textDocument/definition", params)

    def get_hover(
        self, file_path: str, line: int, character: int
    ) -> Optional[dict[str, Any]]:
        """Get hover information for symbol at position.

        Args:
            file_path: Path to the PHP file
            line: 0-indexed line number
            character: 0-indexed column position

        Returns:
            Hover object or None on error
        """
        uri = path_to_uri(file_path)
        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        }
        return self.send_request("textDocument/hover", params)

    def get_document_symbols(self, file_path: str) -> Optional[list[dict[str, Any]]]:
        """Get all symbols in a document.

        Args:
            file_path: Path to the PHP file

        Returns:
            List of DocumentSymbol or SymbolInformation objects
        """
        uri = path_to_uri(file_path)
        params = {"textDocument": {"uri": uri}}
        return self.send_request("textDocument/documentSymbol", params)

    def search_symbols(self, query: str) -> Optional[list[dict[str, Any]]]:
        """Search for symbols in the workspace.

        Args:
            query: Search query (partial name match)

        Returns:
            List of SymbolInformation objects
        """
        params = {"query": query}
        return self.send_request("workspace/symbol", params)
