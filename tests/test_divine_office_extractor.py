#!/usr/bin/env python3
"""Tests for DivineOfficeExtractor."""

import pytest
from unittest.mock import MagicMock, patch

from extraction.exceptions import InvalidConfigValueError, ParseError
from extraction.extractors.configs import DivineOfficeExtractorConfig
from extraction.extractors.divine_office import DivineOfficeExtractor, ALL_HOURS
from extraction.state import ExtractorState


_MORNING_PRAYER_HTML = """
<html>
<head><title>Morning Prayer - Tuesday, March 31, 2026 - divineoffice.org</title></head>
<body>
<div class="entry mb-40">
<p><span style="color: #ff0000;">Morning Prayer for Tuesday in Holy Week</span></p>
<p>God, come to my assistance.<br>
<span style="color: #ff0000;">&#8212;</span> Lord, make haste to help me.</p>
<p>Glory to the Father, and to the Son, and to the Holy Spirit:<br>
<span style="color: #ff0000;">&#8212;</span> as it was in the beginning, is now, and will be for ever. Amen.</p>
<div class="hymn-container" style="margin-bottom: 20px;"><p><span style="color: #ff0000;">HYMN</span></p>
<p>Through Thy Cross and Passion,<br>Good Lord, deliver us.</p></div>
<p><span style="color: #ff0000;">PSALMODY</span></p>
<p><span style="color: #ff0000;">Ant. 1 </span> O Lord, defend my cause; rescue me from deceitful and impious men.</p>
<p style="text-align: center;"><span style="color: #ff0000;">Psalm 43<br>Longing for the temple</span><br>
<em>I have come into the world to be its light</em> (John 12:46).</p>
<p>Defend me, O God, and plead my cause<br>against a godless nation.<br>
From deceitful and cunning men<br>rescue me, O God.</p>
<p>Since you, O God, are my stronghold,<br>why have you rejected me?<br>
Why do I go mourning<br>oppressed by the foe?</p>
<p>Glory to the Father, and to the Son, and to the Holy Spirit:<br>
<span style="color: #ff0000;">&#8212;</span> as it was in the beginning, is now, and will be for ever. Amen.</p>
<p><span style="color: #ff0000;">Psalm-prayer</span></p>
<p>Almighty Father, source of everlasting light, send forth your truth into our hearts.</p>
<p><span style="color: #ff0000;">Ant. </span> O Lord, defend my cause; rescue me from deceitful and impious men.</p>
<p><span style="color: #ff0000;">READING </span> Zechariah 12:10-11a</p>
<p>I will pour out on the house of David a spirit of grace and petition.</p>
<p><span style="color: #ff0000;">Sacred Silence</span>(indicated by a bell)</p>
<p><span style="color: #ff0000;">RESPONSORY </span></p>
<p>By your own blood, Lord, you brought us back to God.<br>
<span style="color: #ff0000;">&#8212;</span> By your own blood, Lord, you brought us back to God.</p>
<p><span style="color: #ff0000;">CANTICLE OF ZECHARIAH</span></p>
<p><span style="color: #ff0000;">Ant. </span> Father, give me the glory that I had with you before the world was made.</p>
<p>Blessed be the Lord, the God of Israel;<br>he has come to his people and set them free.</p>
<p><span style="color: #ff0000;">Ant. </span> Father, give me the glory that I had with you before the world was made.</p>
<p><span style="color: #ff0000;">INTERCESSIONS</span></p>
<p>Let us pray to Christ our Savior, who redeemed us by his death and resurrection:<br>
<em>Lord, have mercy on us.</em></p>
<p>You went up to Jerusalem to suffer and so enter into your glory,<br>
<span style="color: #ff0000;">&#8212;</span> bring your Church to the Passover feast of heaven.</p>
<p><span style="color: #ff0000;">Concluding Prayer</span></p>
<p>Almighty ever-living God, grant us so to celebrate the mysteries of the Lord's Passion
that we may merit to receive your pardon. Through our Lord Jesus Christ, your Son,
who lives and reigns with you in the unity of the Holy Spirit, God, for ever and ever.<br>
<span style="color: #ff0000;">&#8212;</span> Amen.</p>
<p><span style="color: #ff0000;">DISMISSAL</span></p>
<p>May the Lord bless us, protect us from all evil and bring us to everlasting life.<br>
<span style="color: #ff0000;">&#8212;</span> Amen.</p>
</div>
</body>
</html>
"""

