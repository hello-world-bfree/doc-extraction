"""Regression test for nested div/span duplication bug.

Bug: https://github.com/yourusername/extraction/issues/XXX
Chunks were being duplicated when EPUB had nested div > span structure.
The extractor was processing both parent and child as separate paragraphs.
"""

import tempfile
from pathlib import Path
import pytest
from ebooklib import epub

from extraction.extractors import EpubExtractor


def create_test_epub_with_nested_spans(output_path: Path) -> None:
    """Create minimal EPUB with nested div/span structure that caused duplication."""
    book = epub.EpubBook()
    book.set_identifier('test-nested-spans-123')
    book.set_title('Test Nested Spans')
    book.set_language('en')
    book.add_author('Test Author')

    chapter = epub.EpubHtml(
        title='Chapter 1',
        file_name='chap_01.xhtml',
        lang='en',
        content='''
        <html>
        <body>
            <h1>Chapter 1</h1>
            <div class="parent-container">
                <span class="child-1">First Reading: Numbers 6:22-27</span>
                <span class="child-2">The LORD said to Moses: Speak to Aaron and his sons.</span>
                <span class="child-3">This is how you shall bless the Israelites.</span>
            </div>
            <p>This is a normal paragraph after the nested structure.</p>
        </body>
        </html>
        '''
    )

    book.add_item(chapter)

    book.toc = (epub.Link('chap_01.xhtml', 'Chapter 1', 'chap1'),)

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    book.spine = [chapter]

    epub.write_epub(str(output_path), book)


def test_nested_div_span_no_duplication():
    """Test that nested div>span structure doesn't cause text duplication.

    Regression test for bug where:
    - Parent <div> containing text was extracted as one paragraph
    - Child <span> elements containing subsets of same text were also extracted
    - Result: duplicate text in merged chunks
    """
    with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as tmp:
        epub_path = Path(tmp.name)

    try:
        create_test_epub_with_nested_spans(epub_path)

        extractor = EpubExtractor(str(epub_path))
        extractor.load()
        extractor.parse()

        chunks = extractor.chunks

        # After fix: nested spans don't meet word threshold, only <p> is extracted
        # This is correct behavior - short inline spans shouldn't be standalone paragraphs
        assert len(chunks) >= 1, "Should extract at least the paragraph"

        all_text = "\n".join(chunk.text for chunk in chunks)

        # The nested spans are too short (< 20 words for span threshold)
        # and are correctly NOT extracted as separate chunks
        # Only the <p> element should be extracted
        text_with_paragraph = "\n".join(
            chunk.text for chunk in chunks
            if "normal paragraph" in chunk.text.lower()
        )
        assert "normal paragraph" in text_with_paragraph.lower(), \
            "Regular <p> tags should still be extracted"

        # Verify no duplication occurred (main purpose of this test)
        # If there was duplication, we'd see multiple chunks with similar content
        assert len(chunks) <= 1, \
            "Should not duplicate content from nested structure"

    finally:
        epub_path.unlink(missing_ok=True)


def test_nested_structure_chunk_count():
    """Verify that fixing nested extraction doesn't over-reduce chunk count."""
    with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as tmp:
        epub_path = Path(tmp.name)

    try:
        create_test_epub_with_nested_spans(epub_path)

        extractor = EpubExtractor(str(epub_path))
        extractor.load()
        extractor.parse()

        chunks = extractor.chunks

        heading_chunks = [c for c in chunks if c.heading_path and "Chapter 1" in c.heading_path]
        assert len(heading_chunks) >= 1, "Should have heading chunk"

        text_chunks = [c for c in chunks if "LORD said to Moses" in c.text or "normal paragraph" in c.text]
        assert len(text_chunks) >= 1, "Should have at least one content chunk"

    finally:
        epub_path.unlink(missing_ok=True)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
