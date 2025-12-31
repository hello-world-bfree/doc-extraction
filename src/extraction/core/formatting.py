#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Structural formatting preservation utilities.

Provides functions to build formatted text and structure metadata from
BeautifulSoup elements while preserving semantic structure like poetry,
blockquotes, lists, tables, and emphasis.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, NavigableString, Tag


class FormattedTextBuilder:
    """Builds formatted text representation preserving structure.

    Extracts text from HTML/EPUB while preserving structural intent:
    - Poetry/verse: Line breaks, stanza breaks, indentation
    - Blockquotes: > prefix, attribution, quotation boundaries
    - Lists: Numbered/bulleted with nesting (2 spaces per level)
    - Tables: Markdown table format (experimental)
    - Emphasis: *italic*, **bold**, ~~strikethrough~~
    - Code blocks: Triple backticks with language hint

    Uses markdown-like conventions for formatted_text, and structured
    JSON for structure_metadata.
    """

    def __init__(
        self,
        preserve_line_breaks: bool = True,
        preserve_emphasis: bool = True,
        preserve_lists: bool = True,
        preserve_blockquotes: bool = True,
        preserve_tables: bool = False,
    ):
        """Initialize with granular control over preserved features.

        Args:
            preserve_line_breaks: Preserve line breaks in poetry/verse
            preserve_emphasis: Preserve em/strong/mark elements
            preserve_lists: Preserve list structure and nesting
            preserve_blockquotes: Preserve blockquote boundaries
            preserve_tables: Preserve table structure (experimental)
        """
        self.preserve_line_breaks = preserve_line_breaks
        self.preserve_emphasis = preserve_emphasis
        self.preserve_lists = preserve_lists
        self.preserve_blockquotes = preserve_blockquotes
        self.preserve_tables = preserve_tables

    def extract_formatted_text(self, element: Tag) -> str:
        """Extract text with formatting preserved.

        Recursively walks the BeautifulSoup tree and builds formatted
        text using markdown-like conventions.

        Args:
            element: BeautifulSoup Tag to extract from

        Returns:
            Formatted text string with structural markers
        """
        if not element:
            return ""

        return self._walk_tree(element, depth=0)

    def extract_structure_metadata(self, element: Tag) -> Dict[str, Any]:
        """Extract structural metadata as JSON.

        Builds a structured representation of the element tree with
        attributes, formatting hints, and child relationships.

        Args:
            element: BeautifulSoup Tag to extract from

        Returns:
            Dictionary with element_type, attributes, formatting, children
        """
        if not element or not isinstance(element, Tag):
            return {}

        metadata: Dict[str, Any] = {
            "element_type": element.name,
            "attributes": dict(element.attrs) if element.attrs else {},
            "formatting": {},
            "children": []
        }

        # Detect formatting hints
        if self._is_poetry_container(element):
            metadata["formatting"]["poetry"] = True
            metadata["formatting"]["line_breaks"] = self._find_line_break_positions(element)

        if self._is_blockquote(element):
            metadata["formatting"]["blockquote"] = True
            attribution = self._extract_attribution(element)
            if attribution:
                metadata["formatting"]["attribution"] = attribution

        if self._is_list(element):
            metadata["formatting"]["list_type"] = element.name  # ol or ul
            metadata["formatting"]["ordered"] = element.name == "ol"

        # Recursively process children (max 3 levels deep to prevent excessive nesting)
        for child in element.children:
            if isinstance(child, Tag) and len(metadata["children"]) < 10:
                child_meta = self.extract_structure_metadata(child)
                if child_meta:
                    metadata["children"].append(child_meta)

        return metadata

    def _walk_tree(self, element: Tag, depth: int = 0) -> str:
        """Recursively walk element tree and build formatted text.

        Args:
            element: Current element to process
            depth: Current nesting depth (for indentation)

        Returns:
            Formatted text for this element and its children
        """
        if isinstance(element, NavigableString):
            # Text node - return cleaned text
            text = str(element).strip()
            return text if text else ""

        if not isinstance(element, Tag):
            return ""

        tag_name = element.name.lower()

        # Handle special elements
        if tag_name == "blockquote" and self.preserve_blockquotes:
            return self._process_blockquote(element)

        if tag_name in ("ol", "ul") and self.preserve_lists:
            return self._process_list(element, depth=depth)

        if tag_name == "table" and self.preserve_tables:
            return self._process_table(element)

        if tag_name in ("em", "i", "strong", "b", "mark") and self.preserve_emphasis:
            return self._process_emphasis(element)

        if tag_name == "pre":
            return self._process_code_block(element)

        if tag_name == "br" and self.preserve_line_breaks:
            return "\n"

        # Check if this is a poetry/verse container
        if self._is_poetry_container(element) and self.preserve_line_breaks:
            return self._process_poetry(element)

        # Default: recursively process children
        parts: List[str] = []
        for child in element.children:
            child_text = self._walk_tree(child, depth=depth)
            if child_text:
                parts.append(child_text)

        # Join with appropriate separator
        if tag_name in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li"):
            # Block elements get newline separation
            return "\n".join(parts) if parts else ""
        else:
            # Inline elements get space separation
            return " ".join(parts) if parts else ""

    def _process_blockquote(self, element: Tag) -> str:
        """Process blockquote with attribution and indentation.

        Args:
            element: blockquote Tag

        Returns:
            Formatted blockquote with > prefix
        """
        lines: List[str] = []

        # Extract main quote content (skip attribution/footer)
        for child in element.children:
            if isinstance(child, Tag):
                # Skip footer/attribution elements for now
                if child.name in ("footer", "cite"):
                    continue
                child_text = self._walk_tree(child, depth=0)
                if child_text:
                    lines.append(child_text)
            elif isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    lines.append(text)

        # Prefix each line with >
        quoted_lines = [f"> {line}" for line in lines if line]

        # Add attribution if present
        attribution = self._extract_attribution(element)
        if attribution:
            quoted_lines.append(f">\n> — {attribution}")

        return "\n".join(quoted_lines)

    def _process_list(self, element: Tag, depth: int = 0) -> str:
        """Process ordered/unordered list with nesting.

        Args:
            element: ol or ul Tag
            depth: Current nesting depth (0-indexed)

        Returns:
            Formatted list with proper markers and indentation
        """
        is_ordered = element.name == "ol"
        indent = "  " * depth  # 2 spaces per nesting level
        lines: List[str] = []

        item_num = 1
        for child in element.children:
            if isinstance(child, Tag) and child.name == "li":
                # Get list item content
                item_parts: List[str] = []

                for subchild in child.children:
                    if isinstance(subchild, Tag):
                        # Nested list
                        if subchild.name in ("ol", "ul"):
                            nested = self._process_list(subchild, depth=depth + 1)
                            item_parts.append(nested)
                        else:
                            text = self._walk_tree(subchild, depth=depth)
                            if text:
                                item_parts.append(text)
                    elif isinstance(subchild, NavigableString):
                        text = str(subchild).strip()
                        if text:
                            item_parts.append(text)

                # Format list item
                content = " ".join(item_parts) if item_parts else ""
                if content:
                    if is_ordered:
                        lines.append(f"{indent}{item_num}. {content}")
                        item_num += 1
                    else:
                        lines.append(f"{indent}- {content}")

        return "\n".join(lines)

    def _process_poetry(self, element: Tag) -> str:
        """Process verse/poetry with line breaks and indentation.

        Preserves line structure for poetry, detecting line elements
        by class names (line, verse) or <br> tags.

        Args:
            element: Container element (div, p) with poetry

        Returns:
            Poetry text with preserved line breaks
        """
        lines: List[str] = []

        for child in element.children:
            if isinstance(child, Tag):
                # Check if this is a line container
                if self._is_line_element(child):
                    line_text = self._walk_tree(child, depth=0)
                    if line_text:
                        # Preserve leading whitespace for indentation
                        original_text = child.get_text()
                        leading_spaces = len(original_text) - len(original_text.lstrip())
                        indented = (" " * leading_spaces) + line_text.strip()
                        lines.append(indented)
                else:
                    # Recursively process (may contain stanzas)
                    child_text = self._process_poetry(child)
                    if child_text:
                        lines.append(child_text)
            elif isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    lines.append(text)

        # Join with preserved line breaks
        return "\n".join(lines) if lines else ""

    def _process_table(self, element: Tag) -> str:
        """Process table with cell relationships.

        Converts HTML table to markdown table format (experimental).

        Args:
            element: table Tag

        Returns:
            Markdown-formatted table
        """
        rows: List[List[str]] = []

        # Process thead and tbody
        for section in element.find_all(["thead", "tbody"]):
            for tr in section.find_all("tr"):
                row: List[str] = []
                for cell in tr.find_all(["th", "td"]):
                    cell_text = self._walk_tree(cell, depth=0)
                    row.append(cell_text.strip() if cell_text else "")
                if row:
                    rows.append(row)

        # If no thead/tbody, process rows directly
        if not rows:
            for tr in element.find_all("tr"):
                row: List[str] = []
                for cell in tr.find_all(["th", "td"]):
                    cell_text = self._walk_tree(cell, depth=0)
                    row.append(cell_text.strip() if cell_text else "")
                if row:
                    rows.append(row)

        if not rows:
            return ""

        # Build markdown table
        lines: List[str] = []

        # Header row
        if rows:
            lines.append("| " + " | ".join(rows[0]) + " |")
            # Separator
            lines.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
            # Data rows
            for row in rows[1:]:
                lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    def _process_emphasis(self, element: Tag) -> str:
        """Process em/strong/mark elements.

        Args:
            element: Emphasis Tag (em, strong, mark, etc.)

        Returns:
            Markdown-style emphasis (*italic*, **bold**)
        """
        tag_name = element.name.lower()

        # Get text content directly from children to avoid infinite recursion
        # Don't call _walk_tree which would process emphasis tags again
        parts: List[str] = []
        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    parts.append(text)
            elif isinstance(child, Tag):
                # Recursively process child but treat it as a regular element
                child_text = self._walk_tree(child, depth=0)
                if child_text:
                    parts.append(child_text)

        content = " ".join(parts) if parts else ""

        if tag_name in ("strong", "b"):
            return f"**{content}**"
        elif tag_name in ("em", "i"):
            return f"*{content}*"
        elif tag_name == "mark":
            return f"=={content}=="
        else:
            return content

    def _process_code_block(self, element: Tag) -> str:
        """Process code/pre blocks with preserved indentation.

        Args:
            element: pre Tag

        Returns:
            Code block with triple backticks
        """
        # Try to detect language from code child's class
        lang = ""
        code_tag = element.find("code")
        if code_tag and code_tag.get("class"):
            classes = code_tag.get("class", [])
            for cls in classes:
                if cls.startswith("language-"):
                    lang = cls.replace("language-", "")
                    break

        # Also check pre element itself
        if not lang and element.get("class"):
            classes = element.get("class", [])
            for cls in classes:
                if cls.startswith("language-"):
                    lang = cls.replace("language-", "")
                    break

        # Get code content (preserve whitespace)
        if code_tag:
            content = code_tag.get_text()
        else:
            content = element.get_text()

        return f"```{lang}\n{content}\n```"

    def _is_poetry_container(self, element: Tag) -> bool:
        """Check if element is a poetry/verse container.

        Args:
            element: Tag to check

        Returns:
            True if element appears to contain poetry
        """
        if not isinstance(element, Tag):
            return False

        # Check class names
        classes = element.get("class", [])
        poetry_classes = {"poem", "poetry", "verse", "stanza", "lines"}
        if any(cls in poetry_classes for cls in classes):
            return True

        # Check if contains multiple line elements
        line_count = len(element.find_all(class_=lambda c: c and "line" in c))
        return line_count >= 2

    def _is_line_element(self, element: Tag) -> bool:
        """Check if element represents a single line of verse.

        Args:
            element: Tag to check

        Returns:
            True if element is a verse line
        """
        if not isinstance(element, Tag):
            return False

        classes = element.get("class", [])
        line_classes = {"line", "verse"}
        return any(cls in line_classes for cls in classes)

    def _is_blockquote(self, element: Tag) -> bool:
        """Check if element is a blockquote.

        Args:
            element: Tag to check

        Returns:
            True if element is a blockquote
        """
        return isinstance(element, Tag) and element.name == "blockquote"

    def _is_list(self, element: Tag) -> bool:
        """Check if element is a list.

        Args:
            element: Tag to check

        Returns:
            True if element is ol or ul
        """
        return isinstance(element, Tag) and element.name in ("ol", "ul")

    def _extract_attribution(self, blockquote: Tag) -> Optional[str]:
        """Extract attribution from blockquote footer/cite.

        Args:
            blockquote: blockquote Tag

        Returns:
            Attribution text or None
        """
        # Check for footer element
        footer = blockquote.find("footer")
        if footer:
            return footer.get_text(strip=True)

        # Check for cite attribute
        cite = blockquote.get("cite")
        if cite:
            return cite

        # Check for cite element
        cite_elem = blockquote.find("cite")
        if cite_elem:
            return cite_elem.get_text(strip=True)

        return None

    def _find_line_break_positions(self, element: Tag) -> List[int]:
        """Find character positions of line breaks in poetry.

        Args:
            element: Poetry container element

        Returns:
            List of character offsets where line breaks occur
        """
        positions: List[int] = []
        current_pos = 0

        for child in element.descendants:
            if isinstance(child, Tag) and child.name == "br":
                positions.append(current_pos)
            elif isinstance(child, NavigableString):
                text = str(child)
                current_pos += len(text)

        return positions