_TWO_HOURS_HTML = """
<html>
<head><title>Liturgy of the Hours - March 31, 2026 - divineoffice.org</title></head>
<body>
<div class="entry mb-40">
<p><span style="color: #ff0000;">Morning Prayer for Tuesday in Holy Week</span></p>
<p>God, come to my assistance.</p>
<p><span style="color: #ff0000;">HYMN</span></p>
<p>Through Thy Cross and Passion, Good Lord, deliver us.</p>
<p><span style="color: #ff0000;">READING </span> Isaiah 1:1</p>
<p>A reading from Isaiah the prophet.</p>
<p><span style="color: #ff0000;">Concluding Prayer</span></p>
<p>Lord, hear our prayer through Christ our Lord. Amen.</p>
</div>
<div class="entry mb-40">
<p><span style="color: #ff0000;">Evening Prayer for Tuesday in Holy Week</span></p>
<p>God, come to my assistance.</p>
<p><span style="color: #ff0000;">HYMN</span></p>
<p>O gracious light, pure brightness of the everlasting Father in heaven.</p>
<p><span style="color: #ff0000;">READING </span> Romans 8:1</p>
<p>There is no condemnation now for those who are in Christ Jesus.</p>
<p><span style="color: #ff0000;">Concluding Prayer</span></p>
<p>Father, we give you thanks for this day. Amen.</p>
</div>
</body>
</html>
"""

_CLOUDFLARE_HTML = """
<html>
<head><title>Just a moment...</title></head>
<body><p>Please wait while we verify your browser.</p></body>
</html>
"""


def _make_playwright_mock(html_content: str):
    mock_page = MagicMock()
    mock_page.content.return_value = html_content

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_playwright_instance = MagicMock()
    mock_playwright_instance.chromium.launch.return_value = mock_browser

    mock_sync_playwright = MagicMock()
    mock_sync_playwright.return_value.__enter__ = MagicMock(return_value=mock_playwright_instance)
    mock_sync_playwright.return_value.__exit__ = MagicMock(return_value=False)

    return mock_sync_playwright


class TestDivineOfficeExtractorConfig:

    def test_default_config(self):
        config = DivineOfficeExtractorConfig(date="20260331")
        assert config.date == "20260331"
        assert config.hours is None
        assert config.playwright_timeout == 30000
        assert config.min_chunk_words == 5

    def test_invalid_date_format(self):
        with pytest.raises(InvalidConfigValueError):
            DivineOfficeExtractorConfig(date="2026-03-31")

    def test_invalid_date_letters(self):
        with pytest.raises(InvalidConfigValueError):
            DivineOfficeExtractorConfig(date="abcdefgh")

    def test_empty_date_allowed(self):
        config = DivineOfficeExtractorConfig()
        assert config.date == ""

    def test_playwright_timeout_too_low(self):
        with pytest.raises(InvalidConfigValueError):
            DivineOfficeExtractorConfig(date="20260331", playwright_timeout=500)

    def test_hours_list(self):
        config = DivineOfficeExtractorConfig(
            date="20260331", hours=["Morning Prayer", "Evening Prayer"]
        )
        assert config.hours == ["Morning Prayer", "Evening Prayer"]


class TestDivineOfficeExtractorInit:

    def test_url_constructed_from_date(self):
        extractor = DivineOfficeExtractor("20260331")
        assert extractor.source_path == "https://divineoffice.org/?date=20260331"

    def test_state_starts_created(self):
        extractor = DivineOfficeExtractor("20260331")
        assert extractor.state == ExtractorState.CREATED

    def test_uses_catholic_analyzer_by_default(self):
        from extraction.analyzers.catholic import CatholicAnalyzer
        extractor = DivineOfficeExtractor("20260331")
        assert isinstance(extractor.analyzer, CatholicAnalyzer)

    def test_custom_config_respected(self):
        config = DivineOfficeExtractorConfig(date="20260331", playwright_timeout=60000)
        extractor = DivineOfficeExtractor("20260331", config=config)
        assert extractor.config.playwright_timeout == 60000


