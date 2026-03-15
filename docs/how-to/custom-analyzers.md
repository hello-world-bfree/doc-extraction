# Creating Custom Analyzers

This guide shows you how to create domain-specific analyzers to enrich extracted documents with specialized metadata.

## What Are Analyzers?

Analyzers add domain-specific metadata after extraction:

- **Document type**: Classify documents (e.g., "Research Paper", "Legal Contract")
- **Subjects**: Extract topic areas (e.g., "Machine Learning", "Privacy Law")
- **Themes**: Identify key themes from headings
- **Related documents**: Find cross-references
- **Geographic focus**: Detect location mentions

The extraction library includes two built-in analyzers:

- **CatholicAnalyzer**: For religious texts (encyclicals, catechisms, etc.)
- **GenericAnalyzer**: Minimal domain logic (default)

## When to Create a Custom Analyzer

Create a custom analyzer when:

- You have domain-specific document types (legal, medical, academic)
- You need specialized subject classification
- You want to extract domain-specific cross-references
- Generic analyzer produces poor quality metadata

**Don't create a custom analyzer when**:

- GenericAnalyzer already works well for your documents
- You only need structural metadata (hierarchy, word counts)
- You can post-process metadata externally

## Step-by-Step Guide

### 1. Create Analyzer File

Create `src/extraction/analyzers/medical.py` (example domain):

```python
#!/usr/bin/env python3

"""
Medical document analyzer.

Extracts metadata for medical literature including research papers,
clinical guidelines, and patient education materials.
"""

import re
from typing import Dict, List, Any
from collections import OrderedDict

from .base import BaseAnalyzer


class MedicalAnalyzer(BaseAnalyzer):
    """
    Analyzer for medical and healthcare documents.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
```

### 2. Define Document Types

Define patterns to classify documents:

```python
class MedicalAnalyzer(BaseAnalyzer):
    # Document type patterns
    DOC_TYPE_PATTERNS = {
        "Clinical Trial": [
            r"randomized controlled trial",
            r"\brct\b",
            r"clinical trial",
            r"trial registration",
        ],
        "Systematic Review": [
            r"systematic review",
            r"meta-analysis",
            r"prisma",
        ],
        "Clinical Guideline": [
            r"clinical guideline",
            r"practice guideline",
            r"recommendations for",
        ],
        "Case Report": [
            r"case report",
            r"case presentation",
            r"we present a case",
        ],
        "Research Paper": [
            r"abstract.*introduction.*methods.*results",
            r"peer.reviewed",
        ],
    }

    def infer_document_type(self, text: str) -> str:
        """
        Infer medical document type from text patterns.

        Args:
            text: Complete text of the document

        Returns:
            Document type string (empty if no match)
        """
        text_lower = text.lower()

        for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            if any(re.search(pattern, text_lower) for pattern in patterns):
                return doc_type

        return ""
```

### 3. Extract Subjects

Define subject areas for your domain:

```python
class MedicalAnalyzer(BaseAnalyzer):
    # Subject patterns
    SUBJECT_PATTERNS = {
        "Cardiology": [
            r"\bcardiac\b",
            r"\bheart\b",
            r"\bcardiovascular\b",
            r"\bmyocardial\b",
        ],
        "Oncology": [
            r"\bcancer\b",
            r"\btumor\b",
            r"\bneoplasm\b",
            r"\bchemotherapy\b",
        ],
        "Neurology": [
            r"\bneurological\b",
            r"\bbrain\b",
            r"\bstroke\b",
            r"\bseizure\b",
        ],
        "Pharmacology": [
            r"\bdrug\b",
            r"\bmedication\b",
            r"\bpharmacological\b",
            r"\bdose\b",
        ],
        "Epidemiology": [
            r"\bepidemiolog",
            r"\bprevalence\b",
            r"\bincidence\b",
            r"\boutbreak\b",
        ],
    }

    def extract_subjects(self, text: str, chunks: List[Dict]) -> List[str]:
        """
        Extract medical subject areas from text.

        Args:
            text: Complete text of the document
            chunks: List of chunk dictionaries

        Returns:
            List of subject strings
        """
        text_lower = text.lower()

        subjects = [
            subject
            for subject, patterns in self.SUBJECT_PATTERNS.items()
            if any(re.search(pattern, text_lower) for pattern in patterns)
        ]

        return subjects
```

### 4. Extract Themes

Extract meaningful headings from document hierarchy:

