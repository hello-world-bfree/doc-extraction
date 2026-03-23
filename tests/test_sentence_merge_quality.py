#!/usr/bin/env python3
"""Tests for Tier 1 and Tier 2 bug fixes.

Covers: sentence splitting, merge correctness, noise filter, regex precompilation,
reference dedup ordering, streaming provenance hash, full_text reuse.
"""

import hashlib
import io
import pytest
from pathlib import Path

from extraction.core.chunking import split_sentences, ABBREVIATIONS
from extraction.core.strategies import SemanticChunkingStrategy, ChunkConfig
from extraction.core.extraction import (
    extract_dates,
    extract_scripture_references,
    extract_cross_references,
)
from extraction.core.text import clean_text, estimate_word_count
from extraction.core.noise_filter import NoiseFilter
from extraction.core.models import Chunk


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


class TestSentenceSplitter:

    def test_basic_split(self):
        result = split_sentences("Hello world. This is a test.")
        assert len(result) == 2

    def test_protects_st_abbreviation(self):
        text = "St. Thomas Aquinas wrote extensively. His work endures."
        result = split_sentences(text)
        assert len(result) == 2
        assert result[0] == "St. Thomas Aquinas wrote extensively."

    def test_protects_cf_abbreviation(self):
        text = "cf. CIC can. 917. The regulation applies."
        result = split_sentences(text)
        assert "cf." in result[0]

    def test_protects_ibid(self):
        text = "See ibid. The same source confirms this claim."
        result = split_sentences(text)
        assert len(result) == 1
        assert "ibid." in result[0]

    def test_protects_ie_eg(self):
        text = "Some animals, i.e. Cats, are common. They live indoors."
        result = split_sentences(text)
        assert "i.e." in result[0]

    def test_protects_bible_abbreviations(self):
        text = "See Mt. 5:3 for reference. The Beatitudes are important."
        result = split_sentences(text)
        assert "Mt." in result[0]

    def test_protects_ff(self):
        text = "See pp. 42 ff. The discussion continues in detail."
        result = split_sentences(text)
        assert "ff." in result[0]

    def test_protects_rev_fr(self):
        text = "Rev. Fr. Smith celebrated Mass. The parish was grateful."
        result = split_sentences(text)
        assert "Rev. Fr. Smith" in result[0]

    def test_protects_deuterocanonical_books(self):
        text = "Sir. 24:3 speaks of wisdom. Wis. 7:26 echoes this theme."
        result = split_sentences(text)
        assert "Sir." in result[0]
        assert "Wis." in result[1]

    def test_can_removed_allows_split(self):
        text = "We did what we can. The Church teaches differently."
        result = split_sentences(text)
        assert len(result) == 2
        assert result[1].startswith("The Church")

    def test_single_sentence(self):
        result = split_sentences("Just one sentence here")
        assert len(result) == 1

    def test_empty_string(self):
        result = split_sentences("")
        assert result == []

    def test_no_empty_strings_in_output(self):
        result = split_sentences("Hello.  World.")
        assert all(s.strip() for s in result)

    def test_consecutive_abbreviations(self):
        text = "cf. St. Thomas argues convincingly. His logic is sound."
        result = split_sentences(text)
        assert "cf. St. Thomas" in result[0]

    def test_abbreviations_frozenset_contains_deuterocanonicals(self):
        for book in ['Sir', 'Wis', 'Tob', 'Jdt', 'Bar', 'Macc']:
            assert book in ABBREVIATIONS

    def test_can_not_in_abbreviations(self):
        assert 'can' not in ABBREVIATIONS

    def test_ff_in_abbreviations(self):
        assert 'ff' in ABBREVIATIONS

    def test_pp_in_abbreviations(self):
        assert 'pp' in ABBREVIATIONS