class TestDivineOfficeExtractorLoad:

    def test_load_calls_playwright(self):
        mock_pw = _make_playwright_mock(_MORNING_PRAYER_HTML)
        with patch("extraction.extractors.divine_office.sync_playwright", mock_pw):
            extractor = DivineOfficeExtractor("20260331")
            extractor.load()
            assert extractor.state == ExtractorState.LOADED

    def test_load_sets_page_title(self):
        mock_pw = _make_playwright_mock(_MORNING_PRAYER_HTML)
        with patch("extraction.extractors.divine_office.sync_playwright", mock_pw):
            extractor = DivineOfficeExtractor("20260331")
            extractor.load()
            assert "Morning Prayer" in extractor._page_title

    def test_load_sets_provenance(self):
        mock_pw = _make_playwright_mock(_MORNING_PRAYER_HTML)
        with patch("extraction.extractors.divine_office.sync_playwright", mock_pw):
            extractor = DivineOfficeExtractor("20260331")
            extractor.load()
            prov = extractor.provenance
            assert prov.source_file == "https://divineoffice.org/?date=20260331"
            assert prov.content_hash

    def test_load_raises_on_cloudflare_block(self):
        mock_pw = _make_playwright_mock(_CLOUDFLARE_HTML)
        with patch("extraction.extractors.divine_office.sync_playwright", mock_pw):
            extractor = DivineOfficeExtractor("20260331")
            with pytest.raises(ParseError, match="blocked"):
                extractor.load()


