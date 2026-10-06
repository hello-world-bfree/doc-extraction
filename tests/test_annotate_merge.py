"""Tests for merge-chunk action in annotate-chunks TUI."""

import pytest
from pathlib import Path
import tempfile

pytest.importorskip("textual", reason="textual not installed (annotation extra)")
pytest.importorskip("sklearn", reason="sklearn not installed (annotation extra)")

from extraction.tools.annotate.core.session import (
    AnnotationSession,
    MergeChunk,
)
from extraction.tools.annotate.core.dataset_export import (
    DatasetExporter,
    expand_chunks_with_splits,
)


@pytest.fixture
def chunks():
    return [
        {
            'stable_id': 'a',
            'text': 'Alpha text.',
            'metadata': {'word_count': 2, 'source_file': 'doc.epub'},
        },
        {
            'stable_id': 'b',
            'text': 'Beta text.',
            'metadata': {'word_count': 2, 'source_file': 'doc.epub'},
        },
        {
            'stable_id': 'c',
            'text': 'Gamma text.',
            'metadata': {'word_count': 2, 'source_file': 'doc.epub'},
        },
    ]


@pytest.fixture
def session(chunks):
    with tempfile.TemporaryDirectory() as tmp:
        sf = Path(tmp) / "session.json"
        yield AnnotationSession(chunks=chunks, session_file=sf)


def test_merge_collapses_view_order(session):
    merge = session.create_merge(['a', 'b'], merge_reason='combine intro')
    assert merge is not None
    assert isinstance(merge, MergeChunk)
    assert len(session.view_order) == 2
    assert session.view_order[0] == (merge.merged_chunk_id, None)
    assert session.view_order[1] == ('c', None)


def test_merge_produces_concatenated_text(session):
    merge = session.create_merge(['a', 'b'], merge_reason='r', separator=' || ')
    materialized = session.get_chunk(0)
    assert materialized is not None
    assert materialized['text'] == 'Alpha text. || Beta text.'
    assert materialized['is_merged'] is True
    assert materialized['parent_chunk_ids'] == ['a', 'b']
    assert materialized['stable_id'] == merge.merged_chunk_id


def test_merge_rejects_non_adjacent(session):
    assert session.create_merge(['a', 'c'], merge_reason='r') is None


def test_merge_rejects_reversed_order(session):
    assert session.create_merge(['b', 'a'], merge_reason='r') is None


def test_merge_rejects_under_two(session):
    assert session.create_merge(['a'], merge_reason='r') is None
    assert session.create_merge([], merge_reason='r') is None


def test_merge_requires_reason(session):
    assert session.create_merge(['a', 'b'], merge_reason='   ') is None


def test_merge_rejects_unknown_chunk(session):
    assert session.create_merge(['a', 'zzz'], merge_reason='r') is None


def test_merge_rejects_split_member(session):
    session.create_split('b', ['Beta one.', 'Beta two.'], 'split-reason')
    assert session.create_merge(['a', 'b'], merge_reason='r') is None


def test_merge_rejects_already_merged_member(session):
    m1 = session.create_merge(['a', 'b'], merge_reason='r1')
    assert m1 is not None
    assert session.create_merge(['a', 'c'], merge_reason='r2') is None
    assert session.create_merge(['b', 'c'], merge_reason='r3') is None


def test_merge_inherits_worst_label(session):
    session.set_annotation(label=0, index=0)
    session.set_annotation(label=1, rationale='bad', index=1)
    merge = session.create_merge(['a', 'b'], merge_reason='r')
    ann = session.annotations[merge.merged_chunk_id]
    assert ann.label == 1
    assert 'bad' in ann.rationale


def test_merge_inherits_min_confidence(session):
    session.set_annotation(label=0, confidence=5, index=0)
    session.set_annotation(label=0, confidence=2, index=1)
    merge = session.create_merge(['a', 'b'], merge_reason='r')
    ann = session.annotations[merge.merged_chunk_id]
    assert ann.confidence == 2


def test_merge_inherits_union_issues(session):
    session.set_annotation(label=1, issues=['mixed_topics'], index=0)
    session.set_annotation(label=1, issues=['missing_context'], index=1)
    merge = session.create_merge(['a', 'b'], merge_reason='r')
    ann = session.annotations[merge.merged_chunk_id]
    assert set(ann.issues) == {'mixed_topics', 'missing_context'}


def test_merge_id_deterministic(session):
    m1 = session.create_merge(['a', 'b'], merge_reason='r')
    other_chunks = [
        {'stable_id': 'a', 'text': 'X'},
        {'stable_id': 'b', 'text': 'Y'},
    ]
    sess2 = AnnotationSession(chunks=other_chunks)
    m2 = sess2.create_merge(['a', 'b'], merge_reason='r')
    assert m1.merged_chunk_id == m2.merged_chunk_id


def test_merge_uses_edited_text(session):
    session.create_edit('a', 'EDITED alpha.', 'cleanup')
    merge = session.create_merge(['a', 'b'], merge_reason='r')
    assert merge.original_texts[0] == 'EDITED alpha.'
    assert merge.merged_text.startswith('EDITED alpha.')


def test_navigation_with_merge(session):
    session.create_merge(['a', 'b'], merge_reason='r')
    assert len(session.view_order) == 2
    assert session.current_index == 0
    assert session.next_chunk() is True
    assert session.current_index == 1
    assert session.next_chunk() is False


def test_save_load_roundtrip_preserves_merges(chunks):
    with tempfile.TemporaryDirectory() as tmp:
        sf = Path(tmp) / "session.json"
        sess = AnnotationSession(chunks=chunks, session_file=sf)
        m = sess.create_merge(['a', 'b'], merge_reason='combine')
        sess.set_annotation(label=1, rationale='post-merge bad', index=0)
        sess.save()

        sess2 = AnnotationSession(chunks=chunks, session_file=sf)
        assert len(sess2.view_order) == 2
        assert 'a' in sess2.merged_chunks
        loaded = sess2.get_current_merge('a')
        assert loaded is not None
        assert loaded.parent_chunk_ids == ['a', 'b']
        assert loaded.merged_text == m.merged_text
        assert sess2.annotations[m.merged_chunk_id].label == 1
        assert sess2.annotations[m.merged_chunk_id].rationale == 'post-merge bad'


def test_export_emits_one_record_per_merge(session):
    merge = session.create_merge(['a', 'b'], merge_reason='combine')
    session.set_annotation(label=0, index=0)
    session.set_annotation(label=1, index=1)

    expanded = expand_chunks_with_splits(
        session.chunks,
        session.split_chunks,
        session.edited_chunks,
        session.merged_chunks,
    )
    assert len(expanded) == 2
    merged_rec = next(c for c in expanded if c.get('is_merged'))
    assert merged_rec['stable_id'] == merge.merged_chunk_id
    assert merged_rec['parent_chunk_ids'] == ['a', 'b']
    assert merged_rec['merge_reason'] == 'combine'
    other = next(c for c in expanded if not c.get('is_merged'))
    assert other['stable_id'] == 'c'

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.jsonl"
        anns = {cid: a.to_dict() for cid, a in session.annotations.items()}
        count = DatasetExporter.export_jsonl(expanded, anns, out)
        assert count == 2


def test_get_annotated_indices_includes_merged(session):
    session.create_merge(['a', 'b'], merge_reason='r')
    session.set_annotation(label=0, index=0)
    session.set_annotation(label=0, index=1)
    annotated = session.get_annotated_indices()
    assert annotated == {0, 1}
