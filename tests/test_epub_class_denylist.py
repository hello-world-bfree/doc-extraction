"""class_denylist matches individual class names, whichever parser read the spine document."""

import pytest
from bs4 import BeautifulSoup

from test_epub_nested_duplication import PROSE, _extract, _raw_units

NOTE = 'See Augustine, Confessions 10.27, for the source of this phrase.'


def test_denylisted_class_token_excludes_element(tmp_path):
    units = _raw_units(
        tmp_path,
        f'<p class="index-scripture entry">Genesis 1:27, 12, 45, 101, and 230 onward</p><p>{PROSE}</p>',
        class_denylist=r'^index-scripture$',
    )
    texts = [u['text'] for u in units]

    assert PROSE in texts
    assert not any('Genesis 1:27' in t for t in texts)


def test_calibre_body_paragraph_kept_under_default_denylist(tmp_path):
    """calibre gives body paragraphs classes like calibre14; denying them would drop whole books."""
    units = _raw_units(tmp_path, f'<p class="calibre14">{PROSE}</p>')

    assert [u['text'] for u in units] == [PROSE]


def test_denied_container_excludes_its_children_and_records_text(tmp_path):
    """Coverage subtracts denied text, so the extractor must report what the denylist removed."""
    extractor = _extract(tmp_path, f'<div class="note"><p>{NOTE}</p></div><p>{PROSE}</p>')
    texts = [u['text'] for u in extractor._get_raw_chunks()]

    assert texts == [PROSE]
    assert [d['text'] for d in extractor.unit_report['dropped'] if d['stage'] == 'class_denylist'] == [NOTE]


@pytest.mark.parametrize('parser', ['lxml-xml', 'lxml'])
def test_class_tokens_matched_for_xml_and_html_parsers(tmp_path, parser):
    """lxml-xml leaves class as one string; matching it unsplit made every denylist a no-op."""
    from extraction.extractors import EpubExtractor
    from extraction.extractors.configs import EpubExtractorConfig

    _raw_units(tmp_path, f'<p>{PROSE}</p>')
    extractor = EpubExtractor(str(tmp_path / 'synthetic.epub'), EpubExtractorConfig())
    soup = BeautifulSoup('<html><body><p class="calibre3 footnote">x</p><p class="calibre3">y</p></body></html>', parser)
    denied, kept = soup.find_all('p')

    assert extractor._class_denied(denied)
    assert not extractor._class_denied(kept)