class TestDivineOfficeExtractorParse:

    @pytest.fixture
    def loaded_extractor(self):
        extractor = DivineOfficeExtractor("20260331")
        mock_pw = _make_playwright_mock(_MORNING_PRAYER_HTML)
        with patch("extraction.extractors.divine_office.sync_playwright", mock_pw):
            extractor.load()
        return extractor

    def test_parse_produces_chunks(self, loaded_extractor):
        loaded_extractor.parse()
        assert len(loaded_extractor.chunks) > 0

    def test_chunks_have_morning_prayer_in_level_1(self, loaded_extractor):
        loaded_extractor.parse()
        level_ones = {c.hierarchy["level_1"] for c in loaded_extractor.chunks}
        assert "Morning Prayer" in level_ones

    def test_content_types_assigned(self, loaded_extractor):
        loaded_extractor.parse()
        content_types = {c.content_type for c in loaded_extractor.chunks if c.content_type}
        assert content_types
        assert "hymn" in content_types or "psalm" in content_types or "reading" in content_types

    def test_antiphon_content_type(self, loaded_extractor):
        loaded_extractor.parse()
        antiphons = [c for c in loaded_extractor.chunks if c.content_type == "antiphon"]
        assert len(antiphons) > 0

    def test_reading_content_type(self, loaded_extractor):
        loaded_extractor.parse()
        readings = [c for c in loaded_extractor.chunks if c.content_type == "reading"]
        assert len(readings) > 0

    def test_responsory_content_type(self, loaded_extractor):
        loaded_extractor.parse()
        responsories = [c for c in loaded_extractor.chunks if c.content_type == "responsory"]
        assert len(responsories) > 0

    def test_intercession_content_type(self, loaded_extractor):
        loaded_extractor.parse()
        intercessions = [c for c in loaded_extractor.chunks if c.content_type == "intercession"]
        assert len(intercessions) > 0

    def test_psalm_subsection_in_level_2(self, loaded_extractor):
        loaded_extractor.parse()
        psalm_chunks = [c for c in loaded_extractor.chunks if c.content_type == "psalm"]
        assert any("Psalm 43" in c.hierarchy["level_2"] for c in psalm_chunks)

    def test_canticle_zechariah_subsection(self, loaded_extractor):
        loaded_extractor.parse()
        zechariah_chunks = [
            c for c in loaded_extractor.chunks if "Zechariah" in c.hierarchy["level_2"]
        ]
        assert len(zechariah_chunks) > 0

    def test_parse_transitions_state(self, loaded_extractor):
        loaded_extractor.parse()
        assert loaded_extractor.state == ExtractorState.PARSED

    def test_two_hours_in_one_page(self):
        extractor = DivineOfficeExtractor("20260331")
        mock_pw = _make_playwright_mock(_TWO_HOURS_HTML)
        with patch("extraction.extractors.divine_office.sync_playwright", mock_pw):
            extractor.load()
        extractor.parse()
        level_ones = {c.hierarchy["level_1"] for c in extractor.chunks}
        assert "Morning Prayer" in level_ones
        assert "Evening Prayer" in level_ones

    def test_hours_filter(self):
        config = DivineOfficeExtractorConfig(date="20260331", hours=["Morning Prayer"])
        extractor = DivineOfficeExtractor("20260331", config=config)
        mock_pw = _make_playwright_mock(_TWO_HOURS_HTML)
        with patch("extraction.extractors.divine_office.sync_playwright", mock_pw):
            extractor.load()
        extractor.parse()
        level_ones = {c.hierarchy["level_1"] for c in extractor.chunks}
        assert "Evening Prayer" not in level_ones
        assert "Morning Prayer" in level_ones

    def test_real_html_fixture(self):
        import os
        fixture = "/Users/freeman/bjf/extraction/__docs/loth__morning_prayer_20260331.html"
        if not os.path.exists(fixture):
            pytest.skip("Fixture not available")
        with open(fixture) as f:
            html = f.read()
        extractor = DivineOfficeExtractor("20260331")
        extractor.load_from_html(f"<html><body>{html}</body></html>", date="20260331")
        extractor.parse()
        assert len(extractor.chunks) > 0
        level_ones = {c.hierarchy["level_1"] for c in extractor.chunks}
        assert "Morning Prayer" in level_ones
        antiphons = [c for c in extractor.chunks if c.content_type == "antiphon"]
        assert len(antiphons) >= 2
        psalms = [c for c in extractor.chunks if c.content_type == "psalm"]
        assert len(psalms) > 0
        readings = [c for c in extractor.chunks if c.content_type == "reading"]
        assert len(readings) > 0


class TestDivineOfficeExtractorMetadata:

    @pytest.fixture
    def parsed_extractor(self):
        extractor = DivineOfficeExtractor("20260331")
        mock_pw = _make_playwright_mock(_MORNING_PRAYER_HTML)
        with patch("extraction.extractors.divine_office.sync_playwright", mock_pw):
            extractor.load()
        extractor.parse()
        return extractor

    def test_metadata_date_promulgated(self, parsed_extractor):
        meta = parsed_extractor.extract_metadata()
        assert meta.date_promulgated == "2026-03-31"

    def test_metadata_author(self, parsed_extractor):
        meta = parsed_extractor.extract_metadata()
        assert meta.author == "divineoffice.org"

    def test_metadata_language(self, parsed_extractor):
        meta = parsed_extractor.extract_metadata()
        assert meta.language == "en"

    def test_metadata_source_identifiers(self, parsed_extractor):
        meta = parsed_extractor.extract_metadata()
        assert meta.source_identifiers["date"] == "20260331"
        assert "divineoffice.org" in meta.source_identifiers["url"]

    def test_metadata_title_from_page(self, parsed_extractor):
        meta = parsed_extractor.extract_metadata()
        assert meta.title


@pytest.mark.integration
class TestDivineOfficeExtractorIntegration:

    def test_live_fetch_and_parse(self):
        extractor = DivineOfficeExtractor("20260331")
        extractor.load()
        extractor.parse()
        meta = extractor.extract_metadata()

        assert len(extractor.chunks) > 0
        level_ones = {c.hierarchy["level_1"] for c in extractor.chunks}
        assert len(level_ones) >= 1
        assert meta.date_promulgated == "2026-03-31"
