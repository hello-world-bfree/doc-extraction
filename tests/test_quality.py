#!/usr/bin/env python3
"""Tests for quality scoring system."""
import math
import pytest

from extraction.core.quality import (
    quality_signals_from_text,
    score_quality,
    route_doc
)


class TestQualitySignals:
    """Tests for quality_signals_from_text()."""

    def test_empty_text_returns_default_signals(self):
        """Empty text should return default low-quality signals."""
        signals = quality_signals_from_text("")

        assert signals["garble_rate"] == 1.0  # Worst
        assert signals["mean_conf"] == 0.0    # Worst
        assert signals["line_len_std_norm"] == 1.0  # Worst
        assert signals["lang_prob"] == 0.0    # Worst

    def test_clean_text_has_low_garble_rate(self):
        """Clean ASCII text should have low garble rate."""
        clean_text = "This is a simple test with clean ASCII text."
        signals = quality_signals_from_text(clean_text)

        assert 0.0 <= signals["garble_rate"] <= 0.1  # Should be very low
        assert signals["mean_conf"] >= 0.7  # Should be reasonably high (0.8 for short text)

    def test_all_signals_in_valid_range(self):
        """All signals should be in [0, 1] for any input."""
        test_texts = [
            "",
            "Simple text",
            "Text with numbers 123 and symbols !@#$",
            "Unicode: café, naïve, résumé",
            "Code: def foo():\n    return bar",
            "A" * 10000,  # Very long text
        ]

        for text in test_texts:
            signals = quality_signals_from_text(text)

            for signal_name, signal_value in signals.items():
                assert 0.0 <= signal_value <= 1.0, \
                    f"Signal '{signal_name}' = {signal_value} out of bounds for text: {text[:50]}"


class TestScoreQuality:
    """Tests for score_quality()."""

    def test_score_is_always_bounded(self):
        """Score should always be in [0, 1] regardless of signals."""
        test_signal_sets = [
            # Normal signals
            {"garble_rate": 0.0, "mean_conf": 1.0, "line_len_std_norm": 0.0, "lang_prob": 1.0},
            {"garble_rate": 0.5, "mean_conf": 0.5, "line_len_std_norm": 0.5, "lang_prob": 0.5},
            {"garble_rate": 1.0, "mean_conf": 0.0, "line_len_std_norm": 1.0, "lang_prob": 0.0},

            # Edge case: all zeros
            {"garble_rate": 0.0, "mean_conf": 0.0, "line_len_std_norm": 0.0, "lang_prob": 0.0},

            # Edge case: all ones
            {"garble_rate": 1.0, "mean_conf": 1.0, "line_len_std_norm": 1.0, "lang_prob": 1.0},
        ]

        for signals in test_signal_sets:
            score = score_quality(signals)

            assert not math.isnan(score), f"Score is NaN for signals: {signals}"
            assert not math.isinf(score), f"Score is Inf for signals: {signals}"
            assert 0.0 <= score <= 1.0, f"Score {score} out of bounds for signals: {signals}"

    def test_score_handles_malformed_signals(self):
        """Score should handle NaN/Inf in signals gracefully."""
        malformed_signal_sets = [
            {"garble_rate": float('nan'), "mean_conf": 0.5, "line_len_std_norm": 0.5, "lang_prob": 0.5},
            {"garble_rate": float('inf'), "mean_conf": 0.5, "line_len_std_norm": 0.5, "lang_prob": 0.5},
            {"garble_rate": -1.0, "mean_conf": 0.5, "line_len_std_norm": 0.5, "lang_prob": 0.5},
            {"garble_rate": 2.0, "mean_conf": 0.5, "line_len_std_norm": 0.5, "lang_prob": 0.5},
        ]

        for signals in malformed_signal_sets:
            score = score_quality(signals)

            # Should not crash, should return valid score
            assert not math.isnan(score), f"Score is NaN for malformed signals: {signals}"
            assert not math.isinf(score), f"Score is Inf for malformed signals: {signals}"
            assert 0.0 <= score <= 1.0, f"Score {score} out of bounds for malformed signals: {signals}"

    def test_score_formula_weights(self):
        """Verify the formula uses correct weights (0.4 + 0.3 + 0.1 + 0.2 = 1.0)."""
        # Best signals should give score near 1.0
        best_signals = {
            "garble_rate": 0.0,  # Best (contributes 0.4)
            "mean_conf": 1.0,    # Best (contributes 0.3)
            "line_len_std_norm": 0.0,  # Best (contributes 0.1)
            "lang_prob": 1.0     # Best (contributes 0.2)
        }
        score = score_quality(best_signals)
        assert score == 1.0, f"Best signals should give score 1.0, got {score}"

        # Worst signals should give score 0.0
        worst_signals = {
            "garble_rate": 1.0,
            "mean_conf": 0.0,
            "line_len_std_norm": 1.0,
            "lang_prob": 0.0
        }
        score = score_quality(worst_signals)
        assert score == 0.0, f"Worst signals should give score 0.0, got {score}"


class TestRouteDoc:
    """Tests for route_doc()."""

    def test_route_thresholds(self):
        """Verify routing thresholds are correct."""
        assert route_doc(1.0) == "A"
        assert route_doc(0.9) == "A"
        assert route_doc(0.8) == "A"   # Exactly 0.8 is route A
        assert route_doc(0.79) == "B"
        assert route_doc(0.6) == "B"
        assert route_doc(0.55) == "B"  # Exactly 0.55 is route B
        assert route_doc(0.54) == "C"
        assert route_doc(0.3) == "C"
        assert route_doc(0.0) == "C"

    def test_route_handles_edge_values(self):
        """Route should handle edge values gracefully."""
        # These should not crash even though they're out of normal range
        assert route_doc(-0.5) == "C"  # Below 0
        assert route_doc(1.5) == "A"   # Above 1

    def test_route_is_deterministic(self):
        """Same score should always give same route."""
        test_scores = [0.0, 0.5, 0.55, 0.8, 0.9, 1.0]

        for score in test_scores:
            route1 = route_doc(score)
            route2 = route_doc(score)
            assert route1 == route2, f"Route changed for score {score}"
