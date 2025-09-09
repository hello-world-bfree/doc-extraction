#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EPUB → hierarchical chunks with quality routing, provenance, NDJSON.
Tailored for Catholic literature / magisterial texts.

Batch features:
- Pass a single .epub or a directory containing .epub files
- --recursive to include subfolders
- --output-dir to choose output folder

Includes:
- Spaced-caps / small-caps normalization (fixes "S ECOND ..." artifacts)
- ebooklib item-type fix (epub.EpubHtml or ebooklib.ITEM_DOCUMENT)
- No table processing
- Aggressive fallbacks for quirky EPUBs
- Output base name = input EPUB filename (no extension)
- Optional debug dump of per-spine raw text + DOM stats (prefixed by file)
- EXTRA CHUNK FIELDS: heading_path, hierarchy_depth, sentence_count, sentences, normalized_text, doc_stable_id
- CLEAN TOC TITLES: strip leading numbers like "1.", "I.)", "Chapter 5: ..." from TOC titles
- provenance excludes source_path (only source_file retained)

NEW in 1.4.8:
- Skip inline tags nested under block parents to prevent duplicate chunks
- Tighten punctuation spacing; "3 ." → "3."
- Optional enumerator stripping in NOTES sections
- Micro de-dup: skip chunk if fully contained in previous chunk for same spine item
"""

import os
import sys
import re
import json
import hashlib
import logging
import unicodedata
from collections import OrderedDict
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

import ebooklib
from tqdm import tqdm
from bs4 import BeautifulSoup
from ebooklib import epub

# ====================== Versions & Logging ======================

PARSER_VERSION = "1.4.8-catholic-notables-batch"
MD_SCHEMA_VERSION = "2025-09-08"

LOGGER = logging.getLogger("epub_parser")

def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
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

# ====================== Utilities ======================

MONTHS = (
    r'Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)|Apr(?:il)|May|Jun(?:e)|'
    r'Jul(?:y)|Aug(?:ust)|Sep(?:t\.|tember)|Oct(?:ober)|Nov(?:ember)|Dec(?:ember)'
)

SOFT_HYPHEN = "\u00ad"
ZW_SPACES = r"[\u200B-\u200D\u2060\uFEFF]"  # zero-widths

def sha1(x: bytes) -> str:
    return hashlib.sha1(x).hexdigest()

def stable_id(*parts: str) -> str:
    return hashlib.sha1("||".join(parts).encode("utf-8")).hexdigest()[:16]

def normalize_spaced_caps(s: str) -> str:
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
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    # strip soft hyphens & zero-width chars
    s = s.replace(SOFT_HYPHEN, "")
    s = re.sub(ZW_SPACES, "", s)
    # collapse whitespace
    s = re.sub(r"\s+", " ", s)
    s = s.replace("\u00a0", " ").strip()
    # tighten punctuation spacing and list artifacts
    s = re.sub(r'(\b\d+)\s+\.', r'\1.', s)             # "3 ." -> "3."
    s = re.sub(r'\s+([,;:!?])', r'\1', s)              # space before punctuation -> none
    s = re.sub(r'\s+([.”’)\]\}])', r'\1', s)           # space before closing quotes/brackets
    s = re.sub(r'([(\[“‘])\s+', r'\1', s)              # space after opening quotes/brackets
    # fix small-caps / spaced-caps artifacts
    s = normalize_spaced_caps(s)
    return s

def estimate_word_count(text: str) -> int:
    return len(text.split()) if text else 0

def heading_level(tag_name: str) -> int:
    if tag_name and tag_name.lower().startswith("h"):
        try:
            return int(tag_name[1])
        except (ValueError, IndexError):
            return 99
    return 99

def is_heading_tag(tag_name: str) -> bool:
    return tag_name in {f"h{i}" for i in range(1, 7)}

def clean_toc_title(s: str) -> str:
    """Strip leading numbers/ordinals like '1.', '1)', 'I.', 'Chapter 5:' etc."""
    if not s: return s
    s = clean_text(s)
    # Remove "Chapter 5: ..." or "Chap. 5 - ..."
    s = re.sub(r'^\s*(?:chapter|chap\.?)\s*\d+\s*[:.\-–—]\s*', '', s, flags=re.I)
    # Remove "1. ", "1) ", "I.) ", "IV - "
    s = re.sub(r'^\s*(?:\d+|[IVXLC]+)\s*[\.\)\-–—]\s*', '', s, flags=re.I)
    # Handle "1 " (bare number + space)
    s = re.sub(r'^\s*\d+\s+', '', s)
    return s

# ---------- Chunk enrich helpers ----------

def _heading_path(h: Dict[str, str]) -> str:
    parts = [h.get(f"level_{i}", "") for i in range(1, 7)]
    return " / ".join([p for p in parts if p])

def _hier_depth(h: Dict[str, str]) -> int:
    for i in range(6, 0, -1):
        if h.get(f"level_{i}"):
            return i
    return 0

def _split_sents(t: str) -> List[str]:
    # Cheap sentence splitter
    sents = re.split(r'(?<=[.!?])\s+(?=[A-Z“"\'(])', t)
    return [s for s in sents if s.strip()]

def _normalize_ascii(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode("ascii")

# ---------- Extractors ----------

def extract_dates(text: str) -> List[str]:
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

def extract_scripture_references(text: str) -> List[str]:
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
    """Catholic-focused cross-refs: CCC, CIC/CCEO, DS(Denz), GIRM, councils."""
    SEE_MAX = 140
    patterns = [
        r'\b(?:cf\.|compare|see(?: also)?)\s+(?:chapter|section|part|§|art\.?|can\.?)\s+[A-Za-z0-9.:§-]{1,60}',
        r'\b(?:CIC|CCEO)\s*(?:/1983|/1990)?\s*(?:can\.?|canon)\s*\d+(?:\s*§\s*\d+)?',
        r'\b(?:canon|can\.)\s*\d+(?:\s*§\s*\d+)?',
        r'\b(?:CCC|Catechism(?: of the Catholic Church)?)\s*\d{1,4}',
        r'\b(?:Roman Catechism|Catechism of (?:Pius V|Trent))\b',
        r'\b(?:DS|Denz\.?)\s*\d{3,5}\b',
        r'\b(?:GIRM|GILH|IGMR|OGMR)\s*\d{1,4}\b',
        r'\b(?:Council of Trent|Trent(?:,?\s*Session)?\s*[IVXLC]+)\b',
        r'\b(?:Vatican\s*(?:I|II))\b',
        r'\b§{1,2}\s*\d{1,4}\b',
    ]
    refs: List[str] = []
    for pat in patterns:
        matches = re.findall(pat, text, flags=re.IGNORECASE)
        for m in matches:
            m = clean_text(m)
            if 3 < len(m) <= SEE_MAX:
                refs.append(m)
    return sorted(set(refs))

# ====================== Quality Scoring & Routing ======================

def quality_signals_from_text(text: str) -> Dict[str, float]:
    if not text:
        return {"garble_rate": 1.0, "mean_conf": 0.0, "line_len_std_norm": 1.0, "lang_prob": 0.0}
    weird = len(re.findall(r"[^\x09\x0A\x0D\x20-\x7E\u00A0-\u02AF]", text))
    garble_rate = min(1.0, weird / max(1, len(text)))
    mean_conf = max(0.0, 1.0 - garble_rate) * (1.0 if len(text) > 2000 else 0.8)
    line_lens = [len(l) for l in text.splitlines() if l.strip()]
    if line_lens:
        import statistics as stats
        std = stats.pstdev(line_lens)
        line_len_std_norm = min(1.0, std / 120.0)
    else:
        line_len_std_norm = 0.2
    latin_hits = len(re.findall(r'\b(Dei|Ecclesia|Dominus|Verbum|Magisterium|Apostolica)\b', text))
    lang_prob = min(1.0, 0.5 + 0.05 * latin_hits)
    return {
        "garble_rate": float(garble_rate),
        "mean_conf": float(mean_conf),
        "line_len_std_norm": float(line_len_std_norm),
        "lang_prob": float(lang_prob),
    }

def score_quality(signals: Dict[str, float]) -> float:
    return float(
        0.40 * (1 - signals.get("garble_rate", 0.0)) +
        0.30 * signals.get("mean_conf", 0.0) +
        0.10 * (1 - signals.get("line_len_std_norm", 0.0)) +
        0.20 * signals.get("lang_prob", 0.0)
    )

def route_doc(score: float) -> str:
    if score >= 0.80: return "A"
    if score >= 0.55: return "B"
    return "C"

# ====================== Metadata Extractor ======================

class MetadataExtractor:
    def __init__(self, href_to_toc_title: Dict[str, str]):
        self.href_to_toc_title = href_to_toc_title
        self.metadata: Dict[str, Any] = {
            "title": "", "author": "", "document_type": "", "date_promulgated": "",
            "subject": [], "key_themes": [], "related_documents": [],
            "time_period": "", "geographic_focus": "", "language": "",
            "publisher": "", "pages": "", "word_count": "",
            "source_identifiers": {"toc_map": href_to_toc_title or {}},
            "md_schema_version": MD_SCHEMA_VERSION,
        }

    def extract_from_epub(self, book: epub.EpubBook, chunks: List[Dict]) -> Dict[str, Any]:
        self.metadata["title"] = clean_text(book.get_metadata("DC", "title")[0][0] if book.get_metadata("DC", "title") else "")
        self.metadata["author"] = clean_text(book.get_metadata("DC", "creator")[0][0] if book.get_metadata("DC", "creator") else "")
        self.metadata["language"] = clean_text(book.get_metadata("DC", "language")[0][0] if book.get_metadata("DC", "language") else "")
        self.metadata["publisher"] = clean_text(book.get_metadata("DC", "publisher")[0][0] if book.get_metadata("DC", "publisher") else "")

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
                text, re.IGNORECASE
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
        self.metadata["key_themes"] = list(OrderedDict.fromkeys(themes))[:10]

    def _extract_related_documents(self, text: str):
        doc_patterns = [
            'Sacrosanctum Concilium','Lumen Gentium','Dei Verbum','Gaudium et Spes',
            'Dei Filius','Pastor Aeternus','Syllabus of Errors',
            'Council of Trent','Trent',
            'Quo Primum','Humanae Vitae',"Laudato Si'",'Fidei Depositum','Evangelii Nuntiandi',
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

# ====================== EPUB Parser ======================

class EpubParser:
    def __init__(self, epub_path: str, config: Optional[Dict] = None):
        self.epub_path = epub_path
        self.config = config or {}
        self.book: Optional[epub.EpubBook] = None
        self.chunks: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}
        self.href_to_toc_title: Dict[str, str] = {}

        # Config
        self.toc_level = int(self.config.get("toc_hierarchy_level", 3))
        self.min_paragraph_words = int(self.config.get("min_paragraph_words", 6))
        self.min_block_words = int(self.config.get("min_block_words", 30))
        self.preserve_hierarchy_across_docs = bool(self.config.get("preserve_hierarchy_across_docs", False))
        self.reset_depth = int(self.config.get("reset_depth", 2))
        self.class_denylist_re = re.compile(self.config.get("class_denylist", r'^(?:calibre\d+|note|footnote)$'), re.I)

        # Hierarchy tracker
        self.current_hierarchy = {f"level_{i}": "" for i in range(1, 7)}

        # Provenance & quality
        self.provenance: Dict[str, Any] = {}
        self.doc_quality_signals: Dict[str, float] = {}
        self.doc_quality_score: float = 0.0
        self.doc_route: str = "A"

        # Optional debug dump flag (set from CLI in main)
        self.debug_dump: bool = False

    # ---------- load & toc ----------

    def load(self):
        LOGGER.info("Opening EPUB: %s", self.epub_path)
        try:
            self.book = epub.read_epub(self.epub_path)
        except Exception as e:
            raise RuntimeError(f"Failed to load EPUB: {e}")
        if not self.book.spine:
            raise RuntimeError("EPUB has no spine (reading order)")
        self._build_toc_mapping()
        LOGGER.info("✓ EPUB loaded. TOC entries: %d", len(self.href_to_toc_title))

        # Provenance base (no source_path)
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

    # ---------- sanitization ----------

    def _sanitize_dom(self, soup: BeautifulSoup):
        for t in soup(["script", "style"]): t.decompose()
        for t in soup.select(
            'a[epub|type="noteref"], a[epub\\:type="noteref"], sup.noteref, sup.footnote, a.footnote, a.noteref'
        ): t.decompose()
        for br in soup.find_all("br"): br.replace_with(" ")
        # flatten small-caps/dropcaps
        for sc in soup.select('.smallcaps, .smcap, .sc, .caps, [style*="small-caps"]'):
            txt = sc.get_text("", strip=True); sc.clear(); sc.append(txt)
        for dc in soup.select('.dropcap, .drop-cap, .initial'):
            txt = dc.get_text("", strip=True); dc.clear(); dc.append(txt)

    # ---------- parse ----------

    def parse(self):
        if self.book is None:
            raise RuntimeError("Call load() before parse().")

        spine_ids = [sid for (sid, _) in self.book.spine if sid != "nav"]
        id_to_item = {it.get_id(): it for it in self.book.get_items()}

        iterator = spine_ids if len(spine_ids) < 3 else tqdm(spine_ids, desc="Processing documents")

        global_para_id = 0
        full_text_accum: List[str] = []

        for order_idx, sid in enumerate(iterator):
            try:
                item = id_to_item.get(sid)
                is_doc = (
                    item and (
                        isinstance(item, epub.EpubHtml) or
                        (hasattr(item, "get_type") and item.get_type() == getattr(ebooklib, "ITEM_DOCUMENT", None))
                    )
                )
                if not is_doc:
                    try:
                        _ = item.get_content()
                    except Exception:
                        continue

                href, para_id_after, doc_text = self._process_document(item, order_idx, global_para_id)
                global_para_id = para_id_after
                if doc_text:
                    full_text_accum.append(doc_text)

            except Exception as e:
                LOGGER.warning("Error processing document %s: %s", sid, e)

        normalized_doc_text = clean_text("\n".join(full_text_accum))
        self.doc_quality_signals = quality_signals_from_text(normalized_doc_text)
        self.doc_quality_score = score_quality(self.doc_quality_signals)
        self.doc_route = route_doc(self.doc_quality_score)

        self.provenance["normalized_hash"] = sha1(normalized_doc_text.encode("utf-8"))

        extractor = MetadataExtractor(self.href_to_toc_title)
        self.metadata = extractor.extract_from_epub(self.book, self.chunks)
        self.metadata["provenance"] = self.provenance
        self.metadata["quality"] = {
            "signals": self.doc_quality_signals,
            "score": round(self.doc_quality_score, 4),
            "route": self.doc_route,
        }
        LOGGER.info("✓ Extracted %d paragraphs; route=%s (%.2f)", len(self.chunks), self.doc_route, self.doc_quality_score)

    def _reset_lower_hierarchy(self):
        for i in range(self.reset_depth, 7):
            self.current_hierarchy[f"level_{i}"] = ""

    def _set_heading_level(self, level: int, text: str):
        level = max(1, min(6, level))
        self.current_hierarchy[f"level_{level}"] = text
        for deeper in range(level + 1, 7):
            self.current_hierarchy[f"level_{deeper}"] = ""

    def _process_document(self, item, order_idx: int, global_para_id: int) -> Tuple[str, int, str]:
        href = self._norm_href(item.get_name())
        try:
            raw_html = item.get_content()
            try:
                soup = BeautifulSoup(raw_html, "lxml")
            except Exception:
                try:
                    import html5lib  # noqa: F401
                    LOGGER.debug("Falling back to html5lib for %s", href)
                    soup = BeautifulSoup(raw_html, "html5lib")
                except Exception:
                    LOGGER.debug("Falling back to html.parser for %s", href)
                    soup = BeautifulSoup(raw_html, "html.parser")
            self._sanitize_dom(soup)
        except Exception as e:
            LOGGER.warning("Failed to parse HTML in %s: %s", href, e)
            return href, global_para_id, ""

        if not self.preserve_hierarchy_across_docs:
            self._reset_lower_hierarchy()

        toc_title = self.href_to_toc_title.get(href, "")
        if toc_title:
            self.current_hierarchy[f"level_{self.toc_level}"] = toc_title

        def h_snapshot():
            return {f"level_{i}": self.current_hierarchy[f"level_{i}"] for i in range(1, 7)}

        def flush_paragraph(text: str, source_tag: str) -> None:
            nonlocal global_para_id
            text = clean_text(text)
            if not text or estimate_word_count(text) < self.min_paragraph_words:
                return

            h = h_snapshot()

            # OPTIONAL: strip enumerators at start of NOTES items
            if any(x == "NOTES" for x in h.values()):
                text = re.sub(r'^\s*(?:\d+|[IVXLC]+)\s*[.)]?\s*', '', text)

            # micro de-dup: skip if new text fully contained in previous chunk from same spine item
            last = self.chunks[-1] if self.chunks else None
            if last and last["chapter_href"] == href and last["source_order"] == order_idx:
                if text and (text == last["text"] or text in last["text"]):
                    return

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
            }
            sents = _split_sents(chunk["text"])
            chunk["sentence_count"] = len(sents)
            chunk["sentences"] = sents[:6]
            chunk["normalized_text"] = _normalize_ascii(chunk["text"])
            self.chunks.append(chunk)

        body = soup.find("body") or soup

        # Headings set hierarchy; do NOT chunk them
        for h in body.find_all([f"h{i}" for i in range(1, 7)]):
            lvl = heading_level(h.name.lower())
            htxt = clean_text(h.get_text(" "))
            if htxt:
                self._set_heading_level(lvl, htxt)

        # Block-level chunking (route-sensitive)
        BLOCK_TAGS = {
            "p", "blockquote", "li", "pre", "figure",
            "section", "article", "div", "aside", "header", "footer", "main",
            # odd EPUBs: inline wrappers
            "span", "a", "em", "strong"
        }
        INLINE_TAGS = {"span", "a", "em", "strong"}
        BLOCK_PARENTS = {"p", "li", "blockquote", "pre", "figure"}
        texts_for_doc_hash: List[str] = []

        for el in body.find_all(BLOCK_TAGS, recursive=True):
            tag = (el.name or "").lower()
            if is_heading_tag(tag):
                continue
            # prevent double-chunking: skip inline elements if they live inside a block parent
            if tag in INLINE_TAGS and el.find_parent(tuple(BLOCK_PARENTS)):
                continue

            classes = " ".join(el.get("class", []))
            if classes and self.class_denylist_re.search(classes):
                continue

            txt = clean_text(el.get_text(" "))
            if not txt:
                continue

            texts_for_doc_hash.append(txt)

            if self.doc_route == "C":
                continue  # fixed windows later

            if tag == "li":
                flush_paragraph(f"• {txt}", "li")
            elif tag in {"p", "blockquote", "pre", "figure"}:
                flush_paragraph(txt, tag)
            elif tag in {"section", "article", "div", "aside", "header", "footer", "main", "span", "a", "em", "strong"}:
                if estimate_word_count(txt) >= max(2 * self.min_paragraph_words, self.min_block_words):
                    flush_paragraph(txt, tag)

        # Fixed windows for route C
        fixed_text = " ".join(texts_for_doc_hash)
        if self.doc_route == "C" and fixed_text:
            words = fixed_text.split()
            window, overlap = 120, 20
            i = 0
            while i < len(words):
                chunk_words = words[i:i+window]
                if len(chunk_words) >= self.min_paragraph_words:
                    flush_paragraph(" ".join(chunk_words), "fixed_window")
                i += (window - overlap)

        # Aggressive fallbacks
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

        if not any(c for c in self.chunks if c.get("chapter_href") == href):
            for el in soup.find_all(True, recursive=True):
                if is_heading_tag((el.name or "").lower()):
                    continue
                txt = clean_text(el.get_text(" "))
                if txt and estimate_word_count(txt) >= max(3, self.min_paragraph_words):
                    flush_paragraph(txt, f"fallback:{(el.name or 'node')}")

        # Optional debug dump (prefixed with file base)
        if self.debug_dump:
            try:
                os.makedirs("./debug", exist_ok=True)
                file_base = os.path.splitext(os.path.basename(self.epub_path))[0]
                raw_txt = clean_text((soup.get_text(" ") or "")[:2000])
                with open(f"./debug/{file_base}_{order_idx:03d}_{os.path.basename(href) or 'doc'}.raw.txt", "w", encoding="utf-8") as f:
                    f.write(raw_txt)
                from collections import Counter
                tag_counts = Counter([el.name.lower() for el in soup.find_all(True)])
                stats = {
                    "file": os.path.basename(self.epub_path),
                    "href": href,
                    "order_idx": order_idx,
                    "body_present": bool(soup.find('body')),
                    "total_text_len": len(soup.get_text(" ") or ""),
                    "first_300_text": raw_txt[:300],
                    "tag_counts_top10": dict(tag_counts.most_common(10)),
                    "p_count": len(soup.find_all("p")),
                    "div_count": len(soup.find_all("div")),
                    "li_count": len(soup.find_all("li")),
                    "span_count": len(soup.find_all("span")),
                    "a_count": len(soup.find_all("a")),
                }
                with open(f"./debug/{file_base}_{order_idx:03d}_{os.path.basename(href) or 'doc'}.stats.json", "w", encoding="utf-8") as f:
                    f.write(json.dumps(stats, ensure_ascii=False, indent=2))
            except Exception as _e:
                LOGGER.debug("debug dump failed for %s: %s", href, _e)

        return href, global_para_id, " ".join(texts_for_doc_hash)

    # ---------- outputs ----------

    def write_outputs(self, base_filename: Optional[str] = None, ndjson: bool = False, output_dir: Optional[str] = None):
        base = base_filename or os.path.splitext(os.path.basename(self.epub_path))[0]
        outdir = output_dir or "."
        os.makedirs(outdir, exist_ok=True)

        data = {
            "metadata": self.metadata,
            "chunks": self.chunks,
            "extraction_info": {
                "total_paragraphs": len(self.chunks),
                "extraction_date": datetime.now().isoformat(),
                "source_file": os.path.basename(self.epub_path),
                "parser_version": PARSER_VERSION,
                "md_schema_version": MD_SCHEMA_VERSION,
                "route": self.doc_route,
                "quality_score": round(self.doc_quality_score, 4),
            },
        }

        json_out = os.path.join(outdir, f"{base}.json")
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        LOGGER.info("✓ Saved data to %s", json_out)

        md_out = os.path.join(outdir, f"{base}_metadata.json")
        with open(md_out, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        LOGGER.info("✓ Saved metadata to %s", md_out)

        rep_out = os.path.join(outdir, f"{base}_hierarchy_report.txt")
        self._write_hierarchy_report(rep_out)

        if ndjson:
            self.write_chunks_ndjson(os.path.join(outdir, f"{base}.ndjson"))

    def write_chunks_ndjson(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            for ch in self.chunks:
                f.write(json.dumps(ch, ensure_ascii=False) + "\n")
        LOGGER.info("✓ Saved chunks NDJSON to %s", path)

    def _write_hierarchy_report(self, filename: str):
        if not self.chunks:
            return
        structures: OrderedDict = OrderedDict()
        for ch in self.chunks:
            h = ch["hierarchy"]
            key = tuple(h.get(f"level_{i}", "") for i in range(1, 7))
            structures.setdefault(key, []).append(ch["paragraph_id"])

        lines: List[str] = []
        lines.append("EPUB HIERARCHICAL STRUCTURE REPORT")
        lines.append("=" * 70)
        lines.append(f"Source: {os.path.basename(self.epub_path)}")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("DOCUMENT METADATA:")
        lines.append("-" * 20)
        for k, v in self.metadata.items():
            if v:
                if isinstance(v, list):
                    v_str = ", ".join(v) if len(v) <= 3 else f"{', '.join(v[:3])}... ({len(v)} total)"
                elif isinstance(v, dict):
                    js = json.dumps(v)
                    v_str = js[:180] + ("…" if len(js) > 180 else "")
                else:
                    v_str = str(v)
                lines.append(f"{k.replace('_', ' ').title()}: {v_str}")
        lines.append("")
        lines.append("STRUCTURE TREE:")
        lines.append("-" * 15)
        for path, para_ids in structures.items():
            if not any(path):
                continue
            para_range = f"{min(para_ids)}-{max(para_ids)}" if para_ids else ""
            word_count = sum(ch["word_count"] for ch in self.chunks if ch["paragraph_id"] in para_ids)
            for i, level_text in enumerate(path, 1):
                if level_text:
                    indent = "  " * (i - 1)
                    prefix = "└─ " if i > 1 else ""
                    lines.append(f"{indent}{prefix}{level_text}")
            indent = "  " * len([t for t in path if t])
            lines.append(f"{indent}[¶ {para_range}, ~{word_count} words]")
            lines.append("")
        lines.append("SUMMARY:")
        lines.append("-" * 10)
        lines.append(f"Total unique hierarchy paths: {len(structures)}")
        lines.append(f"Total paragraphs: {len(self.chunks)}")
        lines.append(f"Total words: {sum(ch['word_count'] for ch in self.chunks):,}")

        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        LOGGER.info("✓ Created %s", filename)

# ====================== CLI ======================

def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="Parse an EPUB or a folder of EPUBs into hierarchical chunks with quality routing, provenance, and Catholic cross-refs."
    )
    ap.add_argument("path", nargs="?", default="", help="Path to .epub file OR a directory of .epub files")
    ap.add_argument("--output", "-o", help="Base name for output files (single-file mode only)")
    ap.add_argument("--output-dir", help="Directory to write outputs (defaults to current working directory)")
    ap.add_argument("--recursive", action="store_true", help="When a directory is provided, include subfolders")
    ap.add_argument("--toc-level", type=int, default=3, help="Hierarchy level for TOC titles (1-6)")
    ap.add_argument("--min-words", type=int, default=6, help="Minimum words for paragraph inclusion")
    ap.add_argument("--min-block-words", type=int, default=30, help="Min words to chunk generic block tags (div/section/article)")
    ap.add_argument("--preserve-hierarchy", action="store_true", help="Preserve hierarchy across spine documents")
    ap.add_argument("--reset-depth", type=int, default=2, help="On doc boundary, clear levels >= this depth (1-6)")
    ap.add_argument("--deny-class", default=r'^(?:calibre\d+|note|footnote)$', help="Regex for class denylist")
    ap.add_argument("--ndjson", action="store_true", help="Also emit a chunks .ndjson")
    ap.add_argument("--verbose", action="store_true", help="Verbose logging")
    ap.add_argument("--quiet", action="store_true", help="Only warnings and errors")
    ap.add_argument("--debug-dump", action="store_true", help="Write raw per-spine text and DOM stats to ./debug/")

    args = ap.parse_args()
    setup_logging(verbose=args.verbose, quiet=args.quiet)

    in_path = args.path.strip() or input("Enter path to .epub OR folder (or drag-drop): ").strip()
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
    }

    def process_one(epub_path: str):
        parser_obj = EpubParser(epub_path, config)
        parser_obj.debug_dump = args.debug_dump
        try:
            parser_obj.load()
            parser_obj.parse()
            parser_obj.write_outputs(
                base_filename=(args.output if os.path.isfile(in_path) else None),
                ndjson=args.ndjson,
                output_dir=args.output_dir,
            )
            base = os.path.splitext(os.path.basename(epub_path))[0] if not args.output else args.output
            outdir = args.output_dir or "."
            print(f"\n✅ {os.path.basename(epub_path)}")
            print(f"   • paragraphs: {len(parser_obj.chunks)}   quality: {round(parser_obj.doc_quality_score, 3)} (route {parser_obj.doc_route})")
            print(f"   • outputs: {os.path.join(outdir, base)}.json, {base}_metadata.json, {base}_hierarchy_report.txt" + (f", {base}.ndjson" if args.ndjson else ""))
        except Exception as e:
            LOGGER.exception("Failed on %s: %s", epub_path, e)
            return False
        return True

    # Single-file mode
    if os.path.isfile(in_path):
        if not in_path.lower().endswith(".epub"):
            LOGGER.warning("The file does not look like an .epub; continuing anyway...")
        ok = process_one(in_path)
        return 0 if ok else 1

    # Directory mode
    epubs: List[str] = []
    if args.recursive:
        for root, _, files in os.walk(in_path):
            for fn in files:
                if fn.lower().endswith(".epub"):
                    epubs.append(os.path.join(root, fn))
    else:
        epubs = [os.path.join(in_path, fn) for fn in os.listdir(in_path) if fn.lower().endswith(".epub")]

    if not epubs:
        LOGGER.error("No .epub files found in the provided directory%s.", " (recursive)" if args.recursive else "")
        return 2

    print(f"Found {len(epubs)} EPUBs. Processing...")
    successes = 0
    for p in tqdm(epubs, desc="Batch"):
        if process_one(p):
            successes += 1

    print(f"\nDone. {successes}/{len(epubs)} EPUBs processed successfully.")
    return 0 if successes == len(epubs) else 1

if __name__ == "__main__":
    sys.exit(main())
