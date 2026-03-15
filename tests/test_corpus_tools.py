"""Tests for corpus building tools."""

import json
from pathlib import Path
import pytest

pytest.importorskip("sklearn", reason="sklearn not installed (annotation extra)")

from extraction.tools.corpus_builder import CorpusBuilder
from extraction.tools.training_builder import TrainingDataBuilder


@pytest.fixture
def temp_session_dir(tmp_path):
    """Create temporary session directory with sample session."""
    session_dir = tmp_path / ".annotation_sessions"
    session_dir.mkdir()

    session_data = {
        "current_index": 2,
        "annotator_id": "test",
        "annotations": {
            "chunk1": {
                "chunk_id": "chunk1",
                "label": 0,
                "timestamp": "2026-01-19T10:00:00Z",
                "annotator_id": "test"
            },
            "chunk2": {
                "chunk_id": "chunk2",
                "label": 1,
                "timestamp": "2026-01-19T10:01:00Z",
                "annotator_id": "test"
            },
            "chunk3": {
                "chunk_id": "chunk3",
                "label": 0,
                "timestamp": "2026-01-19T10:02:00Z",
                "annotator_id": "test"
            }
        },
        "edited_chunks": {
            "chunk1": [
                {
                    "edited_chunk_id": "ed_123",
                    "parent_chunk_id": "chunk1",
                    "version": 1,
                    "edited_text": "Edited chunk 1 text",
                    "reason": "Fixed typo",
                    "timestamp": "2026-01-19T10:00:30Z"
                }
            ]
        }
    }

    session_file = session_dir / "test_book.json"
    with open(session_file, 'w') as f:
        json.dump(session_data, f)

    return session_dir


@pytest.fixture
def temp_chunks_dir(tmp_path):
    """Create temporary chunks directory with sample chunks."""
    chunks_dir = tmp_path / "extractions"
    chunks_dir.mkdir()

    chunks_data = {
        "metadata": {
            "title": "Test Book",
            "author": "Test Author"
        },
        "chunks": [
            {
                "stable_id": "chunk1",
                "text": "Original chunk 1 text",
                "metadata": {
                    "word_count": 4,
                    "sentence_count": 1,
                    "hierarchy": {"level_1": "Chapter 1"},
                    "quality": {"score": 0.95}
                }
            },
            {
                "stable_id": "chunk2",
                "text": "Chunk 2 text",
                "metadata": {
                    "word_count": 3,
                    "sentence_count": 1,
                    "hierarchy": {"level_1": "Chapter 1"},
                    "quality": {"score": 0.85}
                }
            },
            {
                "stable_id": "chunk3",
                "text": "Chunk 3 text",
                "metadata": {
                    "word_count": 3,
                    "sentence_count": 1,
                    "hierarchy": {"level_1": "Chapter 2"},
                    "quality": {"score": 0.90}
                }
            }
        ]
    }

    chunks_file = chunks_dir / "test_book.json"
    with open(chunks_file, 'w') as f:
        json.dump(chunks_data, f)

    return chunks_dir


def test_corpus_builder_basic(temp_session_dir, temp_chunks_dir, tmp_path):
    """Test basic corpus building."""
    output_file = tmp_path / "corpus.jsonl"

    builder = CorpusBuilder(
        sessions_dir=temp_session_dir,
        chunks_dir=temp_chunks_dir,
        apply_edits=True,
    )

    corpus, stats = builder.build_corpus()

    assert stats['sessions_processed'] == 1
    assert stats['sessions_skipped'] == 0
    assert stats['good_chunks'] == 2
    assert stats['edited_chunks'] == 1

    assert len(corpus) == 2

    edited_chunk = next(c for c in corpus if c['stable_id'] == 'chunk1')
    assert edited_chunk['edited'] is True
    assert edited_chunk['text'] == "Edited chunk 1 text"

    unedited_chunk = next(c for c in corpus if c['stable_id'] == 'chunk3')
    assert unedited_chunk.get('edited') is None


def test_corpus_builder_no_edits(temp_session_dir, temp_chunks_dir):
    """Test corpus building without applying edits."""
    builder = CorpusBuilder(
        sessions_dir=temp_session_dir,
        chunks_dir=temp_chunks_dir,
        apply_edits=False,
    )

    corpus, stats = builder.build_corpus()

    assert stats['edited_chunks'] == 0

    chunk1 = next(c for c in corpus if c['stable_id'] == 'chunk1')
    assert chunk1.get('edited') is None
    assert chunk1['text'] == "Original chunk 1 text"


def test_corpus_builder_quality_filter(temp_session_dir, temp_chunks_dir):
    """Test corpus building with quality filtering."""
    builder = CorpusBuilder(
        sessions_dir=temp_session_dir,
        chunks_dir=temp_chunks_dir,
        min_quality_score=0.92,
    )

    corpus, stats = builder.build_corpus()

    assert stats['quality_filtered'] == 1
    assert len(corpus) == 1
    assert corpus[0]['stable_id'] == 'chunk1'
    assert corpus[0]['metadata']['quality']['score'] >= 0.92


def test_corpus_builder_nested_dirs(temp_session_dir, tmp_path):
    """Test corpus builder with nested directory structure."""
    nested_dir = tmp_path / "extractions" / "book1"
    nested_dir.mkdir(parents=True)

    chunks_data = {
        "metadata": {"title": "Test"},
        "chunks": [
            {
                "stable_id": "chunk1",
                "text": "Text",
                "metadata": {"quality": {"score": 0.9}}
            }
        ]
    }

    with open(nested_dir / "test_book.json", 'w') as f:
        json.dump(chunks_data, f)

    builder = CorpusBuilder(
        sessions_dir=temp_session_dir,
        chunks_dir=tmp_path / "extractions",
        apply_edits=False,
    )

    corpus, stats = builder.build_corpus()

    assert stats['sessions_processed'] == 1
    assert len(corpus) == 1


def test_training_builder_basic(temp_session_dir, temp_chunks_dir):
    """Test basic training dataset building."""
    builder = TrainingDataBuilder(
        sessions_dir=temp_session_dir,
        chunks_dir=temp_chunks_dir,
        test_size=0.3,
    )

    records, stats = builder.aggregate_training_data()

    assert stats['sessions_processed'] == 1
    assert stats['total_annotations'] == 3
    assert stats['label_distribution'][0] == 2
    assert stats['label_distribution'][1] == 1

    assert len(records) == 3

    for record in records:
        assert 'chunk_id' in record
        assert 'text' in record
        assert 'label' in record
        assert 'features' in record
        assert 'annotation_metadata' in record


def test_training_builder_split(temp_session_dir, temp_chunks_dir):
    """Test train/test splitting."""
    builder = TrainingDataBuilder(
        sessions_dir=temp_session_dir,
        chunks_dir=temp_chunks_dir,
        test_size=0.33,
        stratify=False,
    )

    records, _ = builder.aggregate_training_data()
    train, test = builder.create_train_test_split(records)

    assert len(train) == 2
    assert len(test) == 1


def test_training_builder_balance(temp_session_dir, temp_chunks_dir):
    """Test class balancing."""
    builder = TrainingDataBuilder(
        sessions_dir=temp_session_dir,
        chunks_dir=temp_chunks_dir,
        balance_classes=True,
    )

    records, stats = builder.aggregate_training_data()

    assert stats['balanced'] is True

    label_counts = {}
    for record in records:
        label = record['label']
        label_counts[label] = label_counts.get(label, 0) + 1

    assert label_counts[0] == label_counts[1]
