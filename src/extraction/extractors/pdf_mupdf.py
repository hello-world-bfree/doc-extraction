import hashlib
import logging
import os
from collections import Counter
from typing import Optional

from .base import BaseExtractor
from .configs import MuPdfPdfExtractorConfig
from ..core.chunking import split_sentences
from ..core.extraction import (
    extract_cross_references,
    extract_dates,
    extract_scripture_references,
)
from ..core.identifiers import stable_id
from ..core.models import Chunk, Metadata
from ..core.text import clean_text, estimate_word_count
from ..exceptions import DependencyError, FileNotFoundError, ParseError
from ..analyzers.base import BaseAnalyzer

PARSER_VERSION = "3.0.0-mupdf"
MD_SCHEMA_VERSION = "2025-09-08"

LOGGER = logging.getLogger("pdf_mupdf_parser")

try:
    from .._native.mupdf import MuPdfDocument, SpanData
    NATIVE_AVAILABLE = True
except Exception:
    NATIVE_AVAILABLE = False


def _compute_modal_font_size(all_page_spans: list[tuple[int, list]]) -> float:
    size_counter: Counter[float] = Counter()
    for _, spans in all_page_spans:
        for span in spans:
            rounded = round(span.font_size, 1)
            size_counter[rounded] += len(span.text)
    if not size_counter:
        return 12.0
    return size_counter.most_common(1)[0][0]