class TestMergeOptionalFieldAggregation:

    def test_footnotes_aggregated_from_all_source_chunks(self):
        chunks = [
            _make_chunk(1, "First paragraph with enough words to meet the minimum threshold.",
                        footnote_citations={'all': [1, 2], 'by_sentence': []}),
            _make_chunk(2, "Second paragraph with enough words and more content here for testing.",
                        footnote_citations={'all': [3], 'by_sentence': []}),
        ]
        strategy = SemanticChunkingStrategy()
        config = ChunkConfig(min_words=5, max_words=500)
        result = strategy.apply(chunks, config)

        assert len(result) == 1
        fc = result[0].get('footnote_citations')
        assert fc is not None
        assert fc['all'] == [1, 2, 3]

    def test_resolved_footnotes_merged(self):
        chunks = [
            _make_chunk(1, "First paragraph with enough words to meet the minimum threshold.",
                        resolved_footnotes={'1': 'Note one'}),
            _make_chunk(2, "Second paragraph also long enough for testing and meeting threshold.",
                        resolved_footnotes={'2': 'Note two'}),
        ]
        strategy = SemanticChunkingStrategy()
        config = ChunkConfig(min_words=5, max_words=500)
        result = strategy.apply(chunks, config)

        rf = result[0].get('resolved_footnotes')
        assert rf == {'1': 'Note one', '2': 'Note two'}

    def test_ocr_conf_averaged(self):
        chunks = [
            _make_chunk(1, "First paragraph with enough words for testing purposes here.",
                        ocr=True, ocr_conf=0.8),
            _make_chunk(2, "Second paragraph also enough words to be merged together here.",
                        ocr=True, ocr_conf=0.6),
        ]
        strategy = SemanticChunkingStrategy()
        config = ChunkConfig(min_words=5, max_words=500)
        result = strategy.apply(chunks, config)

        assert result[0].get('ocr') is True
        assert result[0].get('ocr_conf') == pytest.approx(0.7)

    def test_no_optional_fields_when_absent(self):
        chunks = [
            _make_chunk(1, "First paragraph with enough words to test optional field absence."),
            _make_chunk(2, "Second paragraph has enough words too for the merge threshold."),
        ]
        strategy = SemanticChunkingStrategy()
        config = ChunkConfig(min_words=5, max_words=500)
        result = strategy.apply(chunks, config)

        assert 'footnote_citations' not in result[0]
        assert 'resolved_footnotes' not in result[0]
        assert 'ocr' not in result[0]
        assert 'ocr_conf' not in result[0]


class TestFootnoteCitationsType:

    def test_chunk_accepts_dict_footnote_citations(self):
        chunk = Chunk(
            stable_id='test', paragraph_id=1, text='Hello',
            hierarchy={}, chapter_href='', source_order=1,
            source_tag='p', text_length=5, word_count=1,
            cross_references=[], scripture_references=[],
            dates_mentioned=[], heading_path='', hierarchy_depth=0,
            doc_stable_id='doc1', sentence_count=1, sentences=['Hello'],
            normalized_text='hello',
            footnote_citations={'all': [1, 2], 'by_sentence': []},
        )
        d = chunk.to_dict()
        assert d['footnote_citations'] == {'all': [1, 2], 'by_sentence': []}


class TestWordCountOnMerge:

    def test_word_count_matches_actual_text(self):
        chunks = [
            _make_chunk(1, "First paragraph with ten words in total right here now."),
            _make_chunk(2, "Second paragraph has another set of words for testing merge."),
        ]
        strategy = SemanticChunkingStrategy()
        config = ChunkConfig(min_words=5, max_words=500)
        result = strategy.apply(chunks, config)

        merged = result[0]
        assert merged['word_count'] == estimate_word_count(merged['text'])


class TestHierarchyClearingOnMerge:

    def test_deep_levels_cleared(self):
        chunks = [
            _make_chunk(1, "First paragraph with enough words to meet the threshold.",
                        hierarchy={'level_1': 'Book', 'level_2': 'Ch', 'level_3': 'Sec', 'level_4': 'A'}),
            _make_chunk(2, "Second paragraph with enough words also meeting the threshold.",
                        hierarchy={'level_1': 'Book', 'level_2': 'Ch', 'level_3': 'Sec', 'level_4': 'B'}),
        ]
        strategy = SemanticChunkingStrategy()
        config = ChunkConfig(min_words=5, max_words=500, preserve_hierarchy_levels=3)
        result = strategy.apply(chunks, config)

        h = result[0]['hierarchy']
        assert h['level_1'] == 'Book'
        assert h['level_2'] == 'Ch'
        assert h['level_3'] == 'Sec'
        assert h['level_4'] == ''
        assert h['level_5'] == ''
        assert h['level_6'] == ''


