"""Tests for file handler utilities."""

import pytest

from intelephense_watcher.file_handler import is_php_file


class TestIsPhpFile:
    """Tests for is_php_file function."""

    def test_php_extension_lowercase(self) -> None:
        """Test detection of .php extension in lowercase."""
        assert is_php_file("test.php") is True
        assert is_php_file("/path/to/file.php") is True
        assert is_php_file("C:\\path\\to\\file.php") is True

    def test_php_extension_uppercase(self) -> None:
        """Test detection of .PHP extension in uppercase."""
        assert is_php_file("test.PHP") is True
        assert is_php_file("TEST.PHP") is True

    def test_php_extension_mixed_case(self) -> None:
        """Test detection of .Php extension in mixed case."""
        assert is_php_file("test.Php") is True
        assert is_php_file("test.pHp") is True

    def test_non_php_extensions(self) -> None:
        """Test that non-PHP files are rejected."""
        assert is_php_file("test.txt") is False
        assert is_php_file("test.js") is False
        assert is_php_file("test.py") is False
        assert is_php_file("test.html") is False
        assert is_php_file("test.css") is False

    def test_no_extension(self) -> None:
        """Test files without extensions."""
        assert is_php_file("test") is False
        assert is_php_file("Makefile") is False

    def test_php_in_filename_but_wrong_extension(self) -> None:
        """Test that 'php' in filename doesn't trigger false positive."""
        assert is_php_file("php_config.txt") is False
        assert is_php_file("myphpfile.js") is False

    def test_hidden_php_file(self) -> None:
        """Test hidden files with .php extension."""
        assert is_php_file(".hidden.php") is True

    def test_double_extension(self) -> None:
        """Test files with double extensions."""
        assert is_php_file("test.blade.php") is True
        assert is_php_file("test.php.bak") is False
