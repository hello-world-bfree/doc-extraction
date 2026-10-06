"""Pre-pack unit stage: noise filter, per-book structural rules, then an injected body judge.

Runs on paragraph units before packing, so a drop removes one paragraph, never a packed chunk.
Every drop and every judge flag is recorded in a unit report that travels with the output.
"""

import re
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Tuple

from ..exceptions import ExtractionError

DEFAULT_LECTIONARY_LABELS = r"^(?:(?:First|Second|Third) Reading|Gospel|Responsorial Psalm)$"
DEFAULT_EDITION_MARKER = r"\s*\[[IVXLCDM]+\.(?:\s*Ben\.)?\]"
CONTEXT_CHARS = 160


class JudgeError(ExtractionError):
    """The unit judge failed or returned no score for a unit; the document cannot be gated."""


class UnitJudge(Protocol):
    """Scores units for their probability of being the author's body text."""

    version: str

    def __call__(self, units: Sequence[Dict[str, Any]]) -> Sequence[Optional[float]]:
        """Return one body probability in [0, 1] per unit, in order.

        Each unit carries text, heading_path, source_tag, position, total, prev_text, next_text.
        """
        ...


def _classes(unit: Dict[str, Any]) -> List[str]:
    return list(unit.get('source_classes') or [])


def lectionary_readings(units: List[Dict[str, Any]], params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Drop reading blocks: a label unit and the units after it whose class matches reading_classes."""
    label = re.compile(params.get('label_pattern', DEFAULT_LECTIONARY_LABELS), re.I)
    label_classes = re.compile(params['label_classes'], re.I) if params.get('label_classes') else None
    reading = re.compile(params['reading_classes'], re.I)

    def is_label(unit):
        return bool(label.match(unit['text'].strip())) or bool(
            label_classes and any(label_classes.search(c) for c in _classes(unit))
        )

    kept, dropped = [], []
    in_block = False
    for unit in units:
        if is_label(unit):
            in_block = True
        elif in_block and not any(reading.search(c) for c in _classes(unit)):
            in_block = False
        (dropped if in_block else kept).append(unit)
    return kept, dropped


def edition_markers(units: List[Dict[str, Any]], params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Strip bracketed edition markers such as "[LXVI. Ben.]"; drop a unit left empty."""
    marker = re.compile(params.get('pattern', DEFAULT_EDITION_MARKER))

    def strip(text):
        return re.sub(r"\s{2,}", " ", marker.sub("", text)).strip()

    kept, dropped = [], []
    for unit in units:
        stripped = strip(unit['text'])
        if stripped == unit['text']:
            kept.append(unit)
        elif stripped:
            sentences = [s for s in (strip(s) for s in unit.get('sentences') or []) if s]
            kept.append({**unit, 'text': stripped, 'sentences': sentences or [stripped],
                         'word_count': len(stripped.split()), 'text_length': len(stripped)})
        else:
            dropped.append(unit)
    return kept, dropped


def exclude_documents(units: List[Dict[str, Any]], params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Drop every unit of the spine documents whose href matches `pattern`, such as an appended Bible."""
    href = re.compile(params['pattern'])
    kept, dropped = [], []
    for unit in units:
        (dropped if href.search(unit.get('chapter_href') or '') else kept).append(unit)
    return kept, dropped


STRUCTURAL_RULES: Dict[str, Callable] = {
    'lectionary_readings': lectionary_readings,
    'edition_markers': edition_markers,
    'exclude_documents': exclude_documents,
}


def _judge_context(units: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    total = len(units)
    return [
        {
            'text': u['text'],
            'heading_path': u.get('heading_path', ''),
            'source_tag': u.get('source_tag', ''),
            'position': i,
            'total': total,
            'prev_text': units[i - 1]['text'][-CONTEXT_CHARS:] if i > 0 else '',
            'next_text': units[i + 1]['text'][:CONTEXT_CHARS] if i + 1 < total else '',
        }
        for i, u in enumerate(units)
    ]


def _entry(unit: Dict[str, Any], stage: str, score: Optional[float] = None) -> Dict[str, Any]:
    entry = {'paragraph_id': unit.get('paragraph_id'), 'stage': stage, 'text': unit['text']}
    if score is not None:
        entry['score'] = score
    return entry


def run_unit_stage(
    units: List[Dict[str, Any]],
    *,
    filter_noise: bool,
    structural_rules: Dict[str, Dict[str, Any]],
    judge: Optional[UnitJudge],
    drop_threshold: float,
    keep_threshold: float,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Return the surviving units and a report of drops and flags."""
    report: Dict[str, Any] = {
        'judge_version': getattr(judge, 'version', None) if judge else None,
        'drop_threshold': drop_threshold if judge else None,
        'keep_threshold': keep_threshold if judge else None,
        'structural_rules': sorted(structural_rules),
        'dropped': [],
        'flagged': [],
    }

    if filter_noise:
        from .noise_filter import NoiseFilter
        kept = []
        for unit in units:
            if NoiseFilter.has_low_semantic_value(unit):
                report['dropped'].append(_entry(unit, 'noise'))
            else:
                kept.append(unit)
        units = kept

    for name, params in structural_rules.items():
        if name not in STRUCTURAL_RULES:
            raise ExtractionError(f"Unknown structural rule '{name}'. Available: {', '.join(STRUCTURAL_RULES)}")
        units, dropped = STRUCTURAL_RULES[name](units, params or {})
        report['dropped'].extend(_entry(u, f'rule:{name}') for u in dropped)

    if judge is not None and units:
        try:
            scores = list(judge(_judge_context(units)))
        except JudgeError:
            raise
        except Exception as e:
            raise JudgeError(f"unit judge {getattr(judge, 'version', '?')} failed: {e}") from e
        if len(scores) != len(units):
            raise JudgeError(f"unit judge returned {len(scores)} scores for {len(units)} units")
        kept = []
        for unit, score in zip(units, scores):
            if score is None:
                raise JudgeError(f"unit judge returned no score for paragraph {unit.get('paragraph_id')}")
            if score <= drop_threshold:
                report['dropped'].append(_entry(unit, 'judge', score))
                continue
            if score < keep_threshold:
                report['flagged'].append(_entry(unit, 'judge', score))
            kept.append(unit)
        units = kept

    return units, report