class TestOrderPreservingReferenceDedup:

    def test_preserves_document_order(self):
        chunks = [
            _make_chunk(1, "First paragraph has enough words for the merge to work.",
                        cross_references=['CCC 100', 'canon 5'],
                        scripture_references=['John 3:16', 'Mt 5:3']),
            _make_chunk(2, "Second paragraph also has enough words and repeats a reference.",
                        cross_references=['canon 5', 'CCC 200'],
                        scripture_references=['Mt 5:3', 'Rom 8:28']),
        ]
        strategy = SemanticChunkingStrategy()
        config = ChunkConfig(min_words=5, max_words=500)
        result = strategy.apply(chunks, config)

        merged = result[0]
        assert merged['cross_references'] == ['CCC 100', 'canon 5', 'CCC 200']
        assert merged['scripture_references'] == ['John 3:16', 'Mt 5:3', 'Rom 8:28']


class TestNoiseFilterNotesRestriction:

    def test_notes_at_level_1_filtered(self):
        chunk = _make_chunk(1, "Some notes content here.",
                            hierarchy={'level_1': 'Notes', 'level_2': ''})
        is_fm, reason = NoiseFilter.is_front_matter(chunk)
        assert is_fm is True

    def test_notes_at_level_2_not_filtered(self):
        chunk = _make_chunk(1, "Study notes for this chapter with lots of content.",
                            hierarchy={'level_1': 'Chapter 5', 'level_2': 'Study Notes'})
        is_fm, reason = NoiseFilter.is_front_matter(chunk)
        assert is_fm is False

    def test_endnotes_at_level_2_caught_by_pattern4(self):
        chunk = _make_chunk(1, "Endnotes section content here.",
                            hierarchy={'level_1': 'Appendix', 'level_2': 'Endnotes'})
        is_fm, reason = NoiseFilter.is_front_matter(chunk)
        assert is_fm is True

    def test_chapter_notes_at_level_2_not_filtered(self):
        chunk = _make_chunk(1, "Chapter notes with important content for studying.",
                            hierarchy={'level_1': 'Chapter 3', 'level_2': 'Chapter Notes'})
        is_fm, reason = NoiseFilter.is_front_matter(chunk)
        assert is_fm is False


class TestRegexPrecompilation:

    def test_extract_dates_produces_results(self):
        text = "On January 15, 2023, the decree was issued. Also referenced is 2023-01-15."
        dates = extract_dates(text)
        assert len(dates) >= 2

    def test_extract_scripture_refs_produces_results(self):
        text = "See John 3:16 and Mt 5:3-12 for reference."
        refs = extract_scripture_references(text)
        assert len(refs) >= 2

    def test_extract_cross_refs_produces_results(self):
        text = "See CCC 2309 and cf. section 5 of the document. Vatican II is referenced."
        refs = extract_cross_references(text)
        assert len(refs) >= 1

    def test_clean_text_preserves_behavior(self):
        text = "  Hello\u00ad\u200B  world  "
        result = clean_text(text)
        assert result == "Hello world"


