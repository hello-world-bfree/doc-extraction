"""
Noise filtering for extraction pipeline.

Detects and filters chunks with low semantic value for embeddings:
- Index pages
- Reference lists
- Number-heavy content
- Navigation/TOC fragments
- Copyright/legal boilerplate
"""
import re
from typing import Dict, Any


class NoiseFilter:
    """
    Multi-tier noise detection for chunks.

    Designed to catch content that has zero semantic value for embeddings
    while preserving all legitimate content chunks.
    """

    @staticmethod
    def is_index_page(chunk: Dict[str, Any]) -> bool:
        """
        Detect index/reference list pages.

        Characteristics:
        - High number density (>50% of tokens are numbers/punctuation)
        - Repetitive patterns (number sequences, reference formats)
        - High token/word ratio (lots of symbols)

        Examples:
        - "1, Part 1 109 24 8* 27 133* 356 109*, 133* 357 108..."
        - "Genesis 1:1-31 ... 2:1-25 ... 3:1-24 ..."
        """
        text = chunk.get('text', '').strip()
        if not text:
            return False

        tokens = text.split()
        if not tokens:
            return False

        # Check 1: High number density
        number_tokens = sum(1 for t in tokens if re.match(r'^[\d\*,\.\-:;]+$', t))
        number_ratio = number_tokens / len(tokens)

        if number_ratio > 0.5:
            return True

        # Check 2: Repetitive reference patterns
        # Matches: "123 45* 678" or "1:1-31 2:1-25" patterns
        reference_pattern = r'(?:\d+[\*,\.\-:;\s]+){5,}'
        if re.search(reference_pattern, text):
            # Verify it's mostly numbers
            nums_in_text = len(re.findall(r'\d+', text))
            if nums_in_text > len(tokens) * 0.3:  # 30%+ of tokens contain numbers
                return True

        # Check 3: High token/word ratio (indicates special chars/symbols)
        word_count = len(tokens)
        token_count = chunk.get('token_count', 0)
        if word_count > 0 and token_count > 0:
            ratio = token_count / word_count
            # Normal text: ~1.3 tokens/word
            # Index pages: ~3+ tokens/word due to symbols
            if ratio > 2.5 and number_ratio > 0.3:
                return True

        return False

    @staticmethod
    def is_navigation_fragment(chunk: Dict[str, Any]) -> bool:
        """
        Detect navigation/TOC fragments.

        Examples:
        - "Chapter 1 ... 5"
        - "Next | Previous | Home"
        - "Table of Contents"
        """
        text = chunk.get('text', '').strip().lower()
        hierarchy = chunk.get('hierarchy', {})
        level_1 = hierarchy.get('level_1', '').lower()

        # TOC/Index in hierarchy
        if any(kw in level_1 for kw in ['table of contents', 'index', 'contents']):
            word_count = chunk.get('word_count', 0)
            if word_count < 20:  # Short chunks in TOC/index sections
                return True

        # Navigation keywords
        nav_patterns = [
            r'^\s*(next|previous|home|back|forward|up)\s*$',
            r'^\s*(chapter|section|part)\s+\d+\s*$',
            r'^\s*page\s+\d+\s*$',
        ]
        for pattern in nav_patterns:
            if re.match(pattern, text):
                return True

        return False

    @staticmethod
    def is_copyright_boilerplate(chunk: Dict[str, Any]) -> bool:
        """
        Detect copyright/legal boilerplate.

        Examples:
        - Copyright notices
        - ISBN numbers
        - Publisher info (when standalone)
        """
        text = chunk.get('text', '').strip().lower()

        # Copyright patterns
        if re.search(r'©|\bcopyright\b|\ball rights reserved\b', text):
            word_count = chunk.get('word_count', 0)
            if word_count < 50:  # Short copyright notices
                return True

        # ISBN/Publisher codes
        if re.search(r'\bisbn\b|publisher code|catalog number', text):
            return True

        return False

    @staticmethod
    def is_front_matter(chunk: Dict[str, Any]) -> tuple[bool, str]:
        """
        Conservative front/back matter detection.

        Detects common front matter sections:
        - Dedications ("Dedicated to...", "For my...", "In memory of...")
        - Endorsements/testimonials ("Praise for...", "What readers are saying...")
        - TOC-labeled front matter (via hierarchy)

        Detects common back matter sections:
        - Suggested Resources / Further Reading
        - Glossary
        - Indexes (Index of Sidebars, General Index, etc.)
        - Notes / Endnotes
        - Bibliography
        - Back Cover

        Returns:
            (is_front_or_back_matter, detection_reason)
        """
        text_lower = chunk.get('text', '').lower()
        hierarchy = chunk.get('hierarchy', {})

        # Collect all hierarchy levels (check level_1 through level_6)
        hierarchy_labels = [
            hierarchy.get(f'level_{i}', '').lower()
            for i in range(1, 7)
        ]

        # Pattern 1: Explicit dedication phrases
        dedication_patterns = [
            r'^\s*dedicated to\b',
            r'^\s*for\s+(my|our|the)\s+\w+',
            r'^\s*for\s+\w+\s*,\s*(my|our|the)',
            r'^\s*in memory of\b',
            r'^\s*to\s+(my|our|the)\s+\w+',
        ]
        for pattern in dedication_patterns:
            if re.search(pattern, text_lower):
                return (True, 'dedication_phrase')

        # Pattern 2: Endorsement/testimonial sections
        endorsement_keywords = [
            'praise for',
            'advance praise',
            'what readers are saying',
            'what people are saying',
            'acclaim for',
            'testimonials',
        ]
        if any(keyword in text_lower for keyword in endorsement_keywords):
            return (True, 'endorsement_section')

        # Pattern 3: Front matter TOC labels (hierarchy-based)
        # Uses substring matching: "Biblical Abbreviations" matches "abbreviations"
        front_matter_toc_labels = {
            'dedication',
            'praise',
            'endorsements',
            'testimonials',
            'also by',
            'title page',
            'series page',
            'illustrations',
            'list of illustrations',
            'list of figures',
            'figures',
            'abbreviations',
            'list of abbreviations',
            "editor's preface",
            "editors' preface",
            'preface',
            'acknowledgments',
            'acknowledgements',
        }
        for label in hierarchy_labels:
            if label in front_matter_toc_labels:
                return (True, 'front_matter_toc_label')
            # Also check if any pattern is a substring of the label
            for pattern in front_matter_toc_labels:
                if pattern in label:
                    return (True, 'front_matter_toc_label')
            # "About [Publisher Name]" pattern (but not "about the author")
            # Matches: "about wyatt north publishing", "about penguin press", etc.
            if re.match(r'^about\s+(?!the\s+author)', label):
                if re.search(r'publishing|press|books|editions|media|house', label):
                    return (True, 'front_matter_toc_label')

        # Pattern 4: Back matter TOC labels (hierarchy-based)
        # Uses substring matching for flexibility
        back_matter_toc_labels = {
            'suggested resources',
            'further reading',
            'recommended reading',
            'bibliography',
            'glossary',
            'general index',
            'subject index',
            'scripture index',
            'index of sidebars',
            'index of subjects',
            'endnotes',
            'footnotes',
            'back cover',
            'about the author',
            'about the authors',
        }
        for label in hierarchy_labels:
            if label in back_matter_toc_labels:
                return (True, 'back_matter_toc_label')
            for pattern in back_matter_toc_labels:
                if pattern in label:
                    return (True, 'back_matter_toc_label')

        # Pattern 5: Standalone "index", "notes", "geography", "map" (require exact or bounded match)
        # These are common words so we need to be more careful with matching
        for label in hierarchy_labels:
            # Exact matches
            if label in {'index', 'notes', 'geography'}:
                return (True, 'back_matter_toc_label')
            # Word boundary matches (e.g., "Book Index" but not "Indexing Strategies")
            if re.search(r'\bindex\b', label) and not re.search(r'index(?:ing|ed|es)', label):
                return (True, 'back_matter_toc_label')
            if re.search(r'\bnotes\b', label) and not re.search(r'note(?:s|d|worthy)', label):
                return (True, 'back_matter_toc_label')
            if re.search(r'\bgeography\b|\bmap(?:s)?\b', label):
                return (True, 'back_matter_toc_label')

        # Pattern 6: Book outlines (hierarchy-based)
        if any('outline' in label for label in hierarchy_labels):
            return (True, 'front_matter_toc_label')

        return (False, 'content')

    @staticmethod
    def detect_reference_block(text: str) -> tuple[bool, int, int]:
        """
        Detect if text contains an end-of-chapter reference/citation block.

        Looks for patterns like:
        - "1. Author Name, Book Title (City: Publisher, 2005), 123."
        - "2. Ibid., 45-46."
        - "3. Author, \"Article Title,\" in Book, ed. Editor (Publisher, 2010), 100."

        Returns:
            (has_references, ref_start_pos, ref_count)
            - has_references: True if reference block detected
            - ref_start_pos: Character position where references start (-1 if none)
            - ref_count: Number of references detected
        """
        if not text:
            return (False, -1, 0)

        # Pattern for numbered citations (must have number + period + author-like text)
        # Matches: "1. Name" or "12. Name" or "4. R. R. Reno" at start of line or after newline
        citation_pattern = re.compile(
            r'(?:^|\n)\s*(\d{1,3})\.\s+([A-Z](?:[a-z]+|\.)\s*[A-Z]?)',
            re.MULTILINE
        )

        matches = list(citation_pattern.finditer(text))
        if len(matches) < 2:
            return (False, -1, 0)

        # Check if citations are sequential (1, 2, 3...) starting from 1
        numbers = [int(m.group(1)) for m in matches]
        if numbers[0] != 1:
            return (False, -1, 0)

        # Check for sequential or near-sequential numbering
        sequential_count = 1
        for i in range(1, len(numbers)):
            if numbers[i] == numbers[i-1] + 1:
                sequential_count += 1
            elif numbers[i] > numbers[i-1]:
                sequential_count += 1
            else:
                break

        # Need at least 3 sequential citations to be confident
        if sequential_count < 3:
            return (False, -1, 0)

        # Additional validation: check for citation-like content
        # (years in parentheses, "Ibid.", publisher patterns)
        ref_section = text[matches[0].start():]
        citation_indicators = [
            r'\(\d{4}\)',           # (2005)
            r'\bIbid\b',            # Ibid.
            r'\bed\.\s',            # ed. or eds.
            r'\btrans\.\s',         # trans.
            r'\bvol\.\s',           # vol.
            r':\s*\d+[-–]\d+',      # : 123-456 (page ranges)
            r',\s*\d+[-–]\d+\.',    # , 123-456. (page ranges at end)
        ]

        indicator_matches = sum(
            1 for pattern in citation_indicators
            if re.search(pattern, ref_section, re.IGNORECASE)
        )

        # Need at least 2 citation indicators to confirm
        if indicator_matches < 2:
            return (False, -1, 0)

        return (True, matches[0].start(), sequential_count)

    @staticmethod
    def has_low_semantic_value(chunk: Dict[str, Any]) -> bool:
        """
        Detect chunks with low semantic value for embeddings.

        Combines all noise detection heuristics.
        """
        if NoiseFilter.is_index_page(chunk):
            return True

        if NoiseFilter.is_navigation_fragment(chunk):
            return True

        if NoiseFilter.is_copyright_boilerplate(chunk):
            return True

        return False

    @staticmethod
    def filter_chunks(chunks: list[Dict[str, Any]], verbose: bool = False) -> tuple[list[Dict[str, Any]], int]:
        """
        Filter noise chunks from a list.

        Args:
            chunks: List of chunk dictionaries
            verbose: Print filtered chunk IDs

        Returns:
            (filtered_chunks, num_filtered)
        """
        filtered = []
        num_filtered = 0

        for chunk in chunks:
            if NoiseFilter.has_low_semantic_value(chunk):
                if verbose:
                    chunk_id = chunk.get('chunk_id', chunk.get('stable_id', 'unknown'))
                    reason = 'index' if NoiseFilter.is_index_page(chunk) else 'nav/boilerplate'
                    print(f"  Filtered ({reason}): {chunk_id}")
                num_filtered += 1
            else:
                filtered.append(chunk)

        return filtered, num_filtered


