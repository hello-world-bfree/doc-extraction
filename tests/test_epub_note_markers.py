"""Superscript note markers without a noteref class.

Older and Kobo-converted books mark notes with a bare <sup>, a link styled vertical-align: super,
or a "superscript" class. Kept, the marker glues to the word ("virtue3", "good298") and the word
no longer matches a keyword search.
"""

from pathlib import Path

from ebooklib import epub

from extraction.extractors import EpubExtractor
from extraction.extractors.configs import EpubExtractorConfig

PARAGRAPHS = [
    'and every one placed the final good<sup><a href="#fnf_1" id="fna_1">298</a></sup> in whatever it appeared.',
    'on account of the excellence of ascetic virtue<span id="cite_ref-3"><a href="#cite_note-3" '
    'style="font-size: 0.75em; vertical-align: super;"><span class="koboSpan">3</span></a></span> and of piety.',
    'These little humiliations are the gifts of God.<a class="char-enref superscript" href="notes.xhtml#en_1">'
    '<span class="smallcaps">20</span></a> Accept them.',
    'every heavy burden becomes light.<span class="superscript"><span class="koboSpan">b</span></span> Then he rests.',
    'He was born on the 21<sup>st</sup> of March and wrote x<sup>n</sup> twice.',
]


def _extract(tmp_path: Path) -> str:
    book = epub.EpubBook()
    book.set_identifier('notes')
    book.set_title('Notes')
    book.set_language('en')
    body = ''.join(f'<p>{p}</p>' for p in PARAGRAPHS)
    chapter = epub.EpubHtml(title='Chapter 1', file_name='chap_01.xhtml', lang='en',
                            content=f'<html><body><h1>Chapter 1</h1>{body}</body></html>')
    book.add_item(chapter)
    book.toc = (epub.Link('chap_01.xhtml', 'Chapter 1', 'chap1'),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = [chapter]
    path = tmp_path / 'notes.epub'
    epub.write_epub(str(path), book)

    extractor = EpubExtractor(str(path), EpubExtractorConfig(min_paragraph_words=1, detect_visual_headings=False,
                                                             filter_tiny_chunks='off'))
    extractor.load()
    extractor.parse()
    return '\n'.join(c.text for c in extractor.chunks)


def test_superscript_note_markers_are_removed(tmp_path):
    text = _extract(tmp_path)

    assert 'the final good in whatever' in text
    assert 'ascetic virtue and of piety' in text
    assert 'gifts of God. Accept them' in text
    assert 'becomes light. Then he rests' in text


def test_superscripts_that_are_not_note_markers_stay(tmp_path):
    text = _extract(tmp_path)

    assert '21st of March' in text
