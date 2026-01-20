"""Active learning for chunk annotation prioritization."""

from typing import List, Dict, Set, Optional
import numpy as np
from dataclasses import dataclass


@dataclass
class ActiveLearningConfig:
    """Configuration for active learning."""

    bootstrap_size: int = 100
    retrain_interval: int = 500
    uncertainty_threshold: float = 0.8
    diversity_deciles: int = 10


class ActiveLearner:
    """Prioritizes chunks for annotation using active learning."""

    def __init__(
        self,
        chunks: List[Dict],
        config: Optional[ActiveLearningConfig] = None,
    ):
        """Initialize active learner.

        Args:
            chunks: List of chunks from extraction
            config: Active learning configuration
        """
        self.chunks = chunks
        self.config = config or ActiveLearningConfig()

        self.annotated_indices: Set[int] = set()
        self.bootstrap_model = None
        self.phase = "bootstrap"

    def get_next_indices(
        self,
        annotated_indices: Set[int],
        batch_size: int = 1,
    ) -> List[int]:
        """Get next batch of chunk indices to annotate.

        Args:
            annotated_indices: Set of already annotated indices
            batch_size: Number of chunks to return

        Returns:
            List of chunk indices prioritized for annotation
        """
        self.annotated_indices = annotated_indices

        if len(self.annotated_indices) < self.config.bootstrap_size:
            return self._diversity_sampling(batch_size)
        else:
            if self.bootstrap_model is None or self._should_retrain():
                self._train_bootstrap_model()

            return self._model_uncertainty_sampling(batch_size)

    def _diversity_sampling(self, batch_size: int) -> List[int]:
        """Sample chunks spanning quality score range.

        Uses existing quality_score from extraction for fast bootstrapping.

        Args:
            batch_size: Number of chunks to sample

        Returns:
            List of chunk indices
        """
        unannotated = [
            i for i in range(len(self.chunks))
            if i not in self.annotated_indices
        ]

        if not unannotated:
            return []

        quality_scores = []
        for i in unannotated:
            score = self.chunks[i].get('metadata', {}).get('quality', {}).get('score', 0.5)
            quality_scores.append(score)

        quality_scores = np.array(quality_scores)

        deciles = np.linspace(0, 1, self.config.diversity_deciles + 1)

        sampled_indices = []
        for _ in range(batch_size):
            if not unannotated:
                break

            decile_idx = len(sampled_indices) % self.config.diversity_deciles
            min_score = deciles[decile_idx]
            max_score = deciles[decile_idx + 1]

            candidates = [
                i for idx, i in enumerate(unannotated)
                if min_score <= quality_scores[idx] < max_score
            ]

            if not candidates:
                candidates = unannotated

            selected_idx = np.random.choice(len(candidates))
            selected_chunk_idx = candidates[selected_idx]

            sampled_indices.append(selected_chunk_idx)

            unannotated_idx = unannotated.index(selected_chunk_idx)
            unannotated.pop(unannotated_idx)
            quality_scores = np.delete(quality_scores, unannotated_idx)

        return sampled_indices

    def _model_uncertainty_sampling(self, batch_size: int) -> List[int]:
        """Prioritize chunks where bootstrap model is most uncertain.

        Args:
            batch_size: Number of chunks to sample

        Returns:
            List of chunk indices
        """
        if self.bootstrap_model is None:
            return self._diversity_sampling(batch_size)

        unannotated = [
            i for i in range(len(self.chunks))
            if i not in self.annotated_indices
        ]

        if not unannotated:
            return []

        uncertainties = []
        for i in unannotated:
            try:
                proba = self.bootstrap_model.predict_proba(self.chunks[i])
                uncertainty = abs(proba - 0.5)
                uncertainties.append(uncertainty)
            except Exception:
                uncertainties.append(0.5)

        uncertainties = np.array(uncertainties)

        sorted_indices = np.argsort(uncertainties)

        selected = [unannotated[i] for i in sorted_indices[:batch_size]]

        return selected

    def _should_retrain(self) -> bool:
        """Check if model should be retrained.

        Returns:
            True if retraining is needed
        """
        if self.bootstrap_model is None:
            return True

        annotations_since_train = len(self.annotated_indices) - self.config.bootstrap_size

        return annotations_since_train > 0 and annotations_since_train % self.config.retrain_interval == 0

    def _train_bootstrap_model(self) -> None:
        """Train lightweight classifier on annotated chunks.

        Note: This is a placeholder. Actual training requires:
        1. Access to annotation labels (not just indices)
        2. Feature extraction (see ChunkQualityClassifier)
        3. LightGBM model training

        The real implementation will be integrated when labels are available.
        """
        try:
            from extraction.ml.chunk_classifier import ChunkQualityClassifier

            annotated_chunks = [self.chunks[i] for i in self.annotated_indices]

            if len(annotated_chunks) < 10:
                return

            self.bootstrap_model = ChunkQualityClassifier.train_bootstrap(
                annotated_chunks,
                quick=True,
            )

            self.phase = "model_uncertainty"

        except ImportError:
            pass

    def get_progress_estimate(self) -> float:
        """Estimate progress toward annotation completion.

        Returns:
            Progress as percentage (0-100)
        """
        if len(self.chunks) == 0:
            return 100.0

        if self.bootstrap_model is None:
            bootstrap_progress = len(self.annotated_indices) / self.config.bootstrap_size
            return min(bootstrap_progress * 50, 50.0)

        try:
            unannotated = [
                i for i in range(len(self.chunks))
                if i not in self.annotated_indices
            ]

            if not unannotated:
                return 100.0

            uncertain_count = 0
            for i in unannotated:
                proba = self.bootstrap_model.predict_proba(self.chunks[i])
                certainty = abs(proba - 0.5)
                if certainty < (1.0 - self.config.uncertainty_threshold):
                    uncertain_count += 1

            certain_percent = 1.0 - (uncertain_count / len(unannotated))

            base_progress = len(self.annotated_indices) / len(self.chunks)
            weighted_progress = base_progress * 0.5 + certain_percent * 0.5

            return weighted_progress * 100

        except Exception:
            return (len(self.annotated_indices) / len(self.chunks)) * 100
