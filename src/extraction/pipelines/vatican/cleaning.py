"""
Removes vatican.va elements that are not document body text: site chrome,
footnote/endnote blocks and tables of contents.

Applied to the parsed tree before HtmlExtractor walks it, so these elements
never reach a chunk.
"""

import re

from bs4 import BeautifulSoup, Tag

CHROME_SELECTORS = ("div.va-tools", "div.translation-field")

_LANG = r"[A-Z]{2}(?:_[A-Z]{2})?"
_LANGUAGE_SWITCHER_RE = re.compile(rf"^\[?\s*{_LANG}(?:\s*-\s*{_LANG})+\s*\]?$")
_FTN_NAME_RE = re.compile(r"^_ftn\d+$")
_NOTES_HEADINGS = {"notes", "footnotes"}
_TOC_HEADINGS = {"index", "contents", "table of contents"}
_TRAILING_PARAGRAPH_REF_RE = re.compile(r"\[\d+(?:\s*[-–]\s*\d+)?\]\s*$")
_NUMBERED_PARAGRAPH_RE = re.compile(r"^\d+\.\s")
_HEADING_TAGS = ("p", "h1", "h2", "h3", "h4", "h5", "h6")


def clean_vatican_soup(soup: BeautifulSoup) -> None:
    for selector in CHROME_SELECTORS:
        for el in soup.select(selector):
            el.decompose()
    _drop_language_switchers(soup)
    _drop_anchored_notes(soup)
    _drop_notes_sections(soup)
    _drop_tocs(soup)


def _drop_language_switchers(soup: BeautifulSoup) -> None:
    # Older pages carry the switcher as a plain <p>[AR - BE - ... - ZH]</p> of language links.
    for el in soup.find_all(["p", "div"]):
        if not el.decomposed and _LANGUAGE_SWITCHER_RE.match(el.get_text(" ", strip=True)):
            el.decompose()


def _drop_anchored_notes(soup: BeautifulSoup) -> None:
    # Modern pages: each note paragraph opens with <a name="_ftnN" href="#_ftnrefN">.
    # The in-body markers are <a name="_ftnrefN">, which this pattern does not match.
    for anchor in soup.find_all("a", attrs={"name": _FTN_NAME_RE}):
        if anchor.decomposed:
            continue
        paragraph = anchor.find_parent("p")
        if paragraph is not None:
            paragraph.decompose()


def _headings(soup: BeautifulSoup, names: set[str]) -> list[Tag]:
    return [
        el for el in soup.find_all(_HEADING_TAGS)
        if el.get_text(" ", strip=True).lower() in names
    ]


def _drop_notes_sections(soup: BeautifulSoup) -> None:
    # Older pages: a <p><b>NOTES</b></p> heading, then one paragraph per note to the
    # end of the document container.
    for heading in _headings(soup, _NOTES_HEADINGS):
        if heading.decomposed:
            continue
        for sibling in heading.find_next_siblings():
            sibling.decompose()
        heading.decompose()


def _is_toc_entry(el: Tag) -> bool:
    text = el.get_text(" ", strip=True)
    if not text:
        return True
    # Body paragraphs are numbered and often end in a note marker such as "[1]", which
    # would otherwise read as a TOC entry's paragraph reference.
    links = [a["href"] for a in el.find_all("a", href=True)]
    if _NUMBERED_PARAGRAPH_RE.match(text) or any(h.startswith("#_ftn") for h in links):
        return False
    if _TRAILING_PARAGRAPH_REF_RE.search(text):
        return True
    return any(h.startswith("#") for h in links)


def _drop_tocs(soup: BeautifulSoup) -> None:
    for heading in _headings(soup, _TOC_HEADINGS):
        if heading.decomposed:
            continue
        for sibling in heading.find_next_siblings():
            if not _is_toc_entry(sibling):
                break
            sibling.decompose()
        heading.decompose()
