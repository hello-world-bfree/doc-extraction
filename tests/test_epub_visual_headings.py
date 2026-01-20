#!/usr/bin/env python3

"""
Unit tests for EPUB visual hierarchy detection.

Tests cover:
- Font-size parsing (em, rem, %, pt, px)
- Threshold checks
- Text-based heading heuristics
- Multi-signal detection
- Level inference
- Integration with chunking
"""

import pytest
from bs4 import BeautifulSoup
from extraction.extractors.epub import EpubExtractor
from extraction.extractors.configs import EpubExtractorConfig


@pytest.fixture
def extractor():
    config = EpubExtractorConfig(detect_visual_headings=True, visual_heading_font_threshold=1.3)
    ext = EpubExtractor.__new__(EpubExtractor)
    ext.config = config
    ext.current_hierarchy = {f"level_{i}": "" for i in range(1, 7)}
    return ext


class TestFontSizeParsing:
    """Test inline font-size parsing."""

    def test_parse_inline_font_size_em(self, extractor):
        style = "font-size: 1.5em; color: red;"
        result = extractor._parse_inline_font_size(style)
        assert result == (1.5, 'em')

    def test_parse_inline_font_size_rem(self, extractor):
        style = "font-size: 2.0rem;"
        result = extractor._parse_inline_font_size(style)
        assert result == (2.0, 'rem')

    def test_parse_inline_font_size_pt(self, extractor):
        style = "font-size: 18pt;"
        result = extractor._parse_inline_font_size(style)
        assert result == (18.0, 'pt')

    def test_parse_inline_font_size_px(self, extractor):
        style = "font-size: 24px;"
        result = extractor._parse_inline_font_size(style)
        assert result == (24.0, 'px')

    def test_parse_inline_font_size_percent(self, extractor):
        style = "font-size: 150%;"
        result = extractor._parse_inline_font_size(style)
        assert result == (150.0, '%')

    def test_parse_inline_font_size_invalid(self, extractor):
        style = "color: red;"
        result = extractor._parse_inline_font_size(style)
        assert result is None

    def test_parse_inline_font_size_empty(self, extractor):
        result = extractor._parse_inline_font_size("")
        assert result is None

    def test_parse_inline_font_size_none(self, extractor):
        result = extractor._parse_inline_font_size(None)
        assert result is None

    def test_parse_inline_font_size_malformed(self, extractor):
        style = "font-size: invalid;"
        result = extractor._parse_inline_font_size(style)
        assert result is None


class TestThresholdChecks:
    """Test font-size threshold detection."""

    def test_is_large_font_size_em_above(self, extractor):
        style = "font-size: 1.5em;"
        assert extractor._is_large_font_size(style) is True

    def test_is_large_font_size_em_equal(self, extractor):
        style = "font-size: 1.3em;"
        assert extractor._is_large_font_size(style) is True

    def test_is_large_font_size_em_below(self, extractor):
        style = "font-size: 1.2em;"
        assert extractor._is_large_font_size(style) is False

    def test_is_large_font_size_rem(self, extractor):
        style = "font-size: 1.5rem;"
        assert extractor._is_large_font_size(style) is True

    def test_is_large_font_size_percent_above(self, extractor):
        style = "font-size: 150%;"
        assert extractor._is_large_font_size(style) is True

    def test_is_large_font_size_percent_equal(self, extractor):
        style = "font-size: 130%;"
        assert extractor._is_large_font_size(style) is True

    def test_is_large_font_size_percent_below(self, extractor):
        style = "font-size: 120%;"
        assert extractor._is_large_font_size(style) is False

    def test_is_large_font_size_pt_above(self, extractor):
        style = "font-size: 18pt;"
        assert extractor._is_large_font_size(style) is True

    def test_is_large_font_size_pt_equal(self, extractor):
        style = "font-size: 16pt;"
        assert extractor._is_large_font_size(style) is True

    def test_is_large_font_size_pt_below(self, extractor):
        style = "font-size: 14pt;"
        assert extractor._is_large_font_size(style) is False

    def test_is_large_font_size_px_above(self, extractor):
        style = "font-size: 22px;"
        assert extractor._is_large_font_size(style) is True

    def test_is_large_font_size_px_equal(self, extractor):
        style = "font-size: 20px;"
        assert extractor._is_large_font_size(style) is True

    def test_is_large_font_size_px_below(self, extractor):
        style = "font-size: 18px;"
        assert extractor._is_large_font_size(style) is False

    def test_is_large_font_size_no_style(self, extractor):
        assert extractor._is_large_font_size("") is False


class TestTextHeuristics:
    """Test text-based heading heuristics."""

    def test_heading_like_text_all_caps(self, extractor):
        text = "CHAPTER ONE"
        word_count = 2
        assert extractor._is_heading_like_text(text, word_count) is True

    def test_heading_like_text_title_case(self, extractor):
        text = "Chapter One: Beginning"
        word_count = 3
        assert extractor._is_heading_like_text(text, word_count) is True

    def test_heading_like_text_mixed_case(self, extractor):
        text = "This Is A Title"
        word_count = 4
        assert extractor._is_heading_like_text(text, word_count) is True

    def test_heading_like_text_lowercase(self, extractor):
        text = "this is body text"
        word_count = 4
        assert extractor._is_heading_like_text(text, word_count) is False

    def test_heading_like_text_too_long(self, extractor):
        text = "THIS IS A VERY LONG HEADING THAT EXCEEDS THE FIFTEEN WORD LIMIT AND SHOULD NOT BE DETECTED"
        word_count = 17
        assert extractor._is_heading_like_text(text, word_count) is False

    def test_heading_like_text_empty(self, extractor):
        text = ""
        word_count = 0
        assert extractor._is_heading_like_text(text, word_count) is False

    def test_heading_like_text_boundary(self, extractor):
        text = "Exactly Fifteen Words Here To Test The Boundary Condition For Heading Detection Logic Implementation"
        word_count = 15
        assert extractor._is_heading_like_text(text, word_count) is True


