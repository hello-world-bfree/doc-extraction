"""Tests for split-chunk action in annotate-chunks TUI."""

import pytest
from pathlib import Path
import tempfile

pytest.importorskip("textual", reason="textual not installed (annotation extra)")
pytest.importorskip("sklearn", reason="sklearn not installed (annotation extra)")

from extraction.tools.annotate.core.session import (
    AnnotationSession,
    ChunkAnnotation,
    SplitChunk,
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
            'text': 'Alpha text content here.',
            'metadata': {'word_count': 4, 'source_file': 'doc.epub'},
        },
        {
            'stable_id': 'b',
            'text': 'Beta one. Beta two. Beta three.',
            'metadata': {'word_count': 6, 'source_file': 'doc.epub'},
        },
        {
            'stable_id': 'c',
            'text': 'Gamma final.',
            'metadata': {'word_count': 2, 'source_file': 'doc.epub'},
        },
    ]


@pytest.fixture
def session(chunks):
    with tempfile.TemporaryDirectory() as tmp:
        sf = Path(tmp) / "session.json"
        yield AnnotationSession(chunks=chunks, session_file=sf)


def test_view_order_initial_matches_chunks(session):
    assert len(session.view_order) == 3
    assert [v[0] for v in session.view_order] == ['a', 'b', 'c']
    assert all(seg is None for _, seg in session.view_order)


def test_create_split_expands_view_order(session):
    split = session.create_split(
        chunk_id='b',
        segments=['Beta one.', 'Beta two.', 'Beta three.'],
        split_reason='mixed topics',
    )
    assert split is not None
    assert len(split.split_chunk_ids) == 3
    assert len(session.view_order) == 5
    assert session.view_order[0] == ('a', None)
    assert session.view_order[1] == ('b', 0)
    assert session.view_order[2] == ('b', 1)
    assert session.view_order[3] == ('b', 2)
    assert session.view_order[4] == ('c', None)


def test_split_rejects_under_2_segments(session):
    assert session.create_split('b', ['only one'], 'reason') is None
    assert session.create_split('b', ['a', ''], 'reason') is None


def test_split_requires_reason(session):
    assert session.create_split('b', ['x', 'y'], '') is None


def test_split_child_ids_deterministic(session):
    s1 = session.create_split('b', ['Same.', 'Other.'], 'r')
    expected_first = SplitChunk.__hash__  # just to keep import
    assert s1 is not None
    ids_run1 = list(s1.split_chunk_ids)

    sess2 = AnnotationSession(chunks=[{'stable_id': 'b', 'text': 'Whatever.'}])
    s2 = sess2.create_split('b', ['Same.', 'Other.'], 'r')
    assert s2.split_chunk_ids == ids_run1


def test_child_inherits_parent_annotation(session):
    session.set_annotation(
        label=1,
        rationale='bad',
        confidence=4,
        issues=['mixed_topics'],
        index=1,
    )
    split = session.create_split('b', ['p1', 'p2'], 'r')
    for child_id in split.split_chunk_ids:
        ann = session.annotations[child_id]
        assert ann.label == 1
        assert ann.confidence == 4
        assert ann.issues == ['mixed_topics']
        assert ann.rationale == 'bad'


def test_annotate_child_independently(session):
    split = session.create_split('b', ['p1', 'p2'], 'r')
    session.current_index = 2
    session.set_annotation(label=0, rationale='actually fine', index=2)
    child_id = split.split_chunk_ids[1]
    assert session.annotations[child_id].label == 0
    assert session.annotations[child_id].rationale == 'actually fine'


def test_get_chunk_returns_child_segment(session):
    split = session.create_split('b', ['Beta one.', 'Beta two.', 'Beta three.'], 'r')
    c1 = session.get_chunk(1)
    assert c1['text'] == 'Beta one.'
    assert c1['stable_id'] == split.split_chunk_ids[0]
    assert c1['parent_chunk_id'] == 'b'
    assert c1['is_split'] is True
    assert c1['split_index'] == 0


def test_navigation_with_split(session):
    session.create_split('b', ['p1', 'p2'], 'r')
    assert len(session.view_order) == 4
    assert session.current_index == 0
    session.next_chunk()
    session.next_chunk()
    session.next_chunk()
    assert session.current_index == 3
    assert session.next_chunk() is False
    assert session.current_index == 3


def test_split_of_edited_chunk_uses_edit_text(session):
    session.create_edit('b', 'Edited beta.', 'cleanup')
    split = session.create_split('b', ['Edit one.', 'Edit two.'], 'r')
    assert split is not None
    assert split.original_text == 'Edited beta.'


def test_split_of_split_child(session):
    s1 = session.create_split('b', ['Beta one.', 'Beta two.'], 'r')
    child_id = s1.split_chunk_ids[1]
    s2 = session.create_split(child_id, ['Beta two part a.', 'Beta two part b.'], 'r2')
    assert s2 is not None
    assert len(session.view_order) == 5
    assert session.view_order[0] == ('a', None)
    assert session.view_order[1] == ('b', 0)
    assert session.view_order[2] == (child_id, 0)
    assert session.view_order[3] == (child_id, 1)
    assert session.view_order[4] == ('c', None)


def test_save_load_roundtrip_preserves_splits(chunks):
    with tempfile.TemporaryDirectory() as tmp:
        sf = Path(tmp) / "session.json"
        sess = AnnotationSession(chunks=chunks, session_file=sf)
        sess.create_split('b', ['Beta one.', 'Beta two.'], 'split reason')
        sess.set_annotation(label=1, rationale='bad child', index=2)
        sess.save()

        sess2 = AnnotationSession(chunks=chunks, session_file=sf)
        assert len(sess2.view_order) == 4
        assert 'b' in sess2.split_chunks
        split = sess2.get_current_split('b')
        assert split.segments == ['Beta one.', 'Beta two.']
        child_id = split.split_chunk_ids[1]
        assert sess2.annotations[child_id].label == 1
        assert sess2.annotations[child_id].rationale == 'bad child'


def test_export_emits_n_records_per_split(session):
    session.create_split('b', ['Beta one.', 'Beta two.', 'Beta three.'], 'split-it')
    session.set_annotation(label=0, index=0)
    session.set_annotation(label=0, index=1)
    session.set_annotation(label=1, index=2)
    session.set_annotation(label=0, index=3)
    session.set_annotation(label=0, index=4)

    expanded = expand_chunks_with_splits(
        session.chunks, session.split_chunks, session.edited_chunks
    )
    assert len(expanded) == 5

    parent_b_children = [c for c in expanded if c.get('parent_chunk_id') == 'b']
    assert len(parent_b_children) == 3
    for child in parent_b_children:
        assert child['is_split'] is True
        assert child['split_reason'] == 'split-it'
        assert child['split_version'] == 1

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.jsonl"
        anns = {cid: a.to_dict() for cid, a in session.annotations.items()}
        count = DatasetExporter.export_jsonl(expanded, anns, out)
        assert count == 5


def test_get_annotated_indices_includes_split_children(session):
    session.create_split('b', ['p1', 'p2'], 'r')
    session.set_annotation(label=0, index=0)
    session.set_annotation(label=0, index=1)
    session.set_annotation(label=1, index=2)
    annotated = session.get_annotated_indices()
    assert annotated == {0, 1, 2, 3}