def scan_corpus_for_noise(corpus_file: str, sample_size: int = 0) -> Dict[str, Any]:
    """
    Scan JSONL corpus file for noise chunks.

    Args:
        corpus_file: Path to JSONL file
        sample_size: If >0, only scan first N chunks

    Returns:
        Statistics dict with noise detection results
    """
    import json

    total = 0
    noise_count = 0
    noise_chunks = []

    with open(corpus_file) as f:
        for i, line in enumerate(f):
            if sample_size > 0 and i >= sample_size:
                break

            chunk = json.loads(line)
            total += 1

            if NoiseFilter.has_low_semantic_value(chunk):
                noise_count += 1
                chunk_id = chunk.get('chunk_id', chunk.get('stable_id', 'unknown'))
                reason = []
                if NoiseFilter.is_index_page(chunk):
                    reason.append('index')
                if NoiseFilter.is_navigation_fragment(chunk):
                    reason.append('navigation')
                if NoiseFilter.is_copyright_boilerplate(chunk):
                    reason.append('copyright')

                noise_chunks.append({
                    'chunk_id': chunk_id,
                    'reason': '+'.join(reason),
                    'text_preview': chunk.get('text', '')[:100],
                    'word_count': chunk.get('word_count', 0),
                    'token_count': chunk.get('token_count', 0),
                })

    return {
        'total_scanned': total,
        'noise_detected': noise_count,
        'noise_rate': noise_count / total if total > 0 else 0,
        'noise_chunks': noise_chunks,
    }
