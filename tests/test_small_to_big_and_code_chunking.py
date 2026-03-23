import os
import tempfile
import pytest

from extraction.core.strategies import (
    SmallToBigChunkingStrategy,
    TokenChunkConfig,
    get_strategy,
)
from extraction.core.code_chunking import (
    split_code_at_boundaries,
    _split_python_ast,
    _split_at_declarations,
    _split_at_blank_lines,
)


def _make_chunk(paragraph_id, text, hierarchy=None, content_type="prose", sentences=None):
    if hierarchy is None:
        hierarchy = {"level_1": "Chapter 1", "level_2": "", "level_3": ""}
    if sentences is None:
        sentences = [s.strip() + "." for s in text.split(".") if s.strip()]
        if not sentences:
            sentences = [text]
    return {
        "paragraph_id": paragraph_id,
        "text": text,
        "hierarchy": hierarchy,
        "word_count": len(text.split()),
        "chapter_href": "",
        "source_order": paragraph_id,
        "source_tag": "p",
        "content_type": content_type,
        "cross_references": [],
        "scripture_references": [],
        "dates_mentioned": [],
        "sentences": sentences,
        "doc_stable_id": "test_doc",
        "footnote_citations": None,
        "resolved_footnotes": None,
    }


def _make_prose(paragraph_id, word_count, hierarchy=None):
    words = " ".join(f"word{i}" for i in range(word_count))
    sents = []
    for i in range(0, word_count, 8):
        sents.append(" ".join(f"word{j}" for j in range(i, min(i + 8, word_count))) + ".")
    return _make_chunk(paragraph_id, words, hierarchy=hierarchy, sentences=sents)


# --- SmallToBigChunkingStrategy ---

class TestSmallToBigRegistry:

    def test_registered(self):
        s = get_strategy("small_to_big")
        assert isinstance(s, SmallToBigChunkingStrategy)

    def test_name(self):
        assert SmallToBigChunkingStrategy().name() == "small_to_big"

    def test_requires_token_config(self):
        from extraction.core.strategies import ChunkConfig
        with pytest.raises(TypeError, match="TokenChunkConfig"):
            SmallToBigChunkingStrategy().apply([], ChunkConfig())


class TestSmallToBigOutput:

    def test_produces_parents_and_children(self):
        strategy = SmallToBigChunkingStrategy()
        config = TokenChunkConfig(
            max_tokens=200,
            min_tokens=1,
            overlap_percent=0.0,
        )
        chunks = [_make_prose(i, 50) for i in range(1, 5)]
        result = strategy.apply(chunks, config)

        parents = [c for c in result if c.get('chunk_level') == 'parent']
        children = [c for c in result if c.get('chunk_level') == 'child']

        assert len(parents) >= 1
        assert len(children) >= 1

    def test_parent_has_child_ids(self):
        strategy = SmallToBigChunkingStrategy()
        config = TokenChunkConfig(
            max_tokens=100,
            min_tokens=1,
            overlap_percent=0.0,
        )
        chunks = [_make_prose(i, 40) for i in range(1, 4)]
        result = strategy.apply(chunks, config)

        parents = [c for c in result if c.get('chunk_level') == 'parent']
        children = [c for c in result if c.get('chunk_level') == 'child']

        for parent in parents:
            child_ids = parent.get('child_chunk_ids', [])
            if child_ids:
                for cid in child_ids:
                    matching = [c for c in children if c['stable_id'] == cid]
                    assert len(matching) == 1

    def test_child_has_parent_id(self):
        strategy = SmallToBigChunkingStrategy()
        config = TokenChunkConfig(
            max_tokens=100,
            min_tokens=1,
            overlap_percent=0.0,
        )
        chunks = [_make_prose(i, 40) for i in range(1, 4)]
        result = strategy.apply(chunks, config)

        children = [c for c in result if c.get('chunk_level') == 'child']
        parent_ids = {c['stable_id'] for c in result if c.get('chunk_level') == 'parent'}

        for child in children:
            assert child['parent_chunk_id'] in parent_ids

    def test_code_blocks_are_standalone(self):
        strategy = SmallToBigChunkingStrategy()
        config = TokenChunkConfig(
            max_tokens=200,
            min_tokens=1,
            overlap_percent=0.0,
        )
        chunks = [
            _make_chunk(1, "def foo(): return 42", content_type="code"),
        ]
        result = strategy.apply(chunks, config)
        assert len(result) == 1
        assert result[0]['chunk_level'] == 'standalone'

    def test_child_stable_ids_deterministic(self):
        strategy = SmallToBigChunkingStrategy()
        config = TokenChunkConfig(max_tokens=100, min_tokens=1, overlap_percent=0.0)
        chunks = [_make_prose(i, 40) for i in range(1, 4)]
        result1 = strategy.apply(chunks, config)
        result2 = strategy.apply(chunks, config)
        ids1 = [c['stable_id'] for c in result1]
        ids2 = [c['stable_id'] for c in result2]
        assert ids1 == ids2


