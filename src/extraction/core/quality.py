#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Quality scoring and routing for documents.

CRITICAL: Quality scoring formulas and thresholds MUST NOT change to maintain
backward compatibility with existing quality routes (A/B/C classification).

Quality signals and routing determine how documents are processed downstream,
so changes here can break existing workflows.
"""

import re
import statistics
from typing import Dict


def quality_signals_from_text(text: str) -> Dict[str, float]:
    """Compute quality signals for given text.

    Signals computed:
    - garble_rate: Ratio of non-standard characters (0-1, lower is better)
    - mean_conf: Confidence in text quality (0-1, higher is better)
    - line_len_std_norm: Normalized standard deviation of line lengths (0-1)
    - lang_prob: Probability text is target language based on keywords (0-1)

    Returns:
        Dictionary with four quality signals, all normalized to 0-1 range.
    """
    if not text:
        return {
            "garble_rate": 1.0,
            "mean_conf": 0.0,
            "line_len_std_norm": 1.0,
            "lang_prob": 0.0
        }

    # Garble rate: ratio of weird characters
    weird = len(re.findall(r"[^\x09\x0A\x0D\x20-\x7E\u00A0-\u02AF]", text))
    garble_rate = min(1.0, weird / max(1, len(text)))

    # Mean confidence: inverse of garble rate, with length bonus
    mean_conf = max(0.0, 1.0 - garble_rate) * (1.0 if len(text) > 2000 else 0.8)

    # Line length standard deviation (normalized)
    lines = [len(l) for l in text.splitlines() if l.strip()]
    if lines:
        std = statistics.pstdev(lines)
        line_len_std_norm = min(1.0, std / 120.0)
    else:
        line_len_std_norm = 0.2

    # Language probability (based on Latin keywords for Catholic texts)
    latin_hits = len(
        re.findall(r'\b(Dei|Ecclesia|Dominus|Verbum|Magisterium|Apostolica)\b', text)
    )
    lang_prob = min(1.0, 0.5 + 0.05 * latin_hits)

    return {
        "garble_rate": float(garble_rate),
        "mean_conf": float(mean_conf),
        "line_len_std_norm": float(line_len_std_norm),
        "lang_prob": float(lang_prob),
    }


def score_quality(signals: Dict[str, float]) -> float:
    """Compute weighted quality score from signals.

    CRITICAL: This formula must not change. The weights are:
    - 40% inverse garble rate (cleanliness)
    - 30% mean confidence
    - 10% inverse line length variation
    - 20% language probability

    Args:
        signals: Dictionary from quality_signals_from_text()

    Returns:
        Quality score in range 0-1 (higher is better).
    """
    import math

    score = float(
        0.40 * (1 - signals.get("garble_rate", 0.0)) +
        0.30 * signals.get("mean_conf", 0.0) +
        0.10 * (1 - signals.get("line_len_std_norm", 0.0)) +
        0.20 * signals.get("lang_prob", 0.0)
    )

    # Defensive validation: Handle NaN/Inf and clamp to valid range
    # This should never trigger with valid signals, but provides safety net
    if math.isnan(score) or math.isinf(score):
        return 0.0  # Treat invalid scores as lowest quality
    return max(0.0, min(1.0, score))  # Clamp to [0, 1]


def route_doc(score: float) -> str:
    """Route document based on quality score.

    CRITICAL: These thresholds must not change:
    - Route A (≥0.80): High quality, use standard chunking
    - Route B (≥0.55): Medium quality, use standard chunking with more validation
    - Route C (<0.55): Low quality, use fixed-window chunking

    Args:
        score: Quality score from score_quality()

    Returns:
        Route designation: "A", "B", or "C"
    """
    if score >= 0.80:
        return "A"
    if score >= 0.55:
        return "B"
    return "C"
