---
title: Sample Markdown Document
author: Test Author
date: 2025-01-15
tags: [test, sample, markdown]
---

# Introduction to Markdown Testing

This is a sample document for testing the Markdown extractor. It contains various elements that should be properly extracted.

## Basic Formatting

This paragraph demonstrates basic text extraction. It should be captured as a single chunk with proper hierarchy tracking.

### Subsection Example

Here we have a level 3 heading with some content beneath it. The hierarchy should show:
- Level 1: Introduction to Markdown Testing
- Level 2: Basic Formatting
- Level 3: Subsection Example

## Lists and Structure

Markdown supports various list types:

- First bullet point
- Second bullet point with some additional text
- Third bullet point

### Code Blocks

Code blocks should be handled appropriately:

```python
def example_function():
    return "This is test code"
```

## References and Cross-References

This section contains some sample references. See Chapter 3 for more details. Compare with Section 2.1 above.

### Biblical References

This text mentions John 3:16 and Matthew 5:1-12 as sample scripture references that should be detected.

## Conclusion

This final section wraps up the test document. It should be extracted with proper metadata including the title and author from the frontmatter.
