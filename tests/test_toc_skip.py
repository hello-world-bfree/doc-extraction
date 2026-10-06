"""Contents and index sections are skipped at any hierarchy level, and only within their own spine document.

A contents heading that stuck to later documents once dropped 99% of a book (The Case for Jesus).
"""

from ebooklib import epub

from extraction.core.strategies import get_strategy, ChunkConfig
from extraction.extractors import EpubExtractor
from extraction.extractors.configs import EpubExtractorConfig

CHAPTER_TEXT = 'In the beginning the author sets out why the question of the historical Jesus matters to every reader.'
INDEX_TEXT = 'Abraham, 12, 45, 101; Adam, 3, 77; Augustine, 15, 230, 231; Babylon, 88, 90'


def _epub(tmp_path, docs, toc_titles):
    book = epub.EpubBook()
    book.set_identifier('toc-skip')
    book.set_title('TOC skip')
    book.set_language('en')
    items = []
    for name, body in docs:
        item = epub.EpubHtml(title=name, file_name=f'{name}.xhtml', lang='en',
                             content=f'<html><body>{body}</body></html>')
        book.add_item(item)
        items.append(item)
    book.toc = tuple(epub.Link(f'{name}.xhtml', title, name) for name, title in toc_titles)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = items
    path = tmp_path / 'book.epub'
    epub.write_epub(str(path), book)
    return path


def _chunk_texts(path, **overrides):
    settings = dict(min_paragraph_words=1, min_block_words=2, detect_visual_headings=False,
                    filter_tiny_chunks='off', filter_noise=False, chunking_strategy='rag')
    settings.update(overrides)
    extractor = EpubExtractor(str(path), EpubExtractorConfig(**settings))
    extractor.load()
    extractor.parse()
    return '\n'.join(c.text for c in extractor.chunks)


def test_strategy_skips_index_below_level_1():
    unit = {'paragraph_id': 1, 'text': INDEX_TEXT, 'word_count': 14, 'sentences': [INDEX_TEXT],
            'hierarchy': {'level_1': 'Volume II', 'level_2': 'Index'}}

    assert get_strategy('rag').apply([unit], ChunkConfig(min_words=1)) == []


def _units(level_1, count, words_each, start_id):
    text = ' '.join(['word'] * words_each)
    return [{'paragraph_id': start_id + i, 'text': text, 'word_count': words_each, 'sentences': [text],
             'hierarchy': {'level_1': level_1}} for i in range(count)]


def test_large_index_in_large_book_is_skipped():
    """A 5,000-word index passes the word cap but is 5% of the book: navigation, not a mislabeled body."""
    units = _units('Chapter One', 1900, 50, 1) + _units('Index', 100, 50, 10_000)

    result = get_strategy('rag').apply(units, ChunkConfig(min_words=1))

    assert result
    assert all(c['hierarchy'].get('level_1') != 'Index' for c in result)


def test_index_skipped_with_toc_hierarchy_level_2(tmp_path):
    path = _epub(tmp_path,
                 [('chap', f'<p>{CHAPTER_TEXT}</p>'), ('index', f'<p>{INDEX_TEXT}</p>')],
                 [('chap', 'Chapter One'), ('index', 'Index')])

    text = _chunk_texts(path, toc_hierarchy_level=2)

    assert CHAPTER_TEXT in text
    assert 'Augustine, 15' not in text


def test_body_chapter_after_contents_is_emitted(tmp_path):
    path = _epub(tmp_path,
                 [('fm02', '<p>Chapter One ... 1</p><p>Chapter Two ... 19</p>'),
                  ('chap1', f'<h2>The Beginning</h2><p>{CHAPTER_TEXT}</p>')],
                 [('fm02', 'Contents')])

    text = _chunk_texts(path)

    assert CHAPTER_TEXT in text
    assert 'Chapter Two ... 19' not in text
