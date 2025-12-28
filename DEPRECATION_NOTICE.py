#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Shared deprecation notice for legacy parsers.
"""

import warnings


def show_deprecation_warning(script_name):
    """
    Display deprecation warning for legacy parser scripts.

    Args:
        script_name: Name of the legacy script (for display)
    """
    warnings.warn(
        "\n" + "=" * 70 + "\n"
        "⚠️  DEPRECATION WARNING\n"
        "=" * 70 + "\n"
        f"This legacy parser ({script_name}) is deprecated.\n\n"
        "Please use the new extraction library instead:\n\n"
        "  CLI:    extract document.epub [OPTIONS]\n"
        "          extract document.pdf [OPTIONS]\n"
        "          extract document.html [OPTIONS]\n"
        "          extract document.md [OPTIONS]\n\n"
        "  Python: from src.extraction.extractors import EpubExtractor\n"
        "          extractor = EpubExtractor('document.epub')\n"
        "          extractor.load()\n"
        "          extractor.parse()\n"
        "          metadata = extractor.extract_metadata()\n\n"
        "The new library supports:\n"
        "  • EPUB, PDF, HTML, Markdown, JSON formats\n"
        "  • Unified CLI and Python API\n"
        "  • Pluggable domain analyzers\n"
        "  • Comprehensive test coverage\n\n"
        "See README.md and USER_GUIDE.md for full documentation.\n"
        "=" * 70 + "\n",
        DeprecationWarning,
        stacklevel=3
    )


# Module-level deprecation notice
DEPRECATION_TEXT = """
⚠️ DEPRECATED - This module is deprecated in favor of src.extraction

Please use:
    from src.extraction.extractors import EpubExtractor, PdfExtractor, HtmlExtractor, MarkdownExtractor
    from src.extraction.analyzers import CatholicAnalyzer, GenericAnalyzer

For CLI usage:
    extract document.epub [OPTIONS]

See README.md and USER_GUIDE.md for documentation.
"""
