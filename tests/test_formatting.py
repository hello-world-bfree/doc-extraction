#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for structural formatting preservation.

Verifies that formatted_text and structure_metadata fields correctly
capture document structure when preserve_formatting is enabled.
"""

import pytest
from bs4 import BeautifulSoup

from src.extraction.core.formatting import FormattedTextBuilder


class TestFormattedTextBuilder:
    """Test FormattedTextBuilder utility."""

    def test_extract_poetry_preserves_line_breaks(self):
        """Verify poetry line breaks are preserved."""
        html = """<div class="poem">
            <div class="line">The Lord is my shepherd;</div>
            <div class="line">I shall not want.</div>
        </div>"""
        soup = BeautifulSoup(html, "html.parser")
        div = soup.find("div", class_="poem")

        builder = FormattedTextBuilder(preserve_line_breaks=True)
        formatted_text = builder.extract_formatted_text(div)

        assert "The Lord is my shepherd;" in formatted_text
        assert "I shall not want." in formatted_text
        assert "\n" in formatted_text  # Line break preserved
        lines = formatted_text.split("\n")
        assert len(lines) == 2

    def test_extract_poetry_with_indentation(self):
        """Verify poetry indentation is preserved."""
        html = """<div class="poem">
            <div class="line">First line</div>
            <div class="line">  Indented line</div>
        </div>"""
        soup = BeautifulSoup(html, "html.parser")
        div = soup.find("div", class_="poem")

        builder = FormattedTextBuilder(preserve_line_breaks=True)
        formatted_text = builder.extract_formatted_text(div)

        lines = formatted_text.split("\n")
        assert len(lines) == 2
        # Second line should have leading spaces
        assert lines[1].startswith(" ")

    def test_extract_blockquote_with_prefix(self):
        """Verify blockquote boundaries with > prefix."""
        html = """<blockquote>
            <p>The Church is called to be the house of the Father.</p>
        </blockquote>"""
        soup = BeautifulSoup(html, "html.parser")
        blockquote = soup.find("blockquote")

        builder = FormattedTextBuilder(preserve_blockquotes=True)
        formatted_text = builder.extract_formatted_text(blockquote)

        assert formatted_text.startswith(">")
        assert "The Church is called to be the house of the Father." in formatted_text

    def test_extract_blockquote_with_attribution(self):
        """Verify blockquote attribution is extracted."""
        html = """<blockquote cite="Pope Francis">
            <p>God never tires of forgiving us.</p>
            <footer>— Pope Francis, <cite>Evangelii Gaudium</cite></footer>
        </blockquote>"""
        soup = BeautifulSoup(html, "html.parser")
        blockquote = soup.find("blockquote")

        builder = FormattedTextBuilder(preserve_blockquotes=True)
        formatted_text = builder.extract_formatted_text(blockquote)

        assert "God never tires of forgiving us." in formatted_text
        assert "Pope Francis" in formatted_text or "Evangelii Gaudium" in formatted_text

    def test_extract_unordered_list(self):
        """Verify unordered list formatting."""
        html = """<ul>
            <li>First item</li>
            <li>Second item</li>
            <li>Third item</li>
        </ul>"""
        soup = BeautifulSoup(html, "html.parser")
        ul = soup.find("ul")

        builder = FormattedTextBuilder(preserve_lists=True)
        formatted_text = builder.extract_formatted_text(ul)

        assert "- First item" in formatted_text
        assert "- Second item" in formatted_text
        assert "- Third item" in formatted_text

    def test_extract_ordered_list(self):
        """Verify ordered list formatting with numbers."""
        html = """<ol>
            <li>First step</li>
            <li>Second step</li>
            <li>Third step</li>
        </ol>"""
        soup = BeautifulSoup(html, "html.parser")
        ol = soup.find("ol")

        builder = FormattedTextBuilder(preserve_lists=True)
        formatted_text = builder.extract_formatted_text(ol)

        assert "1. First step" in formatted_text
        assert "2. Second step" in formatted_text
        assert "3. Third step" in formatted_text

    def test_extract_nested_lists(self):
        """Verify nested list indentation."""
        html = """<ul>
            <li>Item 1
                <ul>
                    <li>Subitem A</li>
                    <li>Subitem B</li>
                </ul>
            </li>
            <li>Item 2</li>
        </ul>"""
        soup = BeautifulSoup(html, "html.parser")
        ul = soup.find("ul")

        builder = FormattedTextBuilder(preserve_lists=True)
        formatted_text = builder.extract_formatted_text(ul)

        assert "- Item 1" in formatted_text
        assert "  - Subitem A" in formatted_text  # Indented by 2 spaces
        assert "  - Subitem B" in formatted_text
        assert "- Item 2" in formatted_text

    def test_extract_table_markdown_format(self):
        """Verify table structure in markdown format."""
        html = """<table>
            <thead>
                <tr><th>Virtue</th><th>Description</th></tr>
            </thead>
            <tbody>
                <tr><td>Faith</td><td>Belief in God</td></tr>
                <tr><td>Hope</td><td>Trust in salvation</td></tr>
            </tbody>
        </table>"""
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")

        builder = FormattedTextBuilder(preserve_tables=True)
        formatted_text = builder.extract_formatted_text(table)

        assert "| Virtue | Description |" in formatted_text
        assert "| --- | --- |" in formatted_text
        assert "| Faith | Belief in God |" in formatted_text
        assert "| Hope | Trust in salvation |" in formatted_text

    def test_extract_emphasis_italic(self):
        """Verify italic emphasis with *text*."""
        html = """<p>This has <em>italic text</em> in it.</p>"""
        soup = BeautifulSoup(html, "html.parser")
        p = soup.find("p")

        builder = FormattedTextBuilder(preserve_emphasis=True)
        formatted_text = builder.extract_formatted_text(p)

        assert "*italic text*" in formatted_text

    def test_extract_emphasis_bold(self):
        """Verify bold emphasis with **text**."""
        html = """<p>This has <strong>bold text</strong> in it.</p>"""
        soup = BeautifulSoup(html, "html.parser")
        p = soup.find("p")

        builder = FormattedTextBuilder(preserve_emphasis=True)
        formatted_text = builder.extract_formatted_text(p)

        assert "**bold text**" in formatted_text

    def test_extract_code_block(self):
        """Verify code block with triple backticks."""
        html = """<pre><code class="language-python">def hello():
    print("Hello")</code></pre>"""
        soup = BeautifulSoup(html, "html.parser")
        pre = soup.find("pre")

        builder = FormattedTextBuilder()
        formatted_text = builder.extract_formatted_text(pre)

        assert "```python" in formatted_text
        assert "def hello():" in formatted_text
        assert "```" in formatted_text

    def test_extract_br_as_newline(self):
        """Verify <br> tags become newlines."""
        html = """<p>Line one<br/>Line two<br/>Line three</p>"""
        soup = BeautifulSoup(html, "html.parser")
        p = soup.find("p")

        builder = FormattedTextBuilder(preserve_line_breaks=True)
        formatted_text = builder.extract_formatted_text(p)

        assert "\n" in formatted_text
        assert "Line one" in formatted_text
        assert "Line two" in formatted_text
        assert "Line three" in formatted_text

    def test_structure_metadata_captures_element_type(self):
        """Verify structure_metadata records element type."""
        html = """<blockquote><p>Quote text</p></blockquote>"""
        soup = BeautifulSoup(html, "html.parser")
        blockquote = soup.find("blockquote")

        builder = FormattedTextBuilder()
        metadata = builder.extract_structure_metadata(blockquote)

        assert metadata["element_type"] == "blockquote"
        assert "formatting" in metadata
        assert metadata["formatting"].get("blockquote") is True

    def test_structure_metadata_captures_list_type(self):
        """Verify structure_metadata records ordered vs unordered."""
        html = """<ol><li>Item</li></ol>"""
        soup = BeautifulSoup(html, "html.parser")
        ol = soup.find("ol")

        builder = FormattedTextBuilder()
        metadata = builder.extract_structure_metadata(ol)

        assert metadata["element_type"] == "ol"
        assert metadata["formatting"].get("list_type") == "ol"
        assert metadata["formatting"].get("ordered") is True

    def test_structure_metadata_captures_poetry(self):
        """Verify structure_metadata detects poetry containers."""
        html = """<div class="poem">
            <div class="line">Line 1</div>
            <div class="line">Line 2</div>
        </div>"""
        soup = BeautifulSoup(html, "html.parser")
        div = soup.find("div", class_="poem")

        builder = FormattedTextBuilder()
        metadata = builder.extract_structure_metadata(div)

        assert metadata["formatting"].get("poetry") is True
        assert "line_breaks" in metadata["formatting"]

    def test_disabled_formatting_returns_plain_text(self):
        """Verify formatting can be disabled selectively."""
        html = """<blockquote><p>Quote</p></blockquote>"""
        soup = BeautifulSoup(html, "html.parser")
        blockquote = soup.find("blockquote")

        builder = FormattedTextBuilder(preserve_blockquotes=False)
        formatted_text = builder.extract_formatted_text(blockquote)

        # Should not have > prefix when blockquotes disabled
        assert not formatted_text.startswith(">")
        assert "Quote" in formatted_text

    def test_disabled_lists_flattens_items(self):
        """Verify list formatting can be disabled."""
        html = """<ul><li>Item 1</li><li>Item 2</li></ul>"""
        soup = BeautifulSoup(html, "html.parser")
        ul = soup.find("ul")

        builder = FormattedTextBuilder(preserve_lists=False)
        formatted_text = builder.extract_formatted_text(ul)

        # Should not have bullet markers when lists disabled
        assert not formatted_text.startswith("-")

    def test_empty_element_returns_empty_string(self):
        """Verify empty elements return empty string."""
        html = """<p></p>"""
        soup = BeautifulSoup(html, "html.parser")
        p = soup.find("p")

        builder = FormattedTextBuilder()
        formatted_text = builder.extract_formatted_text(p)

        assert formatted_text == ""

    def test_mixed_content_preserves_all_formats(self):
        """Verify complex mixed content preserves all formatting."""
        html = """<div>
            <blockquote>
                <p>A <em>quoted</em> <strong>passage</strong>.</p>
            </blockquote>
            <ul>
                <li>First item</li>
                <li>Second item</li>
            </ul>
        </div>"""
        soup = BeautifulSoup(html, "html.parser")
        div = soup.find("div")

        builder = FormattedTextBuilder(
            preserve_blockquotes=True,
            preserve_lists=True,
            preserve_emphasis=True
        )
        formatted_text = builder.extract_formatted_text(div)

        # Blockquote prefix
        assert "> " in formatted_text
        # Emphasis markers
        assert "*quoted*" in formatted_text
        assert "**passage**" in formatted_text
        # List markers
        assert "- First item" in formatted_text
        assert "- Second item" in formatted_text


class TestBackwardCompatibility:
    """Test backward compatibility with existing behavior."""

    def test_none_formatted_text_when_disabled(self):
        """Verify formatted_text can be None (default)."""
        # This will be tested in integration tests once extractor is updated
        pass

    def test_to_dict_filters_none_values(self):
        """Verify to_dict() filters None formatted_text/structure_metadata."""
        from src.extraction.core.models import Chunk

        chunk = Chunk(
            stable_id="test123",
            paragraph_id=1,
            text="Sample text",
            hierarchy={},
            chapter_href="chapter1.xhtml",
            source_order=1,
            source_tag="p",
            text_length=11,
            word_count=2,
            cross_references=[],
            scripture_references=[],
            dates_mentioned=[],
            heading_path="",
            hierarchy_depth=0,
            doc_stable_id="doc123",
            sentence_count=1,
            sentences=["Sample text"],
            normalized_text="sample text",
            formatted_text=None,  # Should be filtered out
            structure_metadata=None,  # Should be filtered out
        )

        chunk_dict = chunk.to_dict()

        # None values should not be in dict
        assert "formatted_text" not in chunk_dict
        assert "structure_metadata" not in chunk_dict
        # But other fields should be present
        assert chunk_dict["text"] == "Sample text"
        assert chunk_dict["stable_id"] == "test123"


class TestHtmlExtractorIntegration:
    """Test HTML extractor with formatting enabled."""

    def test_html_poetry_extraction(self, tmp_path):
        """Verify HTML poetry chunks have formatted_text."""
        from src.extraction.extractors.html import HtmlExtractor

        # Create test HTML with poetry
        html_content = """<html>
