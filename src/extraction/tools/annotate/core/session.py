"""Session state management for annotation tool."""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set
from datetime import datetime, UTC
from pathlib import Path
import json
import hashlib


@dataclass
class SplitChunk:
    """Split of a chunk into N segments with lineage tracking."""

    split_chunk_ids: List[str]
    parent_chunk_id: str
    version: int
    segments: List[str]
    split_reason: str
    original_text: str
    inherited_metadata: Dict = field(default_factory=dict)
    splitter_id: str = "default"
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    is_current_version: bool = True

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "SplitChunk":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class MergeChunk:
    """Merge of N adjacent chunks into one with lineage tracking."""

    merged_chunk_id: str
    parent_chunk_ids: List[str]
    version: int
    merged_text: str
    separator: str
    merge_reason: str
    original_texts: List[str]
    inherited_metadata: Dict = field(default_factory=dict)
    merger_id: str = "default"
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    is_current_version: bool = True

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "MergeChunk":
        """Create from dictionary."""
        return cls(**data)


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
    edited_hierarchy: Optional[Dict[str, str]] = None
    original_hierarchy: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "EditedChunk":
        """Create from dictionary."""
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


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
        self.split_chunks: Dict[str, List[SplitChunk]] = {}
        self.merged_chunks: Dict[str, List[MergeChunk]] = {}
        self.view_order: List[tuple[str, Optional[int]]] = []
        self.current_index = 0
        self.stats = SessionStats(total_chunks=len(chunks))

        self.undo_stack: List[tuple[int, Optional[ChunkAnnotation]]] = []
        self.max_undo = 50

        if session_file and session_file.exists():
            self.load()
        else:
            self._initialize_default_annotations()

        self._rebuild_view_order()

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

    def _resolve_parent_chunk(self, chunk_id: str) -> Optional[Dict]:
        """Resolve original chunk dict (in self.chunks) by id. None if not a root."""
        for c in self.chunks:
            cid = c.get('stable_id') or c.get('chunk_id')
            if cid == chunk_id:
                return c
        return None

    def _resolve_merge_by_id(self, merged_id: str) -> Optional["MergeChunk"]:
        """Find current MergeChunk whose merged_chunk_id matches."""
        for merges in self.merged_chunks.values():
            for m in merges:
                if m.is_current_version and m.merged_chunk_id == merged_id:
                    return m
        return None

    def _materialize_chunk(self, chunk_id: str, segment_idx: Optional[int]) -> Optional[Dict]:
        """Build chunk dict for a view_order entry, applying current split/edit/merge overlay."""
        merge = self._resolve_merge_by_id(chunk_id)
        if merge is not None:
            first_parent = self._resolve_parent_chunk(merge.parent_chunk_ids[0])
            base = first_parent.copy() if first_parent else {}
            base['text'] = merge.merged_text
            base['stable_id'] = merge.merged_chunk_id
            base['chunk_id'] = merge.merged_chunk_id
            base['parent_chunk_ids'] = list(merge.parent_chunk_ids)
            base['is_merged'] = True
            base['merge_version'] = merge.version
            base['merge_reason'] = merge.merge_reason
            if isinstance(base.get('metadata'), dict):
                meta = dict(base['metadata'])
                meta['word_count'] = len(merge.merged_text.split())
                base['metadata'] = meta
            return base

        current_split = self.get_current_split(chunk_id)
        if current_split and segment_idx is not None:
            base = self._materialize_chunk(chunk_id, None) or {}
            child = base.copy() if base else {}
            child['text'] = current_split.segments[segment_idx]
            child['stable_id'] = current_split.split_chunk_ids[segment_idx]
            child['chunk_id'] = current_split.split_chunk_ids[segment_idx]
            child['parent_chunk_id'] = chunk_id
            child['is_split'] = True
            child['split_index'] = segment_idx
            child['split_version'] = current_split.version
            return child

        parent = self._resolve_parent_chunk(chunk_id)
        if parent is None:
            return None

        current_edit = self.get_current_edit(chunk_id)
        if current_edit:
            edited_chunk = parent.copy()
            edited_chunk['text'] = current_edit.edited_text
            edited_chunk['edited_chunk_id'] = current_edit.edited_chunk_id
            edited_chunk['is_edited'] = True
            edited_chunk['edit_version'] = current_edit.version
            if current_edit.edited_hierarchy:
                edited_chunk['hierarchy'] = dict(current_edit.edited_hierarchy)
                if isinstance(edited_chunk.get('metadata'), dict) and 'hierarchy' in edited_chunk['metadata']:
                    meta = dict(edited_chunk['metadata'])
                    meta['hierarchy'] = dict(current_edit.edited_hierarchy)
                    edited_chunk['metadata'] = meta
            return edited_chunk

        return parent

    def get_chunk(self, index: Optional[int] = None) -> Optional[Dict]:
        """Get chunk at view index (or current index).

        Returns split child if applicable, else edited version, else original.
        """
        idx = index if index is not None else self.current_index
        if not (0 <= idx < len(self.view_order)):
            return None

        chunk_id, segment_idx = self.view_order[idx]
        return self._materialize_chunk(chunk_id, segment_idx)

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
        """Move to next chunk."""
        if self.current_index < len(self.view_order) - 1:
            self.current_index += 1
            return True
        return False

    def prev_chunk(self) -> bool:
        """Move to previous chunk."""
        if self.current_index > 0:
            self.current_index -= 1
            return True
        return False

    def jump_to(self, index: int) -> bool:
        """Jump to specific view index."""
        if 0 <= index < len(self.view_order):
            self.current_index = index
            return True
        return False

    def _view_chunk_id(self, view_idx: int) -> Optional[str]:
        """Get effective chunk_id at a view position (child id if split)."""
        if not (0 <= view_idx < len(self.view_order)):
            return None
        parent_id, segment_idx = self.view_order[view_idx]
        if segment_idx is None:
            return parent_id
        current_split = self.get_current_split(parent_id)
        if current_split is None:
            return parent_id
        return current_split.split_chunk_ids[segment_idx]

    def get_unannotated_indices(self) -> List[int]:
        """Get view indices of chunks without annotations."""
        unannotated = []
        for i in range(len(self.view_order)):
            cid = self._view_chunk_id(i)
            if cid is None:
                continue
            if cid not in self.annotations or not self.annotations[cid].is_annotated():
                unannotated.append(i)
        return unannotated

    def get_annotated_indices(self) -> Set[int]:
        """Get set of annotated view indices."""
        annotated = set()
        for i in range(len(self.view_order)):
            cid = self._view_chunk_id(i)
            if cid is None:
                continue
            if cid in self.annotations and self.annotations[cid].is_annotated():
                annotated.add(i)
        return annotated

    @staticmethod
    def _generate_edited_chunk_id(text: str) -> str:
        """Generate unique ID for edited chunk."""
        hash_obj = hashlib.sha256(text.encode('utf-8'))
        return f"ed_{hash_obj.hexdigest()[:16]}"

    @staticmethod
    def _generate_split_chunk_id(text: str, idx: int) -> str:
        """Generate deterministic ID for a split segment."""
        hash_obj = hashlib.sha256(text.encode('utf-8'))
        return f"split_{hash_obj.hexdigest()[:16]}_{idx}"

    @staticmethod
    def _generate_merge_chunk_id(parent_ids: List[str]) -> str:
        """Generate deterministic ID for a merged chunk."""
        key = "|".join(parent_ids)
        hash_obj = hashlib.sha256(key.encode('utf-8'))
        return f"mg_{hash_obj.hexdigest()[:16]}"

    def _current_merge_for_parent(self, chunk_id: str) -> Optional["MergeChunk"]:
        """Get the current merge keyed at this parent id, if any."""
        merges = self.merged_chunks.get(chunk_id, [])
        for m in reversed(merges):
            if m.is_current_version:
                return m
        return None

    def _merge_member_set(self) -> Set[str]:
        """All chunk ids that are non-first members of an active merge (suppressed)."""
        members: Set[str] = set()
        for merges in self.merged_chunks.values():
            for m in merges:
                if m.is_current_version:
                    members.update(m.parent_chunk_ids[1:])
        return members

    def _merge_first_member_index(self, parent_id: str) -> Optional["MergeChunk"]:
        """If parent_id is the *first* member of an active merge, return that merge."""
        for merges in self.merged_chunks.values():
            for m in merges:
                if m.is_current_version and m.parent_chunk_ids and m.parent_chunk_ids[0] == parent_id:
                    return m
        return None

    def _rebuild_view_order(self) -> None:
        """Rebuild view_order from chunks + current splits.

        Each parent chunk expands to its current split's segments (recursively),
        else appears once. Preserves position of self.current_index by chunk identity
        when possible.
        """
        prior_id: Optional[str] = None
        if self.view_order and 0 <= self.current_index < len(self.view_order):
            prior_id = self._view_chunk_id(self.current_index)

        def expand(chunk_id: str) -> List[tuple[str, Optional[int]]]:
            current_split = self.get_current_split(chunk_id)
            if current_split is None:
                return [(chunk_id, None)]
            out: List[tuple[str, Optional[int]]] = []
            for seg_idx, child_id in enumerate(current_split.split_chunk_ids):
                child_split = self.get_current_split(child_id)
                if child_split is None:
                    out.append((chunk_id, seg_idx))
                else:
                    out.extend(expand(child_id))
            return out

        suppressed = self._merge_member_set()
        new_order: List[tuple[str, Optional[int]]] = []
        for chunk in self.chunks:
            cid = chunk.get('stable_id') or chunk.get('chunk_id')
            if not cid:
                continue
            if cid in suppressed:
                continue
            merge = self._merge_first_member_index(cid)
            if merge is not None:
                new_order.append((merge.merged_chunk_id, None))
                continue
            new_order.extend(expand(cid))

        self.view_order = new_order

        if prior_id is not None:
            for i in range(len(self.view_order)):
                if self._view_chunk_id(i) == prior_id:
                    self.current_index = i
                    return
        if self.current_index >= len(self.view_order):
            self.current_index = max(0, len(self.view_order) - 1)

    def create_split(
        self,
        chunk_id: str,
        segments: List[str],
        split_reason: str,
    ) -> Optional[SplitChunk]:
        """Split a chunk into N segments with lineage tracking.

        Children inherit parent's current annotation (label/confidence/issues/rationale).
        Splitting an edited chunk uses the current view text as `original_text`.
        Supports splitting a previously-split child (chunk_id can be a split child id).

        Args:
            chunk_id: Parent chunk id (root or split child)
            segments: List of non-empty segment texts (>=2)
            split_reason: Reason for split (required)

        Returns:
            SplitChunk if created, None on validation failure
        """
        if not split_reason.strip():
            return None
        segments = [s for s in (seg.strip() for seg in segments) if s]
        if len(segments) < 2:
            return None

        view_idx = self._find_view_index_for(chunk_id)
        source_chunk = self.get_chunk(view_idx) if view_idx is not None else None
        if source_chunk is None:
            return None

        original_text = source_chunk.get('text', '')
        inherited_metadata = {
            k: v for k, v in source_chunk.items()
            if k not in ('text', 'stable_id', 'chunk_id')
        }

        existing = self.split_chunks.get(chunk_id, [])
        for s in existing:
            s.is_current_version = False
        version = len(existing) + 1

        split_chunk_ids = [
            self._generate_split_chunk_id(seg, i) for i, seg in enumerate(segments)
        ]

        new_split = SplitChunk(
            split_chunk_ids=split_chunk_ids,
            parent_chunk_id=chunk_id,
            version=version,
            segments=segments,
            split_reason=split_reason,
            original_text=original_text,
            inherited_metadata=inherited_metadata,
            splitter_id=self.annotator_id,
            is_current_version=True,
        )
        self.split_chunks.setdefault(chunk_id, []).append(new_split)

        parent_annotation = self.annotations.get(chunk_id)
        for child_id in split_chunk_ids:
            if parent_annotation is not None:
                self.annotations[child_id] = ChunkAnnotation(
                    chunk_id=child_id,
                    label=parent_annotation.label,
                    confidence=parent_annotation.confidence,
                    rationale=parent_annotation.rationale,
                    issues=list(parent_annotation.issues),
                    annotator_id=self.annotator_id,
                )
            else:
                self.annotations[child_id] = ChunkAnnotation(
                    chunk_id=child_id,
                    label=0,
                    annotator_id=self.annotator_id,
                )

        self._rebuild_view_order()
        self.stats.update(list(self.annotations.values()))
        return new_split

    def _find_view_index_for(self, chunk_id: str) -> Optional[int]:
        """Locate view index of a chunk by its effective id (root or split child)."""
        for i in range(len(self.view_order)):
            if self._view_chunk_id(i) == chunk_id:
                return i
        return None

    def create_merge(
        self,
        chunk_ids: List[str],
        merge_reason: str,
        separator: str = "\n\n",
    ) -> Optional[MergeChunk]:
        """Merge N adjacent root chunks into one merged chunk.

        MVP constraints:
          - chunk_ids must all be root chunks (no split children, no merged ids)
          - must appear contiguously in self.view_order at segment_idx=None
          - >=2 ids, reason required

        Children inherit worst-of annotations: BAD > GOOD > skip,
        min confidence, union of issues. Rationale is concatenated.

        Returns:
            MergeChunk on success, None on validation failure.
        """
        if not merge_reason.strip():
            return None
        if not chunk_ids or len(chunk_ids) < 2:
            return None
        if len(set(chunk_ids)) != len(chunk_ids):
            return None

        root_ids = {
            (c.get('stable_id') or c.get('chunk_id'))
            for c in self.chunks
        }
        for cid in chunk_ids:
            if cid not in root_ids:
                return None

        suppressed = self._merge_member_set()
        for cid in chunk_ids:
            if cid in suppressed:
                return None
            if self._merge_first_member_index(cid) is not None:
                return None
            if self.get_current_split(cid) is not None:
                return None

        view_indices: List[int] = []
        for cid in chunk_ids:
            idx = None
            for i, (vid, seg) in enumerate(self.view_order):
                if seg is None and vid == cid:
                    idx = i
                    break
            if idx is None:
                return None
            view_indices.append(idx)
        if view_indices != list(range(view_indices[0], view_indices[0] + len(view_indices))):
            return None

        parent_chunks = [self._resolve_parent_chunk(cid) for cid in chunk_ids]
        if any(p is None for p in parent_chunks):
            return None

        original_texts: List[str] = []
        for cid, parent in zip(chunk_ids, parent_chunks):
            edit = self.get_current_edit(cid)
            text = edit.edited_text if edit is not None else parent.get('text', '')
            original_texts.append(text)

        merged_text = separator.join(original_texts)
        merged_chunk_id = self._generate_merge_chunk_id(chunk_ids)

        first_parent = parent_chunks[0]
        inherited_metadata = {
            k: v for k, v in first_parent.items()
            if k not in ('text', 'stable_id', 'chunk_id')
        }

        existing = self.merged_chunks.get(chunk_ids[0], [])
        for m in existing:
            m.is_current_version = False
        version = len(existing) + 1

        new_merge = MergeChunk(
            merged_chunk_id=merged_chunk_id,
            parent_chunk_ids=list(chunk_ids),
            version=version,
            merged_text=merged_text,
            separator=separator,
            merge_reason=merge_reason,
            original_texts=original_texts,
            inherited_metadata=inherited_metadata,
            merger_id=self.annotator_id,
            is_current_version=True,
        )
        self.merged_chunks.setdefault(chunk_ids[0], []).append(new_merge)

        parent_anns = [self.annotations.get(cid) for cid in chunk_ids]
        present = [a for a in parent_anns if a is not None]
        if present:
            if any(a.label == 1 for a in present):
                inherited_label = 1
            elif any(a.label == 0 for a in present):
                inherited_label = 0
            else:
                inherited_label = None
            confidences = [a.confidence for a in present if a.confidence is not None]
            inherited_conf = min(confidences) if confidences else None
            inherited_issues = sorted({iss for a in present for iss in a.issues})
            rationale_parts = [a.rationale.strip() for a in present if a.rationale.strip()]
            inherited_rationale = " | ".join(rationale_parts)
        else:
            inherited_label = 0
            inherited_conf = None
            inherited_issues = []
            inherited_rationale = ""

        self.annotations[merged_chunk_id] = ChunkAnnotation(
            chunk_id=merged_chunk_id,
            label=inherited_label,
            confidence=inherited_conf,
            rationale=inherited_rationale,
            issues=inherited_issues,
            annotator_id=self.annotator_id,
        )

        self._rebuild_view_order()
        self.stats.update(list(self.annotations.values()))
        return new_merge

    def get_merge_history(self, parent_id: str) -> List[MergeChunk]:
        """Get all merge versions keyed at parent_id (first member)."""
        return self.merged_chunks.get(parent_id, [])

    def get_current_merge(self, parent_id: str) -> Optional[MergeChunk]:
        """Get current merge keyed at parent_id."""
        for m in reversed(self.merged_chunks.get(parent_id, [])):
            if m.is_current_version:
                return m
        return None

    def get_split_history(self, chunk_id: str) -> List[SplitChunk]:
        """Get all split versions for chunk."""
        return self.split_chunks.get(chunk_id, [])

    def get_current_split(self, chunk_id: str) -> Optional[SplitChunk]:
        """Get current (latest) split for chunk."""
        splits = self.split_chunks.get(chunk_id, [])
        for s in reversed(splits):
            if s.is_current_version:
                return s
        return None

    def create_edit(
        self,
        chunk_id: str,
        edited_text: str,
        edit_reason: str,
        edited_hierarchy: Optional[Dict[str, str]] = None,
    ) -> Optional[EditedChunk]:
        """Create new edit for chunk.

        Args:
            chunk_id: Original chunk stable_id
            edited_text: Modified text
            edit_reason: Reason for edit (required)
            edited_hierarchy: Optional new hierarchy dict (level_1..level_6)

        Returns:
            EditedChunk if created, None if chunk not found
        """
        if not edit_reason.strip():
            return None

        view_idx = self._find_view_index_for(chunk_id)
        source_chunk = self.get_chunk(view_idx) if view_idx is not None else None
        if source_chunk is None:
            return None

        existing_edits = self.edited_chunks.get(chunk_id, [])

        for edit in existing_edits:
            edit.is_current_version = False

        version = len(existing_edits) + 1
        edited_chunk_id = self._generate_edited_chunk_id(edited_text + json.dumps(edited_hierarchy or {}, sort_keys=True))

        inherited_metadata = {
            k: v for k, v in source_chunk.items()
            if k not in ['text', 'stable_id', 'chunk_id']
        }

        if 'metadata' in inherited_metadata and 'word_count' in inherited_metadata['metadata']:
            inherited_metadata['metadata']['word_count'] = len(edited_text.split())

        original_hierarchy = (
            source_chunk.get('hierarchy')
            or source_chunk.get('metadata', {}).get('hierarchy')
        )

        new_edit = EditedChunk(
            edited_chunk_id=edited_chunk_id,
            parent_chunk_id=chunk_id,
            version=version,
            edited_text=edited_text,
            edit_reason=edit_reason,
            original_text=source_chunk.get('text', ''),
            inherited_metadata=inherited_metadata,
            editor_id=self.annotator_id,
            is_current_version=True,
            edited_hierarchy=edited_hierarchy,
            original_hierarchy=dict(original_hierarchy) if original_hierarchy else None,
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
            edited_hierarchy=target_edit.edited_hierarchy,
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
            'split_chunks': {
                k: [s.to_dict() for s in splits]
                for k, splits in self.split_chunks.items()
            },
            'merged_chunks': {
                k: [m.to_dict() for m in merges]
                for k, merges in self.merged_chunks.items()
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

        split_chunks_data = session_data.get('split_chunks', {})
        self.split_chunks = {
            k: [SplitChunk.from_dict(s) for s in splits]
            for k, splits in split_chunks_data.items()
        }

        merged_chunks_data = session_data.get('merged_chunks', {})
        self.merged_chunks = {
            k: [MergeChunk.from_dict(m) for m in merges]
            for k, merges in merged_chunks_data.items()
        }

        self.stats = SessionStats(**session_data.get('stats', {}))
        self.stats.total_chunks = len(self.chunks)

    def get_progress_percent(self) -> float:
        """Get annotation progress as percentage."""
        if self.stats.total_chunks == 0:
            return 0.0
        return (self.stats.annotated_count / self.stats.total_chunks) * 100
