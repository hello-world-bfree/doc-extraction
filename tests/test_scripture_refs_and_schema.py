#!/usr/bin/env python3
"""Tests for Tier 3 fixes.

Covers: scripture false positives, AAS citations, infra/supra abbreviations,
schema version bump, by_sentence footnote offset, concurrency patterns.
"""

import pytest

from extraction.core.extraction import (
    extract_scripture_references,
    extract_cross_references,
)
from extraction.core.chunking import split_sentences, ABBREVIATIONS
from extraction.core.strategies import SemanticChunkingStrategy, ChunkConfig


def _make_chunk(paragraph_id, text, hierarchy=None, **overrides):
    base = {
        'paragraph_id': paragraph_id,
        'text': text,
        'word_count': len(text.split()),
        'hierarchy': hierarchy or {'level_1': 'Chapter', 'level_2': 'Section'},
        'chapter_href': 'ch1.html',
        'source_order': paragraph_id,
        'source_tag': 'p',
        'text_length': len(text),
        'cross_references': [],
        'scripture_references': [],
        'dates_mentioned': [],
        'heading_path': '',
        'hierarchy_depth': 2,
        'doc_stable_id': 'doc1',
        'sentence_count': 1,
        'sentences': [text],
        'normalized_text': text.lower(),
    }
    base.update(overrides)
    return base


class TestScriptureFalsePositives:

    def test_rejects_note_reference(self):
        text = "See Note 3:4 for details."
        refs = extract_scripture_references(text)
        assert not any("Note" in r for r in refs)

    def test_rejects_section_reference(self):
        text = "Refer to Section 2:1 of the document."
        refs = extract_scripture_references(text)
        assert not any("Section" in r for r in refs)

    def test_rejects_chapter_reference(self):
        text = "See Chapter 5:3 for more information."
        refs = extract_scripture_references(text)
        assert not any("Chapter" in r for r in refs)

    def test_rejects_table_reference(self):
        text = "Table 1:2 shows the data."
        refs = extract_scripture_references(text)
        assert not any("Table" in r for r in refs)

    def test_rejects_figure_reference(self):
        text = "Figure 3:1 illustrates the concept."
        refs = extract_scripture_references(text)
        assert not any("Figure" in r for r in refs)

    def test_still_matches_real_scripture(self):
        text = "John 3:16 is a well-known verse."
        refs = extract_scripture_references(text)
        assert any("John 3:16" in r for r in refs)

    def test_still_matches_numbered_books(self):
        text = "1 Corinthians 13:1-13 speaks of love."
        refs = extract_scripture_references(text)
        assert len(refs) >= 1

    def test_still_matches_abbreviated_books(self):
        text = "See Mt 5:3-12 for the Beatitudes."
        refs = extract_scripture_references(text)
        assert any("Mt" in r for r in refs)

    def test_still_matches_old_testament(self):
        text = "Genesis 1:1 begins with creation."
        refs = extract_scripture_references(text)
        assert len(refs) >= 1

    def test_rejects_art_reference(self):
        text = "See Art. 3:4 of the canonical legislation."
        refs = extract_scripture_references(text)
        assert not any("Art" in r for r in refs)

    def test_rejects_item_reference(self):
        text = "Item 2:3 in the list is important."
        refs = extract_scripture_references(text)
        assert not any("Item" in r for r in refs)


class TestAASCitationPattern:

    def test_matches_standard_aas_citation(self):
        text = "See AAS 57 (1965) 105 for the official text."
        refs = extract_cross_references(text)
        assert any("AAS" in r for r in refs)

    def test_matches_aas_with_longer_volume(self):
        text = "Published in AAS 102 (2010) 345."
        refs = extract_cross_references(text)
        assert any("AAS" in r for r in refs)

    def test_no_match_without_page_number(self):
        text = "The AAS journal publishes official acts."
        refs = extract_cross_references(text)
        assert not any("AAS" in r for r in refs)


class TestInfraSupraAbbreviations:

    def test_infra_in_abbreviations(self):
        assert 'infra' in ABBREVIATIONS

    def test_supra_in_abbreviations(self):
        assert 'supra' in ABBREVIATIONS

    def test_infra_protected_in_splitting(self):
        text = "See infra. The following section discusses this in detail."
        result = split_sentences(text)
        assert "infra." in result[0]

    def test_supra_protected_in_splitting(self):
        text = "As noted supra. This argument was already established."
        result = split_sentences(text)
        assert "supra." in result[0]