# --- Contextual prefix ---

class TestContextualPrefix:

    def test_prefix_set_after_extract_metadata(self):
        from extraction.extractors.markdown import MarkdownExtractor
        from extraction.extractors.configs import MarkdownExtractorConfig

        md = "# Test Title\n\n## Chapter One\n\nSome paragraph with enough words to pass the minimum threshold.\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(md)
            path = f.name

        try:
            config = MarkdownExtractorConfig(chunking_strategy='nlp', min_paragraph_words=1)
            ext = MarkdownExtractor(path, config)
            ext.load()
            ext.parse()

            for c in ext.chunks:
                assert c.context_prefix is None

            ext.extract_metadata()

            for c in ext.chunks:
                assert c.context_prefix is not None
                assert "Section:" in c.context_prefix
        finally:
            os.unlink(path)

    def test_prefix_includes_document_title(self):
        from extraction.extractors.markdown import MarkdownExtractor
        from extraction.extractors.configs import MarkdownExtractorConfig

        md = "# My Great Book\n\nSome paragraph with enough words to pass the minimum.\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(md)
            path = f.name

        try:
            config = MarkdownExtractorConfig(chunking_strategy='nlp', min_paragraph_words=1)
            ext = MarkdownExtractor(path, config)
            ext.load()
            ext.parse()
            ext.extract_metadata()

            for c in ext.chunks:
                assert "Document: My Great Book" in c.context_prefix
        finally:
            os.unlink(path)


# --- AST-aware code chunking ---

class TestPythonASTSplitting:

    def test_splits_at_function_boundaries(self):
        code = '''import os

def foo():
    return 1

def bar():
    return 2

def baz():
    return 3
'''
        counter = lambda t: len(t.split())
        result = split_code_at_boundaries(code, "python", max_tokens=8, token_counter=counter)
        assert len(result) >= 2
        assert any("def foo" in r for r in result)
        assert any("def bar" in r for r in result)

    def test_keeps_small_code_intact(self):
        code = "x = 1\ny = 2\n"
        counter = lambda t: len(t.split())
        result = split_code_at_boundaries(code, "python", max_tokens=100, token_counter=counter)
        assert len(result) == 1
        assert result[0] == code

    def test_handles_syntax_error_gracefully(self):
        code = "def foo(\n  broken syntax here"
        counter = lambda t: len(t.split())
        result = split_code_at_boundaries(code, "python", max_tokens=5, token_counter=counter)
        assert len(result) >= 1

    def test_class_boundaries(self):
        code = '''class Foo:
    def method_a(self):
        pass

class Bar:
    def method_b(self):
        pass
'''
        counter = lambda t: len(t.split())
        result = _split_python_ast(code, max_tokens=20, token_counter=counter)
        assert len(result) >= 2


class TestDeclarationSplitting:

    def test_javascript_functions(self):
        code = '''const helper = () => {
  return 1;
};

function main() {
  return helper();
}

export const other = (x) => {
  return x * 2;
};
'''
        counter = lambda t: len(t.split())
        result = _split_at_declarations(code, max_tokens=30, token_counter=counter)
        assert len(result) >= 2

    def test_rust_functions(self):
        code = '''fn main() {
    println!("hello");
}

pub fn helper() -> i32 {
    42
}
'''
        counter = lambda t: len(t.split())
        result = _split_at_declarations(code, max_tokens=15, token_counter=counter)
        assert len(result) >= 2


class TestBlankLineSplitting:

    def test_splits_on_blank_lines(self):
        code = "block1\nline1\n\nblock2\nline2\n\nblock3\nline3"
        counter = lambda t: len(t.split())
        result = _split_at_blank_lines(code, max_tokens=5, token_counter=counter)
        assert len(result) >= 2

    def test_no_split_if_small(self):
        code = "x = 1\ny = 2"
        counter = lambda t: len(t.split())
        result = _split_at_blank_lines(code, max_tokens=100, token_counter=counter)
        assert len(result) == 1

    def test_empty_code(self):
        result = split_code_at_boundaries("", "python")
        assert result == []
