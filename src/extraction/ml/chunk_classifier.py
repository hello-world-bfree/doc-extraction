"""ML classifier for chunk quality filtering."""

from typing import Dict, List, Optional
import re
import numpy as np
from pathlib import Path


def extract_features(chunk: Dict) -> Dict[str, float]:
    """Extract 28 metadata features from chunk for ML classification.

    Args:
        chunk: Chunk dictionary with metadata

    Returns:
        Dictionary of feature name to value
    """
    metadata = chunk.get('metadata', {})
    text = chunk.get('text', '')

    features = {}

    word_count = metadata.get('word_count', 0)
    sentence_count = metadata.get('sentence_count', 0)
    text_length = len(text)

    features['word_count'] = word_count
    features['text_length'] = text_length
    features['sentence_count'] = sentence_count

    hierarchy = metadata.get('hierarchy', {})
    hierarchy_depth = len([v for v in hierarchy.values() if v])
    features['hierarchy_depth'] = hierarchy_depth

    features['avg_sentence_length'] = word_count / max(sentence_count, 1)
    features['chars_per_word'] = text_length / max(word_count, 1)

    words = text.lower().split()
    features['tokens_per_word'] = len(words) / max(word_count, 1)

    unique_words = set(words)
    features['unique_words_ratio'] = len(unique_words) / max(len(words), 1)

    stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
    features['stopword_ratio'] = sum(1 for w in words if w in stopwords) / max(len(words), 1)

    punctuation_chars = sum(1 for c in text if c in '.,;:!?')
    features['punctuation_density'] = punctuation_chars / max(text_length, 1)

    number_tokens = sum(1 for token in text.split() if token.isdigit())
    features['number_token_ratio'] = number_tokens / max(len(text.split()), 1)

    capital_chars = sum(1 for c in text if c.isupper())
    features['capital_ratio'] = capital_chars / max(text_length, 1)

    scripture_refs = chunk.get('scripture_references', [])
    cross_refs = chunk.get('cross_references', [])
    dates = chunk.get('dates_mentioned', [])

    features['scripture_density'] = len(scripture_refs) / max(word_count / 1000, 1)
    features['cross_ref_density'] = len(cross_refs) / max(word_count / 1000, 1)
    features['date_density'] = len(dates) / max(word_count / 1000, 1)

    features['has_hierarchy'] = 1.0 if hierarchy_depth > 0 else 0.0
    features['position_normalized'] = metadata.get('source_order', 0) / 1000.0

    hierarchy_levels = [v for v in hierarchy.values() if v]
    expected_depth = max(1, hierarchy_depth)
    features['hierarchy_consistency'] = len(hierarchy_levels) / expected_depth

    tokens = text.split()
    number_punct_tokens = sum(1 for t in tokens if re.match(r'^[\d\W]+$', t))
    features['number_density'] = number_punct_tokens / max(len(tokens), 1)

    features['token_word_ratio'] = len(tokens) / max(word_count, 1)

    reference_patterns = len(re.findall(r'\d+:\d+(-\d+)?', text))
    features['reference_pattern_density'] = reference_patterns / max(word_count, 1)

    lines = text.split('\n')
    short_lines = sum(1 for line in lines if len(line.split()) < 5)
    features['short_line_ratio'] = short_lines / max(len(lines), 1)

    nav_keywords = ['next', 'previous', 'back', 'index', 'contents', 'page']
    features['nav_keyword_presence'] = 1.0 if any(kw in text.lower() for kw in nav_keywords) else 0.0

    quality = metadata.get('quality', {})
    signals = quality.get('signals', {})

    features['garble_rate'] = signals.get('garble_rate', 0.0)
    features['mean_conf'] = signals.get('mean_conf', 0.5)
    features['line_len_std_norm'] = signals.get('line_len_std_norm', 0.5)

    return features


