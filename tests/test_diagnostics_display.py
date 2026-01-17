"""Tests for diagnostics display utilities."""

import pytest

from intelephense_watcher.config.constants import CONSTANTS
from intelephense_watcher.diagnostics import (
    _is_unused_underscore_variable,
    filter_diagnostics_by_severity,
    filter_unused_underscore_variables,
)


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


class TestIsUnusedUnderscoreVariable:
    """Tests for _is_unused_underscore_variable helper function."""

    def test_matches_underscore_variable_hint(self) -> None:
        """Test matching of valid underscore variable hints."""
        diagnostic = {
            "severity": CONSTANTS.SEVERITY_HINT,
            "message": "Symbol '$_response' is declared but not used.",
        }
        assert _is_unused_underscore_variable(diagnostic) is True

    def test_matches_single_underscore_variable(self) -> None:
        """Test matching a single underscore variable."""
        diagnostic = {
            "severity": CONSTANTS.SEVERITY_HINT,
            "message": "Symbol '$_' is declared but not used.",
        }
        assert _is_unused_underscore_variable(diagnostic) is True

    def test_matches_double_underscore_variable(self) -> None:
        """Test matching double underscore variable."""
        diagnostic = {
            "severity": CONSTANTS.SEVERITY_HINT,
            "message": "Symbol '$__doubleUnderscore' is declared but not used.",
        }
        assert _is_unused_underscore_variable(diagnostic) is True

    def test_matches_camel_case_variable(self) -> None:
        """Test matching camelCase underscore variable."""
        diagnostic = {
            "severity": CONSTANTS.SEVERITY_HINT,
            "message": "Symbol '$_weekStartDay' is declared but not used.",
        }
        assert _is_unused_underscore_variable(diagnostic) is True

    def test_rejects_non_underscore_variable(self) -> None:
        """Test rejection of non-underscore variables."""
        diagnostic = {
            "severity": CONSTANTS.SEVERITY_HINT,
            "message": "Symbol '$response' is declared but not used.",
        }
        assert _is_unused_underscore_variable(diagnostic) is False

    def test_rejects_non_hint_severity(self) -> None:
        """Test rejection of non-hint severity even with underscore prefix."""
        diagnostic = {
            "severity": CONSTANTS.SEVERITY_ERROR,
            "message": "Symbol '$_error' is declared but not used.",
        }
        assert _is_unused_underscore_variable(diagnostic) is False

    def test_rejects_warning_severity(self) -> None:
        """Test rejection of warning severity."""
        diagnostic = {
            "severity": CONSTANTS.SEVERITY_WARNING,
            "message": "Symbol '$_warning' is declared but not used.",
        }
        assert _is_unused_underscore_variable(diagnostic) is False

    def test_rejects_different_message_format(self) -> None:
        """Test rejection of different message formats."""
        diagnostic = {
            "severity": CONSTANTS.SEVERITY_HINT,
            "message": "Undefined variable '$_test'",
        }
        assert _is_unused_underscore_variable(diagnostic) is False

    def test_rejects_missing_message(self) -> None:
        """Test handling of missing message."""
        diagnostic = {"severity": CONSTANTS.SEVERITY_HINT}
        assert _is_unused_underscore_variable(diagnostic) is False

    def test_rejects_missing_severity(self) -> None:
        """Test handling of missing severity (defaults to 1)."""
        diagnostic = {"message": "Symbol '$_test' is declared but not used."}
        assert _is_unused_underscore_variable(diagnostic) is False

    # Tests for underscore-prefixed methods
    def test_matches_underscore_method_hint(self) -> None:
        """Test matching of unused underscore method hints."""
        diagnostic = {
            "severity": CONSTANTS.SEVERITY_HINT,
            "message": "Method '_createFriendship' is declared but never used.",
        }
        assert _is_unused_underscore_variable(diagnostic) is True

    def test_matches_underscore_function_hint(self) -> None:
        """Test matching of unused underscore function hints."""
        diagnostic = {
            "severity": CONSTANTS.SEVERITY_HINT,
            "message": "Function '_myHelper' is declared but never used.",
        }
        assert _is_unused_underscore_variable(diagnostic) is True

    def test_matches_single_underscore_method(self) -> None:
        """Test matching a single underscore method."""
        diagnostic = {
            "severity": CONSTANTS.SEVERITY_HINT,
            "message": "Method '_' is declared but never used.",
        }
        assert _is_unused_underscore_variable(diagnostic) is True

    def test_rejects_non_underscore_method(self) -> None:
        """Test rejection of non-underscore methods."""
        diagnostic = {
            "severity": CONSTANTS.SEVERITY_HINT,
            "message": "Method 'createFriendship' is declared but never used.",
        }
        assert _is_unused_underscore_variable(diagnostic) is False

    def test_rejects_non_underscore_function(self) -> None:
        """Test rejection of non-underscore functions."""
        diagnostic = {
            "severity": CONSTANTS.SEVERITY_HINT,
            "message": "Function 'myHelper' is declared but never used.",
        }
        assert _is_unused_underscore_variable(diagnostic) is False

    def test_rejects_method_with_non_hint_severity(self) -> None:
        """Test rejection of method hint with wrong severity."""
        diagnostic = {
            "severity": CONSTANTS.SEVERITY_WARNING,
            "message": "Method '_unusedMethod' is declared but never used.",
        }
        assert _is_unused_underscore_variable(diagnostic) is False


