#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import re
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, NavigableString, Tag

from ..analyzers.base import BaseAnalyzer
from ..analyzers.catholic import CatholicAnalyzer
from ..core.chunking import heading_path, hierarchy_depth, split_sentences
from ..core.extraction import (
    extract_cross_references,
    extract_dates,
    extract_scripture_references,
)
from ..core.identifiers import sha1, stable_id
from ..core.models import Chunk, Metadata
from ..exceptions import DependencyError, ParseError
from .base import BaseExtractor
from .configs import DivineOfficeExtractorConfig

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore[assignment,misc]

LOGGER = logging.getLogger(__name__)

_PARSER_VERSION = "1.0.0"
_MD_SCHEMA_VERSION = "2026-03-31"
_BASE_URL = "https://divineoffice.org/"

ALL_HOURS = [
    "Invitatory",
    "Office of Readings",
    "Morning Prayer",
    "Midmorning Prayer",
    "Midday Prayer",
    "Midafternoon Prayer",
    "Evening Prayer",
    "Night Prayer",
]

_HOUR_URL_SLUGS: Dict[str, str] = {
    "Invitatory": "invitatory",
    "Office of Readings": "office-of-readings",
    "Morning Prayer": "morning-prayer",
    "Midmorning Prayer": "terce",
    "Midday Prayer": "sext",
    "Midafternoon Prayer": "none",
    "Evening Prayer": "evening-prayer",
    "Night Prayer": "night-prayer",
}

_HOUR_TITLE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"invitatory", re.I), "Invitatory"),
    (re.compile(r"office\s+of\s+readings?", re.I), "Office of Readings"),
    (re.compile(r"morning\s+prayer|lauds", re.I), "Morning Prayer"),
    (re.compile(r"midmorning\s+prayer|terce", re.I), "Midmorning Prayer"),
    (re.compile(r"midday\s+prayer|sext", re.I), "Midday Prayer"),
    (re.compile(r"midafternoon\s+prayer|none", re.I), "Midafternoon Prayer"),
    (re.compile(r"evening\s+prayer|vespers", re.I), "Evening Prayer"),
    (re.compile(r"(night\s+prayer|compline)", re.I), "Night Prayer"),
]

_RED_LABEL_TO_CONTENT_TYPE: Dict[re.Pattern, str] = {
    re.compile(r"^hymn$", re.I): "hymn",
    re.compile(r"^psalmody$", re.I): "label",
    re.compile(r"^ant\.\s*\d*", re.I): "antiphon",
    re.compile(r"^ant\.$", re.I): "antiphon",
    re.compile(r"^psalm.prayer$", re.I): "psalm_prayer",
    re.compile(r"^reading\b", re.I): "reading",
    re.compile(r"^sacred\s+silence", re.I): "label",
    re.compile(r"^responsory$", re.I): "label",
    re.compile(r"^canticle\s+of\s+zechariah", re.I): "label",
    re.compile(r"^canticle\s+of\s+simeon", re.I): "label",
    re.compile(r"^canticle\s+of\s+mary", re.I): "label",
    re.compile(r"^canticle\b", re.I): "label",
    re.compile(r"^intercessions?$", re.I): "label",
    re.compile(r"^concluding\s+prayer", re.I): "label",
    re.compile(r"^dismissal$", re.I): "label",
    re.compile(r"^blessing$", re.I): "label",
    re.compile(r"^antiphon\s+or\s+song", re.I): "label",
    re.compile(r"^examination\s+of\s+conscience", re.I): "label",
    re.compile(r"^opening\s+verse", re.I): "versicle",
    re.compile(r"^ribbon\s+placement", re.I): "skip",
    re.compile(r"^(morning|evening|night|midmorning|midday|midafternoon|invitatory|office\s+of\s+readings?)\s+prayer\b", re.I): "label",
    re.compile(r"\bprayer\s+for\s+", re.I): "label",
}

_SKIP_LABELS = {"skip"}

_LITURGICAL_CONTENT_TYPES = {
    "hymn", "antiphon", "psalm", "psalm_prayer", "canticle",
    "reading", "responsory", "versicle", "intercession", "collect",
}

