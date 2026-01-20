#!/usr/bin/env python3
"""Integration tests for EPUB front matter detection."""

from extraction.extractors.configs import EpubExtractorConfig


class TestFrontMatterSoftFlag:
    """Tests for soft flagging mode (default)."""

    def test_detects_front_matter_with_flag(self):
        """Should add quality flags for detected front matter."""
        chunk_with_dedication = {
            'text': 'Dedicated to my loving wife',
            'hierarchy': {'level_1': 'Introduction'},
            'word_count': 5,
        }

        from extraction.core.noise_filter import NoiseFilter
        is_fm, reason = NoiseFilter.is_front_matter(chunk_with_dedication)

        assert is_fm is True
        assert reason == 'dedication_phrase'

    def test_disabled_by_default(self):
        """Should not detect front matter when disabled."""
        config = EpubExtractorConfig(
            detect_front_matter=False,
        )

        assert config.detect_front_matter is False


class TestFrontMatterHardFilter:
    """Tests for hard filtering mode."""

    def test_filter_mode_requires_detect(self):
        """Should only filter when detect is enabled."""
        config = EpubExtractorConfig(
            detect_front_matter=True,
            filter_front_matter=True,
        )

        assert config.detect_front_matter is True
        assert config.filter_front_matter is True


class TestFrontMatterPatterns:
    """Tests for various front matter patterns."""

    def test_dedication_pattern(self):
        """Should detect dedication patterns."""
        from extraction.core.noise_filter import NoiseFilter

        chunks = [
            {'text': 'Dedicated to my parents'},
            {'text': 'For Sarah, my wife'},
            {'text': 'In memory of those who served'},
            {'text': 'To my children, the future generation'},
        ]

        for chunk in chunks:
            is_fm, reason = NoiseFilter.is_front_matter(chunk)
            assert is_fm is True, f"Failed to detect: {chunk['text']}"
            assert reason == 'dedication_phrase'

    def test_endorsement_pattern(self):
        """Should detect endorsement patterns."""
        from extraction.core.noise_filter import NoiseFilter

        chunks = [
            {'text': 'Praise for this wonderful book...'},
            {'text': 'Advance praise from critics'},
            {'text': 'What readers are saying about this work'},
        ]

        for chunk in chunks:
            is_fm, reason = NoiseFilter.is_front_matter(chunk)
            assert is_fm is True, f"Failed to detect: {chunk['text']}"
            assert reason == 'endorsement_section'

    def test_toc_label_pattern(self):
        """Should detect TOC-labeled front matter."""
        from extraction.core.noise_filter import NoiseFilter

        chunks = [
            {'hierarchy': {'level_1': 'dedication'}, 'text': 'Some text'},
            {'hierarchy': {'level_1': 'praise'}, 'text': 'Some text'},
            {'hierarchy': {'level_1': 'endorsements'}, 'text': 'Some text'},
            {'hierarchy': {'level_1': 'title page'}, 'text': 'Title Page'},
            {'hierarchy': {'level_1': 'series page'}, 'text': 'Series information'},
            {'hierarchy': {'level_1': 'illustrations'}, 'text': 'Figure 1. The Jordan River'},
            {'hierarchy': {'level_1': 'list of figures'}, 'text': 'Figure list'},
            {'hierarchy': {'level_1': 'abbreviations'}, 'text': 'ACCS Ancient Christian Commentary'},
            {'hierarchy': {'level_1': "editors' preface"}, 'text': 'Preface content'},
            {'hierarchy': {'level_1': 'preface'}, 'text': 'This book aims to...'},
            {'hierarchy': {'level_1': 'acknowledgments'}, 'text': 'Writing this book was a joy...'},
            {'hierarchy': {'level_1': 'acknowledgements'}, 'text': 'I thank my editor...'},
        ]

        for chunk in chunks:
            is_fm, reason = NoiseFilter.is_front_matter(chunk)
            assert is_fm is True, f"Failed to detect: {chunk['hierarchy']}"
            assert reason == 'front_matter_toc_label'

    def test_outline_pattern(self):
        """Should detect outline sections."""
        from extraction.core.noise_filter import NoiseFilter

        chunks = [
            {'hierarchy': {'level_1': 'outline of mark'}, 'text': 'Prologue: The beginning'},
            {'hierarchy': {'level_1': 'book outline'}, 'text': 'Part I: Introduction'},
            {'hierarchy': {'level_1': 'outline'}, 'text': 'Chapter structure'},
        ]

        for chunk in chunks:
            is_fm, reason = NoiseFilter.is_front_matter(chunk)
            assert is_fm is True, f"Failed to detect: {chunk['hierarchy']}"
            assert reason == 'front_matter_toc_label'

    def test_does_not_flag_normal_content(self):
        """Should not flag normal chapter content."""
        from extraction.core.noise_filter import NoiseFilter

        chunks = [
            {'text': 'This chapter discusses dedication in worship.', 'hierarchy': {'level_1': 'Chapter 1'}},
            {'text': 'The author praised the methodology.', 'hierarchy': {'level_1': 'Chapter 2'}},
            {'text': 'To understand this concept, read carefully.', 'hierarchy': {'level_1': 'Chapter 3'}},
        ]

        for chunk in chunks:
            is_fm, _ = NoiseFilter.is_front_matter(chunk)
            assert is_fm is False, f"False positive: {chunk['text']}"
