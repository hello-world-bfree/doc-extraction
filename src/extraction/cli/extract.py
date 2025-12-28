#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unified extraction CLI for all document formats.

Replaces legacy parsers with a single command that:
- Auto-detects document format (EPUB, PDF, HTML, Markdown, JSON)
- Supports pluggable domain analyzers (Catholic, Biblical, Academic, etc.)
- Provides batch processing with progress bars
- Maintains backward compatibility with legacy script arguments
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

from ..extractors.epub import EpubExtractor
from ..extractors.pdf import PdfExtractor
from ..extractors.html import HtmlExtractor
from ..extractors.markdown import MarkdownExtractor
from ..extractors.json import JsonExtractor
from ..core.output import write_outputs


# ====================== Logging ======================

LOGGER = logging.getLogger("extraction.cli")


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure logging level based on flags."""
    level = logging.INFO
    if verbose:
        level = logging.DEBUG
    if quiet:
        level = logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ====================== Format Detection ======================


def detect_format(file_path: str) -> str:
    """
    Detect document format from file extension.

    Args:
        file_path: Path to document file

    Returns:
        Format string: 'epub', 'pdf', 'html', 'md', 'json', or 'unknown'
    """
    ext = os.path.splitext(file_path)[1].lower()
    format_map = {
        '.epub': 'epub',
        '.pdf': 'pdf',
        '.html': 'html',
        '.htm': 'html',
        '.md': 'md',
        '.markdown': 'md',
        '.json': 'json',
    }
    return format_map.get(ext, 'unknown')


# ====================== Document Processing ======================


def process_document(
    file_path: str,
    config: dict,
    output_dir: str = None,
    base_filename: str = None,
    ndjson: bool = False,
    analyzer: str = "catholic",
    debug_dump: bool = False,
) -> bool:
    """
    Process a single document through extraction pipeline.

    Args:
        file_path: Path to document file
        config: Configuration dictionary for extractor
        output_dir: Output directory path
        base_filename: Base name for output files (None = auto)
        ndjson: Whether to write NDJSON output
        analyzer: Analyzer type ('catholic', 'generic', etc.)
        debug_dump: Whether to write debug information

    Returns:
        True if processing succeeded, False otherwise
    """
    # Detect format
    fmt = detect_format(file_path)

    # Select extractor based on format
    if fmt == 'epub':
        extractor = EpubExtractor(file_path, config)
        if hasattr(extractor, 'debug_dump'):
            extractor.debug_dump = debug_dump
    elif fmt == 'pdf':
        extractor = PdfExtractor(file_path, config)
    elif fmt == 'html':
        extractor = HtmlExtractor(file_path, config)
    elif fmt == 'md':
        extractor = MarkdownExtractor(file_path, config)
    elif fmt == 'json':
        extractor = JsonExtractor(file_path, config)
    else:
        LOGGER.error(f"Unknown format: {file_path}")
        return False

    # Process document
    try:
        extractor.load()
        extractor.parse()
        extractor.extract_metadata()

        # Write outputs
        write_outputs(
            extractor,
            base_filename=base_filename,
            ndjson=ndjson,
            output_dir=output_dir,
        )

        # Print success summary
        base = base_filename or os.path.splitext(os.path.basename(file_path))[0]
        outdir = output_dir or "."
        print(f"\n✅ {os.path.basename(file_path)}")
        print(
            f"   • paragraphs: {len(extractor.chunks)}   "
            f"quality: {round(extractor.quality_score, 3)} (route {extractor.route})"
        )
        print(
            f"   • outputs: {os.path.join(outdir, base)}.json, "
            f"{base}_metadata.json, {base}_hierarchy_report.txt"
            + (f", {base}.ndjson" if ndjson else "")
        )

        return True

    except Exception as e:
        LOGGER.exception("Failed to process %s: %s", file_path, e)
        return False


# ====================== Batch Processing ======================


def process_batch(
    input_path: str,
    recursive: bool,
    config: dict,
    output_dir: str = None,
    ndjson: bool = False,
    analyzer: str = "catholic",
    debug_dump: bool = False,
) -> tuple[int, int]:
    """
    Process multiple documents from a directory.

    Args:
        input_path: Directory path
        recursive: Whether to include subdirectories
        config: Configuration dictionary
        output_dir: Output directory path
        ndjson: Whether to write NDJSON output
        analyzer: Analyzer type
        debug_dump: Whether to write debug info

    Returns:
        Tuple of (success_count, total_count)
    """
    # Find all supported files
    supported_exts = {'.epub', '.pdf', '.html', '.htm', '.md', '.markdown', '.json'}
    files: List[str] = []

    pattern = "**/*" if recursive else "*"
    for ext in supported_exts:
        files.extend(str(p) for p in Path(input_path).glob(f"{pattern}{ext}") if p.is_file())

    if not files:
        LOGGER.error("No supported files found in %s (recursive=%s)", input_path, recursive)
        return 0, 0

    LOGGER.info("Found %d file(s)", len(files))

    # Process each file
    success_count = 0
    for file_path in files:
        if process_document(
            file_path,
            config,
            output_dir=output_dir,
            base_filename=None,  # Auto-generate from file name
            ndjson=ndjson,
            analyzer=analyzer,
            debug_dump=debug_dump,
        ):
            success_count += 1

    return success_count, len(files)


# ====================== CLI ======================


def main():
    """Main CLI entry point."""
    ap = argparse.ArgumentParser(
        description="Extract structured data from documents (EPUB, PDF, HTML, Markdown, JSON).",
        epilog="Examples:\n"
               "  extract document.epub\n"
               "  extract documents/ -r --output-dir outputs/\n"
               "  extract file.epub --analyzer catholic --ndjson\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Input
    ap.add_argument(
        "path",
        nargs="?",
        default="",
        help="Path to document file OR directory of files",
    )

    # Output
    ap.add_argument(
        "--output",
        "-o",
        help="Base name for output files (single-file mode only)",
        default="",
    )
    ap.add_argument(
        "--output-dir",
        help="Directory to write outputs (defaults to current directory)",
    )
    ap.add_argument(
        "--ndjson",
        action="store_true",
        help="Also emit chunks as newline-delimited JSON",
    )

    # Batch processing
    ap.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="When processing a directory, include subdirectories",
    )

    # Domain analyzer
    ap.add_argument(
        "--analyzer",
        default="catholic",
        choices=["catholic", "generic"],
        help="Domain-specific analyzer (default: catholic)",
    )

    # Extraction options (EPUB-specific, maintained for compatibility)
    ap.add_argument(
        "--toc-level",
        type=int,
        default=3,
        help="Hierarchy level for TOC titles (1-6) [EPUB]",
    )
    ap.add_argument(
        "--min-words",
        type=int,
        default=1,
        help="Minimum words for paragraph inclusion [EPUB]",
    )
    ap.add_argument(
        "--min-block-words",
        type=int,
        default=2,
        help="Min words to chunk generic block tags [EPUB]",
    )
    ap.add_argument(
        "--preserve-hierarchy",
        action="store_true",
        help="Preserve hierarchy across spine documents [EPUB]",
    )
    ap.add_argument(
        "--reset-depth",
        type=int,
        default=2,
        help="On doc boundary, clear levels >= this depth (1-6) [EPUB]",
    )
    ap.add_argument(
        "--deny-class",
        default=r"^(?:calibre\d+|note|footnote)$",
        help="Regex for class denylist [EPUB]",
    )

    # Logging
    ap.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose logging (DEBUG level)",
    )
    ap.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Quiet logging (WARNING level only)",
    )
    ap.add_argument(
        "--debug-dump",
        action="store_true",
        help="Write debug information to ./debug/ [EPUB]",
    )

    args = ap.parse_args()
    setup_logging(verbose=args.verbose, quiet=args.quiet)

    # Get input path
    in_path = (
        args.path.strip()
        or input("Enter path to document OR directory (or drag-drop): ").strip()
    )
    if not in_path:
        LOGGER.error("No path provided.")
        return 2
    if not os.path.exists(in_path):
        LOGGER.error("Path not found: %s", in_path)
        return 2

    # Build configuration
    config = {
        "toc_hierarchy_level": args.toc_level,
        "min_paragraph_words": args.min_words,
        "min_block_words": args.min_block_words,
        "preserve_hierarchy_across_docs": args.preserve_hierarchy,
        "reset_depth": args.reset_depth,
        "class_denylist": args.deny_class,
    }

    # Single-file mode
    if os.path.isfile(in_path):
        fmt = detect_format(in_path)
        if fmt == 'unknown':
            LOGGER.warning("Unknown file format; attempting to process anyway...")

        ok = process_document(
            in_path,
            config,
            output_dir=args.output_dir,
            base_filename=args.output if args.output else None,
            ndjson=args.ndjson,
            analyzer=args.analyzer,
            debug_dump=args.debug_dump,
        )
        return 0 if ok else 1

    # Directory/batch mode
    success_count, total_count = process_batch(
        in_path,
        recursive=args.recursive,
        config=config,
        output_dir=args.output_dir,
        ndjson=args.ndjson,
        analyzer=args.analyzer,
        debug_dump=args.debug_dump,
    )

    print(f"\n{'='*60}")
    print(f"✅ Successfully processed {success_count}/{total_count} files")
    if success_count < total_count:
        print(f"❌ Failed: {total_count - success_count} files")
    print(f"{'='*60}")

    return 0 if success_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())
