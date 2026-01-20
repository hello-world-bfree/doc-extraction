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
from typing import List

from ..extractors.epub import EpubExtractor
from ..extractors.pdf import PdfExtractor
from ..extractors.html import HtmlExtractor
from ..extractors.markdown import MarkdownExtractor
from ..extractors.json import JsonExtractor
from ..extractors.configs import (
    EpubExtractorConfig,
    PdfExtractorConfig,
    HtmlExtractorConfig,
    MarkdownExtractorConfig,
    JsonExtractorConfig,
)
from ..analyzers.generic import GenericAnalyzer
from ..core.output import write_outputs
from ..core.config import load_config, show_config_sources, generate_sample_config


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
        '.txt': 'md',  # Plain text handled by Markdown extractor
        '.json': 'json',
    }
    return format_map.get(ext, 'unknown')


# ====================== Config Building ======================


def build_config_for_format(fmt: str, config_dict: dict):
    """
    Build appropriate config dataclass for the given format.

    Args:
        fmt: Format string ('epub', 'pdf', 'html', 'md', 'json')
        config_dict: Dictionary of config options from CLI args

    Returns:
        Config dataclass instance for the format
    """
    if fmt == 'epub':
        return EpubExtractorConfig(
            toc_hierarchy_level=config_dict.get('toc_hierarchy_level', 3),
            min_paragraph_words=config_dict.get('min_paragraph_words', 1),
            min_block_words=config_dict.get('min_block_words', 2),
            preserve_hierarchy_across_docs=config_dict.get('preserve_hierarchy_across_docs', False),
            reset_depth=config_dict.get('reset_depth', 2),
            class_denylist=config_dict.get('class_denylist', r"^(?:calibre\d+|note|footnote)$"),
            filter_tiny_chunks=config_dict.get('filter_tiny_chunks', 'conservative'),
            filter_noise=config_dict.get('filter_noise', True),
            preserve_small_chunks=config_dict.get('preserve_small_chunks', True),
            detect_visual_headings=config_dict.get('detect_visual_headings', False),
            visual_heading_font_threshold=config_dict.get('visual_heading_font_threshold', 1.3),
            detect_front_matter=config_dict.get('detect_front_matter', False),
            filter_front_matter=config_dict.get('filter_front_matter', False),
            detect_references=config_dict.get('detect_references', False),
            chunking_strategy=config_dict.get('chunking_strategy', 'rag'),
            min_chunk_words=config_dict.get('min_chunk_words', 100),
            max_chunk_words=config_dict.get('max_chunk_words', 500),
        )
    elif fmt == 'pdf':
        return PdfExtractorConfig(
            min_paragraph_words=config_dict.get('min_paragraph_words', 1),
            heading_font_threshold=config_dict.get('heading_font_threshold', 1.2),
            use_ocr=config_dict.get('use_ocr', False),
            filter_noise=config_dict.get('filter_noise', True),
            preserve_small_chunks=config_dict.get('preserve_small_chunks', True),
            chunking_strategy=config_dict.get('chunking_strategy', 'rag'),
            min_chunk_words=config_dict.get('min_chunk_words', 100),
            max_chunk_words=config_dict.get('max_chunk_words', 500),
        )
    elif fmt == 'html':
        return HtmlExtractorConfig(
            min_paragraph_words=config_dict.get('min_paragraph_words', 1),
            preserve_links=config_dict.get('preserve_links', True),
            filter_noise=config_dict.get('filter_noise', True),
            preserve_small_chunks=config_dict.get('preserve_small_chunks', True),
            chunking_strategy=config_dict.get('chunking_strategy', 'rag'),
            min_chunk_words=config_dict.get('min_chunk_words', 100),
            max_chunk_words=config_dict.get('max_chunk_words', 500),
        )
    elif fmt == 'md':
        return MarkdownExtractorConfig(
            min_paragraph_words=config_dict.get('min_paragraph_words', 1),
            preserve_code_blocks=config_dict.get('preserve_code_blocks', True),
            extract_frontmatter=config_dict.get('extract_frontmatter', True),
            filter_noise=config_dict.get('filter_noise', True),
            preserve_small_chunks=config_dict.get('preserve_small_chunks', True),
            chunking_strategy=config_dict.get('chunking_strategy', 'rag'),
            min_chunk_words=config_dict.get('min_chunk_words', 100),
            max_chunk_words=config_dict.get('max_chunk_words', 500),
        )
    elif fmt == 'json':
        return JsonExtractorConfig(
            mode=config_dict.get('import_mode', 'import'),
            import_chunks=config_dict.get('import_chunks', True),
            import_metadata=config_dict.get('import_metadata', True),
            preserve_small_chunks=config_dict.get('preserve_small_chunks', True),
            chunking_strategy=config_dict.get('chunking_strategy', 'rag'),
            min_chunk_words=config_dict.get('min_chunk_words', 100),
            max_chunk_words=config_dict.get('max_chunk_words', 500),
        )
    else:
        return None


