#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Custom exception hierarchy for extraction library.

All extraction errors inherit from ExtractionError for consistent error handling.
"""

from typing import Any, List, Optional, Union


class ExtractionError(Exception):
    """
    Base exception for all extraction errors.

    All custom exceptions in the library inherit from this class,
    making it easy to catch all extraction-related errors.
    """
    pass


class ConfigError(ExtractionError):
    """
    Configuration-related errors.

    Raised when configuration is invalid or incomplete.
    """
    pass


class InvalidConfigValueError(ConfigError):
    """
    Invalid configuration value error.

    Raised when a configuration parameter has an invalid value.

    Attributes:
        param_name: Name of the invalid parameter
        value: The invalid value provided
        expected: Description of expected values
    """

    def __init__(
        self,
        param_name: str,
        value: Any,
        expected: Union[str, List[str]]
    ):
        self.param_name = param_name
        self.value = value
        self.expected = expected

        if isinstance(expected, list):
            expected_str = f"one of {expected}"
        else:
            expected_str = str(expected)

        super().__init__(
            f"Invalid value for '{param_name}': {value!r}. "
            f"Expected: {expected_str}"
        )


class DependencyError(ExtractionError):
    """
    Missing or incompatible dependency error.

    Raised when a required library is not installed or has wrong version.

    Attributes:
        dependency: Name of the missing dependency
        required_for: What feature requires this dependency
        install_hint: Optional installation hint (e.g., pip install command)
    """

    def __init__(
        self,
        dependency: str,
        required_for: str,
        install_hint: Optional[str] = None
    ):
        self.dependency = dependency
        self.required_for = required_for
        self.install_hint = install_hint

        msg = f"Missing dependency '{dependency}' required for {required_for}"
        if install_hint:
            msg += f". Install with: {install_hint}"

        super().__init__(msg)


class FileError(ExtractionError):
    """
    File-related errors.

    Raised when there are issues with file operations.
    """
    pass


class FileNotFoundError(FileError):
    """
    File not found error.

    Raised when a specified file does not exist.

    Attributes:
        file_path: Path to the missing file
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        super().__init__(f"File not found: {file_path}")


class InvalidFileFormatError(FileError):
    """
    Invalid file format error.

    Raised when a file has an unexpected or unsupported format.

    Attributes:
        file_path: Path to the invalid file
        expected_format: Expected format(s)
        reason: Optional reason for the error
    """

    def __init__(
        self,
        file_path: str,
        expected_format: Union[str, List[str]],
        reason: Optional[str] = None
    ):
        self.file_path = file_path
        self.expected_format = expected_format

        if isinstance(expected_format, list):
            format_str = f"one of {expected_format}"
        else:
            format_str = expected_format

        msg = f"Invalid file format for '{file_path}'. Expected: {format_str}"
        if reason:
            msg += f". Reason: {reason}"

        super().__init__(msg)


class StateError(ExtractionError):
    """
    Extractor state-related errors.

    Raised when operations are performed in wrong order or invalid state.
    """
    pass


class MethodOrderError(StateError):
    """
    Method called in wrong order error.

    Raised when extractor methods are called in incorrect order.

    Attributes:
        method_name: Name of the method that was called
        required_state: Required state(s) for the method
        current_state: Current state of the extractor
    """

    def __init__(
        self,
        method_name: str,
        required_state: Union[str, List[str]],
        current_state: str
    ):
        self.method_name = method_name
        self.required_state = required_state
        self.current_state = current_state

        if isinstance(required_state, list):
            state_str = f"one of {required_state}"
        else:
            state_str = required_state

        super().__init__(
            f"Cannot call {method_name}() in state '{current_state}'. "
            f"Required state: {state_str}"
        )


class ParseError(ExtractionError):
    """
    Document parsing error.

    Raised when document cannot be parsed or contains invalid content.

    Attributes:
        file_path: Path to the document being parsed
        reason: Description of why parsing failed
        line_number: Optional line number where error occurred
    """

    def __init__(
        self,
        file_path: str,
        reason: str,
        line_number: Optional[int] = None
    ):
        self.file_path = file_path
        self.reason = reason
        self.line_number = line_number

        msg = f"Failed to parse '{file_path}': {reason}"
        if line_number:
            msg += f" (line {line_number})"

        super().__init__(msg)
