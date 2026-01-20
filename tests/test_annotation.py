"""Tests for chunk annotation tool."""

import pytest
from pathlib import Path
import json
import tempfile

from extraction.tools.annotate.core.session import (
    AnnotationSession,
    ChunkAnnotation,
    EditedChunk,
    SessionStats,
)
from extraction.tools.annotate.core.chunk_loader import ChunkLoader
from extraction.tools.annotate.core.active_learning import ActiveLearner
from extraction.tools.annotate.core.dataset_export import DatasetExporter


@pytest.fixture
def sample_chunks():
    """Create sample chunks for testing."""
    return [
        {
            'stable_id': 'chunk_1',
            'text': 'This is the first chunk with good content.',
            'metadata': {
                'word_count': 8,
                'sentence_count': 1,
                'hierarchy': {'level_1': 'Chapter 1'},
                'quality': {'score': 0.85},
                'source_file': 'test.epub',
            }
        },
        {
            'stable_id': 'chunk_2',
            'text': 'Second chunk here.',
            'metadata': {
                'word_count': 3,
                'sentence_count': 1,
                'hierarchy': {'level_1': 'Chapter 1'},
                'quality': {'score': 0.45},
                'source_file': 'test.epub',
            }
        },
        {
            'stable_id': 'chunk_3',
            'text': 'Third chunk with more substantial content for testing purposes.',
            'metadata': {
                'word_count': 9,
                'sentence_count': 1,
                'hierarchy': {'level_1': 'Chapter 2'},
                'quality': {'score': 0.75},
                'source_file': 'test.epub',
            }
        },
    ]


class TestChunkAnnotation:
    """Tests for ChunkAnnotation model."""

    def test_create_annotation(self):
        """Test creating annotation."""
        annotation = ChunkAnnotation(
            chunk_id='chunk_1',
            label=0,
            confidence=5,
            rationale='Good chunk',
            issues=['missing_context'],
        )

        assert annotation.chunk_id == 'chunk_1'
        assert annotation.label == 0
        assert annotation.confidence == 5
        assert annotation.rationale == 'Good chunk'
        assert 'missing_context' in annotation.issues

    def test_is_annotated(self):
        """Test is_annotated method."""
        annotated = ChunkAnnotation(chunk_id='chunk_1', label=0)
        skipped = ChunkAnnotation(chunk_id='chunk_2', label=None)

        assert annotated.is_annotated()
        assert not skipped.is_annotated()

    def test_to_dict(self):
        """Test converting to dictionary."""
        annotation = ChunkAnnotation(
            chunk_id='chunk_1',
            label=1,
            confidence=3,
            rationale='Bad chunk',
        )

        data = annotation.to_dict()

        assert data['chunk_id'] == 'chunk_1'
        assert data['label'] == 1
        assert data['confidence'] == 3
        assert data['rationale'] == 'Bad chunk'

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            'chunk_id': 'chunk_1',
            'label': 0,
            'confidence': 4,
            'rationale': 'Test',
            'issues': ['noise_index_toc'],
            'timestamp': '2026-01-18T12:00:00Z',
            'annotator_id': 'test_user',
        }

        annotation = ChunkAnnotation.from_dict(data)

        assert annotation.chunk_id == 'chunk_1'
        assert annotation.label == 0
        assert annotation.confidence == 4


