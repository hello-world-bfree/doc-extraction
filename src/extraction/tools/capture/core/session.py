from dataclasses import dataclass, field, asdict
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional
import json

from extraction.core.identifiers import stable_id


@dataclass
class CapturedChunk:
    __slots__ = (
        "capture_id", "text", "start_offset", "end_offset",
        "token_count", "word_count", "order", "hierarchy",
        "source_chunk_ids", "notes", "timestamp",
    )
    capture_id: str
    text: str
    start_offset: int
    end_offset: int
    token_count: int
    word_count: int
    order: int
    hierarchy: dict
    source_chunk_ids: list[str]
    notes: str
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "capture_id": self.capture_id,
            "text": self.text,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "token_count": self.token_count,
            "word_count": self.word_count,
            "order": self.order,
            "hierarchy": self.hierarchy,
            "source_chunk_ids": self.source_chunk_ids,
            "notes": self.notes,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CapturedChunk":
        return cls(**data)


class CaptureSession:
    def __init__(
        self,
        document_path: Path,
        doc_metadata: Optional[dict] = None,
        session_file: Optional[Path] = None,
    ):
        self.document_path = document_path
        self.doc_metadata = doc_metadata or {}
        self.session_file = session_file
        self.captured: list[CapturedChunk] = []
        self._undo_stack: list[CapturedChunk] = []
        self._max_undo = 50

        if session_file and session_file.exists():
            self._load()

    @property
    def total_tokens(self) -> int:
        return sum(c.token_count for c in self.captured)

    @property
    def total_words(self) -> int:
        return sum(c.word_count for c in self.captured)

    def capture(
        self,
        text: str,
        start_offset: int,
        end_offset: int,
        token_count: int,
        hierarchy: Optional[dict] = None,
        source_chunk_ids: Optional[list[str]] = None,
    ) -> CapturedChunk:
        order = len(self.captured) + 1
        capture_id = stable_id(str(self.document_path), text[:200], str(order))

        chunk = CapturedChunk(
            capture_id=capture_id,
            text=text,
            start_offset=start_offset,
            end_offset=end_offset,
            token_count=token_count,
            word_count=len(text.split()),
            order=order,
            hierarchy=hierarchy or {},
            source_chunk_ids=source_chunk_ids or [],
            notes="",
            timestamp=datetime.now(UTC).isoformat(),
        )

        self.captured.append(chunk)
        return chunk

    def remove_last(self) -> Optional[CapturedChunk]:
        if not self.captured:
            return None

        removed = self.captured.pop()
        self._undo_stack.append(removed)
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)
        return removed

    def remove_by_id(self, capture_id: str) -> Optional[CapturedChunk]:
        for i, chunk in enumerate(self.captured):
            if chunk.capture_id == capture_id:
                removed = self.captured.pop(i)
                self._reorder()
                self._undo_stack.append(removed)
                if len(self._undo_stack) > self._max_undo:
                    self._undo_stack.pop(0)
                return removed
        return None

    def undo_remove(self) -> Optional[CapturedChunk]:
        if not self._undo_stack:
            return None

        chunk = self._undo_stack.pop()
        self.captured.append(chunk)
        self._reorder()
        return chunk

    def _reorder(self):
        for i, chunk in enumerate(self.captured, 1):
            chunk.order = i

    def find_overlapping_boundaries(
        self,
        start_offset: int,
        end_offset: int,
        boundaries: list,
    ) -> tuple[dict, list[str]]:
        hierarchy = {}
        source_ids = []

        for b in boundaries:
            if b.start < end_offset and b.end > start_offset:
                if not hierarchy and b.hierarchy:
                    hierarchy = dict(b.hierarchy)
                if b.chunk_id:
                    source_ids.append(b.chunk_id)

        return hierarchy, source_ids

    def save(self):
        if self.session_file is None:
            return

        data = {
            "document_path": str(self.document_path),
            "doc_metadata": self.doc_metadata,
            "captured": [c.to_dict() for c in self.captured],
            "saved_at": datetime.now(UTC).isoformat(),
        }

        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.session_file, "w") as f:
            json.dump(data, f, indent=2)

    def _load(self):
        if not self.session_file or not self.session_file.exists():
            return

        with open(self.session_file) as f:
            data = json.load(f)

        self.captured = [CapturedChunk.from_dict(c) for c in data.get("captured", [])]
        self.doc_metadata = data.get("doc_metadata", self.doc_metadata)

    def export_jsonl(self, output_path: Path) -> int:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        source_file = self.doc_metadata.get("provenance", {}).get(
            "source_file", self.document_path.name
        )
        doc_info = {
            "title": self.doc_metadata.get("title", ""),
            "author": self.doc_metadata.get("author", ""),
        }

        with open(output_path, "w") as f:
            for chunk in self.captured:
                record = {
                    "capture_id": chunk.capture_id,
                    "text": chunk.text,
                    "token_count": chunk.token_count,
                    "word_count": chunk.word_count,
                    "hierarchy": chunk.hierarchy,
                    "source_chunk_ids": chunk.source_chunk_ids,
                    "source_file": source_file,
                    "order": chunk.order,
                    "notes": chunk.notes,
                    "document": doc_info,
                }
                f.write(json.dumps(record) + "\n")

        return len(self.captured)

    def export_extraction_json(self, output_path: Path) -> int:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        chunks = []
        for chunk in self.captured:
            chunks.append({
                "stable_id": chunk.capture_id,
                "paragraph_id": chunk.order,
                "text": chunk.text,
                "hierarchy": chunk.hierarchy,
                "word_count": chunk.word_count,
                "quality_flags": ["manually_captured"],
                "source_order": chunk.order,
            })

        output = {
            "metadata": self.doc_metadata,
            "chunks": chunks,
        }

        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)

        return len(chunks)
