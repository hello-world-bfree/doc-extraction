#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unified output writing for all extractors.

Provides consistent output format across all document types:
- Main JSON (metadata + chunks + extraction_info)
- Metadata JSON (metadata only)
- Hierarchy report (human-readable structure)
- NDJSON (optional, chunks as newline-delimited JSON)
"""

import json
import os
from collections import OrderedDict
from datetime import datetime
from typing import Dict, List, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..extractors.base import BaseExtractor


def write_outputs(
    extractor: 'BaseExtractor',
    base_filename: str = None,
    ndjson: bool = False,
    output_dir: str = None,
    analyzer=None,
) -> None:
    """
    Write extractor outputs to disk in standard 3-file format.

    Creates:
    - {base}.json - Complete data (metadata + chunks + extraction_info)
    - {base}_metadata.json - Metadata only
    - {base}_hierarchy_report.txt - Human-readable hierarchy
    - {base}.ndjson - NDJSON format (if requested)

    Args:
        extractor: BaseExtractor instance (after parse() and extract_metadata())
        base_filename: Base name for output files (defaults to source file name)
        ndjson: Whether to also write NDJSON output
        output_dir: Output directory (defaults to current directory)
        analyzer: Optional analyzer instance to pass to get_output_data()
    """
    import logging
    LOGGER = logging.getLogger("extraction.output")

    base = base_filename or os.path.splitext(os.path.basename(extractor.source_path))[0]
    outdir = output_dir or "."
    os.makedirs(outdir, exist_ok=True)

    # Get complete output data (pass analyzer if extractor supports it)
    try:
        data = extractor.get_output_data(analyzer=analyzer)
    except TypeError:
        # Fallback for extractors that don't support analyzer parameter yet
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
    write_hierarchy_report(extractor, data["metadata"], data["chunks"], rep_out)

    # Write NDJSON if requested
    if ndjson:
        ndjson_out = os.path.join(outdir, f"{base}.ndjson")
        write_chunks_ndjson(data["chunks"], ndjson_out)


def write_chunks_ndjson(chunks: List[Dict], path: str) -> None:
    """
    Write chunks as newline-delimited JSON.

    Args:
        chunks: List of chunk dictionaries
        path: Output file path
    """
    import logging
    LOGGER = logging.getLogger("extraction.output")

    with open(path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    LOGGER.info("✓ Saved chunks NDJSON to %s", path)


def write_hierarchy_report(
    extractor: 'BaseExtractor',
    metadata: Dict[str, Any],
    chunks: List[Dict],
    filename: str
) -> None:
    """
    Generate human-readable hierarchical structure report.

    Creates a text report showing:
    - Document metadata summary
    - Hierarchical structure tree
    - Paragraph ranges and word counts per section
    - Overall statistics

    Args:
        extractor: BaseExtractor instance
        metadata: Metadata dictionary
        chunks: List of chunk dictionaries
        filename: Output file path
    """
    import logging
    LOGGER = logging.getLogger("extraction.output")

    if not chunks:
        return

    # Group chunks by hierarchy path
    structures: OrderedDict = OrderedDict()
    for chunk in chunks:
        h = chunk.get("hierarchy", {})
        key = tuple(h.get(f"level_{i}", "") for i in range(1, 7))
        structures.setdefault(key, []).append(chunk.get("paragraph_id", 0))

    # Build report lines
    lines: List[str] = []
    lines.append("DOCUMENT HIERARCHICAL STRUCTURE REPORT")
    lines.append("=" * 70)
    lines.append(f"Source: {os.path.basename(extractor.source_path)}")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Metadata section
    lines.append("DOCUMENT METADATA:")
    lines.append("-" * 20)
    for k, v in metadata.items():
        # Skip internal fields
        if k in ["provenance", "quality", "source_identifiers", "md_schema_version"]:
            continue
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
            chunk.get("word_count", 0) for chunk in chunks
            if chunk.get("paragraph_id") in para_ids
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
    lines.append(f"Total paragraphs: {len(chunks)}")
    lines.append(f"Total words: {sum(ch.get('word_count', 0) for ch in chunks):,}")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    LOGGER.info("✓ Created %s", filename)
