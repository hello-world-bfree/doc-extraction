"""Session state management for annotation tool."""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set
from datetime import datetime, UTC
from pathlib import Path
import json
import hashlib


@dataclass
class EditedChunk:
    """Edited version of a chunk with lineage tracking."""

    edited_chunk_id: str
    parent_chunk_id: str
    version: int
    edited_text: str
    edit_reason: str
    original_text: str
    inherited_metadata: Dict = field(default_factory=dict)
    editor_id: str = "default"
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    is_current_version: bool = True

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "EditedChunk":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class ChunkAnnotation:
    """Annotation for a single chunk."""

    chunk_id: str
    label: Optional[int] = None  # 0=GOOD, 1=BAD, None=SKIPPED
    confidence: Optional[int] = None  # 1-5 stars
    rationale: str = ""
    issues: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    annotator_id: str = "default"

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "ChunkAnnotation":
        """Create from dictionary."""
        return cls(**data)

    def is_annotated(self) -> bool:
        """Check if chunk has been annotated."""
        return self.label is not None


@dataclass
class SessionStats:
    """Statistics for annotation session."""

    total_chunks: int = 0
    annotated_count: int = 0
    good_count: int = 0
    bad_count: int = 0
    skipped_count: int = 0
    issue_counts: Dict[str, int] = field(default_factory=dict)
    start_time: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_save_time: Optional[str] = None

    def update(self, annotations: List[ChunkAnnotation]) -> None:
        """Update statistics from annotations."""
        self.annotated_count = sum(1 for a in annotations if a.is_annotated())
        self.good_count = sum(1 for a in annotations if a.label == 0)
        self.bad_count = sum(1 for a in annotations if a.label == 1)
        self.skipped_count = sum(1 for a in annotations if not a.is_annotated())

        self.issue_counts.clear()
        for annotation in annotations:
            for issue in annotation.issues:
                self.issue_counts[issue] = self.issue_counts.get(issue, 0) + 1

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)


