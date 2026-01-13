#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Vatican Archive Extraction CLI

Extract all English documents from the Vatican archive for use in LLM chatbots.

Examples:
    # Full pipeline with AWS S3 upload
    vatican-extract --upload

    # Full pipeline with Cloudflare R2 upload
    vatican-extract --upload-to-r2

    # Download only (test mode)
    vatican-extract --download-only --limit 10

    # Process already-downloaded files
    vatican-extract --process-only

    # Resume interrupted extraction
    vatican-extract --resume

    # Filter by section
    vatican-extract --sections CATECHISM COUNCILS

    # Bible only to AWS S3
    vatican-extract --sections BIBLE --upload
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from ..pipelines.vatican.processor import VaticanArchiveProcessor

# Setup logger
LOGGER = logging.getLogger("vatican_extract")


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """
    Configure logging.

    Args:
        verbose: Enable DEBUG level logging
        quiet: Only show WARNING and ERROR
    """
    level = logging.INFO
    if verbose:
        level = logging.DEBUG
    if quiet:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def get_storage_config_from_env() -> dict:
    """
    Get S3/R2 storage configuration from environment variables.

    Supports both AWS S3 and Cloudflare R2:

    For AWS S3:
        - AWS_ACCESS_KEY_ID (or S3_ACCESS_KEY_ID)
        - AWS_SECRET_ACCESS_KEY (or S3_SECRET_ACCESS_KEY)
        - S3_BUCKET_NAME
        - AWS_REGION (optional, default: us-east-1)

    For Cloudflare R2:
        - R2_ACCESS_KEY_ID
        - R2_SECRET_ACCESS_KEY
        - R2_ENDPOINT_URL
        - R2_BUCKET_NAME

    Returns:
        Storage configuration dict
    """
    # Try R2 first (more specific)
    r2_access_key = os.getenv("R2_ACCESS_KEY_ID")
    r2_secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    r2_endpoint = os.getenv("R2_ENDPOINT_URL")
    r2_bucket = os.getenv("R2_BUCKET_NAME")

    if all([r2_access_key, r2_secret_key, r2_endpoint, r2_bucket]):
        LOGGER.info("Using Cloudflare R2 configuration")
        return {
            "access_key_id": r2_access_key,
            "secret_access_key": r2_secret_key,
            "endpoint_url": r2_endpoint,
            "bucket_name": r2_bucket,
        }

    # Try AWS S3
    s3_access_key = os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("S3_ACCESS_KEY_ID")
    s3_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY") or os.getenv("S3_SECRET_ACCESS_KEY")
    s3_bucket = os.getenv("S3_BUCKET_NAME")
    s3_region = os.getenv("AWS_REGION", "us-east-1")

    if all([s3_access_key, s3_secret_key, s3_bucket]):
        LOGGER.info("Using AWS S3 configuration (region: %s)", s3_region)
        return {
            "access_key_id": s3_access_key,
            "secret_access_key": s3_secret_key,
            "endpoint_url": None,  # Use default AWS S3 endpoint
            "bucket_name": s3_bucket,
            "region_name": s3_region,
        }

    # Neither configured
    raise ValueError(
        "Missing required storage environment variables.\n\n"
        "For AWS S3, set:\n"
        "  export AWS_ACCESS_KEY_ID='your_key'\n"
        "  export AWS_SECRET_ACCESS_KEY='your_secret'\n"
        "  export S3_BUCKET_NAME='your_bucket'\n"
        "  export AWS_REGION='us-east-1'  # optional\n\n"
        "For Cloudflare R2, set:\n"
        "  export R2_ACCESS_KEY_ID='your_key'\n"
        "  export R2_SECRET_ACCESS_KEY='your_secret'\n"
        "  export R2_ENDPOINT_URL='https://[account-id].r2.cloudflarestorage.com'\n"
        "  export R2_BUCKET_NAME='your_bucket'\n"
    )


