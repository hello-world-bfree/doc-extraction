from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from extraction.tools.annotate.core.chunk_loader import ChunkLoader


@dataclass
class ChunkBoundary:
    __slots__ = ("chunk_id", "start", "end", "hierarchy")
    chunk_id: str
    start: int
    end: int
    hierarchy: dict


@dataclass
class DocumentText:
    full_text: str
    source_chunks: list[dict] = field(default_factory=list)
    doc_metadata: dict = field(default_factory=dict)
    boundaries: list[ChunkBoundary] = field(default_factory=list)
    source_path: Optional[Path] = None


EPUB_SUFFIXES = {".epub"}
JSON_SUFFIXES = {".json", ".jsonl"}
TEXT_SUFFIXES = {".txt"}


class DocumentLoader:
    @staticmethod
    def load(file_path: Path) -> DocumentText:
        file_path = Path(file_path)

        if file_path.suffix in EPUB_SUFFIXES:
            return DocumentLoader._load_epub(file_path)

        if file_path.suffix in TEXT_SUFFIXES:
            return DocumentLoader._load_raw_text(file_path)

        return DocumentLoader._load_extraction_json(file_path)

    @staticmethod
    def _load_epub(file_path: Path) -> DocumentText:
        import tqdm as _tqdm_mod
        from extraction.extractors.epub import EpubExtractor
        from extraction.extractors.configs import EpubExtractorConfig

        config = EpubExtractorConfig(
            chunking_strategy="nlp",
            preserve_small_chunks=True,
            filter_noise=False,
        )
        extractor = EpubExtractor(str(file_path), config)

        _orig_init = _tqdm_mod.tqdm.__init__

        def _silent_init(self, *args, **kwargs):
            kwargs["disable"] = True
            _orig_init(self, *args, **kwargs)

        _tqdm_mod.tqdm.__init__ = _silent_init
        try:
            extractor.load()
            extractor.parse()
            extractor.extract_metadata()
            output = extractor.get_output_data()
        finally:
            _tqdm_mod.tqdm.__init__ = _orig_init

        chunks = output.get("chunks", [])
        doc_metadata = output.get("metadata", {})

        return DocumentLoader._build_document_text(chunks, doc_metadata, file_path)

    @staticmethod
    def _load_extraction_json(file_path: Path) -> DocumentText:
        chunks, doc_metadata = ChunkLoader.load_with_metadata(file_path)
        return DocumentLoader._build_document_text(chunks, doc_metadata, file_path)

    @staticmethod
    def _load_raw_text(file_path: Path) -> DocumentText:
        text = file_path.read_text(encoding="utf-8")
        return DocumentText(
            full_text=text,
            source_path=file_path,
        )

    @staticmethod
    def _build_document_text(
        chunks: list[dict],
        doc_metadata: dict,
        file_path: Path,
    ) -> DocumentText:
        parts: list[str] = []
        boundaries: list[ChunkBoundary] = []
        offset = 0
        last_hierarchy_key = None

        for chunk in chunks:
            chunk_id = chunk.get("stable_id") or chunk.get("chunk_id", "")
            hierarchy = chunk.get("hierarchy") or chunk.get("metadata", {}).get("hierarchy", {})
            text = chunk.get("text", "")

            header_parts = [v for v in hierarchy.values() if v]
            hierarchy_key = tuple(header_parts)

            if header_parts and hierarchy_key != last_hierarchy_key:
                header = " > ".join(header_parts)
                header_line = f"--- {header} ---\n\n"
                last_hierarchy_key = hierarchy_key
            else:
                header_line = ""

            block = header_line + text
            start = offset
            end = offset + len(block)

            parts.append(block)
            boundaries.append(ChunkBoundary(
                chunk_id=chunk_id,
                start=start,
                end=end,
                hierarchy=hierarchy,
            ))

            offset = end + 2
            parts.append("\n\n")

        full_text = "".join(parts).rstrip("\n")

        return DocumentText(
            full_text=full_text,
            source_chunks=chunks,
            doc_metadata=doc_metadata,
            boundaries=boundaries,
            source_path=file_path,
        )
