#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Vatican archive extraction pipeline.

Provides web scraping, downloading, processing, and storage management
for extracting English documents from the Vatican archive.
"""

from .index import DocumentIndex, VaticanDocument
from .scraper import VaticanArchiveScraper
from .downloader import VaticanDownloader
from .processor import VaticanArchiveProcessor
from .storage import R2StorageManager

__all__ = [
    "DocumentIndex",
    "VaticanDocument",
    "VaticanArchiveScraper",
    "VaticanDownloader",
    "VaticanArchiveProcessor",
    "R2StorageManager",
]