class TestAnnotationSession:
    """Tests for AnnotationSession."""

    def test_create_session(self, sample_chunks):
        """Test creating session."""
        session = AnnotationSession(sample_chunks)

        assert session.stats.total_chunks == 3
        assert session.current_index == 0
        assert len(session.annotations) == 0

    def test_get_chunk(self, sample_chunks):
        """Test getting chunk."""
        session = AnnotationSession(sample_chunks)

        chunk = session.get_chunk()
        assert chunk['stable_id'] == 'chunk_1'

        chunk = session.get_chunk(1)
        assert chunk['stable_id'] == 'chunk_2'

    def test_set_annotation(self, sample_chunks):
        """Test setting annotation."""
        session = AnnotationSession(sample_chunks)

        success = session.set_annotation(
            label=0,
            rationale='Good',
            confidence=5,
            issues=['missing_context'],
        )

        assert success
        assert session.stats.annotated_count == 1
        assert session.stats.good_count == 1

        annotation = session.get_annotation()
        assert annotation.label == 0
        assert annotation.rationale == 'Good'

    def test_navigation(self, sample_chunks):
        """Test chunk navigation."""
        session = AnnotationSession(sample_chunks)

        assert session.current_index == 0

        session.next_chunk()
        assert session.current_index == 1

        session.prev_chunk()
        assert session.current_index == 0

        session.jump_to(2)
        assert session.current_index == 2

    def test_undo(self, sample_chunks):
        """Test undo functionality."""
        session = AnnotationSession(sample_chunks)

        session.set_annotation(label=0)
        assert session.stats.annotated_count == 1

        session.undo()
        assert session.stats.annotated_count == 0

    def test_save_load(self, sample_chunks, tmp_path):
        """Test saving and loading session."""
        session_file = tmp_path / 'session.json'

        session = AnnotationSession(
            sample_chunks,
            session_file=session_file,
        )

        session.set_annotation(label=0, rationale='Test')
        session.next_chunk()
        session.set_annotation(label=1, rationale='Bad')

        session.save()

        assert session_file.exists()

        new_session = AnnotationSession(
            sample_chunks,
            session_file=session_file,
        )

        assert new_session.stats.annotated_count == 2
        assert new_session.stats.good_count == 1
        assert new_session.stats.bad_count == 1
        assert new_session.current_index == 1

    def test_get_progress(self, sample_chunks):
        """Test progress calculation."""
        session = AnnotationSession(sample_chunks)

        assert session.get_progress_percent() == 0.0

        session.set_annotation(label=0)
        progress = session.get_progress_percent()
        assert progress == pytest.approx(33.33, rel=0.1)

        session.next_chunk()
        session.set_annotation(label=1)
        session.next_chunk()
        session.set_annotation(label=0)

        assert session.get_progress_percent() == 100.0