_CLOUDFLARE_TITLES = {"just a moment", "checking your browser", "403 forbidden", "access denied"}

_EMDASH = "\u2014"


class DivineOfficeExtractor(BaseExtractor):

    def __init__(
        self,
        date: str,
        config: Optional[DivineOfficeExtractorConfig] = None,
        analyzer: Optional[BaseAnalyzer] = None,
    ):
        url = f"{_BASE_URL}?date={date}"
        if config is None:
            config = DivineOfficeExtractorConfig(date=date)
        elif not config.date:
            config = DivineOfficeExtractorConfig(
                date=date,
                hours=config.hours,
                playwright_timeout=config.playwright_timeout,
                wait_for_selector=config.wait_for_selector,
                chunking_strategy=config.chunking_strategy,
                min_chunk_words=config.min_chunk_words,
                filter_noise=config.filter_noise,
            )
        super().__init__(url, config, analyzer or CatholicAnalyzer())
        self._soup: Optional[BeautifulSoup] = None
        self._page_title: str = ""
        self._fetched_date: str = date

    def _do_load(self) -> None:
        if sync_playwright is None:
            raise DependencyError(
                "playwright",
                "DivineOfficeExtractor",
                "uv pip install -e '.[scraping]'",
            )

        url = self.source_path
        timeout = self.config.playwright_timeout

        with sync_playwright() as p:
            browser = p.chromium.launch(
                channel="chrome",
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 900},
                locale="en-US",
            )
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = context.new_page()
            page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            page.wait_for_load_state("load", timeout=timeout)
            page.wait_for_timeout(4000)

            if self.config.wait_for_selector:
                try:
                    page.wait_for_selector(self.config.wait_for_selector, timeout=timeout)
                except Exception:
                    LOGGER.warning("wait_for_selector '%s' not found", self.config.wait_for_selector)

            html_content = page.content()
            browser.close()

        html_bytes = html_content.encode("utf-8")
        content_hash = sha1(html_bytes)
        self._set_provenance_url(url, _PARSER_VERSION, _MD_SCHEMA_VERSION, content_hash)

        self._soup = BeautifulSoup(html_bytes, "html.parser")
        title_tag = self._soup.find("title")
        self._page_title = title_tag.get_text(strip=True) if title_tag else ""

        title_lower = self._page_title.lower()
        if any(block in title_lower for block in _CLOUDFLARE_TITLES):
            raise ParseError(
                url,
                f"Request blocked by Cloudflare or server. Page title: '{self._page_title}'",
            )

        LOGGER.info("Loaded Divine Office page: %s", self._page_title)

    def load_from_html(self, html: str, date: str = "") -> None:
        html_bytes = html.encode("utf-8")
        content_hash = sha1(html_bytes)
        self._set_provenance_url(
            self.source_path, _PARSER_VERSION, _MD_SCHEMA_VERSION, content_hash
        )
        self._soup = BeautifulSoup(html_bytes, "html.parser")
        title_tag = self._soup.find("title")
        self._page_title = title_tag.get_text(strip=True) if title_tag else ""
        if date:
            self._fetched_date = date
        from ..state import ExtractorState
        self._BaseExtractor__state = ExtractorState.LOADED  # type: ignore[attr-defined]

    def _do_parse(self) -> None:
        assert self._soup is not None
        hours_to_extract = set(self.config.hours or ALL_HOURS)
        all_text_parts: List[str] = []
        paragraph_counter = 0

        entry_divs = self._soup.find_all("div", class_=lambda c: c and "entry" in c)
        if not entry_divs:
            entry_divs = [self._soup]

        for entry in entry_divs:
            hour_name = self._detect_hour_name(entry)
            if hour_name not in hours_to_extract:
                continue

            chunks_for_entry, texts = self._parse_entry(entry, hour_name, paragraph_counter)
            for chunk in chunks_for_entry:
                self._add_raw_chunk(chunk)
            paragraph_counter += len(chunks_for_entry)
            all_text_parts.extend(texts)

        self._compute_quality(" ".join(all_text_parts))
        self._apply_chunking_strategy()

    def _detect_hour_name(self, entry: Tag) -> str:
        red_spans = entry.find_all("span", style=lambda s: s and "ff0000" in s)
        for span in red_spans:
            text = span.get_text(strip=True)
            for pattern, canonical in _HOUR_TITLE_PATTERNS:
                if pattern.search(text):
                    return canonical

        for tag in entry.find_all(["h1", "h2", "h3", "h4"]):
            text = tag.get_text(strip=True)
            for pattern, canonical in _HOUR_TITLE_PATTERNS:
                if pattern.search(text):
                    return canonical

        page_url = self.source_path.lower()
        for hour, slug in _HOUR_URL_SLUGS.items():
            if slug in page_url:
                return hour

        return "Liturgy of the Hours"

    def _parse_entry(
        self, entry: Tag, hour_name: str, base_counter: int
    ) -> Tuple[List[Chunk], List[str]]:
        chunks: List[Chunk] = []
        texts: List[str] = []
        current_subsection = hour_name
        current_content_type = "prose"
        paragraph_counter = base_counter
        skip_next = False

        doc_id = self.provenance.doc_id

        for p in entry.find_all("p", recursive=True):
            if skip_next:
                skip_next = False
                continue

            psalm_title = _extract_psalm_title(p)
            if psalm_title:
                current_subsection = psalm_title
                current_content_type = "psalm"
                continue

            canticle_ref = _extract_canticle_reference(p)
            if canticle_ref:
                continue

            red_label = _extract_red_label(p)
            if red_label is not None:
                new_type = _classify_red_label(red_label)

                if new_type == "skip":
                    skip_next = True
                    continue

                if new_type == "antiphon":
                    current_content_type = "antiphon"
                elif new_type == "reading":
                    current_subsection = _parse_reading_reference(red_label)
                    current_content_type = "reading"
                    continue
                elif new_type == "psalm_prayer":
                    current_content_type = "psalm_prayer"
                    continue
                elif new_type == "hymn":
                    current_subsection = "Hymn"
                    current_content_type = "hymn"
                    continue
                elif new_type == "versicle":
                    current_content_type = "versicle"
                    continue
                elif new_type == "label":
                    label_upper = red_label.upper()
                    if "RESPONSORY" in label_upper:
                        current_subsection = "Responsory"
                        current_content_type = "responsory"
                    elif "INTERCESSION" in label_upper:
                        current_subsection = "Intercessions"
                        current_content_type = "intercession"
                    elif "CANTICLE OF ZECHARIAH" in label_upper:
                        current_subsection = "Canticle of Zechariah"
                        current_content_type = "canticle"
                    elif "CANTICLE OF SIMEON" in label_upper:
                        current_subsection = "Canticle of Simeon"
                        current_content_type = "canticle"
                    elif "CANTICLE OF MARY" in label_upper:
                        current_subsection = "Canticle of Mary"
                        current_content_type = "canticle"
                    elif "CANTICLE" in label_upper:
                        current_subsection = red_label.title()
                        current_content_type = "canticle"
                    elif "CONCLUDING" in label_upper:
                        current_subsection = "Concluding Prayer"
                        current_content_type = "collect"
                    elif "DISMISSAL" in label_upper:
                        current_subsection = "Dismissal"
                        current_content_type = "prose"
                    elif "BLESSING" in label_upper:
                        current_subsection = "Blessing"
                        current_content_type = "collect"
                    elif "EXAMINATION" in label_upper:
                        current_subsection = "Examination of Conscience"
                        current_content_type = "prose"
                    elif "PSALMODY" in label_upper:
                        current_subsection = "Psalmody"
                        current_content_type = "prose"
                    elif "ANTIPHON OR SONG" in label_upper:
                        continue
                    elif "SACRED SILENCE" in label_upper:
                        continue
                    continue

            text = _clean_paragraph_text(p)
            if not text:
                continue

            word_count = len(text.split())
            paragraph_counter += 1
            sentences = split_sentences(text)
            hierarchy = {
                "level_1": hour_name,
                "level_2": current_subsection,
                "level_3": current_content_type,
                "level_4": "",
                "level_5": "",
                "level_6": "",
            }

            if self.config.words_only and current_content_type not in _LITURGICAL_CONTENT_TYPES:
                continue

            flags: Optional[List[str]] = (
                ["preserve_small_chunk"] if word_count < 10 else None
            )

            chunk = Chunk(
                stable_id=stable_id(doc_id, hour_name, current_content_type, str(paragraph_counter)),
                paragraph_id=paragraph_counter,
                text=text,
                hierarchy=hierarchy,
                chapter_href="",
                source_order=paragraph_counter,
                source_tag="p",
                text_length=len(text),
                word_count=word_count,
                cross_references=extract_cross_references(text),
                scripture_references=extract_scripture_references(text),
                dates_mentioned=extract_dates(text),
                heading_path=heading_path(hierarchy),
                hierarchy_depth=hierarchy_depth(hierarchy),
                doc_stable_id=doc_id,
                sentence_count=len(sentences),
                sentences=sentences,
                normalized_text=text.lower(),
                content_type=current_content_type,
                quality_flags=flags,
            )
            chunks.append(chunk)
            texts.append(text)

        return chunks, texts

    def _do_extract_metadata(self) -> Metadata:
        date_str = self._fetched_date
        if len(date_str) == 8:
            formatted_date = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
        else:
            formatted_date = date_str

        title = self._page_title or f"Liturgy of the Hours — {formatted_date}"
        total_words = sum(c.word_count for c in self.chunks)
        self._formatted_date = formatted_date

        return Metadata(
            title=title,
            author="divineoffice.org",
            language="en",
            publisher="divineoffice.org",
            date_promulgated=formatted_date,
            word_count=str(total_words),
            source_identifiers={"url": self.source_path, "date": date_str},
        )

    def extract_metadata(self):
        meta = super().extract_metadata()
        if not meta.date_promulgated and hasattr(self, "_formatted_date"):
            meta.date_promulgated = self._formatted_date
        return meta