class TestMultiSignalDetection:
    """Test multi-signal visual heading detection."""

    def test_visual_heading_font_only(self, extractor):
        html = '<p style="font-size: 1.5em;">some text</p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._is_visual_heading(element) is False

    def test_visual_heading_font_and_bold(self, extractor):
        html = '<p style="font-size: 1.5em;"><strong>Title</strong></p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._is_visual_heading(element) is True

    def test_visual_heading_font_and_caps(self, extractor):
        html = '<p style="font-size: 1.5em;">CHAPTER ONE</p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._is_visual_heading(element) is True

    def test_visual_heading_bold_and_caps(self, extractor):
        html = '<p><strong>CHAPTER ONE</strong></p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._is_visual_heading(element) is True

    def test_visual_heading_all_signals(self, extractor):
        html = '<p style="font-size: 2.0em;"><strong>CHAPTER ONE</strong></p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._is_visual_heading(element) is True

    def test_visual_heading_bold_only(self, extractor):
        html = '<p><strong>some text</strong></p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._is_visual_heading(element) is False

    def test_visual_heading_caps_only(self, extractor):
        html = '<p>TITLE</p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._is_visual_heading(element) is False

    def test_visual_heading_too_long(self, extractor):
        html = '<p style="font-size: 1.5em;"><strong>This is a very long paragraph that exceeds fifteen words and should not be detected as a heading</strong></p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._is_visual_heading(element) is False

    def test_visual_heading_empty(self, extractor):
        html = '<p style="font-size: 1.5em;"><strong></strong></p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._is_visual_heading(element) is False

    def test_visual_heading_with_b_tag(self, extractor):
        html = '<p style="font-size: 1.5em;"><b>Title</b></p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._is_visual_heading(element) is True


class TestLevelInference:
    """Test heading level inference from font-size."""

    def test_infer_level_2em(self, extractor):
        html = '<p style="font-size: 2.0em;">Title</p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._infer_heading_level_from_font_size(element) == 1

    def test_infer_level_2_5em(self, extractor):
        html = '<p style="font-size: 2.5em;">Title</p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._infer_heading_level_from_font_size(element) == 1

    def test_infer_level_1_8em(self, extractor):
        html = '<p style="font-size: 1.8em;">Title</p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._infer_heading_level_from_font_size(element) == 2

    def test_infer_level_1_5em(self, extractor):
        html = '<p style="font-size: 1.5em;">Title</p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._infer_heading_level_from_font_size(element) == 2

    def test_infer_level_1_4em(self, extractor):
        html = '<p style="font-size: 1.4em;">Title</p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._infer_heading_level_from_font_size(element) == 3

    def test_infer_level_1_3em(self, extractor):
        html = '<p style="font-size: 1.3em;">Title</p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._infer_heading_level_from_font_size(element) == 3

    def test_infer_level_1_2em(self, extractor):
        html = '<p style="font-size: 1.2em;">Title</p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._infer_heading_level_from_font_size(element) == 2

    def test_infer_level_no_style(self, extractor):
        html = '<p>Title</p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._infer_heading_level_from_font_size(element) == 2

    def test_infer_level_200_percent(self, extractor):
        html = '<p style="font-size: 200%;">Title</p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._infer_heading_level_from_font_size(element) == 1

    def test_infer_level_24pt(self, extractor):
        html = '<p style="font-size: 24pt;">Title</p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._infer_heading_level_from_font_size(element) == 1

    def test_infer_level_32px(self, extractor):
        html = '<p style="font-size: 32px;">Title</p>'
        element = BeautifulSoup(html, 'html.parser').p
        assert extractor._infer_heading_level_from_font_size(element) == 1


class TestConfigValidation:
    """Test configuration validation."""

    def test_valid_threshold(self):
        config = EpubExtractorConfig(visual_heading_font_threshold=1.5)
        assert config.visual_heading_font_threshold == 1.5

    def test_threshold_too_low(self):
        with pytest.raises(Exception):
            EpubExtractorConfig(visual_heading_font_threshold=0.5)

    def test_threshold_too_high(self):
        with pytest.raises(Exception):
            EpubExtractorConfig(visual_heading_font_threshold=3.5)

    def test_threshold_boundary_low(self):
        config = EpubExtractorConfig(visual_heading_font_threshold=1.0)
        assert config.visual_heading_font_threshold == 1.0

    def test_threshold_boundary_high(self):
        config = EpubExtractorConfig(visual_heading_font_threshold=3.0)
        assert config.visual_heading_font_threshold == 3.0

    def test_disabled_by_default(self):
        config = EpubExtractorConfig()
        assert config.detect_visual_headings is False

    def test_default_threshold(self):
        config = EpubExtractorConfig()
        assert config.visual_heading_font_threshold == 1.3
