#!/usr/bin/env python3
"""Tests for exception hierarchy."""

import pytest
from extraction.exceptions import (
    ExtractionError,
    ConfigError,
    InvalidConfigValueError,
    DependencyError,
    FileError,
    FileNotFoundError,
    InvalidFileFormatError,
    StateError,
    MethodOrderError,
    ParseError,
)


class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    def test_extraction_error_is_base(self):
        """ExtractionError should be the base exception."""
        assert issubclass(ConfigError, ExtractionError)
        assert issubclass(DependencyError, ExtractionError)
        assert issubclass(FileError, ExtractionError)
        assert issubclass(StateError, ExtractionError)
        assert issubclass(ParseError, ExtractionError)

    def test_config_error_hierarchy(self):
        """InvalidConfigValueError should inherit from ConfigError."""
        assert issubclass(InvalidConfigValueError, ConfigError)
        assert issubclass(InvalidConfigValueError, ExtractionError)

    def test_file_error_hierarchy(self):
        """File-related errors should inherit from FileError."""
        assert issubclass(FileNotFoundError, FileError)
        assert issubclass(InvalidFileFormatError, FileError)

    def test_state_error_hierarchy(self):
        """MethodOrderError should inherit from StateError."""
        assert issubclass(MethodOrderError, StateError)


class TestExtractionError:
    """Tests for ExtractionError base class."""

    def test_message_only(self):
        """Should accept message-only."""
        err = ExtractionError("Test error")
        assert str(err) == "Test error"

    def test_with_details(self):
        """Should accept message with details dict."""
        err = ExtractionError("Test error", {"field": "value"})
        assert "Test error" in str(err)


class TestConfigError:
    """Tests for ConfigError."""

    def test_invalid_config_value_error(self):
        """InvalidConfigValueError should format message correctly."""
        err = InvalidConfigValueError("field_name", "bad_value", "Expected good_value")
        message = str(err)
        assert "field_name" in message
        assert "bad_value" in message
        assert "Expected good_value" in message

    def test_invalid_config_value_with_list(self):
        """InvalidConfigValueError should handle list of expected values."""
        err = InvalidConfigValueError("strategy", "bad", ["rag", "nlp"])
        message = str(err)
        assert "strategy" in message
        assert "bad" in message


class TestFileError:
    """Tests for FileError subclasses."""

    def test_file_not_found_error(self):
        """FileNotFoundError should include file path."""
        err = FileNotFoundError("/path/to/missing.txt")
        assert "/path/to/missing.txt" in str(err)

    def test_invalid_file_format_error(self):
        """InvalidFileFormatError should include file path and format."""
        err = InvalidFileFormatError("/path/to/file.txt", "Expected .epub")
        message = str(err)
        assert "/path/to/file.txt" in message
        assert "Expected .epub" in message


class TestStateError:
    """Tests for StateError subclasses."""

    def test_method_order_error(self):
        """MethodOrderError should format helpful message."""
        err = MethodOrderError("parse", "LOADED", "CREATED")
        message = str(err)
        assert "parse" in message
        assert "LOADED" in message
        assert "CREATED" in message


class TestParseError:
    """Tests for ParseError."""

    def test_parse_error_with_file(self):
        """ParseError should include file path."""
        err = ParseError("/path/to/doc.epub", "Invalid structure")
        message = str(err)
        assert "/path/to/doc.epub" in message
        assert "Invalid structure" in message

    def test_parse_error_with_cause(self):
        """ParseError should chain from other exceptions."""
        original = ValueError("Original error")
        err = ParseError("/path/to/doc.epub", "Failed to parse")
        err.__cause__ = original
        assert err.__cause__ is original


class TestDependencyError:
    """Tests for DependencyError."""

    def test_dependency_error(self):
        """DependencyError should describe missing dependency."""
        err = DependencyError("pdfminer.six", "Install with: pip install pdfminer.six")
        message = str(err)
        assert "pdfminer.six" in message
        assert "pip install" in message


class TestExceptionCatching:
    """Tests for catching exceptions in code."""

    def test_catch_extraction_error_catches_all(self):
        """Catching ExtractionError should catch all subclasses."""
        exceptions_to_test = [
            ConfigError("test"),
            InvalidConfigValueError("field", "value", "expected"),
            FileError("test"),
            FileNotFoundError("/path"),
            InvalidFileFormatError("/path", "format"),
            StateError("test"),
            MethodOrderError("method", "required", "current"),
            ParseError("/path", "error"),
            DependencyError("lib", "msg"),
        ]

        for exc in exceptions_to_test:
            try:
                raise exc
            except ExtractionError:
                pass  # Successfully caught
            else:
                pytest.fail(f"{type(exc).__name__} not caught by ExtractionError")
