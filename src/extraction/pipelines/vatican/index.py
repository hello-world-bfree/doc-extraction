#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Document index for tracking Vatican archive extraction progress.

Provides persistent storage of discovered documents, download status,
processing status, and R2 upload paths. Enables resume capability.
"""

import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

LOGGER = logging.getLogger("vatican.index")


@dataclass
class VaticanDocument:
    """
    Represents a discovered Vatican document.

    Attributes:
        url: Document URL
        title: Document title
        section: Archive section (BIBLE, CATECHISM, COUNCILS, etc.)
        document_type: Type (Encyclical, Constitution, etc.)
        language: Language code (default: "en")
        discovered_at: Discovery timestamp
        downloaded: Whether file has been downloaded
        download_path: Local path to downloaded file
        processed: Whether document has been processed
        r2_paths: Paths to uploaded files in R2
        processing_timestamp: When processing completed
        parent_document: URL of parent document (for multi-part docs)
        collection: Collection name (e.g., "Bible")
        metadata: Additional metadata
    """
    url: str
    title: str
    section: str
    document_type: str = ""
    language: str = "en"
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    downloaded: bool = False
    download_path: Optional[str] = None
    processed: bool = False
    r2_paths: List[str] = field(default_factory=list)
    processing_timestamp: Optional[str] = None
    parent_document: Optional[str] = None
    collection: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "VaticanDocument":
        """Create instance from dictionary."""
        return cls(**data)


class DocumentIndex:
    """
    Persistent index of discovered Vatican documents.

    Tracks discovery, download, processing, and upload status.
    Stored as JSON for easy inspection and modification.
    Enables resume capability if extraction is interrupted.
    """

    def __init__(self, index_path: str = "./vatican_archive/index.json"):
        """
        Initialize document index.

        Args:
            index_path: Path to index JSON file
        """
        self.index_path = Path(index_path)
        self.documents: Dict[str, VaticanDocument] = {}
        self.last_updated: str = datetime.now().isoformat()

        # Load existing index if present
        if self.index_path.exists():
            self.load()

    def add_document(self, doc: VaticanDocument) -> bool:
        """
        Add document to index, avoiding duplicates.

        Args:
            doc: Document to add

        Returns:
            True if added (new), False if duplicate
        """
        if doc.url in self.documents:
            LOGGER.debug("Duplicate document: %s", doc.url)
            return False

        self.documents[doc.url] = doc
        self.last_updated = datetime.now().isoformat()
        LOGGER.info("Added document: %s - %s", doc.title, doc.url)
        return True

    def mark_downloaded(self, url: str, local_path: str) -> None:
        """
        Mark document as successfully downloaded.

        Args:
            url: Document URL
            local_path: Path to downloaded file
        """
        if url not in self.documents:
            LOGGER.warning("Cannot mark unknown document as downloaded: %s", url)
            return

        self.documents[url].downloaded = True
        self.documents[url].download_path = local_path
        self.last_updated = datetime.now().isoformat()
        LOGGER.debug("Marked as downloaded: %s", url)

    def mark_processed(self, url: str, r2_paths: List[str]) -> None:
        """
        Mark document as successfully processed and uploaded.

        Args:
            url: Document URL
            r2_paths: List of R2 paths for uploaded files
        """
        if url not in self.documents:
            LOGGER.warning("Cannot mark unknown document as processed: %s", url)
            return

        self.documents[url].processed = True
        self.documents[url].r2_paths = r2_paths
        self.documents[url].processing_timestamp = datetime.now().isoformat()
        self.last_updated = datetime.now().isoformat()
        LOGGER.debug("Marked as processed: %s (%d files uploaded)", url, len(r2_paths))

    def get_pending_downloads(self) -> List[VaticanDocument]:
        """
        Get documents not yet downloaded.

        Returns:
            List of documents pending download
        """
        pending = [doc for doc in self.documents.values() if not doc.downloaded]
        LOGGER.info("Found %d documents pending download", len(pending))
        return pending

    def get_pending_processing(self) -> List[VaticanDocument]:
        """
        Get downloaded documents not yet processed.

        Returns:
            List of documents pending processing
        """
        pending = [
            doc for doc in self.documents.values()
            if doc.downloaded and not doc.processed
        ]
        LOGGER.info("Found %d documents pending processing", len(pending))
        return pending

    def get_documents_by_section(self, section: str) -> List[VaticanDocument]:
        """
        Get all documents for a specific section.

        Args:
            section: Section name (e.g., "CATECHISM")

        Returns:
            List of documents in the section
        """
        docs = [doc for doc in self.documents.values() if doc.section == section]
        LOGGER.info("Found %d documents in section: %s", len(docs), section)
        return docs

    def export_summary(self) -> dict:
        """
        Export summary statistics.

        Returns:
            Dictionary with summary statistics
        """
        total = len(self.documents)
        downloaded = sum(1 for doc in self.documents.values() if doc.downloaded)
        processed = sum(1 for doc in self.documents.values() if doc.processed)

        # Count by section
        by_section = {}
        for doc in self.documents.values():
            by_section[doc.section] = by_section.get(doc.section, 0) + 1

        return {
            "total_discovered": total,
            "by_section": by_section,
            "downloaded": downloaded,
            "processed": processed,
            "pending_download": total - downloaded,
            "pending_processing": downloaded - processed,
        }

    def save(self) -> None:
        """
        Persist index to disk.

        Creates parent directory if needed.
        Writes JSON with indentation for readability.
        """
        # Ensure parent directory exists
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        # Prepare data
        data = {
            "last_updated": self.last_updated,
            "documents": {
                url: doc.to_dict() for url, doc in self.documents.items()
            },
            "statistics": self.export_summary(),
        }

        # Write JSON
        with open(self.index_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        LOGGER.info("Saved index to: %s (%d documents)", self.index_path, len(self.documents))

    def load(self) -> None:
        """
        Load index from disk.

        Raises:
            FileNotFoundError: If index file doesn't exist
            json.JSONDecodeError: If index file is invalid JSON
        """
        if not self.index_path.exists():
            raise FileNotFoundError(f"Index file not found: {self.index_path}")

        with open(self.index_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.last_updated = data.get("last_updated", datetime.now().isoformat())

        # Load documents
        self.documents = {}
        for url, doc_data in data.get("documents", {}).items():
            self.documents[url] = VaticanDocument.from_dict(doc_data)

        LOGGER.info("Loaded index from: %s (%d documents)", self.index_path, len(self.documents))

    def __len__(self) -> int:
        """Return number of documents in index."""
        return len(self.documents)

    def __contains__(self, url: str) -> bool:
        """Check if document URL is in index."""
        return url in self.documents

    def __getitem__(self, url: str) -> VaticanDocument:
        """Get document by URL."""
        return self.documents[url]
