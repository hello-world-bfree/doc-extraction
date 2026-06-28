"""Regression test: a content spine item whose filename ends in 'contents'.

Bug: Leanpub/pandoc-generated EPUBs put the entire book body in a single spine
item named 'all_chapter_contents.xhtml'. The TOC-skip filter used an unanchored
regex `(toc|nav|contents)\\.x?html?$`, so this body file matched 'contents.xhtml$'
and was discarded as navigation — leaving only front matter (~70 words, 1-2 chunks)
from a full-length book. Fix anchors the match on the basename.
"""

import tempfile
from pathlib import Path

from ebooklib import epub

from extraction.extractors import EpubExtractor


# A multi-paragraph body, long enough to clear the RAG chunk-word threshold.
_BODY = """
<html><body epub:type="bodymatter">
    <section id="ch1" class="level1">
    <h1>Chapter One</h1>
    <p>AI agents today have a memory problem. Vector stores give them semantic
    search, but they forget structure, relationships, and the provenance of every
    fact they retrieve, which makes long-horizon reasoning brittle and unreliable.</p>
    <p>A labeled property graph fixes this by modeling entities as nodes and the
    relationships between them as typed, queryable edges that persist across every
    session and can be traversed, filtered, and reasoned over deterministically.</p>
    <p>This chapter walks through the architecture from first principles so that a
    reader with no prior graph-database experience can build a working memory layer
    for an agent and understand exactly why each design decision was made.</p>
    </section>
</body></html>
"""


def _build_leanpub_style_epub(output_path: Path) -> None:
    """EPUB whose single body file is named like Leanpub's 'all_chapter_contents.xhtml',
    alongside a genuine nav file that should still be skipped."""
    book = epub.EpubBook()
    book.set_identifier("test-contents-filename-1")
    book.set_title("Leanpub Style Book")
    book.set_language("en")
    book.add_author("Test Author")

    body = epub.EpubHtml(
        title="Body", file_name="text/all_chapter_contents.xhtml", lang="en",
        content=_BODY,
    )
    book.add_item(body)

    book.toc = (epub.Link("text/all_chapter_contents.xhtml", "Chapter One", "ch1"),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())  # writes nav.xhtml — must be skipped

    book.spine = [body]
    epub.write_epub(str(output_path), book)


def test_contents_named_body_is_extracted():
    """The body file ending in 'contents.xhtml' must NOT be skipped as a TOC file."""
    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
        epub_path = Path(tmp.name)
    try:
        _build_leanpub_style_epub(epub_path)

        extractor = EpubExtractor(str(epub_path))
        extractor.load()
        extractor.parse()
        chunks = extractor.chunks

        all_text = "\n".join(c.text for c in chunks).lower()

        # The actual book body must survive extraction.
        assert "labeled property graph" in all_text, (
            "Body file all_chapter_contents.xhtml was skipped as a TOC file"
        )
        # Sanity: real prose yields more than the front-matter-only failure mode.
        assert sum(c.word_count for c in chunks) > 100, (
            "Suspiciously few words — content spine item likely skipped"
        )
    finally:
        epub_path.unlink(missing_ok=True)
