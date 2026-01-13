"""
Extraction - Multi-format document extraction library.

Version 2.1.0
"""

__version__ = "2.1.0"

# Re-export commonly used classes for convenience
from extraction.core.models import Chunk, Metadata, Provenance, Quality, Hierarchy

__all__ = [
    "__version__",
    "Chunk",
    "Metadata",
    "Provenance",
    "Quality",
    "Hierarchy",
]
