"""Tests for diagnostics display utilities."""

import pytest

from intelephense_watcher.config.constants import CONSTANTS
from intelephense_watcher.diagnostics import filter_diagnostics_by_severity


class TestFilterDiagnosticsBySeverity:
    """Tests for filter_diagnostics_by_severity function."""

    def test_filter_errors_only(self) -> None:
        """Test filtering to show only errors."""
        diagnostics = {
            "file:///test.php": [
                {"severity": 1, "message": "Error"},
                {"severity": 2, "message": "Warning"},
                {"severity": 3, "message": "Info"},
                {"severity": 4, "message": "Hint"},
            ]
        }

        result = filter_diagnostics_by_severity(diagnostics, CONSTANTS.SEVERITY_ERROR)

        assert len(result["file:///test.php"]) == 1
        assert result["file:///test.php"][0]["message"] == "Error"

    def test_filter_errors_and_warnings(self) -> None:
        """Test filtering to show errors and warnings."""
        diagnostics = {
            "file:///test.php": [
                {"severity": 1, "message": "Error"},
                {"severity": 2, "message": "Warning"},
                {"severity": 3, "message": "Info"},
                {"severity": 4, "message": "Hint"},
            ]
        }

        result = filter_diagnostics_by_severity(diagnostics, CONSTANTS.SEVERITY_WARNING)

        assert len(result["file:///test.php"]) == 2
        messages = [d["message"] for d in result["file:///test.php"]]
        assert "Error" in messages
        assert "Warning" in messages

    def test_filter_all_severities(self) -> None:
        """Test filtering to show all diagnostics."""
        diagnostics = {
            "file:///test.php": [
                {"severity": 1, "message": "Error"},
                {"severity": 2, "message": "Warning"},
                {"severity": 3, "message": "Info"},
                {"severity": 4, "message": "Hint"},
            ]
        }

        result = filter_diagnostics_by_severity(diagnostics, CONSTANTS.SEVERITY_HINT)

        assert len(result["file:///test.php"]) == 4

    def test_empty_file_removed_from_result(self) -> None:
        """Test that files with no matching diagnostics are removed."""
        diagnostics = {
            "file:///test.php": [
                {"severity": 4, "message": "Hint"},
            ]
        }

        result = filter_diagnostics_by_severity(diagnostics, CONSTANTS.SEVERITY_ERROR)

        assert "file:///test.php" not in result

    def test_empty_diagnostics(self) -> None:
        """Test handling of empty diagnostics dictionary."""
        result = filter_diagnostics_by_severity({}, CONSTANTS.SEVERITY_HINT)

        assert result == {}

    def test_multiple_files(self) -> None:
        """Test filtering diagnostics from multiple files."""
        diagnostics = {
            "file:///a.php": [
                {"severity": 1, "message": "Error in A"},
            ],
            "file:///b.php": [
                {"severity": 4, "message": "Hint in B"},
            ],
            "file:///c.php": [
                {"severity": 1, "message": "Error in C"},
                {"severity": 2, "message": "Warning in C"},
            ],
        }

        result = filter_diagnostics_by_severity(diagnostics, CONSTANTS.SEVERITY_ERROR)

        assert "file:///a.php" in result
        assert "file:///b.php" not in result
        assert "file:///c.php" in result
        assert len(result["file:///c.php"]) == 1

    def test_default_severity_when_missing(self) -> None:
        """Test that diagnostics without severity default to 1 (error)."""
        diagnostics = {
            "file:///test.php": [
                {"message": "No severity specified"},
            ]
        }

        result = filter_diagnostics_by_severity(diagnostics, CONSTANTS.SEVERITY_ERROR)

        assert len(result["file:///test.php"]) == 1
