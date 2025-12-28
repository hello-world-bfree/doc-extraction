# Test Fixtures

This directory contains test fixtures for the extraction test suite.

## Structure

- `sample_data/` - Sample documents for testing (EPUB, PDF, HTML, etc.)
- `expected_outputs/` - Expected output files for regression testing
- `mock_data/` - Mock data for unit tests

## Adding Fixtures

When adding test fixtures:

1. Keep files small (< 1MB preferred)
2. Use public domain or openly licensed content
3. Document the source and license in this README
4. Create corresponding expected outputs for regression tests

## Current Fixtures

### Sample Documents

- **Prayer Primer.epub** (if available in project root) - Used for integration tests
  - Source: Project test data
  - License: Internal use

## Note on Large Files

Large test files (> 1MB) should not be committed to the repository.
Instead, tests should gracefully skip when fixtures are not available.
