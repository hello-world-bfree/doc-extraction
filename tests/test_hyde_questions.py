import os
import tempfile
import pytest

from extraction.tools.question_generator import (
    generate_questions_template,
    enrich_document,
)


def _make_chunk(text, hierarchy=None, content_type="prose", scripture_refs=None):
    if hierarchy is None:
        hierarchy = {"level_1": "Book", "level_2": "Chapter", "level_3": "Section"}
    return {
        "stable_id": "test",
        "text": text,
        "hierarchy": hierarchy,
        "content_type": content_type,
        "heading_path": " / ".join(v for v in hierarchy.values() if v),
        "scripture_references": scripture_refs or [],
    }


class TestTemplateQuestions:

    def test_prose_with_hierarchy(self):
        chunk = _make_chunk("Some text about theology.")
        questions = generate_questions_template(chunk)
        assert len(questions) >= 2
        assert any("Section" in q for q in questions)

    def test_prose_single_level(self):
        chunk = _make_chunk("Text.", hierarchy={"level_1": "Introduction"})
        questions = generate_questions_template(chunk)
        assert any("Introduction" in q for q in questions)

    def test_prose_no_hierarchy(self):
        chunk = _make_chunk("Text.", hierarchy={})
        questions = generate_questions_template(chunk)
        assert questions == []

    def test_code_function(self):
        chunk = _make_chunk("def calculate_sum(a, b):\n    return a + b", content_type="code")
        questions = generate_questions_template(chunk)
        assert any("calculate_sum" in q for q in questions)

    def test_code_class(self):
        chunk = _make_chunk("class DataProcessor:\n    pass", content_type="code")
        questions = generate_questions_template(chunk)
        assert any("DataProcessor" in q for q in questions)

    def test_scripture_refs(self):
        chunk = _make_chunk("Text.", scripture_refs=["John 3:16", "Romans 8:28"])
        questions = generate_questions_template(chunk)
        assert any("John 3:16" in q for q in questions)

    def test_empty_text(self):
        chunk = _make_chunk("", hierarchy={})
        questions = generate_questions_template(chunk)
        assert questions == []


class TestEnrichDocument:

    def test_enriches_chunks(self):
        data = {
            "metadata": {"title": "Test"},
            "chunks": [
                _make_chunk("First chunk text."),
                _make_chunk("def foo(): pass", content_type="code"),
            ],
        }
        result = enrich_document(data, mode="template")
        for chunk in result["chunks"]:
            assert "hypothetical_questions" in chunk

    def test_skips_already_enriched(self):
        data = {
            "metadata": {},
            "chunks": [
                {**_make_chunk("Text."), "hypothetical_questions": ["Existing?"]},
            ],
        }
        result = enrich_document(data, mode="template")
        assert result["chunks"][0]["hypothetical_questions"] == ["Existing?"]

    def test_empty_chunks(self):
        data = {"metadata": {}, "chunks": []}
        result = enrich_document(data, mode="template")
        assert result["chunks"] == []


class TestIntegrationWithExtractor:

    def test_questions_set_after_extract_metadata(self):
        from extraction.extractors.markdown import MarkdownExtractor
        from extraction.extractors.configs import MarkdownExtractorConfig

        md = "# Test\n\n## Chapter\n\nEnough text for a paragraph here with multiple words.\n"
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
                assert c.hypothetical_questions is not None
                assert len(c.hypothetical_questions) >= 1
        finally:
            os.unlink(path)

    def test_code_chunk_gets_code_questions(self):
        from extraction.extractors.markdown import MarkdownExtractor
        from extraction.extractors.configs import MarkdownExtractorConfig

        md = "# Docs\n\n## API\n\n```python\ndef process_data(items):\n    return [x * 2 for x in items]\n```\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(md)
            path = f.name

        try:
            config = MarkdownExtractorConfig(chunking_strategy='nlp', min_paragraph_words=1)
            ext = MarkdownExtractor(path, config)
            ext.load()
            ext.parse()
            ext.extract_metadata()

            code_chunks = [c for c in ext.chunks if c.content_type == 'code']
            assert len(code_chunks) >= 1
            q = code_chunks[0].hypothetical_questions
            assert q is not None
            assert any("process_data" in question for question in q)
        finally:
            os.unlink(path)
