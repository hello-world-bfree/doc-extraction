"""Dataset export for training ML models."""

from pathlib import Path
from typing import List, Dict, Optional
import json
from sklearn.model_selection import train_test_split

from .session import EditedChunk


def _get_chunk_field(chunk: Dict, field: str, default=None):
    """Get a field from chunk, checking both top-level and nested metadata."""
    if field in chunk:
        return chunk[field]
    metadata = chunk.get('metadata', {})
    if field in metadata:
        return metadata[field]
    return default


def _extract_chunk_metadata(chunk: Dict) -> Dict:
    """Extract chunk metadata from both top-level and nested locations."""
    hierarchy = _get_chunk_field(chunk, 'hierarchy', {})

    quality = _get_chunk_field(chunk, 'quality', {})
    if isinstance(quality, dict):
        quality_score = quality.get('score', 0.0)
        quality_signals = quality.get('signals', {})
    else:
        quality_score = 0.0
        quality_signals = {}

    result = {
        'word_count': _get_chunk_field(chunk, 'word_count', 0),
        'sentence_count': _get_chunk_field(chunk, 'sentence_count', 0),
        'hierarchy_depth': len([v for v in hierarchy.values() if v]),
        'quality_score': quality_score,
        'scripture_refs': _get_chunk_field(chunk, 'scripture_references', []),
        'cross_refs': _get_chunk_field(chunk, 'cross_references', []),
        'hierarchy': hierarchy,
        'noise_filter_flagged': _get_chunk_field(chunk, 'noise_filter_flagged', False),
        'heading_path': _get_chunk_field(chunk, 'heading_path', ''),
    }

    if quality_signals:
        result['garble_rate'] = quality_signals.get('garble_rate', 0.0)
        result['mean_conf'] = quality_signals.get('mean_conf', 0.5)

    return result


def _extract_doc_metadata(doc_metadata: Dict) -> Dict:
    """Extract essential document-level metadata."""
    return {
        'title': doc_metadata.get('title', ''),
        'author': doc_metadata.get('author', ''),
        'publisher': doc_metadata.get('publisher', ''),
        'description': doc_metadata.get('description', ''),
        'language': doc_metadata.get('language', ''),
        'document_type': doc_metadata.get('document_type', ''),
        'subjects': doc_metadata.get('subject', []),
    }