# ====================== Document Processing ======================


def process_document(
    file_path: str,
    config: dict,
    output_dir: str = None,
    base_filename: str = None,
    ndjson: bool = False,
    analyzer: str = "generic",
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

    # Instantiate analyzer based on CLI flag
    analyzer_instance = None
    if analyzer == "catholic":
        from ..analyzers.catholic import CatholicAnalyzer
        analyzer_instance = CatholicAnalyzer()
    elif analyzer == "generic":
        analyzer_instance = GenericAnalyzer()

    # Build config dataclass for format
    config_obj = build_config_for_format(fmt, config)
    if config_obj is None:
        LOGGER.error(f"Unknown format: {file_path}")
        return False

    # Select extractor based on format (pass config and analyzer to constructor)
    if fmt == 'epub':
        extractor = EpubExtractor(file_path, config_obj, analyzer_instance)
        if hasattr(extractor, 'debug_dump'):
            extractor.debug_dump = debug_dump
    elif fmt == 'pdf':
        extractor = PdfExtractor(file_path, config_obj, analyzer_instance)
    elif fmt == 'html':
        extractor = HtmlExtractor(file_path, config_obj, analyzer_instance)
    elif fmt == 'md':
        extractor = MarkdownExtractor(file_path, config_obj, analyzer_instance)
    elif fmt == 'json':
        extractor = JsonExtractor(file_path, config_obj, analyzer_instance)
    else:
        LOGGER.error(f"Unknown format: {file_path}")
        return False

    # Process document
    try:
        extractor.load()
        extractor.parse()
        extractor.extract_metadata()

        # Write outputs (pass analyzer for get_output_data call)
        write_outputs(
            extractor,
            base_filename=base_filename,
            ndjson=ndjson,
            output_dir=output_dir,
            analyzer=analyzer_instance,
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
    analyzer: str = "generic",
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
    # Load config file defaults
    cfg = load_config()

    ap = argparse.ArgumentParser(
        description="Extract structured data from documents (EPUB, PDF, HTML, Markdown, JSON).",
        epilog="Examples:\n"
               "  extract document.epub\n"
               "  extract documents/ -r --output-dir outputs/\n"
               "  extract file.epub --analyzer catholic --ndjson\n"
               "\n"
               "Configuration:\n"
               "  extract --show-config     Show active configuration sources\n"
               "  extract --init-config     Generate sample extraction.toml\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Config management
    ap.add_argument(
        "--show-config",
        action="store_true",
        help="Show active configuration sources and exit",
    )
    ap.add_argument(
        "--init-config",
        action="store_true",
        help="Generate sample extraction.toml in current directory and exit",
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
        default=cfg.get("analyzer", "generic"),
        choices=["catholic", "generic"],
        help=f"Domain-specific analyzer (default: {cfg.get('analyzer', 'generic')})",
    )

    # Extraction options (EPUB-specific, maintained for compatibility)
    ap.add_argument(
        "--toc-level",
        type=int,
        default=cfg.get("toc_hierarchy_level", 1),
        help=f"Hierarchy level for TOC titles (1-6) [EPUB] (default: {cfg.get('toc_hierarchy_level', 1)})",
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
    ap.add_argument(
        "--filter-tiny-chunks",
        choices=["off", "conservative", "standard", "aggressive"],
        default=cfg.get("filter_tiny_chunks", "conservative"),
        help=f"Filter tiny chunks (<5 words) - conservative (index/TOC/punctuation), standard (+bullets/refs), aggressive (+appendixes), off (disable) [EPUB] (default: {cfg.get('filter_tiny_chunks', 'conservative')})",
    )
    ap.add_argument(
        "--no-filter-noise",
        action="store_true",
        default=not cfg.get("filter_noise", True),
        help="Disable noise filtering (index pages, reference lists, boilerplate).",
    )
    ap.add_argument(
        "--filter-small-chunks",
        action="store_true",
        default=not cfg.get("preserve_small_chunks", True),
        help="Filter out chunks below min_chunk_words instead of preserving them with quality flags.",
    )

    # Visual hierarchy detection (EPUB)
    ap.add_argument(
        "--detect-visual-headings",
        action="store_true",
        default=cfg.get("detect_visual_headings", False),
        help=f"Detect headings from inline font-size styles (EPUB only) (default: {cfg.get('detect_visual_headings', False)})",
    )
    ap.add_argument(
        "--visual-heading-threshold",
        type=float,
        default=cfg.get("visual_heading_font_threshold", 1.3),
        metavar="RATIO",
        help=f"Font-size threshold for visual headings (default: {cfg.get('visual_heading_font_threshold', 1.3)}). EPUB only.",
    )

    # Front/back matter detection (EPUB)
    ap.add_argument(
        "--detect-front-matter",
        action="store_true",
        default=cfg.get("detect_front_matter", False),
        help=f"Detect and flag common front/back matter sections (dedications, glossaries, indexes, etc.). EPUB only (default: {cfg.get('detect_front_matter', False)})",
    )
    ap.add_argument(
        "--filter-front-matter",
        action="store_true",
        default=cfg.get("filter_front_matter", False),
        help=f"Hard filter detected front/back matter (requires --detect-front-matter) (default: {cfg.get('filter_front_matter', False)})",
    )
    ap.add_argument(
        "--detect-references",
        action="store_true",
        default=cfg.get("detect_references", False),
        help=f"Detect and flag end-of-chapter reference/citation blocks. EPUB only (default: {cfg.get('detect_references', False)})",
    )

    # Chunking strategy
    ap.add_argument(
        "--chunking-strategy",
        choices=["rag", "semantic", "embeddings", "nlp", "paragraph"],
        default=cfg.get("chunking_strategy", "rag"),
        help=f"Chunking strategy: 'rag' (100-500 words for embeddings), 'nlp' (paragraph-level for fine-grained analysis). Aliases: semantic=rag, embeddings=rag, paragraph=nlp (default: {cfg.get('chunking_strategy', 'rag')})",
    )
    ap.add_argument(
        "--min-chunk-words",
        type=int,
        default=cfg.get("min_chunk_words", 100),
        help=f"Minimum words per chunk for semantic/RAG strategy (default: {cfg.get('min_chunk_words', 100)})",
    )
    ap.add_argument(
        "--max-chunk-words",
        type=int,
        default=cfg.get("max_chunk_words", 500),
        help=f"Maximum words per chunk for semantic/RAG strategy (default: {cfg.get('max_chunk_words', 500)})",
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

    # Handle config commands
    if args.show_config:
        print(show_config_sources())
        print("\nActive configuration:")
        for key, value in sorted(cfg.items()):
            print(f"  {key}: {value}")
        return 0

    if args.init_config:
        config_path = Path("extraction.toml")
        if config_path.exists():
            print(f"Config file already exists: {config_path}")
            return 1
        config_path.write_text(generate_sample_config())
        print(f"Created {config_path}")
        return 0

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
        "filter_tiny_chunks": args.filter_tiny_chunks,
        "filter_noise": not args.no_filter_noise,
        "preserve_small_chunks": not args.filter_small_chunks,
        "detect_visual_headings": args.detect_visual_headings,
        "visual_heading_font_threshold": args.visual_heading_threshold,
        "detect_front_matter": args.detect_front_matter,
        "filter_front_matter": args.filter_front_matter,
        "detect_references": args.detect_references,
        # Chunking strategy
        "chunking_strategy": args.chunking_strategy,
        "min_chunk_words": args.min_chunk_words,
        "max_chunk_words": args.max_chunk_words,
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