class TestEditedChunks:
    """Tests for chunk editing functionality."""

    def test_create_edit(self, sample_chunks):
        """Test creating a chunk edit."""
        session = AnnotationSession(sample_chunks)

        original_text = sample_chunks[0]['text']
        edited_text = "This is edited text with corrections."
        edit_reason = "Fixed typo"

        edit = session.create_edit(
            chunk_id='chunk_1',
            edited_text=edited_text,
            edit_reason=edit_reason,
        )

        assert edit is not None
        assert edit.parent_chunk_id == 'chunk_1'
        assert edit.edited_text == edited_text
        assert edit.edit_reason == edit_reason
        assert edit.original_text == original_text
        assert edit.version == 1
        assert edit.is_current_version is True
        assert edit.edited_chunk_id.startswith('ed_')

    def test_edit_requires_reason(self, sample_chunks):
        """Test that edit requires non-empty reason."""
        session = AnnotationSession(sample_chunks)

        edit = session.create_edit(
            chunk_id='chunk_1',
            edited_text="Edited text",
            edit_reason="",
        )

        assert edit is None

    def test_get_current_edit(self, sample_chunks):
        """Test getting current edit."""
        session = AnnotationSession(sample_chunks)

        assert session.get_current_edit('chunk_1') is None

        session.create_edit(
            chunk_id='chunk_1',
            edited_text="First edit",
            edit_reason="Reason 1",
        )

        current_edit = session.get_current_edit('chunk_1')
        assert current_edit is not None
        assert current_edit.edited_text == "First edit"
        assert current_edit.version == 1

    def test_multiple_versions(self, sample_chunks):
        """Test creating multiple edit versions."""
        session = AnnotationSession(sample_chunks)

        edit1 = session.create_edit(
            chunk_id='chunk_1',
            edited_text="First edit",
            edit_reason="Reason 1",
        )

        edit2 = session.create_edit(
            chunk_id='chunk_1',
            edited_text="Second edit",
            edit_reason="Reason 2",
        )

        assert edit1.version == 1
        assert edit2.version == 2
        assert edit1.is_current_version is False
        assert edit2.is_current_version is True

        current = session.get_current_edit('chunk_1')
        assert current.version == 2
        assert current.edited_text == "Second edit"

    def test_edit_history(self, sample_chunks):
        """Test getting edit history."""
        session = AnnotationSession(sample_chunks)

        session.create_edit('chunk_1', "Edit 1", "Reason 1")
        session.create_edit('chunk_1', "Edit 2", "Reason 2")
        session.create_edit('chunk_1', "Edit 3", "Reason 3")

        history = session.get_edit_history('chunk_1')
        assert len(history) == 3
        assert history[0].version == 1
        assert history[1].version == 2
        assert history[2].version == 3

    def test_restore_edit_version(self, sample_chunks):
        """Test restoring old edit version."""
        session = AnnotationSession(sample_chunks)

        session.create_edit('chunk_1', "Edit 1", "Reason 1")
        session.create_edit('chunk_1', "Edit 2", "Reason 2")

        restored = session.restore_edit_version(
            chunk_id='chunk_1',
            version=1,
            edit_reason="Restoring v1",
        )

        assert restored is not None
        assert restored.version == 3
        assert restored.edited_text == "Edit 1"
        assert restored.edit_reason == "Restoring v1"
        assert restored.is_current_version is True

    def test_get_chunk_returns_edited_version(self, sample_chunks):
        """Test that get_chunk returns edited version if exists."""
        session = AnnotationSession(sample_chunks)

        original_chunk = session.get_chunk(0)
        assert original_chunk['text'] == sample_chunks[0]['text']
        assert 'is_edited' not in original_chunk

        session.create_edit(
            chunk_id='chunk_1',
            edited_text="Edited text",
            edit_reason="Test edit",
        )

        edited_chunk = session.get_chunk(0)
        assert edited_chunk['text'] == "Edited text"
        assert edited_chunk['is_edited'] is True
        assert edited_chunk['edit_version'] == 1
        assert edited_chunk['edited_chunk_id'].startswith('ed_')

    def test_save_load_with_edits(self, sample_chunks, tmp_path):
        """Test saving and loading session with edits."""
        session_file = tmp_path / 'session.json'

        session = AnnotationSession(
            sample_chunks,
            session_file=session_file,
        )

        session.create_edit('chunk_1', "Edit 1", "Reason 1")
        session.create_edit('chunk_1', "Edit 2", "Reason 2")
        session.create_edit('chunk_2', "Edit A", "Reason A")

        session.save()
        assert session_file.exists()

        new_session = AnnotationSession(
            sample_chunks,
            session_file=session_file,
        )

        assert len(new_session.edited_chunks) == 2
        assert len(new_session.get_edit_history('chunk_1')) == 2
        assert len(new_session.get_edit_history('chunk_2')) == 1

        current_edit = new_session.get_current_edit('chunk_1')
        assert current_edit.version == 2
        assert current_edit.edited_text == "Edit 2"

    def test_edited_chunk_id_uniqueness(self, sample_chunks):
        """Test that edited chunk IDs are unique per text."""
        session = AnnotationSession(sample_chunks)

        edit1 = session.create_edit('chunk_1', "Same text", "Reason 1")
        edit2 = session.create_edit('chunk_2', "Same text", "Reason 2")

        assert edit1.edited_chunk_id == edit2.edited_chunk_id

        edit3 = session.create_edit('chunk_3', "Different text", "Reason 3")
        assert edit3.edited_chunk_id != edit1.edited_chunk_id

    def test_inherited_metadata(self, sample_chunks):
        """Test that edited chunks inherit metadata from original."""
        session = AnnotationSession(sample_chunks)

        edit = session.create_edit(
            chunk_id='chunk_1',
            edited_text="New text with five words.",
            edit_reason="Test metadata",
        )

        assert 'metadata' in edit.inherited_metadata
        assert edit.inherited_metadata['metadata']['hierarchy']['level_1'] == 'Chapter 1'
        assert edit.inherited_metadata['metadata']['source_file'] == 'test.epub'
        assert edit.inherited_metadata['metadata']['word_count'] == 5

    def test_edit_nonexistent_chunk(self, sample_chunks):
        """Test editing nonexistent chunk returns None."""
        session = AnnotationSession(sample_chunks)

        edit = session.create_edit(
            chunk_id='nonexistent',
            edited_text="Text",
            edit_reason="Reason",
        )

        assert edit is None