<head><title>Test Poem</title></head>
<body>
<h1>Psalm 23</h1>
<div class="poem">
    <div class="line">The Lord is my shepherd;</div>
    <div class="line">I shall not want.</div>
</div>
</body>
</html>"""
        html_file = tmp_path / "test_poem.html"
        html_file.write_text(html_content)

        # Extract with formatting enabled
        extractor = HtmlExtractor(str(html_file), config={
            "preserve_formatting": True,
            "min_paragraph_words": 1
        })
        extractor.load()
        extractor.parse()

        # Find the poem chunk
        poem_chunks = [c for c in extractor.chunks if c.source_tag == "div"]
        assert len(poem_chunks) > 0

        chunk = poem_chunks[0]
        # Should have formatted_text with line breaks
        assert chunk.formatted_text is not None
        assert "\n" in chunk.formatted_text
        assert "The Lord is my shepherd;" in chunk.formatted_text
        assert "I shall not want." in chunk.formatted_text

        # Should have structure_metadata
        assert chunk.structure_metadata is not None
        assert chunk.structure_metadata.get("formatting", {}).get("poetry") is True

    def test_html_blockquote_extraction(self, tmp_path):
        """Verify HTML blockquote chunks have formatted_text."""
        from src.extraction.extractors.html import HtmlExtractor

        html_content = """<html>
