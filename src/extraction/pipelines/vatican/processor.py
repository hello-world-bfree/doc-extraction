#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Vatican archive extraction pipeline orchestrator.

Coordinates complete pipeline: discover → download → extract → upload.
Integrates with existing extraction infrastructure.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from tqdm import tqdm

from .downloader import VaticanDownloader
from .index import DocumentIndex, VaticanDocument
from .scraper import VaticanArchiveScraper
from .storage import R2StorageManager

LOGGER = logging.getLogger("vatican.processor")


class VaticanArchiveProcessor:
    """
    Orchestrates complete Vatican archive extraction pipeline.

    Pipeline stages:
    1. Discovery: Scrape Vatican archive for English HTML documents
    2. Download: Download HTML files to local temp directory
    3. Processing: Extract using existing HTML extractor + Catholic analyzer
    4. Upload: Upload JSON/NDJSON to R2
    5. Cleanup: Remove local downloads (optional)
    """

    def __init__(self,
                 work_dir: str = "./vatican_archive",
                 rate_limit: float = 1.0,
                 r2_config: Optional[Dict] = None):
        """
        Initialize pipeline processor.

        Args:
            work_dir: Base working directory
            rate_limit: Requests per second limit
            r2_config: R2 configuration dict with keys:
                - bucket_name
                - access_key_id
                - secret_access_key
                - endpoint_url
        """
        self.work_dir = Path(work_dir)
        self.rate_limit = rate_limit

        # Initialize components
        self.scraper = VaticanArchiveScraper(rate_limit=rate_limit)
        self.downloader = VaticanDownloader(
            download_dir=str(self.work_dir / "downloads" / "temp"),
            rate_limit=rate_limit
        )
        self.index = DocumentIndex(
            index_path=str(self.work_dir / "index.json")
        )

        # Initialize R2 storage if configured
        self.storage = None
        if r2_config:
            try:
                self.storage = R2StorageManager(**r2_config)
                LOGGER.info("R2 storage configured")
            except Exception as e:
                LOGGER.error("Failed to initialize R2 storage: %s", e)
                LOGGER.warning("Continuing without R2 upload capability")

        # Create directories
        self.work_dir.mkdir(parents=True, exist_ok=True)
        (self.work_dir / "logs").mkdir(exist_ok=True)
        (self.work_dir / "outputs" / "temp").mkdir(parents=True, exist_ok=True)

    def run_full_pipeline(self,
                         discover: bool = True,
                         download: bool = True,
                         process: bool = True,
                         upload: bool = True,
                         sections: Optional[List[str]] = None) -> Dict:
        """
        Run complete extraction pipeline.

        Args:
            discover: Run discovery stage
            download: Run download stage
            process: Run processing stage
            upload: Run upload stage
            sections: Optional list of sections to filter (e.g., ["CATECHISM", "COUNCILS"])

        Returns:
            Summary statistics dictionary
        """
        stats = {
            "discovered": 0,
            "downloaded": 0,
            "processed": 0,
            "uploaded": 0,
            "errors": []
        }

        LOGGER.info("=" * 60)
        LOGGER.info("VATICAN ARCHIVE EXTRACTION PIPELINE")
        LOGGER.info("=" * 60)

        # Stage 1: Discovery
        if discover:
            LOGGER.info("Stage 1: Discovering documents...")
            try:
                # Pass sections filter directly to scraper for efficiency
                documents = self.scraper.discover_all_documents(sections_filter=sections)

                # Add to index
                for doc in documents:
                    if self.index.add_document(doc):
                        stats["discovered"] += 1

                self.index.save()
                LOGGER.info("Discovered %d new documents", stats["discovered"])

            except Exception as e:
                LOGGER.error("Discovery stage failed: %s", e, exc_info=True)
                stats["errors"].append(f"Discovery: {e}")

        # Stage 2: Download
        if download:
            LOGGER.info("Stage 2: Downloading documents...")
            try:
                pending = self.index.get_pending_downloads()

                # Filter by sections if specified
                if sections:
                    pending = [d for d in pending if d.section in sections]

                if pending:
                    downloaded_paths = self.downloader.batch_download(
                        pending,
                        progress_callback=self._log_progress
                    )
                    stats["downloaded"] = len(downloaded_paths)

                    # Update index with download status
                    for doc, path in zip(pending, downloaded_paths):
                        if path:
                            self.index.mark_downloaded(doc.url, path)

                    self.index.save()
                    LOGGER.info("Downloaded %d documents", stats["downloaded"])
                else:
                    LOGGER.info("No pending downloads")

            except Exception as e:
                LOGGER.error("Download stage failed: %s", e, exc_info=True)
                stats["errors"].append(f"Download: {e}")

        # Stage 3: Processing
        if process:
            LOGGER.info("Stage 3: Processing documents...")
            try:
                stats["processed"] = self._process_documents(sections)
                LOGGER.info("Processed %d documents", stats["processed"])
            except Exception as e:
                LOGGER.error("Processing stage failed: %s", e, exc_info=True)
                stats["errors"].append(f"Processing: {e}")

        # Stage 4: Upload to R2
        if upload and self.storage:
            LOGGER.info("Stage 4: Uploading to R2...")
            try:
                stats["uploaded"] = self._upload_to_r2(sections)
                LOGGER.info("Uploaded %d documents to R2", stats["uploaded"])

                # Upload master index
                self.storage.upload_index(str(self.work_dir / "index.json"))

            except Exception as e:
                LOGGER.error("Upload stage failed: %s", e, exc_info=True)
                stats["errors"].append(f"Upload: {e}")
        elif upload and not self.storage:
            LOGGER.warning("Upload requested but R2 not configured")

        LOGGER.info("=" * 60)
        LOGGER.info("PIPELINE COMPLETE")
        LOGGER.info("=" * 60)

        return stats

    def _process_documents(self, sections: Optional[List[str]] = None) -> int:
        """
        Process downloaded documents using existing extractors.

        Args:
            sections: Optional list of sections to filter

        Returns:
            Number of successfully processed documents
        """
        pending = self.index.get_pending_processing()

        # Filter by sections if specified
        if sections:
            pending = [d for d in pending if d.section in sections]

        if not pending:
            LOGGER.info("No pending processing")
            return 0

        # Import extraction infrastructure
        try:
            from ...extractors.html import HtmlExtractor
            from ...analyzers.catholic import CatholicAnalyzer
            from ...core.output import write_outputs
            from ...core.noise_filter import NoiseFilter
        except ImportError as e:
            LOGGER.error("Failed to import extraction modules: %s", e)
            return 0

        success_count = 0
        config = {
            "min_paragraph_words": 1,
            "preserve_links": False,
        }

        analyzer = CatholicAnalyzer()
        temp_output_dir = self.work_dir / "outputs" / "temp"

        for doc in tqdm(pending, desc="Processing documents"):
            try:
                download_path = doc.download_path
                if not download_path or not Path(download_path).exists():
                    LOGGER.warning("Download path not found for: %s", doc.url)
                    continue

                # Extract with HTML extractor
                extractor = HtmlExtractor(download_path, config)
                extractor.load()
                extractor.parse()
                metadata = extractor.extract_metadata()

                # Filter noise chunks (index pages, copyright boilerplate, etc.)
                original_count = len(extractor.chunks)
                chunk_dicts = [c.to_dict() for c in extractor.chunks]
                filtered_dicts, filtered_count = NoiseFilter.filter_chunks(chunk_dicts)

                if filtered_count > 0:
                    LOGGER.debug("Filtered %d noise chunks from %s", filtered_count, doc.title)

                # Convert back to Chunk objects
                from ...core.models import Chunk
                extractor.chunks = [Chunk.from_dict(d) for d in filtered_dicts]

                # Enrich with Catholic analyzer
                # Reconstruct full text from chunks
                full_text = " ".join(c.text for c in extractor.chunks)
                enriched_metadata = analyzer.enrich_metadata(
                    base_metadata=metadata.to_dict(),
                    full_text=full_text,
                    chunks=filtered_dicts
                )

                # Update metadata
                for key, value in enriched_metadata.items():
                    setattr(metadata, key, value)

                # Generate output basename
                basename = self._get_output_basename(doc)

                # Write outputs (JSON, metadata, hierarchy, NDJSON)
                write_outputs(
                    extractor=extractor,
                    output_dir=str(temp_output_dir),
                    base_filename=basename,
                    ndjson=True  # Required for LLM chunking
                )

                # Mark as processed (r2_paths will be added during upload)
                self.index.mark_processed(doc.url, [])

                success_count += 1
                LOGGER.debug("Processed: %s", doc.title[:50])

            except Exception as e:
                LOGGER.error("Failed to process %s: %s", doc.title, e)
                continue

        # Save index with updated processing status
        self.index.save()

        return success_count

    def _upload_to_r2(self, sections: Optional[List[str]] = None) -> int:
        """
        Upload processed documents to R2.

        Args:
            sections: Optional list of sections to filter

        Returns:
            Number of successfully uploaded documents
        """
        if not self.storage:
            LOGGER.error("R2 storage not configured")
            return 0

        # Get processed but not yet uploaded documents
        processed = [
            doc for doc in self.index.documents.values()
            if doc.processed and not doc.r2_paths
        ]

        # Filter by sections if specified
        if sections:
            processed = [d for d in processed if d.section in sections]

        if not processed:
            LOGGER.info("No documents to upload")
            return 0

        temp_output_dir = self.work_dir / "outputs" / "temp"
        upload_count = 0

        for doc in tqdm(processed, desc="Uploading to R2"):
            try:
                basename = self._get_output_basename(doc)
                local_json = temp_output_dir / f"{basename}.json"
                local_ndjson = temp_output_dir / f"{basename}.ndjson"

                # Check files exist
                if not local_json.exists() or not local_ndjson.exists():
                    LOGGER.warning("Output files not found for: %s", doc.title)
                    continue

                # Upload
                r2_paths = self.storage.upload_document_outputs(
                    local_json=str(local_json),
                    local_ndjson=str(local_ndjson),
                    doc=doc
                )

                # Mark as uploaded
                if r2_paths:
                    self.index.mark_processed(doc.url, r2_paths)
                    upload_count += 1

            except Exception as e:
                LOGGER.error("Failed to upload %s: %s", doc.title, e)
                continue

        # Save index
        self.index.save()

        return upload_count

    def _get_output_basename(self, doc: VaticanDocument) -> str:
        """
        Generate clean output filename from document metadata.

        Args:
            doc: Document

        Returns:
            Basename for output files (without extension)
        """
        import re
        import hashlib

        # Sanitize title for filename
        clean_title = re.sub(r'[^\w\s-]', '', doc.title.lower())
        clean_title = re.sub(r'[-\s]+', '_', clean_title)
        clean_title = clean_title[:80]  # Limit length

        # Add URL hash to ensure uniqueness
        url_hash = hashlib.md5(doc.url.encode()).hexdigest()[:8]

        return f"{clean_title}_{url_hash}"

    def _log_progress(self, current: int, total: int, doc: VaticanDocument) -> None:
        """
        Progress callback for batch operations.

        Args:
            current: Current document number
            total: Total documents
            doc: Current document
        """
        percent = (current / total) * 100
        LOGGER.debug(
            "[%d/%d] (%.1f%%) %s",
            current,
            total,
            percent,
            doc.title[:50]
        )

        # Update progress file for external monitoring
        progress_file = self.work_dir / "progress.json"
        try:
            with open(progress_file, "w") as f:
                json.dump({
                    "current": current,
                    "total": total,
                    "percent": percent,
                    "current_doc": doc.title,
                    "current_url": doc.url,
                }, f)
        except Exception as e:
            LOGGER.warning("Failed to update progress file: %s", e)

    def resume_from_checkpoint(self, sections: Optional[List[str]] = None) -> Dict:
        """
        Resume interrupted pipeline from index checkpoint.

        Args:
            sections: Optional list of sections to filter

        Returns:
            Summary statistics dictionary
        """
        LOGGER.info("Resuming from checkpoint...")

        # Load existing index
        try:
            self.index.load()
            LOGGER.info("Loaded index with %d documents", len(self.index))
        except FileNotFoundError:
            LOGGER.warning("No checkpoint found, starting fresh")

        # Run pipeline (skip discovery, use existing index)
        return self.run_full_pipeline(
            discover=False,
            download=True,
            process=True,
            upload=True,
            sections=sections
        )

    def cleanup_downloads(self) -> None:
        """
        Remove local downloads after successful upload.

        Keeps index for resume capability.
        """
        download_dir = self.work_dir / "downloads"
        if download_dir.exists():
            import shutil
            try:
                shutil.rmtree(download_dir)
                LOGGER.info("Cleaned up downloads directory")
            except Exception as e:
                LOGGER.error("Failed to cleanup downloads: %s", e)

    def get_summary(self) -> Dict:
        """
        Get pipeline summary statistics.

        Returns:
            Dictionary with pipeline statistics
        """
        stats = self.index.export_summary()

        # Add download and R2 stats
        stats["download_stats"] = self.downloader.get_download_stats()

        if self.storage:
            stats["r2_stats"] = self.storage.get_storage_stats()

        return stats