class TestChunkLoader:
    """Tests for ChunkLoader."""

    def test_load_from_json(self, sample_chunks, tmp_path):
        """Test loading from JSON file."""
        json_file = tmp_path / 'chunks.json'

        data = {
            'metadata': {'provenance': {'source_file': 'test.epub'}},
            'chunks': sample_chunks,
        }

        with open(json_file, 'w') as f:
            json.dump(data, f)

        loaded_chunks = ChunkLoader.load_from_file(json_file)

        assert len(loaded_chunks) == 3
        assert loaded_chunks[0]['stable_id'] == 'chunk_1'

    def test_load_from_jsonl(self, sample_chunks, tmp_path):
        """Test loading from JSONL file."""
        jsonl_file = tmp_path / 'chunks.jsonl'

        with open(jsonl_file, 'w') as f:
            for chunk in sample_chunks:
                f.write(json.dumps(chunk) + '\n')

        loaded_chunks = ChunkLoader.load_from_jsonl(jsonl_file)

        assert len(loaded_chunks) == 3
        assert loaded_chunks[0]['stable_id'] == 'chunk_1'

    def test_auto_detect_format(self, sample_chunks, tmp_path):
        """Test auto-detection of file format."""
        json_file = tmp_path / 'chunks.json'
        jsonl_file = tmp_path / 'chunks.jsonl'

        data = {'chunks': sample_chunks}
        with open(json_file, 'w') as f:
            json.dump(data, f)

        with open(jsonl_file, 'w') as f:
            for chunk in sample_chunks:
                f.write(json.dumps(chunk) + '\n')

        json_chunks = ChunkLoader.load(json_file)
        jsonl_chunks = ChunkLoader.load(jsonl_file)

        assert len(json_chunks) == 3
        assert len(jsonl_chunks) == 3


class TestActiveLearner:
    """Tests for ActiveLearner."""

    def test_create_learner(self, sample_chunks):
        """Test creating active learner."""
        learner = ActiveLearner(sample_chunks)

        assert learner.phase == 'bootstrap'
        assert len(learner.annotated_indices) == 0

    def test_diversity_sampling(self, sample_chunks):
        """Test diversity sampling."""
        learner = ActiveLearner(sample_chunks)

        next_indices = learner.get_next_indices(set(), batch_size=2)

        assert len(next_indices) == 2
        assert all(0 <= i < len(sample_chunks) for i in next_indices)

    def test_progress_estimate(self, sample_chunks):
        """Test progress estimation."""
        learner = ActiveLearner(sample_chunks)

        progress = learner.get_progress_estimate()
        assert progress == 0.0

        learner.annotated_indices = {0}
        progress = learner.get_progress_estimate()
        assert progress > 0.0