class AnnotationSession:
    """Manages annotation session state."""

    ISSUE_TYPES = [
        "missing_hierarchy",
        "formatting_lost",
        "noise_index_toc",
        "mixed_topics",
        "mid_sentence_truncation",
        "missing_context",
    ]

    def __init__(
        self,
        chunks: List[Dict],
        session_file: Optional[Path] = None,
        annotator_id: str = "default",
        doc_metadata: Optional[Dict] = None,
    ):
        """Initialize annotation session.

        Args:
            chunks: List of chunk dictionaries from extraction
            session_file: Path to save/load session state
            annotator_id: Identifier for annotator
            doc_metadata: Document-level metadata (title, author, etc.)
        """
        self.chunks = chunks
        self.session_file = session_file
        self.annotator_id = annotator_id
        self.doc_metadata = doc_metadata or {}

        self.annotations: Dict[str, ChunkAnnotation] = {}
        self.edited_chunks: Dict[str, List[EditedChunk]] = {}
        self.current_index = 0
        self.stats = SessionStats(total_chunks=len(chunks))

        self.undo_stack: List[tuple[int, Optional[ChunkAnnotation]]] = []
        self.max_undo = 50

        if session_file and session_file.exists():
            self.load()
        else:
            self._initialize_default_annotations()

    def _initialize_default_annotations(self) -> None:
        """Initialize all chunks with default 'good' annotation."""
        for chunk in self.chunks:
            chunk_id = chunk.get('stable_id') or chunk.get('chunk_id')
            if chunk_id:
                self.annotations[chunk_id] = ChunkAnnotation(
                    chunk_id=chunk_id,
                    label=0,
                    annotator_id=self.annotator_id,
                )
        self.stats.update(list(self.annotations.values()))

    def get_chunk(self, index: Optional[int] = None) -> Optional[Dict]:
        """Get chunk at index (or current index).

        Returns edited version if exists, otherwise original.
        """
        idx = index if index is not None else self.current_index
        if not (0 <= idx < len(self.chunks)):
            return None

        original_chunk = self.chunks[idx]
        chunk_id = original_chunk.get('stable_id') or original_chunk.get('chunk_id')

        current_edit = self.get_current_edit(chunk_id)
        if current_edit:
            edited_chunk = original_chunk.copy()
            edited_chunk['text'] = current_edit.edited_text
            edited_chunk['edited_chunk_id'] = current_edit.edited_chunk_id
            edited_chunk['is_edited'] = True
            edited_chunk['edit_version'] = current_edit.version
            return edited_chunk

        return original_chunk

    def get_annotation(self, index: Optional[int] = None) -> Optional[ChunkAnnotation]:
        """Get annotation for chunk at index."""
        chunk = self.get_chunk(index)
        if chunk is None:
            return None

        chunk_id = chunk.get('stable_id') or chunk.get('chunk_id')
        return self.annotations.get(chunk_id)

    def set_annotation(
        self,
        label: Optional[int],
        rationale: str = "",
        confidence: Optional[int] = None,
        issues: Optional[List[str]] = None,
        index: Optional[int] = None,
    ) -> bool:
        """Set annotation for chunk.

        Args:
            label: 0=GOOD, 1=BAD, None=SKIP
            rationale: Annotation rationale
            confidence: 1-5 stars
            issues: List of issue types
            index: Chunk index (defaults to current)

        Returns:
            True if annotation was set successfully
        """
        chunk = self.get_chunk(index)
        if chunk is None:
            return False

        chunk_id = chunk.get('stable_id') or chunk.get('chunk_id')

        old_annotation = self.annotations.get(chunk_id)
        self.undo_stack.append((self.current_index, old_annotation))
        if len(self.undo_stack) > self.max_undo:
            self.undo_stack.pop(0)

        annotation = ChunkAnnotation(
            chunk_id=chunk_id,
            label=label,
            confidence=confidence,
            rationale=rationale,
            issues=issues or [],
            annotator_id=self.annotator_id,
        )

        self.annotations[chunk_id] = annotation
        self.stats.update(list(self.annotations.values()))

        return True

    def undo(self) -> bool:
        """Undo last annotation.

        Returns:
            True if undo was successful
        """
        if not self.undo_stack:
            return False

        index, old_annotation = self.undo_stack.pop()
        chunk = self.get_chunk(index)
        if chunk is None:
            return False

        chunk_id = chunk.get('stable_id') or chunk.get('chunk_id')

        if old_annotation is None:
            self.annotations.pop(chunk_id, None)
        else:
            self.annotations[chunk_id] = old_annotation

        self.current_index = index
        self.stats.update(list(self.annotations.values()))

        return True

    def next_chunk(self) -> bool:
        """Move to next chunk.

        Returns:
            True if moved successfully
        """
        if self.current_index < len(self.chunks) - 1:
            self.current_index += 1
            return True
        return False

    def prev_chunk(self) -> bool:
        """Move to previous chunk.

        Returns:
            True if moved successfully
        """
        if self.current_index > 0:
            self.current_index -= 1
            return True
        return False

    def jump_to(self, index: int) -> bool:
        """Jump to specific chunk index.

        Returns:
            True if jump was successful
        """
        if 0 <= index < len(self.chunks):
            self.current_index = index
            return True
        return False

    def get_unannotated_indices(self) -> List[int]:
        """Get indices of chunks without annotations."""
        unannotated = []
        for i, chunk in enumerate(self.chunks):
            chunk_id = chunk.get('stable_id') or chunk.get('chunk_id')
            if chunk_id not in self.annotations or not self.annotations[chunk_id].is_annotated():
                unannotated.append(i)
        return unannotated

    def get_annotated_indices(self) -> Set[int]:
        """Get set of annotated chunk indices."""
        annotated = set()
        for i, chunk in enumerate(self.chunks):
            chunk_id = chunk.get('stable_id') or chunk.get('chunk_id')
            if chunk_id in self.annotations and self.annotations[chunk_id].is_annotated():
                annotated.add(i)
        return annotated

    @staticmethod
    def _generate_edited_chunk_id(text: str) -> str:
        """Generate unique ID for edited chunk."""
        hash_obj = hashlib.sha256(text.encode('utf-8'))
        return f"ed_{hash_obj.hexdigest()[:16]}"

    def create_edit(
        self,
        chunk_id: str,
        edited_text: str,
        edit_reason: str,
    ) -> Optional[EditedChunk]:
        """Create new edit for chunk.

        Args:
            chunk_id: Original chunk stable_id
            edited_text: Modified text
            edit_reason: Reason for edit (required)

        Returns:
            EditedChunk if created, None if chunk not found
        """
        if not edit_reason.strip():
            return None

        original_chunk = None
        for chunk in self.chunks:
            cid = chunk.get('stable_id') or chunk.get('chunk_id')
            if cid == chunk_id:
                original_chunk = chunk
                break

        if original_chunk is None:
            return None

        existing_edits = self.edited_chunks.get(chunk_id, [])

        for edit in existing_edits:
            edit.is_current_version = False

        version = len(existing_edits) + 1
        edited_chunk_id = self._generate_edited_chunk_id(edited_text)

        inherited_metadata = {
            k: v for k, v in original_chunk.items()
            if k not in ['text', 'stable_id', 'chunk_id']
        }

        if 'metadata' in inherited_metadata and 'word_count' in inherited_metadata['metadata']:
            inherited_metadata['metadata']['word_count'] = len(edited_text.split())

        new_edit = EditedChunk(
            edited_chunk_id=edited_chunk_id,
            parent_chunk_id=chunk_id,
            version=version,
            edited_text=edited_text,
            edit_reason=edit_reason,
            original_text=original_chunk.get('text', ''),
            inherited_metadata=inherited_metadata,
            editor_id=self.annotator_id,
            is_current_version=True,
        )

        if chunk_id not in self.edited_chunks:
            self.edited_chunks[chunk_id] = []
        self.edited_chunks[chunk_id].append(new_edit)

        return new_edit

    def get_edit_history(self, chunk_id: str) -> List[EditedChunk]:
        """Get all edit versions for chunk.

        Args:
            chunk_id: Original chunk stable_id

        Returns:
            List of EditedChunk objects, ordered by version
        """
        return self.edited_chunks.get(chunk_id, [])

    def get_current_edit(self, chunk_id: str) -> Optional[EditedChunk]:
        """Get current (latest) edit for chunk.

        Args:
            chunk_id: Original chunk stable_id

        Returns:
            EditedChunk if exists, None otherwise
        """
        edits = self.edited_chunks.get(chunk_id, [])
        for edit in reversed(edits):
            if edit.is_current_version:
                return edit
        return None

    def restore_edit_version(
        self,
        chunk_id: str,
        version: int,
        edit_reason: str,
    ) -> Optional[EditedChunk]:
        """Restore old edit version as new version (git-revert style).

        Args:
            chunk_id: Original chunk stable_id
            version: Version number to restore
            edit_reason: Reason for restoration

        Returns:
            New EditedChunk if successful, None otherwise
        """
        edits = self.edited_chunks.get(chunk_id, [])
        target_edit = None
        for edit in edits:
            if edit.version == version:
                target_edit = edit
                break

        if target_edit is None:
            return None

        return self.create_edit(
            chunk_id=chunk_id,
            edited_text=target_edit.edited_text,
            edit_reason=edit_reason,
        )

    def save(self) -> None:
        """Save session to file."""
        if self.session_file is None:
            return

        self.stats.last_save_time = datetime.now(UTC).isoformat()

        session_data = {
            'current_index': self.current_index,
            'annotator_id': self.annotator_id,
            'annotations': {k: v.to_dict() for k, v in self.annotations.items()},
            'edited_chunks': {
                k: [edit.to_dict() for edit in edits]
                for k, edits in self.edited_chunks.items()
            },
            'stats': self.stats.to_dict(),
            'doc_metadata': self.doc_metadata,
        }

        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.session_file, 'w') as f:
            json.dump(session_data, f, indent=2)

    def load(self) -> None:
        """Load session from file."""
        if self.session_file is None or not self.session_file.exists():
            return

        with open(self.session_file) as f:
            session_data = json.load(f)

        self.current_index = session_data.get('current_index', 0)
        self.annotator_id = session_data.get('annotator_id', 'default')
        self.doc_metadata = session_data.get('doc_metadata', self.doc_metadata)

        annotations_data = session_data.get('annotations', {})
        self.annotations = {
            k: ChunkAnnotation.from_dict(v)
            for k, v in annotations_data.items()
        }

        edited_chunks_data = session_data.get('edited_chunks', {})
        self.edited_chunks = {
            k: [EditedChunk.from_dict(edit) for edit in edits]
            for k, edits in edited_chunks_data.items()
        }

        self.stats = SessionStats(**session_data.get('stats', {}))
        self.stats.total_chunks = len(self.chunks)

    def get_progress_percent(self) -> float:
        """Get annotation progress as percentage."""
        if self.stats.total_chunks == 0:
            return 0.0
        return (self.stats.annotated_count / self.stats.total_chunks) * 100
