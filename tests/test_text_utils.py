#!/usr/bin/env python3
"""Tests for text utility functions, especially clean_toc_title."""
import sys
sys.path.insert(0, 'src')

from extraction.core.text import clean_toc_title, clean_text


def test_clean_toc_title_preserves_words_starting_with_roman_chars():
    """Ensure words starting with I, V, X, L, C are not truncated."""
    # These were failing before the fix
    assert clean_toc_title("Cover Page") == "Cover Page"
    assert clean_toc_title("Copyright Page") == "Copyright Page"
    assert clean_toc_title("Contents") == "Contents"
    assert clean_toc_title("Index") == "Index"
    assert clean_toc_title("List of Tables") == "List of Tables"

    # Additional edge cases
    assert clean_toc_title("Introduction") == "Introduction"
    assert clean_toc_title("Vocabulary") == "Vocabulary"
    assert clean_toc_title("Conclusions") == "Conclusions"
    assert clean_toc_title("Liturgy") == "Liturgy"


def test_clean_toc_title_removes_chapter_prefixes():
    """Ensure 'Chapter N' prefixes are removed."""
    assert clean_toc_title("Chapter 1: Introduction") == "Introduction"
    assert clean_toc_title("Chapter 5 - The Problem") == "The Problem"
    assert clean_toc_title("Chap. 3: Solutions") == "Solutions"


def test_clean_toc_title_removes_numeric_prefixes():
    """Ensure numeric prefixes like '1.', '1)' are removed."""
    assert clean_toc_title("1. Recurrent Problems") == "Recurrent Problems"
    assert clean_toc_title("2. Sums") == "Sums"
    assert clean_toc_title("10) Final Chapter") == "Final Chapter"
    assert clean_toc_title("5 Introduction") == "Introduction"


def test_clean_toc_title_removes_roman_numeral_prefixes():
    """Ensure Roman numeral prefixes (2+ chars) like 'IV.', 'XII)' are removed."""
    assert clean_toc_title("IV. Fourth Chapter") == "Fourth Chapter"
    assert clean_toc_title("XII. Twelfth Section") == "Twelfth Section"
    assert clean_toc_title("II) Second Part") == "Second Part"

    # Single Roman chars without punctuation should be preserved
    assert clean_toc_title("I am a title") == "I am a title"
    assert clean_toc_title("V for Vendetta") == "V for Vendetta"


def test_clean_toc_title_edge_cases():
    """Test edge cases and complex scenarios."""
    # Empty/None
    assert clean_toc_title("") == ""
    assert clean_toc_title(None) is None

    # Already clean
    assert clean_toc_title("Preface") == "Preface"
    assert clean_toc_title("About This eBook") == "About This eBook"

    # Multiple spaces/formatting
    assert clean_toc_title("  1.   Introduction  ") == "Introduction"


def test_clean_toc_title_real_world_examples():
    """Test with actual TOC entries from Concrete Mathematics EPUB."""
    # From the .ncx file we examined
    assert clean_toc_title("1. Recurrent Problems") == "Recurrent Problems"
    assert clean_toc_title("2. Sums") == "Sums"
    assert clean_toc_title("3. Integer Functions") == "Integer Functions"
    assert clean_toc_title("A. Answers to Exercises") == "A. Answers to Exercises"  # Keep letter prefixes in appendices
    assert clean_toc_title("B. Bibliography") == "B. Bibliography"

    # Subsections
    assert clean_toc_title("1.1 The Tower of Hanoi") == "The Tower of Hanoi"
    assert clean_toc_title("2.3 Manipulation of Sums") == "Manipulation of Sums"


def test_clean_text_verse_numbers():
    """Test that verse numbers get a space inserted after them."""
    # Verse numbers without space (from Gospel of Mark)
    assert clean_text("29On leaving the synagogue") == "29 On leaving the synagogue"
    assert clean_text("30Simon's mother-in-law") == "30 Simon's mother-in-law"
    assert clean_text("31He approached, grasped her hand") == "31 He approached, grasped her hand"
    assert clean_text("32When it was evening") == "32 When it was evening"
    assert clean_text("33The whole town") == "33 The whole town"
    assert clean_text("34He cured many") == "34 He cured many"

    # Already has proper spacing
    assert clean_text("29 On leaving") == "29 On leaving"
    assert clean_text("1:29 After the synagogue") == "1:29 After the synagogue"

    # Should not affect normal text
    assert clean_text("Normal text without verse numbers") == "Normal text without verse numbers"
    assert clean_text("The 29th of March") == "The 29th of March"


if __name__ == "__main__":
    # Run all tests
    import traceback

    tests = [
        test_clean_toc_title_preserves_words_starting_with_roman_chars,
        test_clean_toc_title_removes_chapter_prefixes,
        test_clean_toc_title_removes_numeric_prefixes,
        test_clean_toc_title_removes_roman_numeral_prefixes,
        test_clean_toc_title_edge_cases,
        test_clean_toc_title_real_world_examples,
        test_clean_text_verse_numbers,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            print(f"✓ {test_func.__name__}")
            passed += 1
        except AssertionError:
            print(f"✗ {test_func.__name__}")
            traceback.print_exc()
            failed += 1
        except Exception:
            print(f"✗ {test_func.__name__} (error)")
            traceback.print_exc()
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