class DatasetExporter:
    """Exports annotated chunks to training datasets."""

    @staticmethod
    def export_jsonl(
        chunks: List[Dict],
        annotations: Dict[str, Dict],
        output_path: Path,
        include_metadata: bool = True,
        doc_metadata: Optional[Dict] = None,
    ) -> int:
        """Export annotations to JSONL format.

        Args:
            chunks: List of chunk dictionaries
            annotations: Dict mapping chunk_id to annotation data
            output_path: Path to output JSONL file
            include_metadata: Whether to include chunk metadata
            doc_metadata: Document-level metadata (title, author, etc.)

        Returns:
            Number of annotations exported
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc_meta_extracted = _extract_doc_metadata(doc_metadata) if doc_metadata else {}

        exported_count = 0
        with open(output_path, 'w') as f:
            for chunk in chunks:
                chunk_id = chunk.get('stable_id') or chunk.get('chunk_id')
                if chunk_id not in annotations:
                    continue

                annotation = annotations[chunk_id]

                if annotation.get('label') is None:
                    continue

                source_file = _get_chunk_field(chunk, 'source_file', '')

                record = {
                    'chunk_id': chunk_id,
                    'source_file': source_file,
                    'text': chunk.get('text', ''),
                    'label': annotation['label'],
                    'confidence': annotation.get('confidence'),
                    'rationale': annotation.get('rationale', ''),
                    'issues': annotation.get('issues', []),
                    'annotation_timestamp': annotation.get('timestamp'),
                    'annotator_id': annotation.get('annotator_id', 'default'),
                }

                if include_metadata:
                    record['metadata'] = _extract_chunk_metadata(chunk)

                if doc_meta_extracted:
                    record['document'] = doc_meta_extracted

                f.write(json.dumps(record) + '\n')
                exported_count += 1

        return exported_count

    @staticmethod
    def export_train_test_split(
        chunks: List[Dict],
        annotations: Dict[str, Dict],
        output_dir: Path,
        test_size: float = 0.2,
        stratify: bool = True,
        random_state: int = 42,
        doc_metadata: Optional[Dict] = None,
    ) -> tuple[int, int]:
        """Export annotations with train/test split.

        Args:
            chunks: List of chunk dictionaries
            annotations: Dict mapping chunk_id to annotation data
            output_dir: Directory for train.jsonl and test.jsonl
            test_size: Proportion for test set
            stratify: Whether to stratify by label
            random_state: Random seed for reproducibility
            doc_metadata: Document-level metadata (title, author, etc.)

        Returns:
            Tuple of (train_count, test_count)
        """
        annotated_chunks = []
        for chunk in chunks:
            chunk_id = chunk.get('stable_id') or chunk.get('chunk_id')
            if chunk_id in annotations and annotations[chunk_id].get('label') is not None:
                annotated_chunks.append(chunk)

        if not annotated_chunks:
            return 0, 0

        labels = [
            annotations[c.get('stable_id') or c.get('chunk_id')]['label']
            for c in annotated_chunks
        ]

        if stratify and len(set(labels)) > 1:
            train_chunks, test_chunks = train_test_split(
                annotated_chunks,
                test_size=test_size,
                stratify=labels,
                random_state=random_state,
            )
        else:
            train_chunks, test_chunks = train_test_split(
                annotated_chunks,
                test_size=test_size,
                random_state=random_state,
            )

        output_dir.mkdir(parents=True, exist_ok=True)

        train_count = DatasetExporter.export_jsonl(
            train_chunks,
            annotations,
            output_dir / 'train.jsonl',
            doc_metadata=doc_metadata,
        )

        test_count = DatasetExporter.export_jsonl(
            test_chunks,
            annotations,
            output_dir / 'test.jsonl',
            doc_metadata=doc_metadata,
        )

        return train_count, test_count

    @staticmethod
    def export_by_issues(
        chunks: List[Dict],
        annotations: Dict[str, Dict],
        output_dir: Path,
        issues: Optional[List[str]] = None,
        doc_metadata: Optional[Dict] = None,
    ) -> Dict[str, int]:
        """Export chunks grouped by issue type.

        Args:
            chunks: List of chunk dictionaries
            annotations: Dict mapping chunk_id to annotation data
            output_dir: Directory for issue-specific JSONL files
            issues: List of issues to export (None = all)
            doc_metadata: Document-level metadata (title, author, etc.)

        Returns:
            Dict mapping issue type to count of chunks exported
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        issue_chunks: Dict[str, List[Dict]] = {}

        for chunk in chunks:
            chunk_id = chunk.get('stable_id') or chunk.get('chunk_id')
            if chunk_id not in annotations:
                continue

            annotation = annotations[chunk_id]
            chunk_issues = annotation.get('issues', [])

            for issue in chunk_issues:
                if issues is not None and issue not in issues:
                    continue

                if issue not in issue_chunks:
                    issue_chunks[issue] = []

                issue_chunks[issue].append(chunk)

        counts = {}
        for issue, issue_chunk_list in issue_chunks.items():
            output_file = output_dir / f"{issue}.jsonl"
            count = DatasetExporter.export_jsonl(
                issue_chunk_list,
                annotations,
                output_file,
                doc_metadata=doc_metadata,
            )
            counts[issue] = count

        return counts

    @staticmethod
    def export_by_labels(
        chunks: List[Dict],
        annotations: Dict[str, Dict],
        output_dir: Path,
        labels: Optional[List[int]] = None,
        doc_metadata: Optional[Dict] = None,
    ) -> Dict[int, int]:
        """Export chunks grouped by label.

        Args:
            chunks: List of chunk dictionaries
            annotations: Dict mapping chunk_id to annotation data
            output_dir: Directory for label-specific JSONL files
            labels: List of labels to export (None = all)
            doc_metadata: Document-level metadata (title, author, etc.)

        Returns:
            Dict mapping label to count of chunks exported
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        label_chunks: Dict[int, List[Dict]] = {}

        for chunk in chunks:
            chunk_id = chunk.get('stable_id') or chunk.get('chunk_id')
            if chunk_id not in annotations:
                continue

            annotation = annotations[chunk_id]
            label = annotation.get('label')

            if label is None:
                continue

            if labels is not None and label not in labels:
                continue

            if label not in label_chunks:
                label_chunks[label] = []

            label_chunks[label].append(chunk)

        label_names = {0: 'good', 1: 'bad'}

        counts = {}
        for label, label_chunk_list in label_chunks.items():
            label_name = label_names.get(label, f'label_{label}')
            output_file = output_dir / f"{label_name}.jsonl"
            count = DatasetExporter.export_jsonl(
                label_chunk_list,
                annotations,
                output_file,
                doc_metadata=doc_metadata,
            )
            counts[label] = count

        return counts

    @staticmethod
    def export_edited_jsonl(
        chunks: List[Dict],
        annotations: Dict[str, Dict],
        edited_chunks: Dict[str, List[EditedChunk]],
        output_path: Path,
        include_metadata: bool = True,
        doc_metadata: Optional[Dict] = None,
    ) -> int:
        """Export chunks with edited versions where available.

        Args:
            chunks: List of original chunk dictionaries
            annotations: Dict mapping chunk_id to annotation data
            edited_chunks: Dict mapping chunk_id to list of EditedChunk objects
            output_path: Path to output JSONL file
            include_metadata: Whether to include chunk metadata
            doc_metadata: Document-level metadata (title, author, etc.)

        Returns:
            Number of chunks exported
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc_meta_extracted = _extract_doc_metadata(doc_metadata) if doc_metadata else {}

        exported_count = 0
        with open(output_path, 'w') as f:
            for chunk in chunks:
                chunk_id = chunk.get('stable_id') or chunk.get('chunk_id')

                current_edit = None
                if chunk_id in edited_chunks:
                    edits = edited_chunks[chunk_id]
                    for edit in reversed(edits):
                        if edit.is_current_version:
                            current_edit = edit
                            break

                if current_edit:
                    text = current_edit.edited_text
                    edited_chunk_id = current_edit.edited_chunk_id
                    is_edited = True
                    edit_version = current_edit.version
                    edit_reason = current_edit.edit_reason
                else:
                    text = chunk.get('text', '')
                    edited_chunk_id = None
                    is_edited = False
                    edit_version = None
                    edit_reason = None

                record = {
                    'text': text,
                    'parent_chunk_id': chunk_id,
                    'is_edited': is_edited,
                }

                if is_edited:
                    record['edited_chunk_id'] = edited_chunk_id
                    record['edit_version'] = edit_version
                    record['edit_reason'] = edit_reason

                annotation = annotations.get(chunk_id)
                if annotation:
                    record['label'] = annotation.get('label')
                    record['confidence'] = annotation.get('confidence')
                    record['rationale'] = annotation.get('rationale', '')
                    record['issues'] = annotation.get('issues', [])

                if include_metadata:
                    chunk_meta = _extract_chunk_metadata(chunk)
                    if is_edited:
                        chunk_meta['word_count'] = len(text.split())
                    chunk_meta['source_file'] = _get_chunk_field(chunk, 'source_file', '')
                    record['metadata'] = chunk_meta

                if doc_meta_extracted:
                    record['document'] = doc_meta_extracted

                f.write(json.dumps(record) + '\n')
                exported_count += 1

        return exported_count

    @staticmethod
    def export_audit_jsonl(
        chunks: List[Dict],
        annotations: Dict[str, Dict],
        edited_chunks: Dict[str, List[EditedChunk]],
        output_path: Path,
        doc_metadata: Optional[Dict] = None,
    ) -> int:
        """Export chunks with full edit lineage for audit purposes.

        Args:
            chunks: List of original chunk dictionaries
            annotations: Dict mapping chunk_id to annotation data
            edited_chunks: Dict mapping chunk_id to list of EditedChunk objects
            output_path: Path to output JSONL file
            doc_metadata: Document-level metadata (title, author, etc.)

        Returns:
            Number of chunks exported
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc_meta_extracted = _extract_doc_metadata(doc_metadata) if doc_metadata else {}

        exported_count = 0
        with open(output_path, 'w') as f:
            for chunk in chunks:
                chunk_id = chunk.get('stable_id') or chunk.get('chunk_id')

                edit_history = edited_chunks.get(chunk_id, [])
                current_edit = None
                for edit in reversed(edit_history):
                    if edit.is_current_version:
                        current_edit = edit
                        break

                if current_edit:
                    text = current_edit.edited_text
                    edited_chunk_id = current_edit.edited_chunk_id
                else:
                    text = chunk.get('text', '')
                    edited_chunk_id = None

                record = {
                    'text': text,
                    'parent_chunk_id': chunk_id,
                }

                if edited_chunk_id:
                    record['edited_chunk_id'] = edited_chunk_id

                if edit_history:
                    record['lineage'] = {
                        'original_text': chunk.get('text', ''),
                        'versions': [
                            {
                                'version': edit.version,
                                'edited_by': edit.editor_id,
                                'timestamp': edit.timestamp,
                                'edit_reason': edit.edit_reason,
                                'edited_chunk_id': edit.edited_chunk_id,
                            }
                            for edit in edit_history
                        ],
                        'current_version': current_edit.version if current_edit else None,
                    }

                annotation = annotations.get(chunk_id)
                if annotation:
                    record['annotation'] = {
                        'label': annotation.get('label'),
                        'confidence': annotation.get('confidence'),
                        'rationale': annotation.get('rationale', ''),
                        'issues': annotation.get('issues', []),
                        'timestamp': annotation.get('timestamp'),
                        'annotator_id': annotation.get('annotator_id'),
                    }

                record['metadata'] = _extract_chunk_metadata(chunk)
                record['metadata']['source_file'] = _get_chunk_field(chunk, 'source_file', '')

                if doc_meta_extracted:
                    record['document'] = doc_meta_extracted

                f.write(json.dumps(record) + '\n')
                exported_count += 1

        return exported_count

    @staticmethod
    def export_diff_report(
        chunks: List[Dict],
        edited_chunks: Dict[str, List[EditedChunk]],
        output_path: Path,
    ) -> int:
        """Export human-readable diff report for edited chunks.

        Args:
            chunks: List of original chunk dictionaries
            edited_chunks: Dict mapping chunk_id to list of EditedChunk objects
            output_path: Path to output Markdown file

        Returns:
            Number of edited chunks in report
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        edited_count = 0
        with open(output_path, 'w') as f:
            f.write("# Edit Diff Report\n\n")
            f.write(f"Total chunks: {len(chunks)}\n")
            f.write(f"Edited chunks: {len(edited_chunks)}\n\n")

            for chunk in chunks:
                chunk_id = chunk.get('stable_id') or chunk.get('chunk_id')

                edit_history = edited_chunks.get(chunk_id, [])
                if not edit_history:
                    continue

                current_edit = None
                for edit in reversed(edit_history):
                    if edit.is_current_version:
                        current_edit = edit
                        break

                if not current_edit:
                    continue

                edited_count += 1

                f.write(f"## Chunk: {chunk_id} (Version {current_edit.version})\n\n")

                hierarchy = _get_chunk_field(chunk, 'hierarchy', {})
                if hierarchy:
                    breadcrumb = ' > '.join([v for v in hierarchy.values() if v])
                    f.write(f"**Hierarchy**: {breadcrumb}\n\n")

                f.write("**Original**:\n```\n")
                f.write(chunk.get('text', ''))
                f.write("\n```\n\n")

                f.write("**Edited**:\n```\n")
                f.write(current_edit.edited_text)
                f.write("\n```\n\n")

                f.write(f"**Edit Reason**: {current_edit.edit_reason}\n")
                f.write(f"**Edited By**: {current_edit.editor_id}\n")
                f.write(f"**Timestamp**: {current_edit.timestamp}\n\n")

                if len(edit_history) > 1:
                    f.write(f"**Version History**: {len(edit_history)} versions\n")
                    for i, edit in enumerate(edit_history, 1):
                        f.write(f"  {i}. v{edit.version}: {edit.edit_reason}\n")
                    f.write("\n")

                f.write("---\n\n")

        return edited_count
