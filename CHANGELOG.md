# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.1] - 2026-01-12

### Added
- First public release on PyPI
- Multi-format document extraction (EPUB, PDF, HTML, Markdown, JSON)
- Hierarchical chunking with 6-level heading support
- Quality scoring and routing (A/B/C routes)
- Noise filtering for index pages, copyright, navigation
- Chunking strategies: RAG (embeddings) and NLP (paragraph-level)
- Formatting preservation (poetry, blockquotes, lists, tables)
- Catholic domain analyzer for religious texts
- Vatican archive pipeline for vatican.va documents
- Token-based re-chunking tool for embedding optimization
- CLI tools: extract, vatican-extract, token-rechunk
- Comprehensive documentation and examples
- Config dataclasses for type-safe configuration validation
- Custom exception hierarchy for better error handling
- State machine for enforcing method call order
- GenericAnalyzer for non-domain-specific documents
- Comprehensive test suite (228 tests, 41% coverage)
- MkDocs documentation with Diataxis framework
- py.typed marker for type hint support

### Changed
- Reorganized repository structure (scripts moved to examples/)
- Updated package metadata for PyPI distribution
- Improved API consistency across all extractors

### Features
- **Extractors**: BaseExtractor, EpubExtractor, PdfExtractor, HtmlExtractor, MarkdownExtractor, JsonExtractor
- **Analyzers**: BaseAnalyzer, CatholicAnalyzer, GenericAnalyzer
- **Core Utilities**: Chunking, quality scoring, reference extraction, noise filtering
- **Pipelines**: Vatican archive integration with S3/R2 upload support

[Unreleased]: https://github.com/freeman-murray/extraction/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/freeman-murray/extraction/releases/tag/v0.0.1
