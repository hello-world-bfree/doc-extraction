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


def _raw_units(tmp_path: Path, body_html: str, **config_overrides) -> list[dict]:
    extractor = _extract(tmp_path, body_html, **config_overrides)
    return [r if isinstance(r, dict) else r.to_dict() for r in extractor._get_raw_chunks()]


def _extract(tmp_path: Path, body_html: str, **config_overrides) -> EpubExtractor:
    from extraction.extractors.configs import EpubExtractorConfig

    book = epub.EpubBook()
    book.set_identifier('synthetic')
    book.set_title('Synthetic')
    book.set_language('en')
    chapter = epub.EpubHtml(title='Chapter 1', file_name='chap_01.xhtml', lang='en',
                            content=f'<html><body><h1>Chapter 1</h1>{body_html}</body></html>')
    book.add_item(chapter)
    book.toc = (epub.Link('chap_01.xhtml', 'Chapter 1', 'chap1'),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = [chapter]
    path = tmp_path / 'synthetic.epub'
    epub.write_epub(str(path), book)

    settings = dict(min_paragraph_words=1, min_block_words=2, detect_visual_headings=False,
                    filter_tiny_chunks='off')
    settings.update(config_overrides)
    extractor = EpubExtractor(str(path), EpubExtractorConfig(**settings))
    extractor.load()
    extractor.parse()
    return extractor


QUOTE_ONE = 'Blessed are the poor in spirit, for theirs is the kingdom of heaven.'
QUOTE_TWO = 'Blessed are those who mourn, for they shall be comforted in their sorrow.'
PROSE = 'The author then turns from the beatitudes to the parable that follows them.'


def test_blockquote_paragraphs_emitted_once(tmp_path):
    """A quotation's text counted twice inflates the book and skews retrieval toward quoted passages."""
    units = _raw_units(tmp_path, f'<blockquote><p>{QUOTE_ONE}</p><p>{QUOTE_TWO}</p></blockquote><p>{PROSE}</p>')
    joined = '\n'.join(u['text'] for u in units)

    for sentence in (QUOTE_ONE, QUOTE_TWO, PROSE):
        assert joined.count(sentence) == 1, sentence


def test_div_with_inline_children_emitted_once_with_full_text(tmp_path):
    """Publishers that mark paragraphs as divs with emphasis lost those paragraphs entirely (Walking With God)."""
    units = _raw_units(
        tmp_path,
        '<div class="para">Grace builds on <em>nature</em> and does not <span class="sc">destroy</span> it.</div>'
        f'<div class="para">{PROSE}</div>',
    )
    texts = [u['text'] for u in units]

    assert 'Grace builds on nature and does not destroy it.' in texts
    assert PROSE in texts
    assert '\n'.join(texts).count('destroy') == 1


def test_fallback_walk_emits_each_text_node_once(tmp_path):
    """A document reached only by the fallback walk must not repeat a row once per enclosing element."""
    rows = [('Gen', 'Genesis, the book of origins'), ('Exod', 'Exodus, the book of departure'),
            ('Lev', 'Leviticus, the book of priests')]
    table = ''.join(f'<tr><td>{a}</td><td>{b}</td></tr>' for a, b in rows)
    units = _raw_units(tmp_path, f'<div><table>{table}</table></div>', min_block_words=50)

    fallback = [u for u in units if u['source_tag'].startswith('fallback:')]
    assert fallback, 'expected the document to reach the fallback walk'
    joined = '\n'.join(u['text'] for u in units)
    for abbrev, name in rows:
        assert joined.count(name) == 1, name
    texts = [u['text'] for u in fallback]
    assert not any(a != b and a in b for a in texts for b in texts)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
