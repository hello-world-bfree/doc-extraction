#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Compatibility wrapper for book_parser_no_footnotes.py using refactored EpubExtractor.

This script provides the exact same CLI interface as book_parser_no_footnotes.py
but uses the new modular extraction architecture under the hood.

Produces identical output to the original parser for backward compatibility.
"""

import json
import logging
import os
import sys
from collections import OrderedDict
from datetime import datetime
from typing import List, Dict, Any

from src.extraction.extractors.epub import EpubExtractor

# ====================== Logging ======================

LOGGER = logging.getLogger("epub_parser")


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


# ====================== Output Writing ======================


def write_outputs(
    extractor: EpubExtractor,
    base_filename: str = None,
    ndjson: bool = False,
    output_dir: str = None,
) -> None:
    """
    Write extractor outputs to disk in the same format as original parser.

    Creates 3 files:
    - {base}.json - Complete data (metadata + chunks + extraction_info)
    - {base}_metadata.json - Metadata only
    - {base}_hierarchy_report.txt - Human-readable hierarchy
    - {base}.ndjson - NDJSON format (if requested)

    Args:
        extractor: EpubExtractor instance (after parse() and extract_metadata())
        base_filename: Base name for output files (defaults to source file name)
        ndjson: Whether to also write NDJSON output
        output_dir: Output directory (defaults to current directory)
    """
    base = base_filename or os.path.splitext(os.path.basename(extractor.source_path))[0]
    outdir = output_dir or "."
    os.makedirs(outdir, exist_ok=True)

    # Get complete output data
    data = extractor.get_output_data()

    # Write main JSON
    json_out = os.path.join(outdir, f"{base}.json")
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    LOGGER.info("✓ Saved data to %s", json_out)

    # Write metadata JSON
    md_out = os.path.join(outdir, f"{base}_metadata.json")
    with open(md_out, "w", encoding="utf-8") as f:
        json.dump(data["metadata"], f, ensure_ascii=False, indent=2)
    LOGGER.info("✓ Saved metadata to %s", md_out)

    # Write hierarchy report
    rep_out = os.path.join(outdir, f"{base}_hierarchy_report.txt")
    write_hierarchy_report(extractor, rep_out)

    # Write NDJSON if requested
    if ndjson:
        ndjson_out = os.path.join(outdir, f"{base}.ndjson")
        write_chunks_ndjson(extractor, ndjson_out)


def write_chunks_ndjson(extractor: EpubExtractor, path: str) -> None:
    """Write chunks as newline-delimited JSON."""
    with open(path, "w", encoding="utf-8") as f:
        for chunk in extractor.chunks:
            f.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")
    LOGGER.info("✓ Saved chunks NDJSON to %s", path)


def write_hierarchy_report(extractor: EpubExtractor, filename: str) -> None:
    """Generate human-readable hierarchical structure report."""
    if not extractor.chunks:
        return

    # Group chunks by hierarchy path
    structures: OrderedDict = OrderedDict()
    for chunk in extractor.chunks:
        h = chunk.hierarchy
        key = tuple(h.get(f"level_{i}", "") for i in range(1, 7))
        structures.setdefault(key, []).append(chunk.paragraph_id)

    # Build report lines
    lines: List[str] = []
    lines.append("EPUB HIERARCHICAL STRUCTURE REPORT")
    lines.append("=" * 70)
    lines.append(f"Source: {os.path.basename(extractor.source_path)}")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Metadata section
    lines.append("DOCUMENT METADATA:")
    lines.append("-" * 20)
    metadata_dict = extractor.metadata.to_dict()
    for k, v in metadata_dict.items():
        if v:
            if isinstance(v, list):
                v_str = (
                    ", ".join(str(x) for x in v)
                    if len(v) <= 3
                    else f"{', '.join(str(x) for x in v[:3])}... ({len(v)} total)"
                )
            elif isinstance(v, dict):
                js = json.dumps(v)
                v_str = js[:180] + ("…" if len(js) > 180 else "")
            else:
                v_str = str(v)
            lines.append(f"{k.replace('_', ' ').title()}: {v_str}")

    lines.append("")
    lines.append("STRUCTURE TREE:")
    lines.append("-" * 15)

    # Hierarchy tree
    for path, para_ids in structures.items():
        if not any(path):
            continue
        para_range = f"{min(para_ids)}-{max(para_ids)}" if para_ids else ""
        word_count = sum(
            chunk.word_count for chunk in extractor.chunks
            if chunk.paragraph_id in para_ids
        )
        for i, level_text in enumerate(path, 1):
            if level_text:
                indent = "  " * (i - 1)
                prefix = "└─ " if i > 1 else ""
                lines.append(f"{indent}{prefix}{level_text}")
        indent = "  " * len([t for t in path if t])
        lines.append(f"{indent}[¶ {para_range}, ~{word_count} words]")
        lines.append("")

    # Summary
    lines.append("SUMMARY:")
    lines.append("-" * 10)
    lines.append(f"Total unique hierarchy paths: {len(structures)}")
    lines.append(f"Total paragraphs: {len(extractor.chunks)}")
    lines.append(f"Total words: {sum(ch.word_count for ch in extractor.chunks):,}")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    LOGGER.info("✓ Created %s", filename)


# ====================== CLI ======================


def main():
    """Main CLI entry point - exact same interface as book_parser_no_footnotes.py"""
    import argparse

    ap = argparse.ArgumentParser(
        description="Parse an EPUB or a folder of EPUBs into hierarchical chunks with quality routing, provenance, and Catholic cross-refs."
    )
    ap.add_argument(
        "path",
        nargs="?",
        default="",
        help="Path to .epub file OR a directory of .epub files",
    )
    ap.add_argument(
        "--output",
        "-o",
        help="Base name for output files (single-file mode only)",
        default="",
    )
    ap.add_argument(
        "--output-dir",
        help="Directory to write outputs (defaults to current working directory)",
    )
    ap.add_argument(
        "--recursive",
        action="store_true",
        help="When a directory is provided, include subfolders",
    )
    ap.add_argument(
        "--toc-level", type=int, default=3, help="Hierarchy level for TOC titles (1-6)"
    )
    ap.add_argument(
        "--min-words", type=int, default=1, help="Minimum words for paragraph inclusion"
    )
    ap.add_argument(
        "--min-block-words",
        type=int,
        default=2,
        help="Min words to chunk generic block tags (div/section/article)",
    )
    ap.add_argument(
        "--preserve-hierarchy",
        action="store_true",
        help="Preserve hierarchy across spine documents",
    )
    ap.add_argument(
        "--reset-depth",
        type=int,
        default=2,
        help="On doc boundary, clear levels >= this depth (1-6)",
    )
    ap.add_argument(
        "--deny-class",
        default=r"^(?:calibre\d+|note|footnote)$",
        help="Regex for class denylist",
    )
    ap.add_argument("--ndjson", action="store_true", help="Also emit a chunks .ndjson")
    ap.add_argument("--verbose", action="store_true", help="Verbose logging")
    ap.add_argument("--quiet", action="store_true", help="Only warnings and errors")
    ap.add_argument(
        "--debug-dump",
        action="store_true",
        help="Write raw per-spine text and DOM stats to ./debug/",
    )

    args = ap.parse_args()
    setup_logging(verbose=args.verbose, quiet=args.quiet)

    in_path = (
        args.path.strip()
        or input("Enter path to .epub OR folder (or drag-drop): ").strip()
    )
    if not in_path:
        LOGGER.error("No path provided.")
        return 2
    if not os.path.exists(in_path):
        LOGGER.error("Path not found: %s", in_path)
        return 2

    config = {
        "toc_hierarchy_level": args.toc_level,
        "min_paragraph_words": args.min_words,
        "min_block_words": args.min_block_words,
        "preserve_hierarchy_across_docs": args.preserve_hierarchy,
        "reset_depth": args.reset_depth,
        "class_denylist": args.deny_class,
    }

    def process_one(epub_path: str) -> bool:
        """Process a single EPUB file using EpubExtractor."""
        extractor = EpubExtractor(epub_path, config)
        extractor.debug_dump = args.debug_dump
        try:
            extractor.load()
            extractor.parse()
            extractor.extract_metadata()
            write_outputs(
                extractor,
                base_filename=(args.output if os.path.isfile(in_path) else None),
                ndjson=args.ndjson,
                output_dir=args.output_dir,
            )
            base = (
                os.path.splitext(os.path.basename(epub_path))[0]
                if not args.output
                else args.output
            )
            outdir = args.output_dir or "."
            print(f"\n✅ {os.path.basename(epub_path)}")
            print(
                f"   • paragraphs: {len(extractor.chunks)}   quality: {round(extractor.quality_score, 3)} (route {extractor.route})"
            )
            print(
                f"   • outputs: {os.path.join(outdir, base)}.json, {base}_metadata.json, {base}_hierarchy_report.txt"
                + (f", {base}.ndjson" if args.ndjson else "")
            )
        except Exception as e:
            LOGGER.exception("Failed on %s: %s", epub_path, e)
            return False
        return True

    # Single-file mode
    if os.path.isfile(in_path):
        if not in_path.lower().endswith(".epub"):
            LOGGER.warning("The file does not look like an .epub; continuing anyway...")
        ok = process_one(in_path)
        return 0 if ok else 1

    # Directory mode
    from pathlib import Path

    epub_files: List[str] = []
    pattern = "**/*.epub" if args.recursive else "*.epub"
    for p in Path(in_path).glob(pattern):
        if p.is_file():
            epub_files.append(str(p))

    if not epub_files:
        LOGGER.error("No .epub files found in %s (recursive=%s)", in_path, args.recursive)
        return 2

    LOGGER.info("Found %d .epub file(s)", len(epub_files))
    success_count = 0
    for epub_file in epub_files:
        if process_one(epub_file):
            success_count += 1

    print(f"\n{'='*60}")
    print(f"✅ Successfully processed {success_count}/{len(epub_files)} files")
    if success_count < len(epub_files):
        print(f"❌ Failed: {len(epub_files) - success_count} files")
    print(f"{'='*60}")

    return 0 if success_count == len(epub_files) else 1


if __name__ == "__main__":
    sys.exit(main())
