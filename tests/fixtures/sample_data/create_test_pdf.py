#!/usr/bin/env python3
"""
Script to create a sample PDF for testing the PDF extractor.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
import os

# Output path
output_path = os.path.join(os.path.dirname(__file__), "test_document.pdf")

# Create document
doc = SimpleDocTemplate(
    output_path,
    pagesize=letter,
    rightMargin=72,
    leftMargin=72,
    topMargin=72,
    bottomMargin=18,
    title="Sample PDF Document",
    author="Test Author"
)

# Container for the 'Flowable' objects
story = []

# Get styles
styles = getSampleStyleSheet()

# Create custom styles
title_style = ParagraphStyle(
    'CustomTitle',
    parent=styles['Heading1'],
    fontSize=24,
    textColor='black',
    spaceAfter=30,
)

heading1_style = ParagraphStyle(
    'CustomHeading1',
    parent=styles['Heading1'],
    fontSize=18,
    spaceAfter=12,
    spaceBefore=12,
)

heading2_style = ParagraphStyle(
    'CustomHeading2',
    parent=styles['Heading2'],
    fontSize=14,
    spaceAfter=10,
    spaceBefore=10,
)

heading3_style = ParagraphStyle(
    'CustomHeading3',
    parent=styles['Heading3'],
    fontSize=12,
    spaceAfter=8,
    spaceBefore=8,
)

body_style = ParagraphStyle(
    'CustomBody',
    parent=styles['BodyText'],
    fontSize=11,
    alignment=TA_JUSTIFY,
    spaceAfter=12,
)

# Add content
story.append(Paragraph("Sample PDF Document", title_style))
story.append(Paragraph("Test Author", styles['Normal']))
story.append(Spacer(1, 0.2*inch))

# Introduction
story.append(Paragraph("Introduction to PDF Testing", heading1_style))
story.append(Paragraph(
    "This is a sample document for testing the PDF extractor. It contains various "
    "elements that should be properly extracted including headings at multiple levels, "
    "paragraphs with varying lengths, and embedded references.",
    body_style
))

# Basic Structure
story.append(Paragraph("Basic Structure", heading2_style))
story.append(Paragraph(
    "This paragraph demonstrates basic text extraction from PDF. It should be captured "
    "as a single chunk with proper hierarchy tracking showing the main heading and "
    "subheadings. The extractor should handle multi-line paragraphs correctly.",
    body_style
))

# Subsection
story.append(Paragraph("Subsection Example", heading3_style))
story.append(Paragraph(
    "Here we have a level 3 heading with some content beneath it. The hierarchy should "
    "show all three levels properly nested. The PDF extractor uses heuristics to detect "
    "headings based on font size and text characteristics.",
    body_style
))

# Text Features
story.append(Paragraph("Text Features and Formatting", heading2_style))
story.append(Paragraph(
    "This section contains a longer paragraph to test the word count and chunking "
    "functionality. It should be extracted as a complete chunk with accurate word counts "
    "and character counts. The text should maintain proper spacing and formatting even "
    "when extracted from the PDF structure.",
    body_style
))

# Lists simulation (as paragraphs since reportlab SimpleDocTemplate doesn't handle lists easily)
story.append(Paragraph("Key Points", heading3_style))
story.append(Paragraph(
    "• First bullet point demonstrating list-like content in PDF format",
    body_style
))
story.append(Paragraph(
    "• Second bullet point with additional text for testing",
    body_style
))
story.append(Paragraph(
    "• Third bullet point showing consistent formatting",
    body_style
))

# References
story.append(Paragraph("References and Citations", heading2_style))
story.append(Paragraph(
    "This section contains sample references. See Chapter 7 for more details. "
    "Compare with Section 3.2 mentioned above. Cross-references like these should "
    "be detected by the extraction system.",
    body_style
))

# Biblical references
story.append(Paragraph("Biblical Citations", heading3_style))
story.append(Paragraph(
    "This text mentions Ephesians 2:8-9 and Philippians 4:13 as sample scripture "
    "references that should be detected by the Catholic analyzer and extraction system. "
    "These references demonstrate the domain-specific analysis capabilities.",
    body_style
))

# Conclusion
story.append(Paragraph("Conclusion", heading2_style))
story.append(Paragraph(
    "This final section wraps up the test document. It should be extracted with proper "
    "metadata including the title and author information embedded in the PDF properties. "
    "The page structure and hierarchy should be preserved throughout the extraction process.",
    body_style
))

# Build PDF
doc.build(story)

print(f"✅ Created test PDF: {output_path}")
