"""Vatican HTML cleaning: notes, site chrome and tables of contents never reach a chunk.

Fixtures are real vatican.va pages saved 2026-10-02. Dilexit nos marks notes with
`_ftn` anchors; Lumen Gentium uses a NOTES heading followed by one paragraph per note.
"""

import re
from collections import Counter
from pathlib import Path

import pytest

from extraction.extractors.configs import HtmlExtractorConfig
from extraction.extractors.html import HtmlExtractor
from extraction.pipelines.vatican.cleaning import clean_vatican_soup

FIXTURES = Path(__file__).parent / "fixtures" / "vatican"
DILEXIT = FIXTURES / "francis_dilexit_nos_24_october_2024_434014ae.html"
LUMEN = FIXTURES / "vatican_ii_lumen_gentium_126e15e5.html"
ACERBO = FIXTURES / "pius_x_acerbo_nimis_april_15_1905_b6b9a7aa.html"
MARIALIS = FIXTURES / "paul_vi_marialis_cultus_february_2_1974_a5dcb230.html"
GAUDETE = FIXTURES / "francis_gaudete_et_exsultate_apostolic_exhortation_3c07f0f1.html"
VERBUM = FIXTURES / "benedict_xvi_verbum_domini_post_synodal_apostolic__dc4e08c4.html"

# Body paragraphs are numbered "12. ...". Some Lumen Gentium notes are too ("17. Rev. 22:17"),
# but none reaches 200 chars, so number + length counts body paragraphs only.
BODY_PARAGRAPH_RE = re.compile(r"^\d+\.\s.{200}", re.S)
TOC_RANGE_RE = re.compile(r"\[\d+\s*[-–]\s*\d+\]")


def _extract(path: Path, cleaner):
    extractor = HtmlExtractor(str(path), HtmlExtractorConfig(), soup_cleaner=cleaner)
    extractor.load()
    extractor.parse()
    raw = [c.text for c in extractor._BaseExtractor__raw_chunks]
    return raw, [c.text for c in extractor.chunks]


def _notes(path: Path) -> list[str]:
    raw, _ = _extract(path, None)
    kept, _ = _extract(path, clean_vatican_soup)
    if path == DILEXIT:
        return [t for t in raw if re.match(r"^\[\d+\]", t)]
    start = raw.index("NOTES")
    return [t for t in raw[start + 1:] if len(t) > 20 and t not in set(kept)]


@pytest.mark.parametrize("page", [DILEXIT, LUMEN], ids=["ftn-anchors", "notes-heading"])
def test_no_chunk_contains_a_note(page):
    notes = _notes(page)
    _, chunks = _extract(page, clean_vatican_soup)

    assert len(notes) > 100
    leaked = [n for n in notes for c in chunks if n in c]
    assert leaked == []


@pytest.mark.parametrize("page", [DILEXIT, LUMEN], ids=["ftn-anchors", "notes-heading"])
def test_body_paragraph_count_unchanged(page):
    before, _ = _extract(page, None)
    after, _ = _extract(page, clean_vatican_soup)

    body_before = [t for t in before if BODY_PARAGRAPH_RE.match(t)]
    body_after = [t for t in after if BODY_PARAGRAPH_RE.match(t)]
    assert len(body_after) == len(body_before) > 50


def test_inline_note_markers_stay_in_body():
    _, chunks = _extract(DILEXIT, clean_vatican_soup)

    assert any(re.search(r"\[\d+\]", c) for c in chunks)


@pytest.mark.parametrize("page", [ACERBO, LUMEN, MARIALIS, DILEXIT])
def test_first_chunk_is_document_text_not_chrome(page):
    _, chunks = _extract(page, clean_vatican_soup)

    first = chunks[0]
    assert not re.search(r"\b[A-Z]{2} - [A-Z]{2}\b", first)
    assert not re.match(r"^A( ?A)*\b", first)


def test_acerbo_nimis_first_chunk_starts_with_title():
    _, chunks = _extract(ACERBO, clean_vatican_soup)

    assert chunks[0].startswith("ACERBO NIMIS")


@pytest.mark.parametrize("page", [GAUDETE, VERBUM])
def test_toc_is_dropped(page):
    _, before = _extract(page, None)
    _, after = _extract(page, clean_vatican_soup)

    assert any(len(TOC_RANGE_RE.findall(c)) >= 3 for c in before)
    assert not any(len(TOC_RANGE_RE.findall(c)) >= 3 for c in after)


def test_wrapper_divs_do_not_repeat_the_document():
    raw, _ = _extract(MARIALIS, clean_vatican_soup)

    counts = Counter(t for t in raw if len(t) > 200)
    assert max(counts.values()) == 1
    assert max(len(t) for t in raw) < 10_000


def test_footnote_reference_anchor_is_not_a_note(tmp_path):
    page = tmp_path / "p.html"
    page.write_text(
        "<html><body>"
        '<p>Body text that cites a source.<a name="_ftnref1" href="#_ftn1">[1]</a></p>'
        '<p><a name="_ftn1" href="#_ftnref1">[1]</a> Cf. Lumen Gentium, 1.</p>'
        "</body></html>"
    )

    raw, _ = _extract(page, clean_vatican_soup)

    assert raw == ["Body text that cites a source. [1]"]


@pytest.mark.parametrize(
    "body",
    [
        '1. The opening paragraph of the body cites a note. [1]',
        'The opening paragraph of the body cites a note.<a name="_ftnref1" href="#_ftn1">[1]</a>',
    ],
    ids=["numbered", "footnote-link"],
)
def test_toc_run_stops_at_body_paragraph_ending_in_note_marker(tmp_path, body):
    page = tmp_path / "p.html"
    page.write_text(
        "<html><body>"
        "<p><b>INDEX</b></p>"
        '<p><a href="#INTRO">Introduction</a> [1-2]</p>'
        f"<p>{body}</p>"
        "</body></html>"
    )

    raw, _ = _extract(page, clean_vatican_soup)

    assert len(raw) == 1 and raw[0].startswith(("1. The opening", "The opening"))