def _rank_heading_sizes(
    all_page_spans: list[tuple[int, list]],
    body_size: float,
    config: "MuPdfPdfExtractorConfig",
) -> dict[float, int]:
    threshold = body_size * config.heading_font_threshold
    heading_sizes: Counter[float] = Counter()
    for _, spans in all_page_spans:
        for span in spans:
            if span.is_mono:
                continue
            rounded = round(span.font_size, 1)
            if rounded >= threshold:
                heading_sizes[rounded] += 1
            elif rounded > body_size and span.is_bold:
                heading_sizes[rounded] += 1

    if not heading_sizes:
        return {}
    max_count = heading_sizes.most_common(1)[0][1]
    min_count = max(5, max_count // 10)
    ranked = sorted(
        (size for size, count in heading_sizes.items() if count >= min_count),
        reverse=True,
    )
    return {size: level + 1 for level, size in enumerate(ranked) if level < 6}


class MuPdfPdfExtractor(BaseExtractor):

    def __init__(
        self,
        source_path: str,
        config: Optional[MuPdfPdfExtractorConfig] = None,
        analyzer: Optional[BaseAnalyzer] = None,
    ):
        if not NATIVE_AVAILABLE:
            raise DependencyError(
                "de_mupdf native library",
                "MuPDF PDF extraction",
                "cd zig && zig build -Doptimize=ReleaseFast",
            )
        super().__init__(source_path, config or MuPdfPdfExtractorConfig(), analyzer)
        self.__total_pages = 0

    def _do_load(self) -> None:
        if not os.path.exists(self.source_path):
            raise FileNotFoundError(self.source_path)

        with open(self.source_path, "rb") as f:
            content_hash = hashlib.file_digest(f, "sha1").hexdigest()

        from ..core.identifiers import stable_id as sid
        import os as _os
        from datetime import datetime

        from ..core.models import Provenance

        self._BaseExtractor__provenance = Provenance(
            doc_id=sid(
                _os.path.abspath(self.source_path),
                str(_os.path.getmtime(self.source_path)),
            ),
            source_file=_os.path.basename(self.source_path),
            parser_version=PARSER_VERSION,
            md_schema_version=MD_SCHEMA_VERSION,
            ingestion_ts=datetime.now().isoformat(),
            content_hash=content_hash,
        )

    def _do_parse(self) -> None:
        all_page_spans: list[tuple[int, list[SpanData]]] = []

        with MuPdfDocument(
            self.source_path,
            max_memory_mb=self.config.max_memory_mb,
        ) as doc:
            self.__total_pages = doc.page_count

            self._outline_entries = doc.get_outline()

            for page_num in range(doc.page_count):
                with doc.load_page(page_num) as page:
                    spans = page.get_all_spans()
                    all_page_spans.append((page_num, spans))

        body_size = _compute_modal_font_size(all_page_spans)
        heading_sizes = _rank_heading_sizes(all_page_spans, body_size, self.config)

        all_text_parts = []
        paragraph_counter = 0

        current_hierarchy = {
            f"level_{i}": "" for i in range(1, 7)
        }

        outline_by_page: dict[int, list] = {}
        for entry in self._outline_entries:
            outline_by_page.setdefault(entry.page_num, []).append(entry)

        for page_num, spans in all_page_spans:
            if not spans:
                continue

            if page_num in outline_by_page:
                for entry in outline_by_page[page_num]:
                    level = min(entry.level + 1, 6)
                    level_key = f"level_{level}"
                    current_hierarchy[level_key] = entry.title[:100]
                    for deeper in range(level + 1, 7):
                        current_hierarchy[f"level_{deeper}"] = ""

            lines: dict[tuple[int, int], list[SpanData]] = {}
            for span in spans:
                key = (span.block_idx, span.line_idx)
                lines.setdefault(key, []).append(span)

            current_block = -1
            block_text_parts: list[str] = []
            block_is_heading = False
            block_font_size = 0.0
            block_is_bold = False
            block_is_mono = False

            for (block_idx, _line_idx), line_spans in sorted(lines.items()):
                if block_idx != current_block:
                    if block_text_parts:
                        self._emit_block(
                            block_text_parts, block_is_heading, block_font_size,
                            block_is_bold, block_is_mono, body_size,
                            heading_sizes, current_hierarchy, page_num,
                            paragraph_counter, all_text_parts,
                        )
                        if not block_is_heading:
                            paragraph_counter += 1
                        block_text_parts = []

                    current_block = block_idx
                    block_is_mono = False
                    if line_spans:
                        block_font_size = round(line_spans[0].font_size, 1)
                        block_is_bold = line_spans[0].is_bold

                line_text = "".join(s.text for s in line_spans)
                block_text_parts.append(line_text)

                if line_spans:
                    first = line_spans[0]
                    rounded = round(first.font_size, 1)
                    if rounded > block_font_size:
                        block_font_size = rounded
                    if first.is_bold:
                        block_is_bold = True
                    if first.is_mono:
                        block_is_mono = True

            if block_text_parts:
                self._emit_block(
                    block_text_parts, block_is_heading, block_font_size,
                    block_is_bold, block_is_mono, body_size,
                    heading_sizes, current_hierarchy, page_num,
                    paragraph_counter, all_text_parts,
                )
                if not block_is_heading:
                    paragraph_counter += 1

        full_text = " ".join(all_text_parts)
        self._compute_quality(full_text)
        self._apply_chunking_strategy()

        LOGGER.info(
            "Extracted %d chunks from %d pages (strategy: %s)",
            len(self._get_raw_chunks()),
            self.__total_pages,
            self.config.chunking_strategy,
        )

    def _emit_block(
        self,
        text_parts: list[str],
        is_heading: bool,
        font_size: float,
        is_bold: bool,
        is_mono: bool,
        body_size: float,
        heading_sizes: dict[float, int],
        current_hierarchy: dict[str, str],
        page_num: int,
        paragraph_counter: int,
        all_text_parts: list[str],
    ) -> None:
        raw = " ".join(text_parts)
        cleaned = clean_text(raw)
        if not cleaned:
            return

        word_count = estimate_word_count(cleaned)

        threshold = body_size * self.config.heading_font_threshold
        strong_size = font_size >= body_size * 1.5
        is_heading_candidate = (
            font_size in heading_sizes
            and word_count < 15
            and not is_mono
            and (is_bold or strong_size)
        )

        if is_heading_candidate:
            level = heading_sizes[font_size]
            level_key = f"level_{level}"
            current_hierarchy[level_key] = cleaned[:100]
            for deeper in range(level + 1, 7):
                current_hierarchy[f"level_{deeper}"] = ""
            return

        if word_count < self.config.min_paragraph_words:
            return

        sentences = split_sentences(cleaned)

        chunk = Chunk(
            stable_id=stable_id(
                self.provenance.doc_id,
                f"page_{page_num}",
                str(paragraph_counter),
            ),
            paragraph_id=paragraph_counter,
            text=cleaned,
            hierarchy=current_hierarchy.copy(),
            chapter_href=f"page_{page_num}",
            source_order=paragraph_counter,
            source_tag="p",
            text_length=len(cleaned),
            word_count=word_count,
            cross_references=extract_cross_references(cleaned),
            scripture_references=extract_scripture_references(cleaned),
            dates_mentioned=extract_dates(cleaned),
            heading_path=" / ".join(
                h for h in current_hierarchy.values() if h
            ),
            hierarchy_depth=sum(1 for h in current_hierarchy.values() if h),
            doc_stable_id=self.provenance.doc_id,
            sentence_count=len(sentences),
            sentences=sentences,
            normalized_text=cleaned.lower(),
        )

        self._add_raw_chunk(chunk)
        all_text_parts.append(cleaned)

    def _do_extract_metadata(self) -> Metadata:
        title = None
        author = None
        with MuPdfDocument(
            self.source_path,
            max_memory_mb=self.config.max_memory_mb,
        ) as doc:
            title = doc.get_metadata("info:Title")
            author = doc.get_metadata("info:Author")

        if not title:
            title = os.path.splitext(os.path.basename(self.source_path))[0]

        return Metadata(
            title=title or "Untitled PDF",
            author=author or "Unknown",
            language="en",
            pages=f"approximately {self.__total_pages}",
            word_count=f"approximately {sum(c.word_count for c in self.chunks):,}",
        )