def _extract_red_label(p: Tag) -> Optional[str]:
    first = next(
        (c for c in p.children if not isinstance(c, NavigableString) or c.strip()),
        None,
    )
    if first is None:
        return None
    if isinstance(first, NavigableString):
        return None
    if first.name == "span":
        style = first.get("style") or ""
        if "ff0000" in style.lower():
            label = first.get_text(strip=True).rstrip(":")
            if not label or label == _EMDASH or label == "\u2014":
                return None
            trailing = "".join(
                str(c) for c in first.next_siblings
                if isinstance(c, NavigableString)
            ).strip()
            if trailing:
                return f"{label} {trailing}"
            return label
    return None


def _classify_red_label(label: str) -> str:
    for pattern, ct in _RED_LABEL_TO_CONTENT_TYPE.items():
        if pattern.match(label):
            return ct
    return "prose"


def _extract_psalm_title(p: Tag) -> Optional[str]:
    style = p.get("style") or ""
    if "text-align" not in style:
        return None
    red_spans = p.find_all("span", style=lambda s: s and "ff0000" in s)
    if not red_spans:
        return None
    title_text = red_spans[0].get_text(separator="\n", strip=True)
    first_line = title_text.split("\n")[0].strip()
    if re.match(r"^(psalm\s+[\d:]+|canticle|isaiah|zechariah|luke|revelation)", first_line, re.I):
        return first_line
    return None


def _extract_canticle_reference(p: Tag) -> bool:
    red_spans = p.find_all("span", style=lambda s: s and "ff0000" in s)
    if not red_spans:
        return False
    first = red_spans[0]
    text = first.get_text(strip=True)
    if re.match(r"^(luke|john|revelation|isaiah|philippians|ephesians|colossians)\s+\d+", text, re.I):
        return True
    return False


def _parse_reading_reference(label: str) -> str:
    m = re.match(r"^reading\s+(.+)$", label, re.I)
    if m:
        return f"Reading: {m.group(1).strip()}"
    return "Reading"


def _clean_paragraph_text(p: Tag) -> str:
    parts: List[str] = []
    for child in p.descendants:
        if isinstance(child, NavigableString):
            t = str(child)
            if t.strip():
                parts.append(t)
    text = " ".join(parts)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("\u2014", "—")
    return text