def print_summary(stats: dict, work_dir: str) -> None:
    """
    Print pipeline summary.

    Args:
        stats: Statistics dictionary
        work_dir: Working directory path
    """
    print("\n" + "=" * 60)
    print("VATICAN ARCHIVE EXTRACTION COMPLETE")
    print("=" * 60)

    # Discovery stats
    if stats.get("discovered"):
        print(f"Discovered:  {stats['discovered']:,} new documents")

    # Download stats
    if stats.get("downloaded"):
        print(f"Downloaded:  {stats['downloaded']:,} documents")

    # Processing stats
    if stats.get("processed"):
        print(f"Processed:   {stats['processed']:,} documents")

    # Upload stats
    if stats.get("uploaded"):
        print(f"Uploaded:    {stats['uploaded']:,} documents to R2")

    # Error stats
    if stats.get("errors"):
        print(f"\nErrors:      {len(stats['errors'])} (see logs)")
        for error in stats["errors"][:5]:  # Show first 5 errors
            print(f"  - {error}")
        if len(stats["errors"]) > 5:
            print(f"  ... and {len(stats['errors']) - 5} more")

    print("\n" + "-" * 60)
    print(f"Working directory: {work_dir}")
    print(f"Index file:        {work_dir}/index.json")
    print(f"Logs:              {work_dir}/logs/")
    print("=" * 60 + "\n")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract English documents from Vatican archive",
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Working directory
    parser.add_argument(
        "--work-dir",
        default="./vatican_archive",
        help="Working directory for downloads and outputs (default: ./vatican_archive)"
    )

    # Pipeline stages
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="Only discover documents, don't download or process"
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Only download documents, don't process"
    )
    parser.add_argument(
        "--process-only",
        action="store_true",
        help="Only process already-downloaded documents"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume interrupted extraction from checkpoint"
    )

    # Cloud upload
    parser.add_argument(
        "--upload-to-r2",
        action="store_true",
        help="Upload processed outputs to S3/R2 (requires AWS_*/S3_* or R2_* env vars)"
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Alias for --upload-to-r2"
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip R2 upload even if configured"
    )

    # Filtering
    parser.add_argument(
        "--sections",
        nargs="+",
        choices=["BIBLE", "CATECHISM", "CANON_LAW", "COUNCILS", "MAGISTERIUM", "SOCIAL"],
        help="Only process specific sections"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of documents to process (for testing)"
    )

    # Performance
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=1.0,
        help="Seconds between requests (default: 1.0)"
    )

    # Cleanup
    parser.add_argument(
        "--cleanup-downloads",
        action="store_true",
        help="Remove local downloads after successful upload"
    )

    # Output
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose logging (DEBUG level)"
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Quiet mode (WARNING level only)"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose, quiet=args.quiet)

    # Get S3/R2 config if upload requested
    storage_config = None
    upload_requested = (args.upload_to_r2 or args.upload) and not args.no_upload
    if upload_requested:
        try:
            storage_config = get_storage_config_from_env()
            LOGGER.info("Cloud storage upload enabled")
        except ValueError as e:
            LOGGER.error(str(e))
            return 1

    # Initialize processor
    try:
        processor = VaticanArchiveProcessor(
            work_dir=args.work_dir,
            rate_limit=args.rate_limit,
            r2_config=storage_config
        )
    except Exception as e:
        LOGGER.error("Failed to initialize processor: %s", e)
        return 1

    # Determine pipeline stages
    if args.resume:
        LOGGER.info("Resuming from checkpoint...")
        stats = processor.resume_from_checkpoint(sections=args.sections)
    else:
        discover = not (args.download_only or args.process_only)
        download = not (args.discover_only or args.process_only)
        process = not (args.discover_only or args.download_only)

        stats = processor.run_full_pipeline(
            discover=discover,
            download=download,
            process=process,
            upload=upload_requested,
            sections=args.sections
        )

    # Cleanup if requested
    if args.cleanup_downloads and upload_requested:
        LOGGER.info("Cleaning up downloads...")
        processor.cleanup_downloads()

    # Print summary
    print_summary(stats, args.work_dir)

    # Write final summary to file
    summary_file = Path(args.work_dir) / "summary.json"
    import json
    with open(summary_file, 'w') as f:
        json.dump(stats, f, indent=2)
    LOGGER.info("Summary written to: %s", summary_file)

    # Return exit code
    return 0 if not stats.get("errors") else 1


if __name__ == "__main__":
    sys.exit(main())
