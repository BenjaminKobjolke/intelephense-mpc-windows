"""URI utility functions for LSP communication."""

import os
from urllib.parse import unquote


def path_to_uri(path: str) -> str:
    """Convert a file path to a file:// URI.

    Args:
        path: File system path (absolute or relative).

    Returns:
        A file:// URI string.
    """
    abs_path = os.path.abspath(path)
    # On Windows, convert backslashes and add leading slash
    if os.name == "nt":
        abs_path = abs_path.replace("\\", "/")
        if not abs_path.startswith("/"):
            abs_path = "/" + abs_path
    return "file://" + abs_path


def uri_to_path(uri: str) -> str:
    """Convert a file:// URI to a file path.

    Args:
        uri: A file:// URI string.

    Returns:
        A file system path.
    """
    # URL-decode the URI first to handle encoded characters like %3A -> :
    uri = unquote(uri)

    if uri.startswith("file://"):
        path = uri[7:]
        # On Windows, remove leading slash before drive letter
        if os.name == "nt" and len(path) > 2 and path[0] == "/" and path[2] == ":":
            path = path[1:]
        return path.replace("/", os.sep)
    return uri


def normalize_uri(uri: str) -> str:
    """Normalize a URI for comparison.

    Handles different URI formats that might be returned by the LSP server.
    On Windows, normalizes drive letters to uppercase for case-insensitive comparison.

    Args:
        uri: A file:// URI or path string.

    Returns:
        A normalized file:// URI string.
    """
    # URL-decode first
    uri = unquote(uri)

    # Convert to absolute file path and back to ensure consistent format
    if uri.startswith("file://"):
        path = uri_to_path(uri)
        # On Windows, normalize drive letter to uppercase
        if os.name == "nt" and len(path) >= 2 and path[1] == ":":
            path = path[0].upper() + path[1:]
        return path_to_uri(path)

    # Handle relative paths or non-standard formats
    if os.path.exists(uri):
        return path_to_uri(uri)

    # Try to extract path from malformed URIs
    # Handle cases like "..\..\..\d%3A\wamp64\..." which are relative paths
    path = uri.replace("/", os.sep).replace("\\", os.sep)
    if os.path.isabs(path) or (os.name == "nt" and len(path) > 1 and path[1] == ":"):
        # Normalize drive letter to uppercase
        if os.name == "nt" and len(path) >= 2 and path[1] == ":":
            path = path[0].upper() + path[1:]
        return path_to_uri(path)

    return uri