class TestStreamingProvenanceHash:

    def test_file_digest_matches_sha1(self):
        data = b"test document content for hashing"
        legacy_hash = hashlib.sha1(data).hexdigest()
        streaming_hash = hashlib.file_digest(io.BytesIO(data), "sha1").hexdigest()
        assert legacy_hash == streaming_hash

    def test_html_extractor_provenance(self, tmp_path):
        from extraction.extractors.html import HtmlExtractor
        from extraction.extractors.configs import HtmlExtractorConfig

        html_file = tmp_path / "test.html"
        html_file.write_text("""
        <html><body>
            <h1>Title</h1>
            <p>This is content with enough words to be extracted as a chunk.</p>
        </body></html>
        """)
        config = HtmlExtractorConfig(chunking_strategy='nlp', filter_noise=False)
        extractor = HtmlExtractor(str(html_file), config)
        extractor.load()
        assert extractor.provenance.content_hash is not None
        assert len(extractor.provenance.content_hash) == 40

    def test_set_provenance_requires_hash_or_bytes(self):
        from extraction.extractors.html import HtmlExtractor
        from extraction.extractors.configs import HtmlExtractorConfig

        html_file = Path("/nonexistent_for_init.html")
        extractor = HtmlExtractor(str(html_file), HtmlExtractorConfig())
        with pytest.raises(ValueError, match="Either source_bytes or content_hash"):
            extractor._set_provenance(
                parser_version="test",
                md_schema_version="test",
            )

    def test_content_hash_kwarg_takes_precedence(self):
        from extraction.extractors.html import HtmlExtractor
        from extraction.extractors.configs import HtmlExtractorConfig

        html_file = Path("/tmp/test_precedence.html")
        html_file.write_text("<html></html>")
        try:
            extractor = HtmlExtractor(str(html_file), HtmlExtractorConfig())
            extractor._set_provenance(
                parser_version="test",
                md_schema_version="test",
                source_bytes=b"different content",
                content_hash="abc123",
            )
            assert extractor.provenance.content_hash == "abc123"
        finally:
            html_file.unlink(missing_ok=True)


class TestFullTextReuse:

    def test_full_text_used_in_metadata(self, tmp_path):
        from extraction.extractors.html import HtmlExtractor
        from extraction.extractors.configs import HtmlExtractorConfig

        html_file = tmp_path / "test.html"
        html_file.write_text("""
        <html><head><title>Test Document</title></head><body>
            <h1>Test Document</h1>
            <p>This paragraph has enough words to be extracted properly as a chunk.</p>
            <p>A second paragraph also has enough words to meet the minimum threshold.</p>
        </body></html>
        """)
        config = HtmlExtractorConfig(chunking_strategy='nlp', filter_noise=False)
        extractor = HtmlExtractor(str(html_file), config)
        extractor.load()
        extractor.parse()
        metadata = extractor.extract_metadata()
        assert metadata is not None
        assert metadata.title == "Test Document"


class TestEpubSentencesNotTruncated:

    def test_long_paragraph_keeps_all_sentences(self, tmp_path):
        from extraction.extractors.html import HtmlExtractor
        from extraction.extractors.configs import HtmlExtractorConfig

        sentences = [f"Sentence number {i} has enough words." for i in range(1, 12)]
        paragraph = " ".join(sentences)

        html_file = tmp_path / "test.html"
        html_file.write_text(f"""
        <html><body>
            <p>{paragraph}</p>
        </body></html>
        """)
        config = HtmlExtractorConfig(chunking_strategy='nlp', filter_noise=False)
        extractor = HtmlExtractor(str(html_file), config)
        extractor.load()
        extractor.parse()

        for chunk in extractor.chunks:
            assert chunk.sentence_count == len(chunk.sentences)


class TestEmergencySplitPath:

    def test_uses_split_sentences_not_naive_split(self):
        text = "St. Thomas Aquinas wrote extensively. His work was groundbreaking. It influenced many scholars."
        result = split_sentences(text)
        assert "St. Thomas" in result[0]
        assert len(result) == 3