class TestFilterUnusedUnderscoreVariables:
    """Tests for filter_unused_underscore_variables function."""

    def test_filters_underscore_prefixed_unused_vars(self) -> None:
        """Test that underscore-prefixed unused variable hints are filtered."""
        diagnostics = {
            "file:///test.php": [
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Symbol '$_response' is declared but not used.",
                },
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Symbol '$data' is declared but not used.",
                },
            ]
        }

        result = filter_unused_underscore_variables(diagnostics, enabled=True)

        assert len(result["file:///test.php"]) == 1
        assert "$data" in result["file:///test.php"][0]["message"]

    def test_preserves_non_hint_severities(self) -> None:
        """Test that errors/warnings are not filtered even with underscore prefix."""
        diagnostics = {
            "file:///test.php": [
                {
                    "severity": CONSTANTS.SEVERITY_ERROR,
                    "message": "Symbol '$_error' is declared but not used.",
                },
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Symbol '$_hint' is declared but not used.",
                },
            ]
        }

        result = filter_unused_underscore_variables(diagnostics, enabled=True)

        # Error should be preserved, hint should be filtered
        assert len(result["file:///test.php"]) == 1
        assert result["file:///test.php"][0]["severity"] == CONSTANTS.SEVERITY_ERROR

    def test_disabled_returns_unfiltered(self) -> None:
        """Test that disabled filter returns diagnostics unchanged."""
        diagnostics = {
            "file:///test.php": [
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Symbol '$_response' is declared but not used.",
                },
            ]
        }

        result = filter_unused_underscore_variables(diagnostics, enabled=False)

        assert result == diagnostics

    def test_empty_diagnostics(self) -> None:
        """Test handling of empty diagnostics."""
        result = filter_unused_underscore_variables({}, enabled=True)
        assert result == {}

    def test_various_underscore_patterns(self) -> None:
        """Test various underscore variable name patterns."""
        diagnostics = {
            "file:///test.php": [
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Symbol '$_' is declared but not used.",
                },
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Symbol '$_a' is declared but not used.",
                },
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Symbol '$_weekStartDay' is declared but not used.",
                },
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Symbol '$__doubleUnderscore' is declared but not used.",
                },
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Symbol '$response' is declared but not used.",
                },  # Should NOT be filtered
            ]
        }

        result = filter_unused_underscore_variables(diagnostics, enabled=True)

        # Only the non-underscore variable should remain
        assert len(result["file:///test.php"]) == 1
        assert "$response" in result["file:///test.php"][0]["message"]

    def test_removes_empty_files_from_result(self) -> None:
        """Test that files with no remaining diagnostics are removed."""
        diagnostics = {
            "file:///test.php": [
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Symbol '$_onlyOne' is declared but not used.",
                },
            ]
        }

        result = filter_unused_underscore_variables(diagnostics, enabled=True)

        assert "file:///test.php" not in result

    def test_multiple_files(self) -> None:
        """Test filtering across multiple files."""
        diagnostics = {
            "file:///a.php": [
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Symbol '$_unused' is declared but not used.",
                },
            ],
            "file:///b.php": [
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Symbol '$used' is declared but not used.",
                },
            ],
            "file:///c.php": [
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Symbol '$_ignore' is declared but not used.",
                },
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Symbol '$keep' is declared but not used.",
                },
            ],
        }

        result = filter_unused_underscore_variables(diagnostics, enabled=True)

        # a.php should be removed (only had underscore var)
        assert "file:///a.php" not in result
        # b.php should remain
        assert "file:///b.php" in result
        assert len(result["file:///b.php"]) == 1
        # c.php should have only the non-underscore var
        assert "file:///c.php" in result
        assert len(result["file:///c.php"]) == 1
        assert "$keep" in result["file:///c.php"][0]["message"]

    def test_filters_underscore_prefixed_methods(self) -> None:
        """Test that underscore-prefixed unused method hints are filtered."""
        diagnostics = {
            "file:///test.php": [
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Method '_createFriendship' is declared but never used.",
                },
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Method 'publicMethod' is declared but never used.",
                },
            ]
        }

        result = filter_unused_underscore_variables(diagnostics, enabled=True)

        assert len(result["file:///test.php"]) == 1
        assert "publicMethod" in result["file:///test.php"][0]["message"]

    def test_filters_underscore_prefixed_functions(self) -> None:
        """Test that underscore-prefixed unused function hints are filtered."""
        diagnostics = {
            "file:///test.php": [
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Function '_helperFunc' is declared but never used.",
                },
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Function 'publicFunc' is declared but never used.",
                },
            ]
        }

        result = filter_unused_underscore_variables(diagnostics, enabled=True)

        assert len(result["file:///test.php"]) == 1
        assert "publicFunc" in result["file:///test.php"][0]["message"]

    def test_filters_mixed_symbols(self) -> None:
        """Test filtering a mix of variables, methods, and functions."""
        diagnostics = {
            "file:///test.php": [
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Symbol '$_unused' is declared but not used.",
                },
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Method '_privateHelper' is declared but never used.",
                },
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Function '_utilFunc' is declared but never used.",
                },
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Symbol '$keepThis' is declared but not used.",
                },
                {
                    "severity": CONSTANTS.SEVERITY_HINT,
                    "message": "Method 'keepThisMethod' is declared but never used.",
                },
            ]
        }

        result = filter_unused_underscore_variables(diagnostics, enabled=True)

        # Only 2 should remain (non-underscore variable and method)
        assert len(result["file:///test.php"]) == 2
        messages = [d["message"] for d in result["file:///test.php"]]
        assert any("$keepThis" in m for m in messages)
        assert any("keepThisMethod" in m for m in messages)
