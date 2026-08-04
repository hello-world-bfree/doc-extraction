#!/usr/bin/env python3
"""Scores NoiseFilter against the frozen core/non-core taxonomy fixture.

The fixture (tests/fixtures/noncore_taxonomy.json) is the definition of correct.
Its two rules:

    1. informational value — drop only pointers into the physical book and bare
       answer/label lists whose substance lives elsewhere
    2. front-matter position — publisher/apparatus front matter drops even when it
       is subject-relevant prose (deliberately overrides rule 1)

Scores are reported with precision on the *drop* class separated from recall, and
with rule 1 split from rule 2: a false positive destroys real content while a false
negative only leaves junk behind, and rule 2 is a keyword list that scores ~1.0
trivially, so a blended number would hide rule 1's failures.
"""
import json
from pathlib import Path

import pytest

from extraction.core.noise_filter import NoiseFilter

FIXTURE = Path(__file__).parent / "fixtures" / "noncore_taxonomy.json"


def _load():
    with FIXTURE.open() as fh:
        return json.load(fh)


def _predict(case):
    """Run the detector the way the epub extractor does, returning 'drop'/'keep'."""
    chunk = {
        "text": case["text"],
        "hierarchy": {"level_1": case["label"]},
        "word_count": len(case["text"].split()),
    }
    is_noncore, reason = NoiseFilter.is_front_matter(chunk)
    return ("drop" if is_noncore else "keep"), reason


def _confusion(cases):
    """Confusion matrix treating 'drop' as the positive class."""
    m = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    misses = []
    for case in cases:
        got, reason = _predict(case)
        want = case["verdict"]
        if want == "drop" and got == "drop":
            m["tp"] += 1
        elif want == "keep" and got == "drop":
            m["fp"] += 1
            misses.append(("FP", case, reason))
        elif want == "drop" and got == "keep":
            m["fn"] += 1
            misses.append(("FN", case, reason))
        else:
            m["tn"] += 1
    return m, misses


def _precision(m):
    denom = m["tp"] + m["fp"]
    return m["tp"] / denom if denom else 1.0


def _recall(m):
    denom = m["tp"] + m["fn"]
    return m["tp"] / denom if denom else 1.0


ALL_CASES = _load()["cases"]

# Cases the label-based rules cannot reach: the label says keep but the content says
# drop. Distinguishing a bare answer key from Knuth's derivations, or a list of table
# titles from a table of data, needs to read the text — which is what the classifier
# ticket exists to price. Listed as xfail so the suite stays green while the gap stays
# visible; delete an entry here when something actually closes it.
CONTENT_JUDGMENT_CASES = {"bare-answer-key", "table-titles-only"}


def _case_param(case):
    marks = []
    if case["id"] in CONTENT_JUDGMENT_CASES:
        marks.append(
            pytest.mark.xfail(
                strict=True,
                reason="needs content-level judgment, not a label rule",
            )
        )
    return pytest.param(case, id=case["id"], marks=marks)


@pytest.mark.parametrize("case", [_case_param(c) for c in ALL_CASES])
def test_case_verdict(case):
    """Each fixture case must classify as its recorded verdict."""
    got, reason = _predict(case)
    assert got == case["verdict"], (
        f"{case['id']}: want {case['verdict']}, got {got} (reason={reason})\n"
        f"  rule {case['rule']} — {case['note']}"
    )


def test_no_false_positives_on_keep_cases():
    """Precision on the drop class must be 1.0.

    This is the metric that matters: a false positive silently removes real content
    from retrieval, and is only discovered when a search comes up empty. A false
    negative merely leaves junk behind, which is visible and harmless by comparison.
    """
    keep_cases = [c for c in ALL_CASES if c["verdict"] == "keep"]
    dropped = [(c["id"], _predict(c)[1]) for c in keep_cases if _predict(c)[0] == "drop"]
    assert not dropped, f"real content wrongly dropped: {dropped}"


def test_report_scores(capsys):
    """Print the confusion matrix, split by rule. Never fails — this is the report."""
    overall, misses = _confusion(ALL_CASES)
    rule1, _ = _confusion([c for c in ALL_CASES if c["rule"] == 1])
    rule2, _ = _confusion([c for c in ALL_CASES if c["rule"] == 2])

    lines = ["", "=== core/non-core taxonomy scores (drop = positive class) ==="]
    for name, m in (("overall", overall), ("rule 1 (judgment)", rule1),
                    ("rule 2 (front matter)", rule2)):
        lines.append(
            f"{name:22} precision={_precision(m):.3f} recall={_recall(m):.3f}  "
            f"tp={m['tp']} fp={m['fp']} fn={m['fn']} tn={m['tn']}"
        )
    if misses:
        lines.append("")
        lines.append("misclassified:")
        for kind, case, reason in misses:
            lines.append(f"  {kind}  {case['id']:32} rule {case['rule']}  reason={reason}")
    print("\n".join(lines))

    with capsys.disabled():
        print("\n".join(lines))
