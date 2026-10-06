"""Pre-pack unit stage: drops act on one paragraph, never on a packed chunk of body prose."""

import pytest

from extraction.core.unit_stage import JudgeError, run_unit_stage
from test_epub_nested_duplication import PROSE, _extract

PROSE_TWO = 'Marriage in the prophets becomes the image of the covenant between God and his people.'
CITATIONS = ' '.join(f'{n},' for n in range(101, 181)) + ' 182.'


def unit(pid, text, classes=None):
    u = {'paragraph_id': pid, 'text': text, 'word_count': len(text.split()), 'hierarchy': {'level_1': 'Ch'},
         'heading_path': 'Ch', 'source_tag': 'p'}
    if classes:
        u['source_classes'] = classes
    return u


def stage(units, **overrides):
    settings = dict(filter_noise=False, structural_rules={}, judge=None, drop_threshold=0.2, keep_threshold=0.8)
    settings.update(overrides)
    return run_unit_stage(units, **settings)


def test_citation_unit_between_prose_drops_only_itself(tmp_path):
    """At HEAD the filter judged the packed chunk, so one note paragraph took its prose neighbours with it."""
    extractor = _extract(tmp_path, f'<p>{PROSE}</p><p>{CITATIONS}</p><p>{PROSE_TWO}</p>',
                         filter_noise=True, min_chunk_words=1)
    text = '\n'.join(c.text for c in extractor.chunks)

    assert PROSE in text
    assert PROSE_TWO in text
    assert '145,' not in text
    assert [d['stage'] for d in extractor.unit_report['dropped']] == ['noise']


class TestLectionaryReadings:
    RULE = {'lectionary_readings': {'reading_classes': r'^(?:Heading-scripture|Scripture-.*)$'}}

    def units(self):
        return [
            unit(1, 'First Reading', ['Heading-reading']),
            unit(2, 'Isaiah 42:1–4, 6–7', ['Heading-scripture']),
            unit(3, 'Thus says the Lord: Here is my servant whom I uphold,', ['Scripture-verse']),
            unit(4, 'Baptism is the beginning of the Christian life.', ['First-para-after-reading']),
            unit(5, 'When Christ was baptized in the Jordan River, God did not use the water.', ['Normal']),
            unit(6, 'Gospel', ['Heading-reading']),
            unit(7, 'After this Jesus went about Galilee.', ['Scripture-prose']),
            unit(8, 'The Gospel shows the same pattern.', ['Normal']),
        ]

    def test_reading_blocks_dropped_and_author_text_kept(self):
        kept, report = stage(self.units(), structural_rules=self.RULE)

        assert [u['paragraph_id'] for u in kept] == [4, 5, 8]
        assert {d['stage'] for d in report['dropped']} == {'rule:lectionary_readings'}
        assert [d['paragraph_id'] for d in report['dropped']] == [1, 2, 3, 6, 7]

    def test_book_without_rules_unchanged(self):
        units = self.units()

        kept, report = stage(units)

        assert kept == units
        assert report['dropped'] == []

    def test_rule_reads_classes_from_epub_markup(self, tmp_path):
        body = ('<p class="Heading-reading">First Reading</p>'
                '<p class="Scripture-verse">Thus says the Lord: Here is my servant whom I uphold,</p>'
                f'<p class="Normal">{PROSE}</p>')
        extractor = _extract(tmp_path, body, structural_rules=self.RULE, min_chunk_words=1)
        text = '\n'.join(c.text for c in extractor.chunks)

        assert PROSE in text
        assert 'servant whom I uphold' not in text


class TestEditionMarkers:
    RULE = {'edition_markers': {}}

    def test_markers_stripped_translator_insertions_kept(self):
        units = [unit(1, 'Of the creation of the world. [LXVI. Ben.] God made all things good.'),
                 unit(2, '[VII.]'),
                 unit(3, 'And [He] said to them, Peace.')]

        kept, report = stage(units, structural_rules=self.RULE)

        assert [u['text'] for u in kept] == ['Of the creation of the world. God made all things good.',
                                             'And [He] said to them, Peace.']
        assert [d['paragraph_id'] for d in report['dropped']] == [2]

    def test_markers_cannot_return_through_packing_overlap(self):
        """The packer builds overlap and splits from `sentences`, so the rule must rewrite them too."""
        from extraction.core.strategies import TokenAwareChunkingStrategy, TokenChunkConfig

        sentences = [f'Chapter {n} [{numeral}.]—On the resurrection of the body, part {n}, as the apostle teaches it.'
                     for n, numeral in enumerate(['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII'], start=1)]
        units = [{**unit(i, s), 'sentences': [s]} for i, s in enumerate(sentences)]

        kept, _ = stage(units, structural_rules=self.RULE)
        chunks = TokenAwareChunkingStrategy().apply(kept, TokenChunkConfig(
            target_tokens=40, min_tokens=30, max_tokens=60, overlap_percent=0.3, allow_word_estimate=True))

        assert any(c.get('overlap_token_count') for c in chunks)
        assert not any('[V' in c['text'] or '[I' in c['text'] for c in chunks)