class TestDatasetExporter:
    """Tests for DatasetExporter."""

    def test_export_jsonl(self, sample_chunks, tmp_path):
        """Test exporting to JSONL."""
        output_file = tmp_path / 'annotations.jsonl'

        annotations = {
            'chunk_1': {
                'label': 0,
                'confidence': 5,
                'rationale': 'Good',
                'issues': [],
                'timestamp': '2026-01-18T12:00:00Z',
                'annotator_id': 'test',
            },
            'chunk_2': {
                'label': 1,
                'confidence': 3,
                'rationale': 'Bad',
                'issues': ['noise_index_toc'],
                'timestamp': '2026-01-18T12:01:00Z',
                'annotator_id': 'test',
            },
        }

        count = DatasetExporter.export_jsonl(
            sample_chunks,
            annotations,
            output_file,
        )

        assert count == 2
        assert output_file.exists()

        with open(output_file) as f:
            lines = f.readlines()
            assert len(lines) == 2

            record = json.loads(lines[0])
            assert record['label'] == 0
            assert record['chunk_id'] == 'chunk_1'

    def test_export_train_test_split(self, sample_chunks, tmp_path):
        """Test exporting train/test split."""
        annotations = {
            'chunk_1': {'label': 0, 'rationale': 'Good', 'issues': [], 'timestamp': '2026-01-18T12:00:00Z', 'annotator_id': 'test'},
            'chunk_2': {'label': 1, 'rationale': 'Bad', 'issues': [], 'timestamp': '2026-01-18T12:00:00Z', 'annotator_id': 'test'},
            'chunk_3': {'label': 0, 'rationale': 'Good', 'issues': [], 'timestamp': '2026-01-18T12:00:00Z', 'annotator_id': 'test'},
        }

        train_count, test_count = DatasetExporter.export_train_test_split(
            sample_chunks,
            annotations,
            tmp_path,
            test_size=0.33,
            stratify=False,
        )

        assert train_count + test_count == 3
        assert (tmp_path / 'train.jsonl').exists()
        assert (tmp_path / 'test.jsonl').exists()

    def test_export_by_issues(self, sample_chunks, tmp_path):
        """Test exporting by issue type."""
        annotations = {
            'chunk_1': {'label': 0, 'issues': ['missing_context'], 'rationale': '', 'timestamp': '2026-01-18T12:00:00Z', 'annotator_id': 'test'},
            'chunk_2': {'label': 1, 'issues': ['noise_index_toc'], 'rationale': '', 'timestamp': '2026-01-18T12:00:00Z', 'annotator_id': 'test'},
        }

        output_dir = tmp_path / 'issues'
        counts = DatasetExporter.export_by_issues(
            sample_chunks,
            annotations,
            output_dir,
        )

        assert 'missing_context' in counts
        assert 'noise_index_toc' in counts
        assert (output_dir / 'missing_context.jsonl').exists()

    def test_export_by_labels(self, sample_chunks, tmp_path):
        """Test exporting by label."""
        annotations = {
            'chunk_1': {'label': 0, 'issues': [], 'rationale': '', 'timestamp': '2026-01-18T12:00:00Z', 'annotator_id': 'test'},
            'chunk_2': {'label': 1, 'issues': [], 'rationale': '', 'timestamp': '2026-01-18T12:00:00Z', 'annotator_id': 'test'},
            'chunk_3': {'label': 0, 'issues': [], 'rationale': '', 'timestamp': '2026-01-18T12:00:00Z', 'annotator_id': 'test'},
        }

        output_dir = tmp_path / 'labels'
        counts = DatasetExporter.export_by_labels(
            sample_chunks,
            annotations,
            output_dir,
        )

        assert counts[0] == 2
        assert counts[1] == 1
        assert (output_dir / 'good.jsonl').exists()
        assert (output_dir / 'bad.jsonl').exists()

    def test_export_edited_jsonl(self, sample_chunks, tmp_path):
        """Test exporting edited chunks to JSONL."""
        session = AnnotationSession(sample_chunks)

        session.create_edit('chunk_1', "Edited text for chunk 1", "Fixed typo")
        session.create_edit('chunk_2', "Edited text for chunk 2", "Improved clarity")

        output_file = tmp_path / 'edited.jsonl'
        count = DatasetExporter.export_edited_jsonl(
            sample_chunks,
            {},
            session.edited_chunks,
            output_file,
        )

        assert count == 3
        assert output_file.exists()

        with open(output_file) as f:
            lines = f.readlines()
            assert len(lines) == 3

            record1 = json.loads(lines[0])
            assert record1['is_edited'] is True
            assert record1['text'] == "Edited text for chunk 1"
            assert record1['edited_chunk_id'].startswith('ed_')
            assert record1['edit_version'] == 1

            record2 = json.loads(lines[1])
            assert record2['is_edited'] is True

            record3 = json.loads(lines[2])
            assert record3['is_edited'] is False
            assert record3['text'] == sample_chunks[2]['text']

    def test_export_audit_jsonl(self, sample_chunks, tmp_path):
        """Test exporting audit JSONL with full lineage."""
        session = AnnotationSession(sample_chunks)

        session.create_edit('chunk_1', "First edit", "Reason 1")
        session.create_edit('chunk_1', "Second edit", "Reason 2")

        output_file = tmp_path / 'audit.jsonl'
        count = DatasetExporter.export_audit_jsonl(
            sample_chunks,
            {},
            session.edited_chunks,
            output_file,
        )

        assert count == 3
        assert output_file.exists()

        with open(output_file) as f:
            lines = f.readlines()
            record = json.loads(lines[0])

            assert record['text'] == "Second edit"
            assert 'lineage' in record
            assert len(record['lineage']['versions']) == 2
            assert record['lineage']['current_version'] == 2
            assert record['lineage']['original_text'] == sample_chunks[0]['text']

    def test_export_diff_report(self, sample_chunks, tmp_path):
        """Test exporting diff report."""
        session = AnnotationSession(sample_chunks)

        session.create_edit('chunk_1', "Edited chunk 1", "Fixed error")
        session.create_edit('chunk_2', "Edited chunk 2", "Improved text")

        output_file = tmp_path / 'diff_report.md'
        count = DatasetExporter.export_diff_report(
            sample_chunks,
            session.edited_chunks,
            output_file,
        )

        assert count == 2
        assert output_file.exists()

        with open(output_file) as f:
            content = f.read()
            assert '# Edit Diff Report' in content
            assert 'chunk_1' in content
            assert 'chunk_2' in content
            assert 'Fixed error' in content
            assert 'Improved text' in content
            assert 'Original' in content
            assert 'Edited' in content
