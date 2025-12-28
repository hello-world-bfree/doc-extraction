#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Document extractors for various formats.

All extractors inherit from BaseExtractor and implement:
- load(): Load the source document
- parse(): Extract chunks with hierarchy
- extract_metadata(): Extract document metadata
"""

from .base import BaseExtractor
from .epub import EpubExtractor
from .pdf import PdfExtractor
from .html import HtmlExtractor
from .markdown import MarkdownExtractor
from .json import JsonExtractor

__all__ = [
    "BaseExtractor",
    "EpubExtractor",
    "PdfExtractor",
    "HtmlExtractor",
    "MarkdownExtractor",
    "JsonExtractor",
]
