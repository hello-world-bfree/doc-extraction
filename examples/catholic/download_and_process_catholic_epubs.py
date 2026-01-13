#!/usr/bin/env python3
"""
Download and process Catholic EPUBs from S3 with minimal disk usage.

Storage-efficient pipeline:
1. Download one EPUB at a time
2. Process it immediately with extraction pipeline
3. Delete the EPUB after processing
4. Keep only the JSON outputs

This approach minimizes disk usage for laptops with limited storage.
"""

import os
import sys
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from tqdm import tqdm
import logging

# Import extraction infrastructure
from extraction.extractors.epub import EpubExtractor
from extraction.analyzers.catholic import CatholicAnalyzer
from extraction.core.output import write_outputs

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
LOGGER = logging.getLogger(__name__)


class StreamingEpubProcessor:
    """Downloads and processes EPUBs one at a time to minimize disk usage."""

    def __init__(
        self,
        bucket_name: str,
        s3_prefix: str,
        output_dir: str = "./catholic_epub_outputs",
        temp_dir: str = "./temp_epub",
        aws_profile: str = None,
        preserve_formatting: bool = True,
        chunking_strategy: str = "rag",
    ):
        self.bucket_name = bucket_name
        self.s3_prefix = s3_prefix
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(temp_dir)
        self.preserve_formatting = preserve_formatting
        self.chunking_strategy = chunking_strategy

        # Initialize S3 client
        session = boto3.Session(profile_name=aws_profile) if aws_profile else boto3.Session()
        self.s3 = session.client('s3')

        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Initialize analyzer
        self.analyzer = CatholicAnalyzer()

        # Stats
        self.stats = {
            "total_epubs": 0,
            "processed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": []
        }

    def list_epubs(self):
        """List all EPUB files in the S3 bucket."""
        LOGGER.info(f"Listing EPUBs in s3://{self.bucket_name}/{self.s3_prefix}")

        paginator = self.s3.get_paginator('list_objects_v2')
        epub_keys = []

        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.s3_prefix):
            if 'Contents' not in page:
                continue
            for obj in page['Contents']:
                key = obj['Key']
                if key.lower().endswith('.epub'):
                    epub_keys.append(key)

        self.stats["total_epubs"] = len(epub_keys)
        LOGGER.info(f"Found {len(epub_keys)} EPUB files")
        return epub_keys

    def process_single_epub(self, s3_key: str):
        """
        Download, process, and cleanup a single EPUB.

        Args:
            s3_key: S3 object key for the EPUB

        Returns:
            True if successful, False otherwise
        """
        epub_name = Path(s3_key).name
        temp_epub_path = self.temp_dir / epub_name

        # Generate output basename (remove .epub extension)
        output_basename = epub_name.rsplit('.epub', 1)[0]
        output_json = self.output_dir / f"{output_basename}.json"

        # Skip if already processed
        if output_json.exists():
            LOGGER.info(f"Skipping (already processed): {epub_name}")
            self.stats["skipped"] += 1
            return True

        try:
            # Step 1: Download EPUB
            LOGGER.info(f"Downloading: {epub_name}")
            self.s3.download_file(self.bucket_name, s3_key, str(temp_epub_path))

            # Step 2: Extract
            LOGGER.info(f"Processing: {epub_name}")
            config = {
                "preserve_formatting": self.preserve_formatting,
                "chunking_strategy": self.chunking_strategy,
                "min_chunk_words": 100,
                "max_chunk_words": 500,
                "filter_noise": True,  # Enable noise filtering
                "filter_tiny_chunks": "conservative",  # Conservative tiny chunk filter
            }

            extractor = EpubExtractor(str(temp_epub_path), config)
            extractor.load()
            extractor.parse()
            metadata = extractor.extract_metadata()

            # Step 3: Enrich with Catholic analyzer
            full_text = " ".join(c.text for c in extractor.chunks)
            enriched_metadata = self.analyzer.enrich_metadata(
                base_metadata=metadata.to_dict(),
                full_text=full_text,
                chunks=[c.to_dict() for c in extractor.chunks]
            )

            # Update metadata
            for key, value in enriched_metadata.items():
                setattr(metadata, key, value)

            # Step 4: Write outputs (this populates quality/provenance in output)
            write_outputs(
                extractor=extractor,
                output_dir=str(self.output_dir),
                base_filename=output_basename,
                ndjson=True  # Also create NDJSON for embedding pipelines
            )

            # Get quality score for logging (from extractor properties)
            quality_score = extractor.quality_score if hasattr(extractor, 'quality_score') else 0.0
            quality_route = extractor.route if hasattr(extractor, 'route') else 'N/A'

            LOGGER.info(
                f"✓ Processed: {epub_name} "
                f"({len(extractor.chunks)} chunks, "
                f"quality: {quality_score:.2f}, route: {quality_route})"
            )

            self.stats["processed"] += 1
            return True

        except Exception as e:
            LOGGER.error(f"✗ Failed to process {epub_name}: {e}", exc_info=True)
            self.stats["failed"] += 1
            self.stats["errors"].append({
                "epub": epub_name,
                "error": str(e)
            })
            return False

        finally:
            # Step 5: Cleanup - Always delete the EPUB to save space
            if temp_epub_path.exists():
                temp_epub_path.unlink()
                LOGGER.debug(f"Deleted: {temp_epub_path}")

    def process_all(self):
        """Process all EPUBs in the S3 bucket."""
        epub_keys = self.list_epubs()

        if not epub_keys:
            LOGGER.warning("No EPUBs found in bucket")
            return

        LOGGER.info("=" * 60)
        LOGGER.info("STARTING CATHOLIC EPUB PROCESSING PIPELINE")
        LOGGER.info(f"Total EPUBs: {len(epub_keys)}")
        LOGGER.info(f"Output directory: {self.output_dir}")
        LOGGER.info(f"Chunking strategy: {self.chunking_strategy}")
        LOGGER.info(f"Preserve formatting: {self.preserve_formatting}")
        LOGGER.info("=" * 60)

        # Process each EPUB
        for s3_key in tqdm(epub_keys, desc="Processing EPUBs"):
            self.process_single_epub(s3_key)

        # Cleanup temp directory
        if self.temp_dir.exists() and not list(self.temp_dir.iterdir()):
            self.temp_dir.rmdir()

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print processing summary."""
        LOGGER.info("=" * 60)
        LOGGER.info("PROCESSING COMPLETE")
        LOGGER.info("=" * 60)
        LOGGER.info(f"Total EPUBs: {self.stats['total_epubs']}")
        LOGGER.info(f"Successfully processed: {self.stats['processed']}")
        LOGGER.info(f"Skipped (already done): {self.stats['skipped']}")
        LOGGER.info(f"Failed: {self.stats['failed']}")

        if self.stats["errors"]:
            LOGGER.info("\nErrors:")
            for error in self.stats["errors"]:
                LOGGER.info(f"  - {error['epub']}: {error['error']}")

        LOGGER.info(f"\nOutputs saved to: {self.output_dir}")
        LOGGER.info("=" * 60)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Download and process Catholic EPUBs from S3 (storage-efficient)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all EPUBs with default settings
  python download_and_process_catholic_epubs.py

  # Custom output directory
  python download_and_process_catholic_epubs.py --output-dir ./my_outputs

  # NLP chunking mode (paragraph-level)
  python download_and_process_catholic_epubs.py --chunking-strategy nlp

  # Disable formatting preservation
  python download_and_process_catholic_epubs.py --no-preserve-formatting

  # With AWS profile
  python download_and_process_catholic_epubs.py --profile my-sso-profile
        """
    )

    parser.add_argument(
        "--bucket",
        default="ai-resources-zjr42b1jkj",
        help="S3 bucket name (default: ai-resources-zjr42b1jkj)"
    )
    parser.add_argument(
        "--prefix",
        default="epubs/",
        help="S3 prefix/folder (default: epubs/)"
    )
    parser.add_argument(
        "--output-dir",
        default="./catholic_epub_outputs",
        help="Output directory for JSON files (default: ./catholic_epub_outputs)"
    )
    parser.add_argument(
        "--temp-dir",
        default="./temp_epub",
        help="Temporary directory for downloads (default: ./temp_epub)"
    )
    parser.add_argument(
        "--profile",
        help="AWS profile name (optional, uses default credentials if not specified)"
    )
    parser.add_argument(
        "--chunking-strategy",
        choices=["rag", "nlp", "semantic", "paragraph"],
        default="rag",
        help="Chunking strategy: rag/semantic (100-500 words) or nlp/paragraph (paragraph-level)"
    )
    parser.add_argument(
        "--no-preserve-formatting",
        action="store_true",
        help="Disable formatting preservation (poetry, blockquotes, lists, etc.)"
    )

    args = parser.parse_args()

    # Check boto3 is installed
    try:
        import boto3
    except ImportError:
        LOGGER.error("boto3 not installed. Install with: uv pip install -e \".[vatican]\"")
        sys.exit(1)

    # Create processor
    processor = StreamingEpubProcessor(
        bucket_name=args.bucket,
        s3_prefix=args.prefix,
        output_dir=args.output_dir,
        temp_dir=args.temp_dir,
        aws_profile=args.profile,
        preserve_formatting=not args.no_preserve_formatting,
        chunking_strategy=args.chunking_strategy,
    )

    # Process all EPUBs
    processor.process_all()


if __name__ == "__main__":
    main()