```python
class MedicalAnalyzer(BaseAnalyzer):
    def extract_themes(self, chunks: List[Dict]) -> List[str]:
        """
        Extract key themes from document hierarchy.

        Args:
            chunks: List of chunk dictionaries with hierarchy

        Returns:
            List of up to 10 unique theme strings
        """
        themes = []

        for chunk in chunks:
            hierarchy = chunk.get("hierarchy", {})

            # Extract headings from levels 1-4
            for level in ["level_1", "level_2", "level_3", "level_4"]:
                heading = hierarchy.get(level, "")

                # Filter out short or generic headings
                if heading and len(heading) > 10:
                    themes.append(heading)

        # Deduplicate while preserving order
        unique_themes = list(OrderedDict.fromkeys(themes))

        # Return top 10
        return unique_themes[:10]
```

### 5. Extract Related Documents

Find cross-references to other documents:

```python
class MedicalAnalyzer(BaseAnalyzer):
    # Known medical document names
    RELATED_DOCUMENTS = [
        "WHO Guidelines",
        "CDC Recommendations",
        "NICE Guidelines",
        "Cochrane Review",
        "UpToDate",
        "PubMed",
        "ClinicalTrials.gov",
    ]

    def extract_related_documents(self, text: str) -> List[str]:
        """
        Find references to medical documents and databases.

        Args:
            text: Complete text of the document

        Returns:
            Sorted list of unique related document names
        """
        related = [
            doc for doc in self.RELATED_DOCUMENTS
            if re.search(re.escape(doc), text, re.IGNORECASE)
        ]

        return sorted(set(related))
```

### 6. Infer Geographic Focus

Detect geographic scope of the document:

```python
class MedicalAnalyzer(BaseAnalyzer):
    # Geographic patterns
    GEO_PATTERNS = {
        "Global": [
            r"\bglobal\b",
            r"\bworldwide\b",
            r"\binternational\b",
            r"\bwho\b",  # World Health Organization
        ],
        "United States": [
            r"\bus\b",
            r"\bunited states\b",
            r"\bamerica\b",
            r"\bcdc\b",
            r"\bfda\b",
        ],
        "European Union": [
            r"\beu\b",
            r"\beuropean union\b",
            r"\bema\b",  # European Medicines Agency
        ],
    }

    def infer_geographic_focus(self, text: str) -> str:
        """
        Infer geographic focus of medical document.

        Args:
            text: Complete text of the document

        Returns:
            Geographic focus string (empty if no match)
        """
        text_lower = text.lower()

        for location, patterns in self.GEO_PATTERNS.items():
            if any(re.search(pattern, text_lower) for pattern in patterns):
                return location

        return ""
```

### 7. Orchestrate Enrichment

Implement the main `enrich_metadata` method:

```python
from ..core.extraction import extract_dates


class MedicalAnalyzer(BaseAnalyzer):
    def enrich_metadata(
        self,
        base_metadata: Dict[str, Any],
        full_text: str,
        chunks: List[Dict]
    ) -> Dict[str, Any]:
        """
        Enrich metadata with medical-specific fields.

        Args:
            base_metadata: Basic metadata (title, author, etc.)
            full_text: Complete text of the document
            chunks: List of chunk dictionaries

        Returns:
            Enriched metadata dictionary
        """
        # Extract all domain-specific fields
        base_metadata["document_type"] = self.infer_document_type(full_text)
        base_metadata["subject"] = self.extract_subjects(full_text, chunks)
        base_metadata["key_themes"] = self.extract_themes(chunks)
        base_metadata["related_documents"] = self.extract_related_documents(full_text)
        base_metadata["geographic_focus"] = self.infer_geographic_focus(full_text)

        # Extract publication date (uses base implementation)
        dates = extract_dates(full_text)
        base_metadata["publication_date"] = self.extract_promulgation_date(full_text, dates)

        # Calculate statistics
        stats = self.calculate_stats(chunks)
        base_metadata["word_count"] = stats["word_count"]
        base_metadata["pages"] = stats["pages"]

        return base_metadata
```

## Pattern Matching Best Practices

### Use Word Boundaries

```python
# Bad: Matches "heart" in "sweetheart"
r"heart"

# Good: Matches only whole word "heart"
r"\bheart\b"
```

### Case-Insensitive Matching

```python
# Convert text to lowercase first
text_lower = text.lower()

# Or use re.IGNORECASE flag
re.search(pattern, text, re.IGNORECASE)
```

### Multi-Word Patterns