def test_exclude_documents_drops_only_the_named_document(tmp_path):
    """The Athanasius collection appends a whole King James Bible; that is not the author's text."""
    extractor = _extract(tmp_path, f'<p>{PROSE}</p><p>{PROSE_TWO}</p>',
                         structural_rules={'exclude_documents': {'pattern': r'^chap_01\.xhtml$'}}, min_chunk_words=1)
    assert extractor.chunks == []
    assert {d['stage'] for d in extractor.unit_report['dropped']} == {'rule:exclude_documents'}

    kept, report = stage([{**unit(1, PROSE), 'chapter_href': 'chp2.xhtml'},
                          {**unit(2, PROSE_TWO), 'chapter_href': 'bible.xhtml'}],
                         structural_rules={'exclude_documents': {'pattern': r'^bible\.xhtml$'}})
    assert [u['paragraph_id'] for u in kept] == [1]
    assert [d['paragraph_id'] for d in report['dropped']] == [2]


def test_unknown_rule_is_an_error():
    with pytest.raises(Exception, match='Unknown structural rule'):
        stage([unit(1, PROSE)], structural_rules={'lectionary': {}})


class FakeJudge:
    version = 'fake-1'

    def __init__(self, scores):
        self.scores = scores
        self.seen = None

    def __call__(self, units):
        self.seen = units
        return [self.scores[u['text']] for u in units]


class TestJudgeBands:

    def test_drop_keep_and_flag_bands(self):
        units = [unit(1, 'copyright page'), unit(2, 'editor intro'), unit(3, 'uncertain epigraph'), unit(4, PROSE)]
        judge = FakeJudge({'copyright page': 0.05, 'editor intro': 0.2, 'uncertain epigraph': 0.5, PROSE: 0.8})

        kept, report = stage(units, judge=judge)

        assert [u['paragraph_id'] for u in kept] == [3, 4]
        assert [(d['paragraph_id'], d['score']) for d in report['dropped']] == [(1, 0.05), (2, 0.2)]
        assert [(f['paragraph_id'], f['score']) for f in report['flagged']] == [(3, 0.5)]
        assert (report['judge_version'], report['drop_threshold'], report['keep_threshold']) == ('fake-1', 0.2, 0.8)

    def test_judge_sees_neighbour_context(self):
        judge = FakeJudge({'a b c': 0.9, 'd e f': 0.9})

        stage([unit(1, 'a b c'), unit(2, 'd e f')], judge=judge)

        assert judge.seen[1]['prev_text'] == 'a b c'
        assert judge.seen[0]['next_text'] == 'd e f'
        assert (judge.seen[1]['position'], judge.seen[1]['total']) == (1, 2)

    @pytest.mark.parametrize('broken', ['raises', 'missing_score', 'short'])
    def test_judge_failure_fails_the_document(self, broken):
        class Broken:
            version = 'broken-1'

            def __call__(self, units):
                if broken == 'raises':
                    raise TimeoutError('judge unavailable after retries')
                if broken == 'missing_score':
                    return [0.9, None]
                return [0.9]

        with pytest.raises(JudgeError):
            stage([unit(1, PROSE), unit(2, PROSE_TWO)], judge=Broken())

    def test_extractor_applies_judge_and_reports_in_output(self, tmp_path):
        judge = FakeJudge({PROSE: 0.95, PROSE_TWO: 0.1})
        extractor = _extract(tmp_path, f'<p>{PROSE}</p><p>{PROSE_TWO}</p>', unit_judge=judge, min_chunk_words=1)
        extractor.extract_metadata()
        output = extractor.get_output_data()

        assert PROSE_TWO not in '\n'.join(c['text'] for c in output['chunks'])
        assert output['unit_report']['dropped'][0]['text'] == PROSE_TWO
        assert output['unit_report']['judge_version'] == 'fake-1'