class TestQualitySignalExpansion:

    def test_lang_prob_uses_original_latin_keywords(self):
        from extraction.core.quality import quality_signals_from_text
        text = "Dei Verbum and Ecclesia are central to the Magisterium of the Apostolica."
        signals = quality_signals_from_text(text)
        assert signals['lang_prob'] == pytest.approx(min(1.0, 0.5 + 0.05 * 5))

    def test_lang_prob_floor_is_0_5(self):
        from extraction.core.quality import quality_signals_from_text
        text = "Generic text with no theological terms at all just normal words."
        signals = quality_signals_from_text(text)
        assert signals['lang_prob'] == pytest.approx(0.5)

    def test_lang_prob_v2_responds_to_english_catholic_terms(self):
        from extraction.core.quality import quality_signals_from_text
        text = "The Eucharist is a sacrament of great importance in the liturgy of the parish and diocese."
        signals = quality_signals_from_text(text)
        assert signals['lang_prob_v2'] > 0.3

    def test_lang_prob_v2_floor_is_0_3(self):
        from extraction.core.quality import quality_signals_from_text
        text = "Generic text with no theological terms at all just normal words."
        signals = quality_signals_from_text(text)
        assert signals['lang_prob_v2'] == pytest.approx(0.3)

    def test_lang_prob_v2_case_insensitive(self):
        from extraction.core.quality import quality_signals_from_text
        text = "The eucharist and the sacrament of ordination are important."
        signals = quality_signals_from_text(text)
        assert signals['lang_prob_v2'] > 0.3

    def test_lang_prob_unchanged_for_route_stability(self):
        from extraction.core.quality import quality_signals_from_text, score_quality, route_doc
        text = "Clean document text with proper formatting. " * 50
        signals = quality_signals_from_text(text)
        assert signals['lang_prob'] == pytest.approx(0.5)
        score = score_quality(signals)
        assert score >= 0.80
        assert route_doc(score) == "A"

    def test_lang_prob_v2_not_used_in_scoring(self):
        from extraction.core.quality import quality_signals_from_text, score_quality
        text = "The Eucharist and sacrament of liturgy in the diocese."
        signals = quality_signals_from_text(text)
        score_with = score_quality(signals)
        signals_without_v2 = {k: v for k, v in signals.items() if k != 'lang_prob_v2'}
        score_without = score_quality(signals_without_v2)
        assert score_with == score_without


class TestObservationModeSignals:

    def test_lexical_density_present(self):
        from extraction.core.quality import quality_signals_from_text
        text = "The quick brown fox jumps over the lazy dog near the old barn."
        signals = quality_signals_from_text(text)
        assert 'lexical_density' in signals
        assert 0.0 < signals['lexical_density'] <= 1.0

    def test_short_line_ratio_present(self):
        from extraction.core.quality import quality_signals_from_text
        text = "Short\nAlso short\nVery short\nAnother"
        signals = quality_signals_from_text(text)
        assert 'short_line_ratio' in signals
        assert signals['short_line_ratio'] > 0.5

    def test_lexical_density_high_for_prose(self):
        from extraction.core.quality import quality_signals_from_text
        text = "Philosophy examines fundamental questions about existence knowledge values reason."
        signals = quality_signals_from_text(text)
        assert signals['lexical_density'] > 0.7

    def test_lexical_density_low_for_repetitive(self):
        from extraction.core.quality import quality_signals_from_text
        text = "the the the the the the the the the the the the the the the"
        signals = quality_signals_from_text(text)
        assert signals['lexical_density'] < 0.2

    def test_short_line_ratio_zero_for_long_lines(self):
        from extraction.core.quality import quality_signals_from_text
        text = "This is a very long line that clearly exceeds the forty character threshold for being short.\n"
        text += "Another very long line that also exceeds the forty character threshold significantly.\n"
        signals = quality_signals_from_text(text)
        assert signals['short_line_ratio'] == 0.0

    def test_observation_signals_in_empty_text(self):
        from extraction.core.quality import quality_signals_from_text
        signals = quality_signals_from_text("")
        assert signals['lexical_density'] == 0.0
        assert signals['short_line_ratio'] == 0.0
        assert signals['lang_prob_v2'] == 0.0

    def test_observation_signals_not_in_score_formula(self):
        from extraction.core.quality import quality_signals_from_text, score_quality
        text = "Normal text with enough content for quality scoring purposes here."
        signals = quality_signals_from_text(text)
        score_with = score_quality(signals)
        scoring_only = {k: v for k, v in signals.items()
                       if k in ('garble_rate', 'mean_conf', 'line_len_std_norm', 'lang_prob')}
        score_without = score_quality(scoring_only)
        assert score_with == score_without

    def test_all_signals_bounded_0_to_1(self):
        from extraction.core.quality import quality_signals_from_text
        texts = [
            "Simple text",
            "A" * 5000,
            "Short\nlines\nhere",
            "the the the the the the",
        ]
        for text in texts:
            signals = quality_signals_from_text(text)
            for name, value in signals.items():
                assert 0.0 <= value <= 1.0, f"{name}={value} out of bounds for: {text[:30]}"