```python
# Allow flexible spacing
r"clinical\s+trial"  # One or more spaces
r"randomized\s*controlled"  # Zero or more spaces
```

### Alternative Patterns

```python
# Match any variation
r"(?:tumor|tumour)"  # US or UK spelling
r"(?:cancer|neoplasm|malignancy)"  # Synonyms
```

### Escaping Special Characters

```python
# Escape dots, parentheses, etc.
re.escape("ClinicalTrials.gov")  # Becomes "ClinicalTrials\.gov"
```

## Testing Your Analyzer

Create `tests/test_medical_analyzer.py`:

```python
import pytest
from extraction.analyzers.medical import MedicalAnalyzer


def test_document_type_clinical_trial():
    analyzer = MedicalAnalyzer()

    text = """
    This randomized controlled trial evaluated the efficacy of...
    Trial registration: NCT12345678
    """

    doc_type = analyzer.infer_document_type(text)
    assert doc_type == "Clinical Trial"


def test_extract_subjects_cardiology():
    analyzer = MedicalAnalyzer()

    text = """
    Cardiac function was assessed using echocardiography.
    Myocardial infarction was diagnosed based on...
    """

    subjects = analyzer.extract_subjects(text, [])
    assert "Cardiology" in subjects


def test_extract_themes_from_hierarchy():
    analyzer = MedicalAnalyzer()

    chunks = [
        {"hierarchy": {"level_1": "Introduction", "level_2": "Background and Rationale"}},
        {"hierarchy": {"level_1": "Methods", "level_2": "Study Design"}},
        {"hierarchy": {"level_1": "Results", "level_2": "Patient Characteristics"}},
    ]

    themes = analyzer.extract_themes(chunks)
    assert "Background and Rationale" in themes
    assert "Study Design" in themes


def test_related_documents():
    analyzer = MedicalAnalyzer()

    text = """
    According to WHO Guidelines, treatment should...
    See also Cochrane Review on this topic.
    """

    related = analyzer.extract_related_documents(text)
    assert "WHO Guidelines" in related
    assert "Cochrane Review" in related


def test_enrich_metadata():
    analyzer = MedicalAnalyzer()

    base_metadata = {"title": "Test Study", "author": "Dr. Smith"}
    full_text = "This clinical trial evaluated cardiac outcomes..."
    chunks = [
        {"hierarchy": {"level_1": "Methods"}, "word_count": 100},
        {"hierarchy": {"level_1": "Results"}, "word_count": 150},
    ]

    enriched = analyzer.enrich_metadata(base_metadata, full_text, chunks)

    assert enriched["document_type"] == "Clinical Trial"
    assert "Cardiology" in enriched["subject"]
    assert "word_count" in enriched
```

Run tests:

```bash
uv run pytest tests/test_medical_analyzer.py -v
```

## Registering Your Analyzer

### 1. Add to `__init__.py`

Edit `src/extraction/analyzers/__init__.py`:

```python
from .base import BaseAnalyzer
from .catholic import CatholicAnalyzer
from .generic import GenericAnalyzer
from .medical import MedicalAnalyzer  # Add this

__all__ = [
    "BaseAnalyzer",
    "CatholicAnalyzer",
    "GenericAnalyzer",
    "MedicalAnalyzer",  # Add this
]
```

### 2. Register in CLI

Edit `src/extraction/cli/extract.py`:

```python
# Find the analyzer argument definition
parser.add_argument(
    "--analyzer",
    choices=["catholic", "generic", "medical"],  # Add "medical"
    default="generic",
    help="Domain-specific analyzer to use"
)

# Find the analyzer instantiation
if args.analyzer == "catholic":
    analyzer = CatholicAnalyzer()
elif args.analyzer == "medical":  # Add this
    analyzer = MedicalAnalyzer()
else:
    analyzer = GenericAnalyzer()
```

## Using Your Analyzer

### CLI

```bash
# Use medical analyzer
extract research_paper.pdf --analyzer medical

# Batch processing with medical analyzer
extract medical_corpus/ -r --output-dir outputs/ --analyzer medical
```

### Python API

```python
from extraction.extractors import PdfExtractor
from extraction.analyzers import MedicalAnalyzer

# Extract document
extractor = PdfExtractor("research_paper.pdf")
extractor.load()
extractor.parse()
metadata = extractor.extract_metadata()

# Enrich with medical analyzer
analyzer = MedicalAnalyzer()
enriched_metadata = analyzer.enrich_metadata(
    metadata.to_dict(),
    extractor.full_text,
    [chunk.to_dict() for chunk in extractor.chunks]
)

# Output
output_data = extractor.get_output_data()
output_data['metadata'].update(enriched_metadata)
```

