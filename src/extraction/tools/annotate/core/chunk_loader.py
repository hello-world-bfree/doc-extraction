"""Load chunks from extraction JSON output."""

from pathlib import Path
from typing import List, Dict, Tuple, Optional
import json


class ChunkLoader:
    """Loads chunks from extraction library output."""

    @staticmethod
    def load_from_file(file_path: Path) -> List[Dict]:
        """Load chunks from extraction JSON output file.

        Args:
            file_path: Path to extraction output JSON

        Returns:
            List of chunk dictionaries with metadata

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        chunks, _ = ChunkLoader.load_from_file_with_metadata(file_path)
        return chunks

    @staticmethod
    def load_from_file_with_metadata(file_path: Path) -> Tuple[List[Dict], Dict]:
        """Load chunks and document metadata from extraction JSON output file.

        Args:
            file_path: Path to extraction output JSON

        Returns:
            Tuple of (chunks list, document metadata dict)

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path) as f:
            data = json.load(f)

        if 'chunks' not in data:
            raise ValueError(f"Invalid extraction file: missing 'chunks' key")

        chunks = data['chunks']
        doc_metadata = data.get('metadata', {})

        source_file = doc_metadata.get('provenance', {}).get('source_file', file_path.name)

        for i, chunk in enumerate(chunks):
            if 'stable_id' not in chunk and 'chunk_id' not in chunk:
                chunk['chunk_id'] = f"{source_file}_chunk_{i}"

            if 'metadata' not in chunk:
                chunk['metadata'] = {}

            if 'source_file' not in chunk['metadata']:
                chunk['metadata']['source_file'] = source_file

            if 'source_order' not in chunk['metadata']:
                chunk['metadata']['source_order'] = i

        return chunks, doc_metadata

    @staticmethod
    def load_from_jsonl(file_path: Path) -> List[Dict]:
        """Load chunks from JSONL file (one chunk per line).

        Args:
            file_path: Path to JSONL file

        Returns:
            List of chunk dictionaries
        """
        chunks, _ = ChunkLoader.load_from_jsonl_with_metadata(file_path)
        return chunks

    @staticmethod
    def load_from_jsonl_with_metadata(file_path: Path) -> Tuple[List[Dict], Dict]:
        """Load chunks from JSONL file with inferred document metadata.

        Args:
            file_path: Path to JSONL file

        Returns:
            Tuple of (chunks list, document metadata dict)
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        chunks = []
        with open(file_path) as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue

                chunk = json.loads(line)

                if 'stable_id' not in chunk and 'chunk_id' not in chunk:
                    chunk['chunk_id'] = f"chunk_{i}"

                chunks.append(chunk)

        doc_metadata = {'source_file': file_path.name}
        return chunks, doc_metadata

    @staticmethod
    def load(file_path: Path) -> List[Dict]:
        """Auto-detect format and load chunks.

        Args:
            file_path: Path to chunk file (JSON or JSONL)

        Returns:
            List of chunk dictionaries
        """
        chunks, _ = ChunkLoader.load_with_metadata(file_path)
        return chunks

    @staticmethod
    def load_with_metadata(file_path: Path) -> Tuple[List[Dict], Dict]:
        """Auto-detect format and load chunks with document metadata.

        Args:
            file_path: Path to chunk file (JSON or JSONL)

        Returns:
            Tuple of (chunks list, document metadata dict)
        """
        file_path = Path(file_path)

        if file_path.suffix == '.jsonl':
            return ChunkLoader.load_from_jsonl_with_metadata(file_path)
        elif file_path.suffix == '.json':
            return ChunkLoader.load_from_file_with_metadata(file_path)
        else:
            try:
                return ChunkLoader.load_from_file_with_metadata(file_path)
            except (ValueError, KeyError):
                return ChunkLoader.load_from_jsonl_with_metadata(file_path)
