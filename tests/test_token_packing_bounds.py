"""Token bounds of TokenAwareChunkingStrategy: every chunk fits the embedding model, overlap included.

Chunks over the embedding model's limit are truncated at embed time, so their tail is unretrievable;
chunks flushed early under the minimum carry too little context to rank.
"""

import pytest

from extraction.core import strategies
from extraction.core.strategies import TokenAwareChunkingStrategy, TokenChunkConfig
from extraction.exceptions import DependencyError


class WordTokenizer:
    """One token per whitespace word, plus BOS/EOS like the real tokenizer."""

    def encode(self, text, add_special_tokens=True):
        return text.split() + (['<bos>', '<eos>'] if add_special_tokens else [])


def tokens(text):
    return len(WordTokenizer().encode(text))


@pytest.fixture(autouse=True)
def word_tokenizer(monkeypatch):
    monkeypatch.setattr(strategies, '_load_tokenizer', lambda name, allow: WordTokenizer())


def retrieval_config(**overrides):
    settings = dict(target_tokens=320, min_tokens=256, max_tokens=400, overlap_percent=0.15)
    settings.update(overrides)
    return TokenAwareChunkingStrategy(), TokenChunkConfig(**settings)


def sentence(start, n_words):
    return ' '.join(f'w{start + i}' for i in range(n_words - 1)) + f' w{start + n_words - 1}.'


def paragraph(pid, n_words, section='Chapter 1', sentence_words=20):
    sents = []
    i = 0
    while i < n_words:
        k = min(sentence_words, n_words - i)
        sents.append(sentence(pid * 100_000 + i, k))
        i += k
    text = ' '.join(sents)
    return {
        'paragraph_id': pid, 'text': text, 'sentences': sents, 'word_count': n_words,
        'hierarchy': {'level_1': section}, 'content_type': 'prose', 'chapter_href': 'c.xhtml',
        'source_order': 0, 'source_tag': 'p', 'doc_stable_id': 'doc',
    }


def strip_overlap(chunk):
    if chunk.get('overlap_token_count'):
        return chunk['text'].split('\n\n', 1)[1]
    return chunk['text']


def test_paragraph_over_max_split_within_max_and_text_preserved():
    strategy, config = retrieval_config()
    para = paragraph(1, 1198)

    chunks = strategy.apply([para], config)

    assert len(chunks) >= 3
    assert all(tokens(c['text']) <= 400 for c in chunks)
    rebuilt = ' '.join(strip_overlap(c) for c in chunks)
    assert rebuilt.split() == para['text'].split()


def test_sentence_over_max_split_at_token_boundary():
    strategy, config = retrieval_config()
    para = paragraph(1, 900, sentence_words=900)

    chunks = strategy.apply([para], config)

    assert all(tokens(c['text']) <= 400 for c in chunks)
    assert ' '.join(strip_overlap(c) for c in chunks).split() == para['text'].split()


def test_overlap_counted_inside_max_tokens():
    strategy, config = retrieval_config()
    paras = [paragraph(i, n) for i, n in enumerate([390, 395, 380, 398, 200, 390], start=1)]

    chunks = strategy.apply(paras, config)

    assert any(c.get('overlap_token_count') for c in chunks)
    assert all(tokens(c['text']) <= 400 for c in chunks)


def test_mid_section_chunks_reach_min_tokens():
    strategy, config = retrieval_config()
    sizes = [100, 250, 180, 60, 300, 90, 40, 220, 130, 75, 310, 50]
    paras = [paragraph(i, n) for i, n in enumerate(sizes, start=1)]

    chunks = strategy.apply(paras, config)

    assert all(tokens(c['text']) <= 400 for c in chunks)
    assert all(tokens(c['text']) >= 256 for c in chunks[:-1])


def test_long_next_sentence_still_fills_to_min_tokens():
    strategy, config = retrieval_config()
    long_tail = paragraph(2, 30, sentence_words=30)
    tail_sentence = sentence(900_000, 200)
    long_tail['sentences'].append(tail_sentence)
    long_tail['text'] += ' ' + tail_sentence
    paras = [paragraph(1, 218), long_tail, paragraph(3, 200)]

    chunks = strategy.apply(paras, config)

    assert tokens(chunks[0]['text']) >= 256
    assert all(tokens(c['text']) <= 400 for c in chunks)


def test_short_section_closes_at_section_end():
    strategy, config = retrieval_config()
    paras = [paragraph(1, 118, section='One'), paragraph(2, 300, section='Two')]

    chunks = strategy.apply(paras, config)

    assert [c['hierarchy']['level_1'] for c in chunks] == ['One', 'Two']
    assert chunks[0]['text'] == paras[0]['text']
    assert chunks[0]['quality_flags'] == ['below_rag_minimum']


def test_chunk_reaching_max_absolute_tokens_is_an_error():
    strategy, config = retrieval_config(max_absolute_tokens=300)

    with pytest.raises(AssertionError, match='max_absolute_tokens'):
        strategy.apply([paragraph(1, 390)], config)


class TestTokenizerUnavailable:

    @pytest.fixture(autouse=True)
    def missing_tokenizer(self, monkeypatch):
        monkeypatch.undo()

        def gated(name):
            raise OSError(f'{name} is a gated repository')

        monkeypatch.setattr('extraction.tools.tokenizer_utils.load_tokenizer', gated)

    def test_raises_naming_the_tokenizer(self):
        strategy, config = retrieval_config()

        with pytest.raises(DependencyError, match='google/embeddinggemma-300m'):
            strategy.apply([paragraph(1, 50)], config)

    def test_word_estimate_only_when_allowed(self):
        strategy, config = retrieval_config(allow_word_estimate=True)

        chunks = strategy.apply([paragraph(1, 50)], config)

        assert len(chunks) == 1
