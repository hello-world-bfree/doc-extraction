"""Corpus builder for aggregating good chunks across multiple annotation sessions.

This tool collects all "good" (label=0) chunks from multiple EPUBs that have been
annotated, applies any edits, and produces a unified corpus ready for embedding
and RAG applications.

Usage:
    corpus-builder --sessions-dir .annotation_sessions --chunks-dir extractions/ --output corpus.jsonl
    corpus-builder --sessions-dir .annotation_sessions --chunks-dir extractions/ --output corpus.jsonl --apply-edits
    corpus-builder --sessions-dir .annotation_sessions --chunks-dir extractions/ --output corpus.jsonl --min-quality 0.8
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional
import sys


class CorpusBuilder:
    """Aggregates good chunks from multiple annotation sessions."""

    def __init__(
        self,
        sessions_dir: Path,
        chunks_dir: Path,
        apply_edits: bool = True,
        min_quality_score: Optional[float] = None,
        include_metadata: bool = True,
    ):
        self.sessions_dir = sessions_dir
        self.chunks_dir = chunks_dir
        self.apply_edits = apply_edits
        self.min_quality_score = min_quality_score
        self.include_metadata = include_metadata

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

    def apply_edit(self, chunk: Dict, edit_data) -> Dict:
        """Apply edit to chunk.

        Args:
            chunk: Original chunk dict
            edit_data: Either a list of version dicts or a dict with 'versions' key
        """
        edited_chunk = chunk.copy()

        if isinstance(edit_data, list):
            versions = edit_data
        else:
            versions = edit_data.get('versions', [edit_data])

        if not versions:
            return chunk

        latest_version = versions[-1]
        edited_chunk['text'] = latest_version.get('edited_text', latest_version.get('text', chunk['text']))

        edited_chunk['edited'] = True
        edited_chunk['edited_chunk_id'] = latest_version.get('edited_chunk_id', '')
        edited_chunk['edit_reason'] = latest_version.get('reason', '')
        edited_chunk['edit_timestamp'] = latest_version.get('timestamp', '')
        edited_chunk['edit_version'] = len(versions)

        return edited_chunk

    def build_corpus(self) -> List[Dict]:
        """Build corpus from all annotation sessions.

        Returns:
            List of good chunks with metadata
        """
        corpus = []
        stats = {
            'sessions_processed': 0,
            'sessions_skipped': 0,
            'good_chunks': 0,
            'edited_chunks': 0,
            'quality_filtered': 0,
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
            edited_chunks = session.get('edited_chunks', {})

            for chunk_id, annotation in annotations.items():
                if annotation.get('label') != 0:
                    continue

                chunk = chunks_dict.get(chunk_id)
                if not chunk:
                    continue

                if self.min_quality_score is not None:
                    quality_score = chunk.get('metadata', {}).get('quality', {}).get('score', 0.0)
                    if quality_score < self.min_quality_score:
                        stats['quality_filtered'] += 1
                        continue

                if self.apply_edits and chunk_id in edited_chunks:
                    chunk = self.apply_edit(chunk, edited_chunks[chunk_id])
                    stats['edited_chunks'] += 1

                if self.include_metadata:
                    chunk['corpus_metadata'] = {
                        'source_session': session_file.stem,
                        'annotation_timestamp': annotation.get('timestamp'),
                        'annotator_id': annotation.get('annotator_id', 'default'),
                        'confidence': annotation.get('confidence'),
                        'rationale': annotation.get('rationale', ''),
                    }

                corpus.append(chunk)
                stats['good_chunks'] += 1

            stats['sessions_processed'] += 1

        return corpus, stats

    def export_corpus(self, corpus: List[Dict], output_path: Path) -> None:
        """Export corpus to JSONL."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            for chunk in corpus:
                f.write(json.dumps(chunk) + '\n')

    def export_manifest(self, stats: Dict, output_path: Path) -> None:
        """Export corpus manifest with statistics."""
        manifest_path = output_path.parent / f"{output_path.stem}_manifest.json"

        with open(manifest_path, 'w') as f:
            json.dump(stats, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Build production corpus from annotated chunks"
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
        '--output',
        type=Path,
        required=True,
        help='Output JSONL file for corpus',
    )
    parser.add_argument(
        '--apply-edits',
        action='store_true',
        default=True,
        help='Apply chunk edits to output (default: True)',
    )
    parser.add_argument(
        '--no-apply-edits',
        action='store_false',
        dest='apply_edits',
        help='Do not apply chunk edits',
    )
    parser.add_argument(
        '--min-quality',
        type=float,
        help='Minimum quality score for inclusion (0.0-1.0)',
    )
    parser.add_argument(
        '--no-metadata',
        action='store_false',
        dest='include_metadata',
        default=True,
        help='Exclude corpus metadata (annotation info)',
    )
    parser.add_argument(
        '--manifest',
        action='store_true',
        help='Export corpus manifest with statistics',
    )

    args = parser.parse_args()

    if not args.sessions_dir.exists():
        print(f"Error: Sessions directory not found: {args.sessions_dir}", file=sys.stderr)
        sys.exit(1)

    if not args.chunks_dir.exists():
        print(f"Error: Chunks directory not found: {args.chunks_dir}", file=sys.stderr)
        sys.exit(1)

    builder = CorpusBuilder(
        sessions_dir=args.sessions_dir,
        chunks_dir=args.chunks_dir,
        apply_edits=args.apply_edits,
        min_quality_score=args.min_quality,
        include_metadata=args.include_metadata,
    )

    print(f"Building corpus from {args.sessions_dir}...")
    corpus, stats = builder.build_corpus()

    print(f"\nCorpus Statistics:")
    print(f"  Sessions processed: {stats['sessions_processed']}")
    print(f"  Sessions skipped: {stats['sessions_skipped']}")
    print(f"  Good chunks: {stats['good_chunks']}")
    print(f"  Edited chunks: {stats['edited_chunks']}")
    print(f"  Quality filtered: {stats['quality_filtered']}")

    builder.export_corpus(corpus, args.output)
    print(f"\nCorpus exported to: {args.output}")

    if args.manifest:
        builder.export_manifest(stats, args.output)
        print(f"Manifest exported to: {args.output.parent / f'{args.output.stem}_manifest.json'}")


if __name__ == '__main__':
    main()