class TestSchemaVersionBump:

    def test_html_schema_version(self):
        from extraction.extractors.html import MD_SCHEMA_VERSION
        assert MD_SCHEMA_VERSION == "2026-03-21"

    def test_epub_schema_version(self):
        from extraction.extractors.epub import MD_SCHEMA_VERSION
        assert MD_SCHEMA_VERSION == "2026-03-21"

    def test_pdf_schema_version(self):
        from extraction.extractors.pdf import MD_SCHEMA_VERSION
        assert MD_SCHEMA_VERSION == "2026-03-21"

    def test_pdf_mupdf_schema_version(self):
        from extraction.extractors.pdf_mupdf import MD_SCHEMA_VERSION
        assert MD_SCHEMA_VERSION == "2026-03-21"

    def test_json_schema_version(self):
        from extraction.extractors.json import MD_SCHEMA_VERSION
        assert MD_SCHEMA_VERSION == "2026-03-21"

    def test_markdown_schema_version(self):
        from extraction.extractors.markdown import MD_SCHEMA_VERSION
        assert MD_SCHEMA_VERSION == "2026-03-21"


class TestBySentenceFootnoteOffset:

    def test_indices_offset_on_merge(self):
        chunks = [
            _make_chunk(
                1, "First paragraph has three sentences here. Second sentence follows. Third wraps it up.",
                sentences=["First paragraph has three sentences here.", "Second sentence follows.", "Third wraps it up."],
                sentence_count=3,
                footnote_citations={
                    'all': [1],
                    'by_sentence': [{'index': 0, 'numbers': [1]}],
                },
            ),
            _make_chunk(
                2, "Fourth sentence starts new chunk. Fifth sentence has footnote reference.",
                sentences=["Fourth sentence starts new chunk.", "Fifth sentence has footnote reference."],
                sentence_count=2,
                footnote_citations={
                    'all': [2],
                    'by_sentence': [{'index': 1, 'numbers': [2]}],
                },
            ),
        ]
        strategy = SemanticChunkingStrategy()
        config = ChunkConfig(min_words=5, max_words=500)
        result = strategy.apply(chunks, config)

        assert len(result) == 1
        fc = result[0]['footnote_citations']
        by_sent = fc['by_sentence']

        assert by_sent[0]['index'] == 0
        assert by_sent[1]['index'] == 4

    def test_no_offset_for_first_chunk(self):
        chunks = [
            _make_chunk(
                1, "Only one chunk with enough words for the minimum threshold.",
                sentences=["Only one chunk with enough words for the minimum threshold."],
                sentence_count=1,
                footnote_citations={
                    'all': [1],
                    'by_sentence': [{'index': 0, 'numbers': [1]}],
                },
            ),
        ]
        strategy = SemanticChunkingStrategy()
        config = ChunkConfig(min_words=5, max_words=500)
        result = strategy.apply(chunks, config)

        fc = result[0]['footnote_citations']
        assert fc['by_sentence'][0]['index'] == 0

    def test_handles_missing_by_sentence(self):
        chunks = [
            _make_chunk(
                1, "First paragraph with enough words to meet the minimum threshold.",
                footnote_citations={'all': [1], 'by_sentence': []},
            ),
            _make_chunk(
                2, "Second paragraph with enough words also meeting the threshold.",
                footnote_citations={'all': [2], 'by_sentence': []},
            ),
        ]
        strategy = SemanticChunkingStrategy()
        config = ChunkConfig(min_words=5, max_words=500)
        result = strategy.apply(chunks, config)

        fc = result[0]['footnote_citations']
        assert fc['all'] == [1, 2]
        assert fc['by_sentence'] == []


class TestConcurrencyImports:

    def test_process_pool_available(self):
        from concurrent.futures import ProcessPoolExecutor
        assert ProcessPoolExecutor is not None

    def test_thread_pool_available(self):
        from concurrent.futures import ThreadPoolExecutor
        assert ThreadPoolExecutor is not None

    def test_s3_uploader_has_upload_images(self):
        from extraction.storage.s3_uploader import S3Uploader
        assert hasattr(S3Uploader, 'upload_images')

    def test_batch_process_function_exists(self):
        from extraction.cli.extract import process_batch
        assert callable(process_batch)
