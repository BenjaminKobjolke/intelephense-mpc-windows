"""Tests for LSP client utilities."""

import os

import pytest

from intelephense_watcher.lsp_client import path_to_uri, uri_to_path


class TestPathToUri:
    """Tests for path_to_uri function."""

    def test_absolute_path_unix_style(self) -> None:
        """Test conversion of Unix-style absolute path."""
        if os.name == "nt":
            # On Windows, test with Windows paths
            result = path_to_uri("C:\\Users\\test\\file.php")
            assert result == "file:///C:/Users/test/file.php"
        else:
            result = path_to_uri("/home/user/file.php")
            assert result == "file:///home/user/file.php"

    def test_path_with_spaces(self) -> None:
        """Test conversion of path containing spaces."""
        if os.name == "nt":
            result = path_to_uri("C:\\My Project\\file.php")
            assert result == "file:///C:/My Project/file.php"
        else:
            result = path_to_uri("/home/user/my project/file.php")
            assert result == "file:///home/user/my project/file.php"

    def test_relative_path_becomes_absolute(self) -> None:
        """Test that relative paths are converted to absolute."""
        result = path_to_uri("test.php")
        assert result.startswith("file://")
        assert "test.php" in result


class TestUriToPath:
    """Tests for uri_to_path function."""

    def test_file_uri_to_path(self) -> None:
        """Test conversion of file:// URI to path."""
        if os.name == "nt":
            result = uri_to_path("file:///C:/Users/test/file.php")
            assert result == "C:\\Users\\test\\file.php"
        else:
            result = uri_to_path("file:///home/user/file.php")
            assert result == "/home/user/file.php"

    def test_uri_with_spaces(self) -> None:
        """Test conversion of URI with spaces in path."""
        if os.name == "nt":
            result = uri_to_path("file:///C:/My Project/file.php")
            assert result == "C:\\My Project\\file.php"
        else:
            result = uri_to_path("file:///home/user/my project/file.php")
            assert result == "/home/user/my project/file.php"

    def test_non_file_uri_returned_unchanged(self) -> None:
        """Test that non-file URIs are returned unchanged."""
        result = uri_to_path("https://example.com/file.php")
        assert result == "https://example.com/file.php"

    def test_roundtrip_conversion(self) -> None:
        """Test that path->uri->path roundtrip preserves the path."""
        if os.name == "nt":
            original = "C:\\Users\\test\\file.php"
        else:
            original = "/home/user/file.php"

        uri = path_to_uri(original)
        result = uri_to_path(uri)
        assert result == original
