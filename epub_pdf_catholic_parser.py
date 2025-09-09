#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os
import sys
import re
import json
import hashlib
import logging
import unicodedata
import statistics as stats
from collections import OrderedDict, defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from tqdm import tqdm
from bs4 import BeautifulSoup

# Optional: EPUB dependencies
try:
    import ebooklib
    from ebooklib import epub
    EPUB_AVAILABLE = True
except Exception:
    EPUB_AVAILABLE = False

# Optional: PDF dependencies
try:
    import PyPDF2
    PDF_PYPDF2 = True
except Exception:
    PDF_PYPDF2 = False

try:
    import pdfplumber
    PDF_PLUMBER = True
except Exception:
    PDF_PLUMBER = False

# Optional: PDF rendering and OCR
try:
    import pypdfium2 as pdfium
    PDF_RENDER = True
except Exception:
    PDF_RENDER = False

try:
    import pytesseract
    from pytesseract import Output as TesseractOutput
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False


# Versioning
PARSER_VERSION = "1.6.0-catholic-pdf-ocr"
MD_SCHEMA_VERSION = "2025-09-08"

# Logger setup
LOGGER = logging.getLogger("rag_parser")


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure logging level based on CLI flags."""
    level = logging.INFO
    if verbose:
        level = logging.DEBUG
    if quiet:
        level = logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# Predefined month patterns for date extraction
MONTHS = (
    r'Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)|Apr(?:il)|May|Jun(?:e)|'
    r'Jul(?:y)|Aug(?:ust)|Sep(?:t\.|tember)|Oct(?:ober)|Nov(?:ember)|Dec(?:ember)'
)

# Unicode characters to normalize away
SOFT_HYPHEN = "\u00ad"
ZW_SPACES = r"[\u200B-\u200D\u2060\uFEFF]"


# Utility functions

def sha1(x: bytes) -> str:
    """Return SHA-1 hash of input bytes as a hex string."""
    return hashlib.sha1(x).hexdigest()


def stable_id(*parts: str) -> str:
    """Create a stable ID by hashing joined parts. Shorten to 16 hex chars."""
    return hashlib.sha1("||".join(parts).encode("utf-8")).hexdigest()[:16]


def normalize_spaced_caps(s: str) -> str:
    """Fix spaced small-caps artifacts (e.g. "S E C O N D" → "SECOND")."""
    if not s:
        return s
    # A) "S E C O N D" → "SECOND"
    s = re.sub(r'\b(?:[A-Z]\s){2,}[A-Z]\b', lambda m: m.group(0).replace(' ', ''), s)
    # B) "P RODIGAL" → "PRODIGAL"
    s = re.sub(r'\b([A-Z])\s(?=[A-Z][a-z])', r'\1', s)
    # C) "S ON" → "SON"
    s = re.sub(r'\b([A-Z])\s(?=[A-Z]{2,}\b)', r'\1', s)
    return s


def clean_text(s: str) -> str:
    """Normalize text: remove soft hyphens, zero-width spaces, collapse spaces,
    tighten punctuation spacing, and fix spaced-caps artifacts."""
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    # Remove soft hyphen and zero-width spaces
    s = s.replace(SOFT_HYPHEN, "")
    s = re.sub(ZW_SPACES, "", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    s = s.replace("\u00a0", " ").strip()
    # Tighten punctuation spacing
    s = re.sub(r'(\b\d+)\s+\.', r'\1.', s)
    s = re.sub(r'\s+([,;:!?])', r'\1', s)
    s = re.sub(r'\s+([.\"’)\]\}])', r'\1', s)
    s = re.sub(r'([([“‘])\s+', r'\1', s)
    # Fix small-caps artifacts
    s = normalize_spaced_caps(s)
    return s


def estimate_word_count(text: str) -> int:
    """Estimate number of words in text by splitting on whitespace."""
    return len(text.split()) if text else 0


def heading_level(tag_name: str) -> int:
    """Return integer level if tag is h1-h6; else 99."""
    if tag_name and tag_name.lower().startswith("h"):
        try:
            return int(tag_name[1])
        except (ValueError, IndexError):
            return 99
    return 99


def is_heading_tag(tag_name: str) -> bool:
    """Check if tag is one of h1-h6."""
    return tag_name in {f"h{i}" for i in range(1, 7)}


def clean_toc_title(s: str) -> str:
    """Clean TOC titles by stripping leading numbers/ordinals."""
    if not s:
        return s
    s = clean_text(s)
    # Remove "Chapter 5:" etc.
    s = re.sub(r'^\s*(?:chapter|chap\.?)\s*\d+\s*[:.\-–—]\s*', '', s, flags=re.I)
    # Remove "1.", "1)", "I.", etc.
    s = re.sub(r'^\s*(?:\d+|[IVXLC]+)\s*[.\)\-–—]\s*', '', s, flags=re.I)
    # Remove bare leading numbers and spaces
    s = re.sub(r'^\s*\d+\s+', '', s)
    return s


def _heading_path(h: Dict[str, str]) -> str:
    """Join non-empty hierarchy levels into a path string."""
    parts = [h.get(f"level_{i}", "") for i in range(1, 7)]
    return " / ".join([p for p in parts if p])


def _hier_depth(h: Dict[str, str]) -> int:
    """Return deepest non-empty level index."""
    for i in range(6, 0, -1):
        if h.get(f"level_{i}"):
            return i
    return 0


def _split_sents(t: str) -> List[str]:
    """Simple sentence splitter based on punctuation boundaries.

    This uses a regex that looks behind for sentence-ending punctuation and
    ahead for an uppercase letter or opening quote/parenthesis. Quotes are
    escaped appropriately within the regex string.
    """
    # We use double quotes to avoid interfering with single quotes inside the pattern
    sents = re.split(r"(?<=[.!?])\s+(?=[A-Z“\"'\(])", t)
    return [s for s in sents if s.strip()]


def _normalize_ascii(t: str) -> str:
    """Return ASCII-normalized version of string."""
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode("ascii")


# Cross-reference and date extraction

def extract_dates(text: str) -> List[str]:
    """Extract various date formats from text."""
    patterns = [
        rf'\b(?:{MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?\,?\s+\d{{4}}\b',
        rf'\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})\s+\d{{4}}\b',
        r'\b\d{4}-\d{2}-\d{2}\b',
        r'\b\d{1,2}/\d{1,2}/\d{4}\b',
    ]
    out: List[str] = []
    for pat in patterns:
        out.extend(re.findall(pat, text, flags=re.IGNORECASE))
    return sorted(set(clean_text(x) for x in out))


# Regex to identify lines containing scripture or CCC references
SCRIPTURE_OR_CCC_LINE_RE = re.compile(
    r'\b(?:CCC|Catechism|Gen|Ex|Lev|Num|Deut|Josh|Judg|Ruth|Sam|Kgs|Chr|Ezra|Neh|Esth|Job|Ps|Prov|Eccl|Song|Isa|Jer|Lam|Ezek|Dan|Hos|Joel|Amos|Obad|Jonah|Mic|Nah|Hab|Zeph|Hag|Zech|Mal|Mt|Mk|Lk|Jn|Acts|Rom|Cor|Gal|Eph|Phil|Col|Thess|Tim|Tit|Phlm|Heb|Jas|Pet|Jude|Rev)\b',
    re.IGNORECASE
)


def extract_scripture_references(text: str) -> List[str]:
    """Extract scripture references, e.g., 'John 3:16-17'."""
    patterns = [
        r'\b(?:[1-3]\s*)?[A-Z][a-z]+\.?\s+\d+:\d+(?:-\d+(?::\d+)?)?',  # John 3:16-18
        r'\b(?:[1-3]\s*)?(?:Kings?|Chronicles?|Corinthians?|Thessalonians?|Timothy|Peter|John)\s+\d+:\d+(?:-\d+)?',
        r'\b(?:Gen|Ex|Lev|Num|Deut|Josh|Judg|Ruth|Sam|Kgs|Chr|Ezra|Neh|Esth|Job|Ps|Prov|Eccl|Song|Isa|Jer|Lam|Ezek|Dan|Hos|Joel|Amos|Obad|Jonah|Mic|Nah|Hab|Zeph|Hag|Zech|Mal|Mt|Mk|Lk|Jn|Acts|Rom|Cor|Gal|Eph|Phil|Col|Thess|Tim|Tit|Phlm|Heb|Jas|Pet|Jude|Rev)\.?\s+\d+:\d+(?:-\d+)?'
    ]
    refs: List[str] = []
    for pat in patterns:
        refs.extend(re.findall(pat, text, flags=re.IGNORECASE))
    return sorted(set(clean_text(r) for r in refs))


def extract_cross_references(text: str) -> List[str]:
    """Extract Catholic-focused cross references from text."""
    SEE_MAX = 140
    patterns = [
        r'\b(?:cf\.|compare|see(?: also)?)\s+(?:chapter|section|part|§|art\.?|can\.?)\s+[A-Za-z0-9.:§-]{1,60}',
        r'\b(?:CIC|CCEO)\s*(?:/1983|/1990)?\s*(?:can\.?|canon)\s*\d+(?:\s*§\s*\d+)?',
        r'\b(?:canon|can\.)\s*\d+(?:\s*§\s*\d+)?',
        r'\b(?:CCC|Catechism(?: of the Catholic Church)?)\s*\d{1,4}',
        r'\b(?:DS|Denz\.?)\s*\d{3,5}\b',
        r'\b(?:GIRM|GILH|IGMR|OGMR)\s*\d{1,4}\b',
        r'\b(?:Council of Trent|Trent(?:,?\s*Session)?\s*[IVXLC]+)\b',
        r'\b(?:Vatican\s*(?:I|II))\b',
        r'\b§{1,2}\s*\d{1,4}\b',
    ]
    refs: List[str] = []
    for pat in patterns:
        for m in re.findall(pat, text, flags=re.IGNORECASE):
            m = clean_text(m)
            if 3 < len(m) <= SEE_MAX:
                refs.append(m)
    return sorted(set(refs))


# Footnote handling

FOOTNOTE_ENUM_RE = re.compile(r'^\s*(\d{1,3})[.)]\s+(.*\S)\s*$')


def sentence_final_footnote_numbers(text: str) -> List[int]:
    """Detect footnote numbers at the end of sentences.

    Matches numbers at sentence boundaries (like '(10)' or '... 10.') but avoids
    numbers preceded by letters (e.g. 'CCC 2309').
    """
    nums: List[int] = []
    for sent in _split_sents(text):
        s = sent.strip()
        m = re.search(r'(?<![A-Za-z])(\d{1,3})\s*[)"’\]]*[.!?]?\s*$', s)
        if m:
            try:
                n = int(m.group(1))
                if 1 <= n <= 999:
                    nums.append(n)
            except Exception:
                pass
    # Remove duplicates while preserving order
    seen, out = set(), []
    for n in nums:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def harvest_enumerated_footnotes_from_text_lines(lines: List[str]) -> Dict[int, str]:
    """Harvest enumerated notes (e.g. '1. text') from a list of lines."""
    footnotes: Dict[int, str] = {}
    for raw in lines:
        line = clean_text(raw)
        m = FOOTNOTE_ENUM_RE.match(line)
        if not m:
            continue
        try:
            idx = int(m.group(1))
            body = m.group(2).strip()
            if 1 <= idx <= 999 and len(body) >= 3:
                prev = footnotes.get(idx, "")
                # Prefer the longest version if duplicates exist
                if len(body) > len(prev):
                    footnotes[idx] = body
        except Exception:
            pass
    return footnotes


# Quality scoring and routing

def quality_signals_from_text(text: str) -> Dict[str, float]:
    """Compute quality signals for given text."""
    if not text:
        return {"garble_rate": 1.0, "mean_conf": 0.0, "line_len_std_norm": 1.0, "lang_prob": 0.0}
    weird = len(re.findall(r"[^\x09\x0A\x0D\x20-\x7E\u00A0-\u02AF]", text))
    garble_rate = min(1.0, weird / max(1, len(text)))
    mean_conf = max(0.0, 1.0 - garble_rate) * (1.0 if len(text) > 2000 else 0.8)
    lines = [len(l) for l in text.splitlines() if l.strip()]
    line_len_std_norm = min(1.0, (stats.pstdev(lines) if lines else 24) / 120.0)
    latin_hits = len(re.findall(r'\b(Dei|Ecclesia|Dominus|Verbum|Magisterium|Apostolica)\b', text))
    lang_prob = min(1.0, 0.5 + 0.05 * latin_hits)
    return {
        "garble_rate": float(garble_rate),
        "mean_conf": float(mean_conf),
        "line_len_std_norm": float(line_len_std_norm),
        "lang_prob": float(lang_prob),
    }


def score_quality(signals: Dict[str, float]) -> float:
    """Compute a weighted quality score from signals."""
    return float(
        0.40 * (1 - signals.get("garble_rate", 0.0)) +
        0.30 * signals.get("mean_conf", 0.0) +
        0.10 * (1 - signals.get("line_len_std_norm", 0.0)) +
        0.20 * signals.get("lang_prob", 0.0)
    )


def route_doc(score: float) -> str:
    """Route document based on quality score."""
    if score >= 0.80:
        return "A"
    if score >= 0.55:
        return "B"
    return "C"


# Metadata extraction class

class MetadataExtractor:
    """Extract document-level metadata and summarise footnote stats."""
    def __init__(self, href_to_toc_title: Optional[Dict[str, str]] = None):
        self.href_to_toc_title = href_to_toc_title or {}
        self.metadata: Dict[str, Any] = {
            "title": "",
            "author": "",
            "document_type": "",
            "date_promulgated": "",
            "subject": [],
            "key_themes": [],
            "related_documents": [],
            "time_period": "",
            "geographic_focus": "",
            "language": "",
            "publisher": "",
            "pages": "",
            "word_count": "",
            "source_identifiers": {"toc_map": self.href_to_toc_title},
            "md_schema_version": MD_SCHEMA_VERSION,
            "footnotes_index": {},
            "footnote_index_count": 0,
            "footnote_citation_stats": {"unique_citations": [], "citation_frequency": {}},
        }

    def extract_from_epub(self, book: "epub.EpubBook", chunks: List[Dict]) -> Dict[str, Any]:
        """Extract metadata for EPUB files using ebooklib API."""
        try:
            self.metadata["title"] = clean_text(book.get_metadata("DC", "title")[0][0] if book.get_metadata("DC", "title") else "")
            self.metadata["author"] = clean_text(book.get_metadata("DC", "creator")[0][0] if book.get_metadata("DC", "creator") else "")
            self.metadata["language"] = clean_text(book.get_metadata("DC", "language")[0][0] if book.get_metadata("DC", "language") else "")
            self.metadata["publisher"] = clean_text(book.get_metadata("DC", "publisher")[0][0] if book.get_metadata("DC", "publisher") else "")
        except Exception:
            pass
        all_text = " ".join(ch["text"] for ch in chunks)
        self._infer_document_type(all_text)
        self._extract_dates(all_text)
        self._extract_subjects_and_themes(all_text, chunks)
        self._extract_related_documents(all_text)
        self._infer_geographic_focus(all_text)
        self._calculate_stats(chunks)
        return self.metadata

    def extract_minimal(self, chunks: List[Dict]) -> Dict[str, Any]:
        """Minimal metadata extraction for PDF or fallback when EPUB metadata is unavailable."""
        all_text = " ".join(ch["text"] for ch in chunks)
        self._infer_document_type(all_text)
        self._extract_dates(all_text)
        self._extract_subjects_and_themes(all_text, chunks)
        self._extract_related_documents(all_text)
        self._infer_geographic_focus(all_text)
        self._calculate_stats(chunks)
        return self.metadata

    def _infer_document_type(self, text: str):
        doc_type_patterns = {
            "Dogmatic Constitution": [r"\bdogmatic constitution\b", r"constitutio dogmatica"],
            "Pastoral Constitution": [r"\bpastoral constitution\b", r"constitutio pastoralis"],
            "Apostolic Constitution": [r"apostolic constitution", r"constitutio apostolica"],
            "Encyclical": [r"\bencyclical\b", r"litterae encyclicae"],
            "Apostolic Exhortation": [r"apostolic exhortation", r"adhortatio"],
            "Apostolic Letter": [r"apostolic letter", r"\bepistula\b"],
            "Motu Proprio": [r"\bmotu proprio\b"],
            "Decree": [r"\bdecree\b", r"\bdecretum\b"],
            "Instruction": [r"\binstruction\b", r"\binstructio\b"],
            "Declaration": [r"\bdeclaration\b", r"\bdeclaratio\b"],
            "Constitution": [r"\bconstitution\b", r"\bconstitutio\b"],
        }
        tl = text.lower()
        for name, pats in doc_type_patterns.items():
            if any(re.search(p, tl) for p in pats):
                self.metadata["document_type"] = name
                break

    def _extract_dates(self, text: str):
        dates = extract_dates(text)
        if dates:
            ctx = re.search(
                rf'(?:promulgated?|given|issued|published).*?((?:{MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?\,?\s+\d{{4}})',
                text,
                re.IGNORECASE
            )
            self.metadata["date_promulgated"] = ctx.group(1) if ctx else dates[0]

    def _extract_subjects_and_themes(self, text: str, chunks: List[Dict]):
        subject_patterns = {
            "Liturgy": [r"\blitur(?:gy|gica|gical)\b", r"liturgy of the hours", r"officium divinum"],
            "Mass": [r"\bmass\b", r"eucharist", r"holy sacrifice"],
            "Divine Office": [r"divine office", r"breviary", r"breviarium"],
            "Sacraments": [r"\bsacrament", r"\bbaptism\b", r"\bconfirmation\b", r"\borders\b", r"\bmarriage\b", r"\breconciliation\b", r"\banointing\b"],
            "Magisterium": [r"\bmagisterium\b", r"\bapostolic see\b", r"\bholy see\b"],
            "Ecclesiology": [r"\bchurch\b", r"\becclesia\b", r"\bepiscopal\b", r"\bbishop\b", r"\bdiocese\b", r"\bparish\b"],
            "Mariology": [r"\bmary\b", r"\bimmaculate conception\b", r"\bassumption\b", r"\btheotokos\b"],
            "Moral Theology": [r"\bmoral\b", r"\bethics\b", r"\bconscience\b", r"\bvirtue\b"],
            "Scripture": [r"\bscripture\b", r"\bverbum\b", r"\bdivine revelation\b"],
            "Canon Law": [r"canon law", r"code of canon law", r"\bcic\b", r"\bcceo\b"],
            "Prayer": [r"\bprayer\b", r"\boratio\b", r"\bdevotion\b", r"\bro\sary\b"],
            "Council Documents": [r"vatican\s*(?:i|ii)", r"council of trent", r"lumen gentium", r"dei verbum"],
        }
        tl = text.lower()
        subjects = [name for name, pats in subject_patterns.items() if any(re.search(p, tl) for p in pats)]
        self.metadata["subject"] = subjects

        themes: List[str] = []
        for ch in chunks:
            h = ch.get("hierarchy", {})
            for level in ["level_1", "level_2", "level_3", "level_4"]:
                head = h.get(level, "")
                if head and len(head) > 10:
                    themes.append(head)
        # Remove duplicates preserving order
        self.metadata["key_themes"] = list(OrderedDict.fromkeys(themes))[:10]

    def _extract_related_documents(self, text: str):
        doc_patterns = [
            'Sacrosanctum Concilium','Lumen Gentium','Dei Verbum','Gaudium et Spes',
            'Dei Filius','Pastor Aeternus','Syllabus of Errors',
            'Council of Trent','Trent',
            'Quo Primum','Humanae Vitae','Laudato Si\'','Fidei Depositum','Evangelii Nuntiandi',
            'Missale Romanum','Liturgiam Authenticam','Mysterii Paschalis','Mediator Dei',
            'Catechism of the Catholic Church','Roman Catechism','General Instruction of the Roman Missal',
        ]
        related = [p for p in doc_patterns if re.search(p, text, re.IGNORECASE)]
        self.metadata["related_documents"] = sorted(set(related))

    def _infer_geographic_focus(self, text: str):
        patterns = {
            "Vatican City (Rome)": [r"vatican", r"\brome\b", r"apostolic see", r"holy see"],
            "Universal Church": [r"universal church", r"catholic church", r"whole church"],
            "Diocese": [r"\bdiocese\b", r"\bepiscopal\b", r"\bbishop\b"],
            "Parish": [r"\bparish\b", r"\bpastor\b", r"\bfaithful\b"],
        }
        tl = text.lower()
        for loc, pats in patterns.items():
            if any(re.search(p, tl) for p in pats):
                self.metadata["geographic_focus"] = loc
                break

    def _calculate_stats(self, chunks: List[Dict]):
        total_words = sum(ch["word_count"] for ch in chunks)
        self.metadata["word_count"] = f"approximately {total_words:,}"
        pages = max(1, total_words // 250)
        self.metadata["pages"] = f"approximately {pages}"


# EPUB parser

class EpubParser:
    """Parse EPUB documents into hierarchical chunks with metadata and footnotes."""
    def __init__(self, epub_path: str, config: Optional[Dict] = None):
        self.epub_path = epub_path
        self.config = config or {}
        self.book: Optional["epub.EpubBook"] = None
        self.chunks: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}
        self.href_to_toc_title: Dict[str, str] = {}
        # Config values
        self.toc_level = int(self.config.get("toc_hierarchy_level", 3))
        self.min_paragraph_words = int(self.config.get("min_paragraph_words", 6))
        self.min_block_words = int(self.config.get("min_block_words", 30))
        self.preserve_hierarchy_across_docs = bool(self.config.get("preserve_hierarchy_across_docs", False))
        self.reset_depth = int(self.config.get("reset_depth", 2))
        self.class_denylist_re = re.compile(self.config.get("class_denylist", r'^(?:calibre\d+|note)$'), re.I)
        # Hierarchy tracking
        self.current_hierarchy = {f"level_{i}": "" for i in range(1, 7)}
        # Provenance & quality
        self.provenance: Dict[str, Any] = {}
        self.doc_quality_signals: Dict[str, float] = {}
        self.doc_quality_score: float = 0.0
        self.doc_route: str = "A"
        # Debug flag
        self.debug_dump: bool = False
        # Footnote index aggregated across spine
        self.footnote_index: Dict[int, str] = {}

    def load(self):
        if not EPUB_AVAILABLE:
            raise RuntimeError("ebooklib not installed. Please install with: pip install ebooklib bs4 lxml")
        LOGGER.info("Opening EPUB: %s", self.epub_path)
        self.book = epub.read_epub(self.epub_path)
        if not self.book.spine:
            raise RuntimeError("EPUB has no spine (reading order)")
        self._build_toc_mapping()
        # Setup provenance base (without source path)
        src_bytes = open(self.epub_path, "rb").read()
        self.provenance = {
            "doc_id": stable_id(os.path.abspath(self.epub_path), str(os.path.getmtime(self.epub_path))),
            "source_file": os.path.basename(self.epub_path),
            "parser_version": PARSER_VERSION,
            "md_schema_version": MD_SCHEMA_VERSION,
            "ingestion_ts": datetime.now().isoformat(),
            "content_hash": sha1(src_bytes),
        }

    def _norm_href(self, href: Optional[str]) -> str:
        return (href or "").split("#")[0].lstrip("./")

    def _build_toc_mapping(self):
        def walk(node):
            try:
                if isinstance(node, epub.Link):
                    href = self._norm_href(node.href)
                    raw_title = clean_text(node.title)
                    title = clean_toc_title(raw_title)
                    if href and title:
                        self.href_to_toc_title[href] = title
                elif isinstance(node, (list, tuple)):
                    if node and isinstance(node[0], epub.Link):
                        href = self._norm_href(node[0].href)
                        raw_title = clean_text(node[0].title)
                        title = clean_toc_title(raw_title)
                        if href and title:
                            self.href_to_toc_title[href] = title
                    for child in (node[1] if len(node) > 1 else []):
                        walk(child)
            except Exception as e:
                LOGGER.debug("TOC node error: %s", e)
        if getattr(self.book, "toc", None):
            for n in self.book.toc:
                walk(n)

    def _sanitize_dom(self, soup: BeautifulSoup):
        # Remove script and style tags completely
        for t in soup(["script", "style"]):
            t.decompose()
        # Convert <br> to spaces
        for br in soup.find_all("br"):
            br.replace_with(" ")
        # Flatten small-caps and dropcaps to plain text
        for sc in soup.select('.smallcaps, .smcap, .sc, .caps, [style*="small-caps"]'):
            txt = sc.get_text("", strip=True)
            sc.clear()
            sc.append(txt)
        for dc in soup.select('.dropcap, .drop-cap, .initial'):
            txt = dc.get_text("", strip=True)
            dc.clear()
            dc.append(txt)

    def parse(self):
        id_to_item = {it.get_id(): it for it in self.book.get_items()}
        spine_ids = [sid for (sid, _) in self.book.spine if sid != "nav"]
        global_para_id = 0
        full_text_accum: List[str] = []

        # Pre-pass: harvest footnotes by scanning each spine item for enumerations
        for sid in spine_ids:
            item = id_to_item.get(sid)
            if not item:
                continue
            try:
                soup = BeautifulSoup(item.get_content(), "lxml")
            except Exception:
                soup = BeautifulSoup(item.get_content(), "html.parser")
            self._sanitize_dom(soup)
            body = soup.find("body") or soup
            lines = [clean_text(x) for x in body.stripped_strings if clean_text(x)]
            self.footnote_index.update(harvest_enumerated_footnotes_from_text_lines(lines))

        # Parse each document in spine order
        iterator = tqdm(spine_ids, desc="EPUB docs") if len(spine_ids) > 3 else spine_ids
        for order_idx, sid in enumerate(iterator):
            item = id_to_item.get(sid)
            if not item:
                continue
            href = (item.get_name() or "").split("#")[0].lstrip("./")
            try:
                raw_html = item.get_content()
                try:
                    soup = BeautifulSoup(raw_html, "lxml")
                except Exception:
                    soup = BeautifulSoup(raw_html, "html.parser")
                self._sanitize_dom(soup)
            except Exception as e:
                LOGGER.warning("Failed to parse HTML in %s: %s", href, e)
                continue

            # Reset hierarchy at doc boundary if not preserving across docs
            if not self.preserve_hierarchy_across_docs:
                for i in range(self.reset_depth, 7):
                    self.current_hierarchy[f"level_{i}"] = ""

            # Update TOC title at configured level
            toc_title = self.href_to_toc_title.get(href, "")
            if toc_title:
                self.current_hierarchy[f"level_{self.toc_level}"] = toc_title

            def h_snapshot():
                return {f"level_{i}": self.current_hierarchy[f"level_{i}"] for i in range(1, 7)}

            def flush_paragraph(text: str, source_tag: str):
                nonlocal global_para_id
                text = clean_text(text)
                # Allow shorter lines if bullet or scripture/CCC reference present
                short_ok = text.startswith("•") or SCRIPTURE_OR_CCC_LINE_RE.search(text)
                if not text or (estimate_word_count(text) < self.min_paragraph_words and not short_ok):
                    return
                h = h_snapshot()
                # Avoid micro-duplication: skip if new text fully contained in previous chunk within same doc
                last = self.chunks[-1] if self.chunks else None
                if last and last["chapter_href"] == href and last["source_order"] == order_idx:
                    if text and (text == last["text"] or text in last["text"]):
                        return
                foot_cites = sentence_final_footnote_numbers(text)
                resolved = {str(n): self.footnote_index.get(n, "") for n in foot_cites if n in self.footnote_index}
                global_para_id += 1
                chunk = {
                    "stable_id": stable_id(href, str(order_idx), str(global_para_id), text[:80]),
                    "paragraph_id": global_para_id,
                    "text": text,
                    "hierarchy": h,
                    "chapter_href": href,
                    "source_order": order_idx,
                    "source_tag": source_tag,
                    "text_length": len(text),
                    "word_count": estimate_word_count(text),
                    "cross_references": extract_cross_references(text),
                    "scripture_references": extract_scripture_references(text),
                    "dates_mentioned": extract_dates(text),
                    "heading_path": _heading_path(h),
                    "hierarchy_depth": _hier_depth(h),
                    "doc_stable_id": self.provenance.get("doc_id", ""),
                    "footnote_citations": foot_cites,
                    "resolved_footnotes": resolved,
                }
                sents = _split_sents(chunk["text"])
                chunk["sentence_count"] = len(sents)
                chunk["sentences"] = sents[:6]
                chunk["normalized_text"] = _normalize_ascii(chunk["text"])
                self.chunks.append(chunk)

            body = soup.find("body") or soup
            # Update headings to track hierarchy (do not chunk headings themselves)
            for h_tag in body.find_all([f"h{i}" for i in range(1, 7)]):
                lvl = heading_level(h_tag.name.lower())
                htxt = clean_text(h_tag.get_text(" "))
                if htxt:
                    self.current_hierarchy[f"level_{lvl}"] = htxt
                    for deeper in range(lvl + 1, 7):
                        self.current_hierarchy[f"level_{deeper}"] = ""

            # Define tags for block-level chunking
            BLOCK_TAGS = {"p", "blockquote", "li", "pre", "figure",
                          "section", "article", "div", "aside", "header", "footer", "main",
                          "span", "a", "em", "strong"}
            INLINE_TAGS = {"span", "a", "em", "strong"}
            BLOCK_PARENTS = {"p", "li", "blockquote", "pre", "figure"}
            texts_for_doc_hash: List[str] = []

            # Iterate over block-level elements and flush paragraphs
            for el in body.find_all(BLOCK_TAGS, recursive=True):
                tag = (el.name or "").lower()
                if is_heading_tag(tag):
                    continue
                # Skip inline tags inside block parents to avoid duplication
                if tag in INLINE_TAGS and el.find_parent(tuple(BLOCK_PARENTS)):
                    continue
                classes = " ".join(el.get("class", []))
                if classes and self.class_denylist_re.search(classes):
                    continue
                txt = clean_text(el.get_text(" "))
                if not txt:
                    continue
                texts_for_doc_hash.append(txt)
                if tag == "li":
                    flush_paragraph(f"• {txt}", "li")
                elif tag in {"p", "blockquote", "pre", "figure"}:
                    flush_paragraph(txt, tag)
                else:
                    if estimate_word_count(txt) >= max(2 * self.min_paragraph_words, self.min_block_words):
                        flush_paragraph(txt, tag)

            # Fallback: if no text collected for doc, chunk entire body into windows
            if not texts_for_doc_hash:
                doc_text = clean_text(soup.get_text(" "))
                if doc_text:
                    texts_for_doc_hash.append(doc_text)
                    words = doc_text.split()
                    window, overlap = 100, 20
                    i = 0
                    while i < len(words):
                        chunk_words = words[i:i+window]
                        i += (window - overlap)
                        if len(chunk_words) >= self.min_paragraph_words:
                            flush_paragraph(" ".join(chunk_words), "fallback_window")

            full_text_accum.append(" ".join(texts_for_doc_hash))

        # Compute quality signals and route
        normalized_doc_text = clean_text("\n".join(full_text_accum))
        self.doc_quality_signals = quality_signals_from_text(normalized_doc_text)
        self.doc_quality_score = score_quality(self.doc_quality_signals)
        self.doc_route = route_doc(self.doc_quality_score)
        self.provenance["normalized_hash"] = sha1(normalized_doc_text.encode("utf-8"))

        # Extract metadata
        extractor = MetadataExtractor(self.href_to_toc_title)
        self.metadata = extractor.extract_from_epub(self.book, self.chunks)
        self.metadata["provenance"] = self.provenance
        self.metadata["quality"] = {
            "signals": self.doc_quality_signals,
            "score": round(self.doc_quality_score, 4),
            "route": self.doc_route,
        }
        # Attach footnote summary stats
        self.metadata["footnotes_index"] = {str(k): v for k, v in sorted(self.footnote_index.items())}
        self.metadata["footnote_index_count"] = len(self.footnote_index)
        cit_freq: Dict[int, int] = defaultdict(int)
        for ch in self.chunks:
            for n in ch.get("footnote_citations", []):
                cit_freq[n] += 1
        self.metadata["footnote_citation_stats"] = {
            "unique_citations": [int(n) for n in sorted(set(cit_freq.keys()))],
            "citation_frequency": {str(k): v for k, v in sorted(cit_freq.items())},
        }


# PDF parser

class PdfParser:
    """Parse PDF documents, using pdfplumber for text extraction and OCR fallback."""
    def __init__(self, pdf_path: str, config: Optional[Dict] = None):
        self.pdf_path = pdf_path
        self.config = config or {}
        self.chunks: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}
        self.min_paragraph_words = int(self.config.get("min_paragraph_words_pdf", 3))
        self.ocr_min_chars = int(self.config.get("ocr_min_chars", 40))
        self.enable_ocr = bool(self.config.get("enable_ocr", True))
        self.ocr_psm = str(self.config.get("ocr_psm", "6"))
        self.ocr_oem = str(self.config.get("ocr_oem", "1"))
        self.doc_quality_signals: Dict[str, float] = {}
        self.doc_quality_score: float = 0.0
        self.doc_route: str = "A"
        self.provenance: Dict[str, Any] = {}
        self.debug_dump: bool = False
        self.footnote_index: Dict[int, str] = {}

    def load(self):
        if not (PDF_PLUMBER or PDF_PYPDF2):
            raise RuntimeError("Install pdfplumber or PyPDF2 for PDF support")
        LOGGER.info("Opening PDF: %s", self.pdf_path)
        src_bytes = open(self.pdf_path, "rb").read()
        self.provenance = {
            "doc_id": stable_id(os.path.abspath(self.pdf_path), str(os.path.getmtime(self.pdf_path))),
            "source_file": os.path.basename(self.pdf_path),
            "parser_version": PARSER_VERSION,
            "md_schema_version": MD_SCHEMA_VERSION,
            "ingestion_ts": datetime.now().isoformat(),
            "content_hash": sha1(src_bytes),
        }

    # Helper methods for PDF extraction
    def _pdf_extract_text_plumber(self) -> List[str]:
        pages: List[str] = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                # Use layout=True for more faithful line breaks
                txt = page.extract_text(layout=True) or ""
                pages.append(txt)
        return pages

    def _pdf_extract_text_pypdf2(self) -> List[str]:
        pages: List[str] = []
        with open(self.pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for i in range(len(reader.pages)):
                try:
                    txt = reader.pages[i].extract_text() or ""
                except Exception:
                    txt = ""
                pages.append(txt)
        return pages

    def _ocr_page_image(self, index: int) -> Tuple[str, float]:
        """Render a page to an image using pypdfium2 and OCR it via pytesseract."""
        if not (PDF_RENDER and OCR_AVAILABLE):
            return "", -1.0
        try:
            pdf = pdfium.PdfDocument(self.pdf_path)
            page = pdf.get_page(index)
            # Render at 2x scale for better accuracy
            pil = page.render(scale=2.0).to_pil()
            config = f'--psm {self.ocr_psm} --oem {self.ocr_oem}'
            data = pytesseract.image_to_data(pil, output_type=TesseractOutput.DICT, config=config)
            lines_by_num: Dict[int, List[str]] = defaultdict(list)
            n = len(data.get("text", []))
            confs = []
            for i in range(n):
                txt = data["text"][i]
                if txt and txt.strip():
                    lines_by_num[data["line_num"][i]].append(txt)
                conf = data.get("conf", [])[i]
                try:
                    conf_val = float(conf)
                    if conf_val >= 0:
                        confs.append(conf_val)
                except Exception:
                    pass
            lines = [" ".join(v) for _, v in sorted(lines_by_num.items()) if " ".join(v).strip()]
            text = "\n".join(lines)
            mean_conf = (sum(confs) / len(confs)) if confs else -1.0
            return text, mean_conf
        except Exception as e:
            LOGGER.debug("OCR failed for page %d: %s", index + 1, e)
            return "", -1.0

    def _split_paragraphs_from_page_text(self, txt: str) -> List[str]:
        # If double newlines present, split into paragraphs
        if "\n\n" in txt:
            paras = re.split(r'(?:\n\s*\n)+', txt)
        else:
            # Fallback to sliding window splitting
            words = txt.split()
            window, overlap = 120, 20
            i = 0
            paras = []
            while i < len(words):
                w = words[i:i+window]
                if len(w) >= self.min_paragraph_words:
                    paras.append(" ".join(w))
                i += (window - overlap)
        out: List[str] = []
        for p in paras:
            p = clean_text(p)
            if not p:
                continue
            short_ok = p.startswith("•") or SCRIPTURE_OR_CCC_LINE_RE.search(p)
            if estimate_word_count(p) >= self.min_paragraph_words or short_ok:
                out.append(p)
        return out

    def parse(self):
        # 1) Extract text using pdfplumber if available; else PyPDF2
        if PDF_PLUMBER:
            raw_pages = self._pdf_extract_text_plumber()
        else:
            raw_pages = self._pdf_extract_text_pypdf2()

        # 2) OCR fallback for low-yield pages
        if self.enable_ocr:
            for i, raw in enumerate(raw_pages):
                if len(clean_text(raw)) < self.ocr_min_chars:
                    ocr_text, mean_conf = self._ocr_page_image(i)
                    if len(clean_text(ocr_text)) > len(clean_text(raw)):
                        raw_pages[i] = ocr_text + "\n"
                        # Save OCR confidence for this page
                        setattr(self, "_ocr_conf_map", getattr(self, "_ocr_conf_map", {}))
                        self._ocr_conf_map[i + 1] = mean_conf

        # 3) Harvest footnotes across all pages
        for i, raw in enumerate(raw_pages):
            lines = [clean_text(x) for x in (raw or "").splitlines() if clean_text(x)]
            self.footnote_index.update(harvest_enumerated_footnotes_from_text_lines(lines))

        # 4) Chunk each page into paragraphs
        paragraph_id = 0
        full_text_accum: List[str] = []
        for i, raw in enumerate(tqdm(raw_pages, desc="PDF pages") if len(raw_pages) > 5 else raw_pages):
            page_no = i + 1
            page_text = clean_text(raw or "")
            if not page_text:
                continue
            full_text_accum.append(page_text)
            paras = self._split_paragraphs_from_page_text(page_text)
            for para in paras:
                cites = sentence_final_footnote_numbers(para)
                resolved = {str(n): self.footnote_index.get(n, "") for n in cites if n in self.footnote_index}
                paragraph_id += 1
                h = {"level_1": "PDF Document", "level_2": f"Page {page_no}"}
                ocr_conf = getattr(self, "_ocr_conf_map", {}).get(page_no, None)
                chunk = {
                    "stable_id": stable_id(self.pdf_path, str(page_no), str(paragraph_id), para[:80]),
                    "paragraph_id": paragraph_id,
                    "text": para,
                    "hierarchy": h,
                    "chapter_href": f"page:{page_no}",
                    "source_order": i,
                    "source_tag": "pdf_page_ocr" if ocr_conf is not None else "pdf_page",
                    "ocr": (ocr_conf is not None),
                    "ocr_conf": None if ocr_conf is None else round(float(ocr_conf), 2),
                    "text_length": len(para),
                    "word_count": estimate_word_count(para),
                    "cross_references": extract_cross_references(para),
                    "scripture_references": extract_scripture_references(para),
                    "dates_mentioned": extract_dates(para),
                    "heading_path": _heading_path(h),
                    "hierarchy_depth": _hier_depth(h),
                    "doc_stable_id": self.provenance.get("doc_id", ""),
                    "footnote_citations": cites,
                    "resolved_footnotes": resolved,
                }
                sents = _split_sents(chunk["text"])
                chunk["sentence_count"] = len(sents)
                chunk["sentences"] = sents[:6]
                chunk["normalized_text"] = _normalize_ascii(chunk["text"])
                self.chunks.append(chunk)

        # Compute quality signals and route
        normalized_doc_text = clean_text("\n".join(full_text_accum))
        self.doc_quality_signals = quality_signals_from_text(normalized_doc_text)
        self.doc_quality_score = score_quality(self.doc_quality_signals)
        self.doc_route = route_doc(self.doc_quality_score)

        extractor = MetadataExtractor()
        self.metadata = extractor.extract_minimal(self.chunks)
        self.metadata["provenance"] = self.provenance
        self.metadata["quality"] = {
            "signals": self.doc_quality_signals,
            "score": round(self.doc_quality_score, 4),
            "route": self.doc_route,
        }
        self.metadata["footnotes_index"] = {str(k): v for k, v in sorted(self.footnote_index.items())}
        self.metadata["footnote_index_count"] = len(self.footnote_index)
        cit_freq: Dict[int, int] = defaultdict(int)
        for ch in self.chunks:
            for n in ch.get("footnote_citations", []):
                cit_freq[n] += 1
        self.metadata["footnote_citation_stats"] = {
            "unique_citations": [int(n) for n in sorted(set(cit_freq.keys()))],
            "citation_frequency": {str(k): v for k, v in sorted(cit_freq.items())},
        }
        LOGGER.info("✓ PDF paragraphs: %d; route=%s (%.2f)", len(self.chunks), self.doc_route, self.doc_quality_score)


# Shared output writing functions

def write_outputs(base: str, outdir: str, metadata: Dict[str, Any], chunks: List[Dict], doc_quality_score: float, doc_route: str, source_file: str, ndjson: bool):
    """Write outputs in JSON and optionally NDJSON for chunks."""
    os.makedirs(outdir, exist_ok=True)
    data = {
        "metadata": metadata,
        "chunks": chunks,
        "extraction_info": {
            "total_paragraphs": len(chunks),
            "extraction_date": datetime.now().isoformat(),
            "source_file": os.path.basename(source_file),
            "parser_version": PARSER_VERSION,
            "md_schema_version": MD_SCHEMA_VERSION,
            "route": doc_route,
            "quality_score": round(doc_quality_score, 4),
        },
    }
    json_out = os.path.join(outdir, f"{base}.json")
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    LOGGER.info("✓ Saved data to %s", json_out)
    md_out = os.path.join(outdir, f"{base}_metadata.json")
    with open(md_out, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    LOGGER.info("✓ Saved metadata to %s", md_out)
    if ndjson:
        nd_out = os.path.join(outdir, f"{base}.ndjson")
        with open(nd_out, "w", encoding="utf-8") as f:
            for ch in chunks:
                f.write(json.dumps(ch, ensure_ascii=False) + "\n")
        LOGGER.info("✓ Saved chunks NDJSON to %s", nd_out)


# Command-line interface

def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="Parse EPUB or PDF (with OCR fallback) into hierarchical chunks with cross-refs and footnotes."
    )
    ap.add_argument("path", nargs="?", default="", help="Path to .epub/.pdf file or a directory")
    ap.add_argument("--output", "-o", help="Base name for output files (single-file mode only)")
    ap.add_argument("--output-dir", default=".", help="Directory to write outputs")
    ap.add_argument("--recursive", action="store_true", help="When a directory is provided, include subfolders")
    # EPUB options
    ap.add_argument("--toc-level", type=int, default=3, help="(EPUB) Hierarchy level for TOC titles (1-6)")
    ap.add_argument("--min-words", type=int, default=6, help="(EPUB) Minimum words for paragraph inclusion")
    ap.add_argument("--min-block-words", type=int, default=30, help="(EPUB) Minimum words for generic block tags")
    ap.add_argument("--preserve-hierarchy", action="store_true", help="(EPUB) Preserve hierarchy across spine docs")
    ap.add_argument("--reset-depth", type=int, default=2, help="(EPUB) Clear levels >= this depth on doc boundary")
    ap.add_argument("--deny-class", default=r'^(?:calibre\d+|note)$', help="(EPUB) Regex for class denylist")
    # PDF options
    ap.add_argument("--min-words-pdf", type=int, default=3, help="(PDF) Minimum words for paragraph inclusion")
    ap.add_argument("--ocr-min-chars", type=int, default=40, help="OCR page if extracted chars < this")
    ap.add_argument("--disable-ocr", action="store_true", help="Disable OCR fallback for PDFs")
    ap.add_argument("--ocr-psm", default="6", help="Tesseract PSM (default 6)")
    ap.add_argument("--ocr-oem", default="1", help="Tesseract OEM (default 1)")
    ap.add_argument("--ndjson", action="store_true", help="Also emit chunks NDJSON")
    ap.add_argument("--verbose", action="store_true", help="Verbose logging")
    ap.add_argument("--quiet", action="store_true", help="Only warnings and errors")
    ap.add_argument("--debug-dump", action="store_true", help="(EPUB) Write raw per-spine text (debug)")
    args = ap.parse_args()
    setup_logging(verbose=args.verbose, quiet=args.quiet)
    in_path = args.path.strip() or input("Enter path to .epub/.pdf or folder: ").strip()
    if not in_path:
        LOGGER.error("No path provided.")
        return 2
    if not os.path.exists(in_path):
        LOGGER.error("Path not found: %s", in_path)
        return 2
    config = {
        "toc_hierarchy_level": args.toc_level,
        "min_paragraph_words": args.min_words,
        "min_block_words": args.min_block_words,
        "preserve_hierarchy_across_docs": args.preserve_hierarchy,
        "reset_depth": args.reset_depth,
        "class_denylist": args.deny_class,
        "min_paragraph_words_pdf": args.min_words_pdf,
        "ocr_min_chars": args.ocr_min_chars,
        "enable_ocr": not args.disable_ocr,
        "ocr_psm": args.ocr_psm,
        "ocr_oem": args.ocr_oem,
    }
    def process_one(path: str) -> bool:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".epub":
            if not EPUB_AVAILABLE:
                LOGGER.error("EPUB support not available. Install ebooklib.")
                return False
            parser = EpubParser(path, config)
            parser.debug_dump = args.debug_dump
            parser.load()
            parser.parse()
            base = args.output if os.path.isfile(in_path) and args.output else os.path.splitext(os.path.basename(path))[0]
            write_outputs(base, args.output_dir, parser.metadata, parser.chunks, parser.doc_quality_score, parser.doc_route, path, args.ndjson)
            print(f"\n✅ {os.path.basename(path)}  paragraphs={len(parser.chunks)}  quality={round(parser.doc_quality_score,3)} (route {parser.doc_route})")
            return True
        elif ext == ".pdf":
            parser = PdfParser(path, config)
            parser.load()
            parser.parse()
            base = args.output if os.path.isfile(in_path) and args.output else os.path.splitext(os.path.basename(path))[0]
            write_outputs(base, args.output_dir, parser.metadata, parser.chunks, parser.doc_quality_score, parser.doc_route, path, args.ndjson)
            print(f"\n✅ {os.path.basename(path)}  paragraphs={len(parser.chunks)}  quality={round(parser.doc_quality_score,3)} (route {parser.doc_route})")
            return True
        else:
            LOGGER.warning("Unsupported extension %s (only .epub or .pdf)", ext)
            return False
    if os.path.isfile(in_path):
        ok = process_one(in_path)
        return 0 if ok else 1
    # Directory mode
    paths: List[str] = []
    if args.recursive:
        for root, _, files in os.walk(in_path):
            for fn in files:
                if fn.lower().endswith((".epub", ".pdf")):
                    paths.append(os.path.join(root, fn))
    else:
        paths = [os.path.join(in_path, fn) for fn in os.listdir(in_path) if fn.lower().endswith((".epub", ".pdf"))]
    if not paths:
        LOGGER.error("No .epub/.pdf files found in the provided directory%s.", " (recursive)" if args.recursive else "")
        return 2
    print(f"Found {len(paths)} files. Processing...")
    successes = 0
    for p in tqdm(paths, desc="Batch"):
        if process_one(p):
            successes += 1
    print(f"\nDone. {successes}/{len(paths)} files processed successfully.")
    return 0 if successes == len(paths) else 1


if __name__ == "__main__":
    sys.exit(main())