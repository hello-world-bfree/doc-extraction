# How-To Guides

Goal-oriented guides for solving specific problems with the extraction library.

## Available Guides

### [Choosing a Chunking Strategy](chunking-strategy.md)
Learn when to use RAG vs NLP chunking strategies, customize chunk sizes, and troubleshoot chunking issues.

**Topics covered**:

- Decision tree for choosing strategies
- RAG mode (100-500 words) for embeddings
- NLP mode (paragraph-level) for fine-grained analysis
- Custom chunk sizes for different embedding models
- Performance comparison and troubleshooting

### [Creating Custom Analyzers](custom-analyzers.md)
Step-by-step guide to building domain-specific metadata analyzers for your documents.

**Topics covered**:

- Implementing the BaseAnalyzer interface
- Pattern matching for document types and subjects
- Extracting themes from hierarchy
- Testing and registering your analyzer
- Real-world examples (Medical, Academic)

### [Debugging Extraction Issues](debugging.md)
Diagnose and fix common extraction problems with detailed troubleshooting steps.

**Topics covered**:

- Empty or missing output
- Missing hierarchy in chunks
- Quality score too low
- PDF heading detection issues
- Debug mode and logging
- Performance troubleshooting

### [Token-Based Re-chunking](token-rechunking.md)
Transform word-based chunks into token-optimized chunks for embedding models and RAG systems.

**Topics covered**:

- When to use token re-chunking
- Three modes: retrieval, recommendation, balanced
- Complete workflow: extract → re-chunk → embed
- Statistics and metadata preservation
- Integration with vector databases

## Quick Links

- **For beginners**: Start with [Quickstart Tutorial](../getting-started/quickstart.md)
- **For multi-format extraction**: See [Multi-Format Tutorial](../getting-started/multi-format.md)
- **For vector databases**: See [Vector DB Tutorial](../getting-started/vector-db.md)
- **For API reference**: See [Reference Documentation](../reference/index.md)