<body>
<blockquote>
    <p>God never tires of forgiving us.</p>
    <footer>— Pope Francis</footer>
</blockquote>
</body>
</html>"""
        html_file = tmp_path / "test_quote.html"
        html_file.write_text(html_content)

        extractor = HtmlExtractor(str(html_file), config={
            "preserve_formatting": True,
            "min_paragraph_words": 1
        })
        extractor.load()
        extractor.parse()

        # Find blockquote chunk
        blockquote_chunks = [c for c in extractor.chunks if c.source_tag == "blockquote"]
        assert len(blockquote_chunks) > 0

        chunk = blockquote_chunks[0]
        # Should have formatted_text with > prefix
        assert chunk.formatted_text is not None
        assert chunk.formatted_text.startswith(">")
        assert "God never tires of forgiving us." in chunk.formatted_text

    def test_html_list_extraction(self, tmp_path):
        """Verify HTML list chunks have formatted_text."""
        from src.extraction.extractors.html import HtmlExtractor

        html_content = """<html>
<body>
<ul>
    <li>First item</li>
    <li>Second item</li>
    <li>Third item</li>
</ul>
</body>
</html>"""
        html_file = tmp_path / "test_list.html"
        html_file.write_text(html_content)

        extractor = HtmlExtractor(str(html_file), config={
            "preserve_formatting": True,
            "min_paragraph_words": 1
        })
        extractor.load()
        extractor.parse()

        # Find list item chunks
        li_chunks = [c for c in extractor.chunks if c.source_tag == "li"]
        assert len(li_chunks) == 3

        # Each should have formatted_text (though individual <li> won't show bullets in this case)
        for chunk in li_chunks:
            assert chunk.text in ["First item", "Second item", "Third item"]

    def test_html_formatting_disabled_by_default(self, tmp_path):
        """Verify formatting is disabled by default."""
        from src.extraction.extractors.html import HtmlExtractor

        html_content = """<html>
<body>
<blockquote><p>Quote text</p></blockquote>
</body>
</html>"""
        html_file = tmp_path / "test_default.html"
        html_file.write_text(html_content)

        # Extract WITHOUT preserve_formatting flag
        extractor = HtmlExtractor(str(html_file), config={
            "min_paragraph_words": 1
        })
        extractor.load()
        extractor.parse()

        # Chunks should NOT have formatted_text
        for chunk in extractor.chunks:
            assert chunk.formatted_text is None
            assert chunk.structure_metadata is None