## Advanced: Configurable Patterns

Allow users to customize patterns:

```python
class MedicalAnalyzer(BaseAnalyzer):
    DEFAULT_DOC_TYPES = {
        "Clinical Trial": [r"randomized controlled trial"],
        # ... more defaults
    }

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)

        # Load patterns from config or use defaults
        self.doc_type_patterns = self.config.get(
            "document_types",
            self.DEFAULT_DOC_TYPES
        )
        self.subject_patterns = self.config.get(
            "subjects",
            self.DEFAULT_SUBJECTS
        )
```

Usage with custom patterns:

```python
custom_config = {
    "document_types": {
        "Meta-Analysis": [r"meta-analysis", r"systematic review"],
        "Guideline": [r"clinical guideline", r"best practice"],
    }
}

analyzer = MedicalAnalyzer(config=custom_config)
```

## Real-World Example: Academic Analyzer

Here's a complete academic paper analyzer:

```python
#!/usr/bin/env python3

"""Academic paper analyzer."""

import re
from typing import Dict, List, Any
from collections import OrderedDict

from .base import BaseAnalyzer
from ..core.extraction import extract_dates


class AcademicAnalyzer(BaseAnalyzer):
    """Analyzer for academic research papers."""

    DOC_TYPE_PATTERNS = {
        "Research Paper": [r"abstract.*introduction.*methodology"],
        "Review Article": [r"systematic review", r"literature review"],
        "Conference Paper": [r"conference", r"proceedings"],
        "Thesis": [r"\bthesis\b", r"\bdissertation\b"],
        "Technical Report": [r"technical report", r"working paper"],
    }

    SUBJECT_PATTERNS = {
        "Computer Science": [r"algorithm", r"software", r"computing"],
        "Machine Learning": [r"neural network", r"deep learning", r"\bml\b"],
        "Natural Language Processing": [r"\bnlp\b", r"language model"],
        "Data Science": [r"data analysis", r"dataset", r"analytics"],
    }

    RELATED_DOCUMENTS = ["arXiv", "IEEE", "ACM", "NIPS", "ICML", "NeurIPS"]

    def infer_document_type(self, text: str) -> str:
        text_lower = text.lower()
        for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            if any(re.search(p, text_lower) for p in patterns):
                return doc_type
        return "Article"

    def extract_subjects(self, text: str, chunks: List[Dict]) -> List[str]:
        text_lower = text.lower()
        return [
            subject
            for subject, patterns in self.SUBJECT_PATTERNS.items()
            if any(re.search(p, text_lower) for p in patterns)
        ]

    def extract_themes(self, chunks: List[Dict]) -> List[str]:
        themes = []
        for chunk in chunks:
            hierarchy = chunk.get("hierarchy", {})
            for level in ["level_1", "level_2", "level_3"]:
                heading = hierarchy.get(level, "")
                if heading and len(heading) > 10:
                    themes.append(heading)
        return list(OrderedDict.fromkeys(themes))[:10]

    def extract_related_documents(self, text: str) -> List[str]:
        return [
            doc for doc in self.RELATED_DOCUMENTS
            if re.search(re.escape(doc), text, re.IGNORECASE)
        ]

    def infer_geographic_focus(self, text: str) -> str:
        return ""  # Not applicable for academic papers

    def enrich_metadata(
        self,
        base_metadata: Dict[str, Any],
        full_text: str,
        chunks: List[Dict]
    ) -> Dict[str, Any]:
        base_metadata["document_type"] = self.infer_document_type(full_text)
        base_metadata["subject"] = self.extract_subjects(full_text, chunks)
        base_metadata["key_themes"] = self.extract_themes(chunks)
        base_metadata["related_documents"] = self.extract_related_documents(full_text)
        base_metadata["geographic_focus"] = self.infer_geographic_focus(full_text)

        dates = extract_dates(full_text)
        base_metadata["publication_date"] = dates[0] if dates else ""

        stats = self.calculate_stats(chunks)
        base_metadata.update(stats)

        return base_metadata
```

## Next Steps

- See the source code (`src/extraction/analyzers/base.py`) for complete interface
- See [CatholicAnalyzer source](https://github.com/hello-world-bfree/extraction/blob/master/src/extraction/analyzers/catholic.py) for production example
- For debugging analyzer issues, see [Debugging Guide](debugging.md)
