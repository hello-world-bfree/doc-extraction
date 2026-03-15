"""Training data builder for ML classification models.

This tool aggregates labeled data from multiple annotation sessions and creates
train/test splits suitable for fine-tuning classification models.

Usage:
    training-builder --sessions-dir .annotation_sessions --chunks-dir extractions/ --output-dir training_data/
    training-builder --sessions-dir .annotation_sessions --chunks-dir extractions/ --output-dir training_data/ --test-size 0.3
    training-builder --sessions-dir .annotation_sessions --chunks-dir extractions/ --output-dir training_data/ --balanced
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import Counter
import sys
try:
    from sklearn.model_selection import train_test_split
except ImportError:
    train_test_split = None


class TrainingDataBuilder:
    """Aggregates labeled data from multiple annotation sessions."""

    def __init__(
        self,
        sessions_dir: Path,
        chunks_dir: Path,
        test_size: float = 0.2,
        stratify: bool = True,
        balance_classes: bool = False,
        random_state: int = 42,
    ):
        self.sessions_dir = sessions_dir
        self.chunks_dir = chunks_dir
        self.test_size = test_size
        self.stratify = stratify
        self.balance_classes = balance_classes
        self.random_state = random_state

    def load_session(self, session_file: Path) -> Dict:
        """Load annotation session file."""
        with open(session_file) as f:
            return json.load(f)

    def find_chunks_file(self, session_file: Path) -> Optional[Path]:
        """Find corresponding chunks file for a session.

        Tries multiple patterns:
        1. Exact match: {session_name}.json in chunks_dir
        2. Recursive search: Look in subdirectories
        3. Fuzzy match: Case-insensitive matching
        """
        session_stem = session_file.stem

        exact_match = self.chunks_dir / f"{session_stem}.json"
        if exact_match.exists():
            return exact_match

        for chunks_file in self.chunks_dir.glob("*.json"):
            if chunks_file.stem.lower() == session_stem.lower():
                return chunks_file

        for chunks_file in self.chunks_dir.rglob("*.json"):
            if chunks_file.stem.lower() == session_stem.lower():
                return chunks_file

        return None

    def load_chunks(self, chunks_file: Path) -> Dict[str, Dict]:
        """Load chunks file and index by stable_id."""
        with open(chunks_file) as f:
            data = json.load(f)

        chunks_dict = {}
        for chunk in data.get('chunks', []):
            chunk_id = chunk.get('stable_id') or chunk.get('chunk_id')
            if chunk_id:
                chunks_dict[chunk_id] = chunk

        return chunks_dict

    def create_training_record(
        self,
        chunk: Dict,
        annotation: Dict,
        session_name: str,
    ) -> Dict:
        """Create training record from chunk and annotation."""
        record = {
            'chunk_id': chunk.get('stable_id') or chunk.get('chunk_id'),
            'text': chunk.get('text', ''),
            'label': annotation['label'],
            'source_file': chunk.get('metadata', {}).get('provenance', {}).get('source_file', ''),
            'source_session': session_name,
        }

        metadata = chunk.get('metadata', {})
        record['features'] = {
            'word_count': metadata.get('word_count', 0),
            'sentence_count': metadata.get('sentence_count', 0),
            'hierarchy_depth': len([v for v in metadata.get('hierarchy', {}).values() if v]),
            'quality_score': metadata.get('quality', {}).get('score', 0.0),
            'scripture_refs_count': len(chunk.get('scripture_references', [])),
            'cross_refs_count': len(chunk.get('cross_references', [])),
            'noise_filter_flagged': metadata.get('noise_filter_flagged', False),
        }

        quality_signals = metadata.get('quality', {}).get('signals', {})
        if quality_signals:
            record['features']['garble_rate'] = quality_signals.get('garble_rate', 0.0)
            record['features']['mean_conf'] = quality_signals.get('mean_conf', 0.5)

        record['annotation_metadata'] = {
            'confidence': annotation.get('confidence'),
            'rationale': annotation.get('rationale', ''),
            'issues': annotation.get('issues', []),
            'timestamp': annotation.get('timestamp'),
            'annotator_id': annotation.get('annotator_id', 'default'),
        }

        return record

    def balance_dataset(self, records: List[Dict]) -> List[Dict]:
        """Balance dataset by undersampling majority class."""
        label_counts = Counter(r['label'] for r in records)
        min_count = min(label_counts.values())

        balanced_records = []
        label_samples = {label: [] for label in label_counts.keys()}

        for record in records:
            label_samples[record['label']].append(record)

        for label, samples in label_samples.items():
            if len(samples) > min_count:
                samples = sorted(samples, key=lambda x: x.get('features', {}).get('quality_score', 0), reverse=True)[:min_count]
            balanced_records.extend(samples)

        return balanced_records

    def aggregate_training_data(self) -> Tuple[List[Dict], Dict]:
        """Aggregate labeled data from all sessions.

        Returns:
            Tuple of (records, stats)
        """
        all_records = []
        stats = {
            'sessions_processed': 0,
            'sessions_skipped': 0,
            'total_annotations': 0,
            'label_distribution': Counter(),
            'sources': set(),
        }

        for session_file in sorted(self.sessions_dir.glob("*.json")):
            try:
                session = self.load_session(session_file)
            except Exception as e:
                print(f"Error loading session {session_file.name}: {e}", file=sys.stderr)
                stats['sessions_skipped'] += 1
                continue

            chunks_file = self.find_chunks_file(session_file)
            if not chunks_file:
                print(f"Warning: No chunks file found for {session_file.name}", file=sys.stderr)
                stats['sessions_skipped'] += 1
                continue

            try:
                chunks_dict = self.load_chunks(chunks_file)
            except Exception as e:
                print(f"Error loading chunks {chunks_file.name}: {e}", file=sys.stderr)
                stats['sessions_skipped'] += 1
                continue

            annotations = session.get('annotations', {})

            for chunk_id, annotation in annotations.items():
                if annotation.get('label') is None:
                    continue

                chunk = chunks_dict.get(chunk_id)
                if not chunk:
                    continue

                record = self.create_training_record(
                    chunk,
                    annotation,
                    session_file.stem,
                )

                all_records.append(record)
                stats['total_annotations'] += 1
                stats['label_distribution'][annotation['label']] += 1
                stats['sources'].add(session_file.stem)

            stats['sessions_processed'] += 1

        if self.balance_classes and len(stats['label_distribution']) > 1:
            all_records = self.balance_dataset(all_records)
            stats['balanced'] = True
            stats['balanced_label_distribution'] = Counter(r['label'] for r in all_records)
        else:
            stats['balanced'] = False

        stats['sources'] = sorted(stats['sources'])

        return all_records, stats

    def create_train_test_split(
        self,
        records: List[Dict],
    ) -> Tuple[List[Dict], List[Dict]]:
        """Split records into train and test sets."""
        if train_test_split is None:
            raise ImportError("scikit-learn is required: install with `uv pip install doc-extraction[annotation]`")
        if len(records) == 0:
            return [], []

        labels = [r['label'] for r in records]

        if self.stratify and len(set(labels)) > 1:
            train_records, test_records = train_test_split(
                records,
                test_size=self.test_size,
                stratify=labels,
                random_state=self.random_state,
            )
        else:
            train_records, test_records = train_test_split(
                records,
                test_size=self.test_size,
                random_state=self.random_state,
            )

        return train_records, test_records

    def export_jsonl(self, records: List[Dict], output_path: Path) -> None:
        """Export records to JSONL."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            for record in records:
                f.write(json.dumps(record) + '\n')

    def export_manifest(self, stats: Dict, output_dir: Path) -> None:
        """Export training manifest with statistics."""
        manifest_path = output_dir / 'manifest.json'

        stats_serializable = stats.copy()
        stats_serializable['label_distribution'] = dict(stats['label_distribution'])
        if 'balanced_label_distribution' in stats_serializable:
            stats_serializable['balanced_label_distribution'] = dict(stats['balanced_label_distribution'])

        with open(manifest_path, 'w') as f:
            json.dump(stats_serializable, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Build training dataset from annotated chunks"
    )
    parser.add_argument(
        '--sessions-dir',
        type=Path,
        default=Path('.annotation_sessions'),
        help='Directory containing annotation session files',
    )
    parser.add_argument(
        '--chunks-dir',
        type=Path,
        required=True,
        help='Directory containing extracted chunks files',
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        required=True,
        help='Output directory for train.jsonl and test.jsonl',
    )
    parser.add_argument(
        '--test-size',
        type=float,
        default=0.2,
        help='Proportion for test set (default: 0.2)',
    )
    parser.add_argument(
        '--no-stratify',
        action='store_false',
        dest='stratify',
        default=True,
        help='Disable stratified splitting',
    )
    parser.add_argument(
        '--balanced',
        action='store_true',
        help='Balance classes by undersampling majority class',
    )
    parser.add_argument(
        '--random-state',
        type=int,
        default=42,
        help='Random seed for reproducibility (default: 42)',
    )

    args = parser.parse_args()

    if not args.sessions_dir.exists():
        print(f"Error: Sessions directory not found: {args.sessions_dir}", file=sys.stderr)
        sys.exit(1)

    if not args.chunks_dir.exists():
        print(f"Error: Chunks directory not found: {args.chunks_dir}", file=sys.stderr)
        sys.exit(1)

    builder = TrainingDataBuilder(
        sessions_dir=args.sessions_dir,
        chunks_dir=args.chunks_dir,
        test_size=args.test_size,
        stratify=args.stratify,
        balance_classes=args.balanced,
        random_state=args.random_state,
    )

    print(f"Aggregating training data from {args.sessions_dir}...")
    all_records, stats = builder.aggregate_training_data()

    print(f"\nDataset Statistics:")
    print(f"  Sessions processed: {stats['sessions_processed']}")
    print(f"  Sessions skipped: {stats['sessions_skipped']}")
    print(f"  Total annotations: {stats['total_annotations']}")
    print(f"  Label distribution: {dict(stats['label_distribution'])}")
    if stats['balanced']:
        print(f"  Balanced distribution: {dict(stats['balanced_label_distribution'])}")
    print(f"  Sources: {len(stats['sources'])} EPUBs")

    train_records, test_records = builder.create_train_test_split(all_records)

    print(f"\nTrain/Test Split:")
    print(f"  Train: {len(train_records)} records")
    print(f"  Test: {len(test_records)} records")

    builder.export_jsonl(train_records, args.output_dir / 'train.jsonl')
    builder.export_jsonl(test_records, args.output_dir / 'test.jsonl')
    builder.export_manifest(stats, args.output_dir)

    print(f"\nTraining data exported to: {args.output_dir}")
    print(f"  - train.jsonl")
    print(f"  - test.jsonl")
    print(f"  - manifest.json")


if __name__ == '__main__':
    main()
