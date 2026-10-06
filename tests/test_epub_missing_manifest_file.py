"""A manifest item whose file is absent from the archive.

Kobo injects `js/kobo.js` into some manifests at a path where the file is not stored. A
missing script must not refuse the book; a missing document must, or its text is lost silently.
"""

import zipfile
from pathlib import Path

import pytest
from ebooklib import epub

from extraction.exceptions import ParseError
from extraction.extractors import EpubExtractor
from extraction.extractors.configs import EpubExtractorConfig

PROSE = 'The author then turns from the beatitudes to the parable that follows them.'


def _epub_with_manifest_gap(tmp_path: Path, *, drop: str | None = None, add_item: str | None = None) -> Path:
    book = epub.EpubBook()
    book.set_identifier('synthetic')
    book.set_title('Synthetic')
    book.set_language('en')
    chapter = epub.EpubHtml(title='Chapter 1', file_name='chap_01.xhtml', lang='en',
                            content=f'<html><body><h1>Chapter 1</h1><p>{PROSE}</p></body></html>')
    book.add_item(chapter)
    book.toc = (epub.Link('chap_01.xhtml', 'Chapter 1', 'chap1'),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = [chapter]
    built = tmp_path / 'built.epub'
    epub.write_epub(str(built), book)

    path = tmp_path / 'gap.epub'
    with zipfile.ZipFile(built) as src, zipfile.ZipFile(path, 'w') as dst:
        for info in src.infolist():
            if drop and info.filename.endswith(drop):
                continue
            data = src.read(info)
            if add_item and info.filename.endswith('.opf'):
                data = data.replace(b'</manifest>', add_item.encode() + b'</manifest>')
            dst.writestr(info, data)
    return path


def _extract(path: Path) -> EpubExtractor:
    extractor = EpubExtractor(str(path), EpubExtractorConfig(min_paragraph_words=1, detect_visual_headings=False,
                                                             filter_tiny_chunks='off'))
    extractor.load()
    extractor.parse()
    return extractor


def test_missing_script_file_does_not_refuse_the_book(tmp_path):
    path = _epub_with_manifest_gap(
        tmp_path, add_item='<item id="js-kobo.js" href="js/kobo.js" media-type="application/javascript"/>')

    extractor = _extract(path)

    assert any(PROSE in c.text for c in extractor.chunks)


def test_missing_document_still_fails_the_book(tmp_path):
    path = _epub_with_manifest_gap(tmp_path, drop='chap_01.xhtml')

    with pytest.raises(ParseError, match='chap_01.xhtml'):
        _extract(path)