class TestLxmlBackendSwap:

    def test_html_extractor_uses_lxml(self, tmp_path):
        from extraction.extractors.html import HtmlExtractor
        from extraction.extractors.configs import HtmlExtractorConfig

        html_file = tmp_path / "test.html"
        html_file.write_text("""
        <html><head><title>Test</title></head><body>
            <h1>Main Title</h1>
            <p>A paragraph with enough words to be extracted as a valid chunk.</p>
            <h2>Subsection</h2>
            <p>Another paragraph under a subsection heading with sufficient words.</p>
        </body></html>
        """)
        config = HtmlExtractorConfig(chunking_strategy='nlp', filter_noise=False)
        extractor = HtmlExtractor(str(html_file), config)
        extractor.load()
        extractor.parse()

        assert len(extractor.chunks) >= 2

    def test_lxml_handles_unclosed_tags(self, tmp_path):
        from extraction.extractors.html import HtmlExtractor
        from extraction.extractors.configs import HtmlExtractorConfig

        html_file = tmp_path / "messy.html"
        html_file.write_text("""
        <html><body>
            <p>Paragraph one with unclosed tag and enough words for extraction.
            <p>Paragraph two also unclosed but should still be parsed correctly.
            <p>Third paragraph has enough words to meet the minimum word threshold.
        </body></html>
        """)
        config = HtmlExtractorConfig(chunking_strategy='nlp', filter_noise=False)
        extractor = HtmlExtractor(str(html_file), config)
        extractor.load()
        extractor.parse()

        assert len(extractor.chunks) >= 1

    def test_lxml_preserves_heading_hierarchy(self, tmp_path):
        from extraction.extractors.html import HtmlExtractor
        from extraction.extractors.configs import HtmlExtractorConfig

        html_file = tmp_path / "hierarchy.html"
        html_file.write_text("""
        <html><body>
            <h1>Top Level</h1>
            <h2>Second Level</h2>
            <p>Content under second level heading with enough words for extraction.</p>
            <h3>Third Level</h3>
            <p>Content under third level heading also with sufficient word count.</p>
        </body></html>
        """)
        config = HtmlExtractorConfig(chunking_strategy='nlp', filter_noise=False)
        extractor = HtmlExtractor(str(html_file), config)
        extractor.load()
        extractor.parse()

        chunks = extractor.chunks
        assert any(c.hierarchy.get('level_1') == 'Top Level' for c in chunks)
        assert any(c.hierarchy.get('level_2') == 'Second Level' for c in chunks)

    def test_lxml_vs_html_parser_equivalence(self, tmp_path):
        """Qualification test: verify lxml produces same text as html.parser."""
        from bs4 import BeautifulSoup

        html_content = """
        <html><head><title>Test</title></head><body>
            <h1>Heading One</h1>
            <p>First paragraph with enough content for testing purposes and comparison.</p>
            <h2>Heading Two</h2>
            <p>Second paragraph also has sufficient content for the comparison test.</p>
            <blockquote>A quoted block with enough words to be extracted properly.</blockquote>
        </body></html>
        """
        lxml_soup = BeautifulSoup(html_content, 'lxml')
        html_parser_soup = BeautifulSoup(html_content, 'html.parser')

        tags = ['h1', 'h2', 'p', 'blockquote']
        for tag in tags:
            lxml_elems = lxml_soup.find_all(tag)
            hp_elems = html_parser_soup.find_all(tag)
            assert len(lxml_elems) == len(hp_elems), f"Different count for <{tag}>"
            for le, he in zip(lxml_elems, hp_elems):
                assert le.get_text(strip=True) == he.get_text(strip=True), \
                    f"Text differs for <{tag}>: {le.get_text()!r} vs {he.get_text()!r}"