class ChunkQualityClassifier:
    """ML classifier for filtering low-quality chunks."""

    FEATURE_NAMES = [
        'word_count',
        'text_length',
        'sentence_count',
        'hierarchy_depth',
        'avg_sentence_length',
        'chars_per_word',
        'tokens_per_word',
        'unique_words_ratio',
        'stopword_ratio',
        'punctuation_density',
        'number_token_ratio',
        'capital_ratio',
        'scripture_density',
        'cross_ref_density',
        'date_density',
        'has_hierarchy',
        'position_normalized',
        'hierarchy_consistency',
        'number_density',
        'token_word_ratio',
        'reference_pattern_density',
        'short_line_ratio',
        'nav_keyword_presence',
        'garble_rate',
        'mean_conf',
        'line_len_std_norm',
    ]

    def __init__(self, model, threshold: float = 0.5):
        """Initialize classifier.

        Args:
            model: Trained LightGBM model
            threshold: Decision threshold (default: 0.5)
        """
        self.model = model
        self.threshold = threshold

    @classmethod
    def load(cls, model_path: Path, threshold_path: Optional[Path] = None) -> "ChunkQualityClassifier":
        """Load trained model from disk.

        Args:
            model_path: Path to LightGBM model file
            threshold_path: Path to threshold file (default: optimal_threshold.npy)

        Returns:
            ChunkQualityClassifier instance
        """
        try:
            import lightgbm as lgb
        except ImportError:
            raise ImportError(
                "LightGBM is required for ML filtering. "
                "Install with: uv pip install -e '.[annotation]'"
            )

        model = lgb.Booster(model_file=str(model_path))

        threshold = 0.5
        if threshold_path is None:
            threshold_path = model_path.parent / 'optimal_threshold.npy'

        if threshold_path.exists():
            threshold = float(np.load(threshold_path))

        return cls(model, threshold)

    def predict(self, chunk: Dict) -> int:
        """Predict if chunk is GOOD (0) or BAD (1).

        Args:
            chunk: Chunk dictionary

        Returns:
            0 for GOOD, 1 for BAD
        """
        proba = self.predict_proba(chunk)
        return 1 if proba >= self.threshold else 0

    def predict_proba(self, chunk: Dict) -> float:
        """Return probability of BAD class.

        Args:
            chunk: Chunk dictionary

        Returns:
            Probability (0-1) that chunk is BAD
        """
        features = extract_features(chunk)

        X = np.array([[features.get(name, 0.0) for name in self.FEATURE_NAMES]])

        proba = self.model.predict(X)[0]

        return float(proba)

    @classmethod
    def train_bootstrap(
        cls,
        annotated_chunks: List[Dict],
        quick: bool = True,
    ) -> "ChunkQualityClassifier":
        """Train lightweight classifier for active learning bootstrap.

        Args:
            annotated_chunks: List of chunks with 'annotation' field
            quick: Whether to use quick training (fewer boosting rounds)

        Returns:
            Trained classifier
        """
        try:
            import lightgbm as lgb
        except ImportError:
            raise ImportError(
                "LightGBM is required for ML filtering. "
                "Install with: uv pip install -e '.[annotation]'"
            )

        X = []
        y = []

        for chunk in annotated_chunks:
            annotation = chunk.get('annotation', {})
            label = annotation.get('label')

            if label is None:
                continue

            features = extract_features(chunk)
            feature_vector = [features.get(name, 0.0) for name in cls.FEATURE_NAMES]

            X.append(feature_vector)
            y.append(label)

        X = np.array(X)
        y = np.array(y)

        class_counts = np.bincount(y)
        if len(class_counts) < 2:
            raise ValueError("Need both GOOD and BAD labels to train classifier")

        class_weight = {0: 1.0, 1: class_counts[0] / class_counts[1]}

        params = {
            'objective': 'binary',
            'num_leaves': 15 if quick else 31,
            'learning_rate': 0.1 if quick else 0.05,
            'verbose': -1,
            'class_weight': class_weight,
        }

        train_data = lgb.Dataset(X, label=y)
        num_rounds = 10 if quick else 100

        model = lgb.train(params, train_data, num_boost_round=num_rounds)

        return cls(model, threshold=0.5)

    def save(self, model_path: Path, threshold_path: Optional[Path] = None) -> None:
        """Save model to disk.

        Args:
            model_path: Path to save LightGBM model
            threshold_path: Path to save threshold (default: optimal_threshold.npy)
        """
        model_path.parent.mkdir(parents=True, exist_ok=True)
        self.model.save_model(str(model_path))

        if threshold_path is None:
            threshold_path = model_path.parent / 'optimal_threshold.npy'

        np.save(threshold_path, self.threshold)
