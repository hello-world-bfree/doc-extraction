import json
import os
import re
from typing import List, Optional

from bs4 import BeautifulSoup

# Try to import a tokenizer for more accurate token counting.  When
# unavailable, fall back to a simple whitespace split.  This allows
# callers to adjust chunk sizes based on real LLM token counts if the
# tiktoken library is installed.  Otherwise the code behaves as
# before.
try:
    import tiktoken  # type: ignore
    _TOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")
    def count_llm_tokens(text: str) -> int:
        return len(_TOKEN_ENCODER.encode(text))
except Exception:
    raise RuntimeError("Failed to initialize tiktoken tokenizer")


class BibleHTMLParser:
    """Parse a directory of Bible HTML files into verse and chunk structures.

    This class can be used to extract structured verse information from HTML
    files and then aggregate those verses into token-based chunks suitable
    for retrieval augmented generation (RAG).  You can tune the chunk
    parameters – such as token threshold and token overlap – via the
    constructor.  Token counting is done via the `tiktoken` library when
    available; otherwise it falls back to whitespace splitting.
    """

    def __init__(
        self,
        html_directory: str,
        manifest_path: str = "manifest.json",
        *,
        token_threshold: int = 250,
        token_overlap: int = 0,
    ) -> None:
        """
        Parameters
        ----------
        html_directory : str
            Path to a directory containing HTML files to parse.
        manifest_path : str, optional
            Path to the manifest JSON describing books and translation
            information (default: "manifest.json").
        token_threshold : int, optional
            Maximum number of LLM tokens per chunk.  When adding a verse
            would exceed this threshold, the current chunk is finalized and
            a new one is started.  Default is 250.
        token_overlap : int, optional
            Number of LLM tokens to copy from the end of the previous chunk
            to the beginning of the next chunk.  Overlap helps maintain
            context between adjacent chunks when using them for retrieval.
            Default is 0 (no overlap).
        """
        self.html_directory: str = html_directory
        self.manifest_path: str = manifest_path
        self.token_threshold: int = max(1, token_threshold)
        self.token_overlap: int = max(0, token_overlap)
        self.chunks: List[dict] = []
        self.manifest: Optional[dict] = None
        self.book_lookup: dict = {}

    # Manifest loading and HTML discovery
    def load_manifest(self) -> bool:
        """Load the Bible manifest file and populate lookup dictionaries."""
        print(f"Loading manifest: {self.manifest_path}")
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                self.manifest = json.load(f)
            # Build a case-insensitive lookup for book identifiers
            for book in self.manifest.get("books", []):
                for key in (book["id"], book["name"], str(book.get("numeric_id"))):
                    self.book_lookup[key] = book
                    self.book_lookup[key.lower()] = book
            print(
                f"✓ Loaded manifest with {len(self.manifest['books'])} books\n"
                f"  Translation: {self.manifest['translation_name']} "
                f"({self.manifest['translation_id']})\n"
                f"  Language: {self.manifest['translation_language']}"
            )
            return True
        except Exception as exc:
            print(f"❌ Error loading manifest: {exc}")
            return False

    def find_html_files(self) -> List[str]:
        """Walk the directory tree and return a sorted list of HTML files."""
        html_files: List[str] = []
        if not os.path.exists(self.html_directory):
            print(f"❌ Directory not found: {self.html_directory}")
            return []
        for root, _, files in os.walk(self.html_directory):
            for filename in files:
                if filename.lower().endswith(".html"):
                    html_files.append(os.path.join(root, filename))
        print(f"Found {len(html_files)} HTML files")
        return sorted(html_files)

    # Book identification
    def identify_book_from_filename(self, filename: str):
        basename = os.path.basename(filename)
        folder = os.path.basename(os.path.dirname(filename))
        folder_key = folder.lower()
        if folder_key in self.book_lookup:
            book_info = self.book_lookup[folder_key]
            m = re.match(r"^(\d+)\.html$", basename)
            chapter_num = int(m.group(1)) if m else None
            print(f"    📖 Book: {book_info['name']}, Chapter: {chapter_num}")
            return book_info, chapter_num
        # If purely numeric, it's a chapter number only
        m = re.match(r"^(\d+)\.html$", basename)
        if m:
            return None, int(m.group(1))
        identifier = os.path.splitext(basename)[0]
        key = identifier.lower()
        if key in self.book_lookup:
            return self.book_lookup[key], None
        return None, None

    def identify_book_from_content(self, soup: BeautifulSoup):
        """Attempt to deduce book and chapter numbers from HTML headings."""
        for heading in soup.find_all(["h1", "h2", "h3"]):
            text = heading.get_text().strip()
            m = re.match(r"^([A-Za-z0-9\s]+)\s+(\d+)$", text)
            if m:
                book_name = m.group(1).strip().lower()
                if book_name in self.book_lookup:
                    return self.book_lookup[book_name], int(m.group(2))
            if text.lower() in self.book_lookup:
                return self.book_lookup[text.lower()], None
        return None, None

    # Verse extraction
    def extract_verses_from_html(
        self, soup: BeautifulSoup, book_info: dict, chapter_num: Optional[int] = None
    ) -> List[dict]:
        verses: List[dict] = []
        if chapter_num is None:
            chapter_num = 1
        print(f"    🔍 Extracting verses from {book_info['name']} Chapter {chapter_num}")
        verse_wrappers = soup.find_all("span", class_="verseWrapper")
        print(f"    📝 Found {len(verse_wrappers)} verse wrapper elements")
        # Section titles help with chunk context; optional
        section_title = ""
        section_header = soup.find("h2", class_="ahaft")
        if section_header:
            section_title = section_header.get_text().strip()
        # Iterate over wrapper spans
        for wrapper in verse_wrappers:
            ver_el = wrapper.find("span", class_=["ver", "ver-f"])
            if not ver_el:
                continue
            ver_text = ver_el.get_text().strip()
            try:
                verse_num = int(ver_text)
            except (ValueError, TypeError):
                continue
            full_text = wrapper.get_text().strip()
            clean_text = full_text[len(ver_text) :].strip()
            if not clean_text or len(clean_text) < 3:
                continue
            verses.append(
                {
                    "book_id": book_info["id"],
                    "book_name": book_info["name"],
                    "book_numeric_id": book_info["numeric_id"],
                    "testament": book_info["testament"],
                    "chapter": chapter_num,
                    "verse": verse_num,
                    "text": clean_text,
                    "section_title": section_title,
                    "reference": f"{book_info['name']} {chapter_num}:{verse_num}",
                    "text_length": len(clean_text),
                }
            )
        print(
            f"    ✅ Extracted {len(verses)} verses from {book_info['name']} Chapter {chapter_num}"
        )
        return verses

    def process_html_file(self, filepath: str) -> List[dict]:
        print(f"\n📄 Processing: {os.path.relpath(filepath, self.html_directory)}")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            soup = BeautifulSoup(content, "html.parser")
            book_info, chapter_num = self.identify_book_from_filename(filepath)
            if not book_info:
                print("    🔍 Trying to identify from content...")
                book_info, chapter_num = self.identify_book_from_content(soup)
            if not book_info:
                print(
                    f"    ❌ Could not identify book for {os.path.basename(filepath)}"
                )
                return []
            verses = self.extract_verses_from_html(soup, book_info, chapter_num)
            if verses:
                print(f"    ✅ Successfully extracted {len(verses)} verses")
            else:
                print("    ⚠️ No verses extracted")
            return verses
        except Exception as exc:
            print(f"    ❌ Error processing {filepath}: {exc}")
            import traceback
            traceback.print_exc()
            return []

    def extract_cross_references(self, text: str) -> List[str]:
        refs: List[str] = []
        patterns = [
            r"\b(?:[1-3]\s*)?[A-Z][a-z]+\.?\s*\d+[:]\d+(?:-\d+)?",
            r"\bcf\.\s*([A-Z][a-z]+\.?\s*\d+[:]\d+)",
            r"\bsee\s*([A-Z][a-z]+\.?\s*\d+[:]\d+)",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text)
            refs.extend(matches)
        return list(sorted(set(refs)))

    def process_all_files(self) -> Optional[List[dict]]:
        print("=" * 60)
        print("BIBLE HTML PARSER WITH MANIFEST")
        print("=" * 60)
        if not self.load_manifest():
            return None
        html_files = self.find_html_files()
        if not html_files:
            print("❌ No HTML files found")
            return None
        all_verses: List[dict] = []
        print(f"\n🔄 Processing {len(html_files)} HTML files...")
        for filepath in html_files:
            verses = self.process_html_file(filepath)
            if verses:
                all_verses.extend(verses)
            if len(all_verses) > 0 and len(all_verses) % 100 == 0:
                print(f"📊 Progress: {len(all_verses)} verses extracted so far...")
        print("\n📊 EXTRACTION COMPLETE:")
        print(f"  📄 Files processed: {len(html_files)}")
        print(f"  📝 Total verses extracted: {len(all_verses)}")
        if not all_verses:
            print("❌ No verses were extracted from any files!")
            return None
        all_verses_sorted = sorted(
            all_verses,
            key=lambda v: (v["book_numeric_id"], v["chapter"], v["verse"]),
        )
        print(f"\n🔄 Creating chunks from {len(all_verses_sorted)} verses...")
        chunk_id = 1
        current_chunk: Optional[dict] = None
        overlap_buffer: List[str] = []

        def finalize_chunk():
            nonlocal chunk_id, current_chunk, overlap_buffer
            if current_chunk and current_chunk["verse_nums"]:
                # Trim whitespace and build chunk text
                chunk_text = current_chunk["text"].strip()
                if chunk_text:
                    # Determine the overlap tokens for the next chunk
                    tokens = chunk_text.split()
                    overlap_buffer = (
                        tokens[-self.token_overlap :].copy()
                        if self.token_overlap > 0
                        else []
                    )
                    verse_nums = current_chunk["verse_nums"]
                    # Determine reference string: contiguous range vs comma-separated
                    if len(verse_nums) == 1:
                        ref_part = str(verse_nums[0])
                    else:
                        # Check if consecutive sequence
                        is_contiguous = all(
                            verse_nums[i] + 1 == verse_nums[i + 1]
                            for i in range(len(verse_nums) - 1)
                        )
                        if is_contiguous:
                            ref_part = f"{verse_nums[0]}–{verse_nums[-1]}"
                        else:
                            ref_part = ",".join(str(v) for v in verse_nums)
                    # Append chunk with additional metadata
                    self.chunks.append(
                        {
                            "chunk_id": chunk_id,
                            "book_id": current_chunk["book_id"],
                            "book_name": current_chunk["book_name"],
                            "book_numeric_id": current_chunk["book_numeric_id"],
                            "testament": current_chunk["testament"],
                            "chapter": current_chunk["chapter"],
                            "verses": verse_nums,
                            "reference": f"{current_chunk['book_name']} {current_chunk['chapter']}:{ref_part}",
                            "text": chunk_text,
                            "section_title": "; ".join(
                                sorted(current_chunk["sections"])
                            )
                            if current_chunk["sections"]
                            else "",
                            # Character and token counts
                            "text_length": len(chunk_text),
                            "token_count": current_chunk.get("token_count", 0),
                            "cross_references": sorted(current_chunk["cross_refs"])
                            if current_chunk["cross_refs"]
                            else [],
                            "translation": {
                                "id": self.manifest.get("translation_id"),
                                "name": self.manifest.get("translation_name"),
                                "language": self.manifest.get("translation_language"),
                                "description": self.manifest.get("translation_description", ""),
                            },
                        }
                    )
                    chunk_id += 1
                # Reset current_chunk after finalizing
                current_chunk = None

        # Iterate through sorted verses and build chunks
        for verse in all_verses_sorted:
            verse_tokens = count_llm_tokens(verse["text"])
            # Determine if we need to start a new chunk
            if (
                current_chunk is None
                or verse["book_id"] != current_chunk["book_id"]
                or verse["chapter"] != current_chunk["chapter"]
                or current_chunk["token_count"] + verse_tokens > self.token_threshold
            ):
                # finalize existing chunk
                finalize_chunk()
                # start new chunk and include overlap buffer if available
                current_chunk = {
                    "book_id": verse["book_id"],
                    "book_name": verse["book_name"],
                    "book_numeric_id": verse["book_numeric_id"],
                    "testament": verse["testament"],
                    "chapter": verse["chapter"],
                    "verse_nums": [],
                    "text": "",
                    "sections": set(),
                    "cross_refs": set(),
                    "token_count": 0,
                }
                # Prefill with overlap buffer
                if overlap_buffer:
                    pre_text = " ".join(overlap_buffer)
                    current_chunk["text"] = pre_text
                    current_chunk["token_count"] = len(overlap_buffer)
            # Append verse to current chunk
            current_chunk["verse_nums"].append(verse["verse"])
            # Prepend a space if text already exists
            current_chunk["text"] += (" " if current_chunk["text"] else "") + verse["text"]
            if verse["section_title"]:
                current_chunk["sections"].add(verse["section_title"])
            current_chunk["cross_refs"].update(
                self.extract_cross_references(verse["text"])
            )
            current_chunk["token_count"] += verse_tokens
        # finalize any remaining chunk
        finalize_chunk()
        print(f"📦 Created {len(self.chunks)} chunks")
        if self.chunks:
            with open("bible_structured.json", "w", encoding="utf-8") as f:
                json.dump(self.chunks, f, indent=2, ensure_ascii=False)
            print(
                f"✅ Saved {len(self.chunks)} chunks to bible_structured.json"
            )
        else:
            print("⚠️ No chunks created")
        # Generate reports
        self.create_summary_report()
        self.create_structure_tree()
        self.show_samples()
        self.show_chunk_stats()
        return self.chunks

    # Reporting utilities
    def create_summary_report(self) -> None:
        if not self.chunks or not self.manifest:
            return
        with open("bible_summary_report.txt", "w", encoding="utf-8") as f:
            f.write("BIBLE PARSING SUMMARY REPORT\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Translation: {self.manifest['translation_name']}\n")
            f.write(f"Language: {self.manifest['translation_language']}\n")
            f.write(f"Total chunks extracted: {len(self.chunks)}\n\n")
            book_stats: dict = {}
            testament_stats = {"old": 0, "new": 0}
            for chunk in self.chunks:
                book_name = chunk["book_name"]
                testament = chunk["testament"]
                book_stats[book_name] = book_stats.get(book_name, 0) + 1
                testament_stats[testament] += 1
            f.write("TESTAMENT DISTRIBUTION:\n")
            f.write(
                f"  Old Testament: {testament_stats['old']} chunks\n"
                f"  New Testament: {testament_stats['new']} chunks\n\n"
            )
            f.write("BOOKS WITH CHUNKS:\n")
            for book_name in sorted(book_stats):
                f.write(f"  {book_name}: {book_stats[book_name]} chunks\n")
            processed_books = set(book_stats)
            available_books = set(book["name"] for book in self.manifest["books"])
            missing_books = available_books - processed_books
            if missing_books:
                f.write("\nMISSING BOOKS (in manifest but not processed):\n")
                for book in sorted(missing_books):
                    f.write(f"  {book}\n")
            f.write(
                f"\nProcessed {len(processed_books)} out of {len(available_books)} available books"
            )
        print("✅ Created bible_summary_report.txt")

    def show_samples(self) -> None:
        if not self.chunks:
            return
        print("\n📖 Sample chunks:")
        for chunk in self.chunks[:5]:
            print(f"\n{chunk['reference']}:")
            print(f"  Testament: {chunk['testament'].title()}")
            print(f"  Book ID: {chunk['book_id']}")
            print(f"  Section: {chunk['section_title']}")
            print(f"  Text: {chunk['text'][:100]}...")
            if chunk["cross_references"]:
                print(
                    f"  Cross-refs: {', '.join(chunk['cross_references'][:3])}"
                )

    def create_structure_tree(self) -> None:
        if not self.manifest or not self.chunks:
            return
        # index chunks by book and chapter
        parsed: dict = {}
        for chunk in self.chunks:
            parsed.setdefault(chunk["book_id"], {}).setdefault(chunk["chapter"], []).append(
                chunk
            )
        with open("bible_structure_tree.txt", "w", encoding="utf-8") as f:
            f.write("BIBLE STRUCTURE TREE (MANIFEST ALIGNMENT)\n")
            f.write("=" * 60 + "\n\n")
            for book in self.manifest["books"]:
                name = book["name"]
                chap_count = book["chapter_count"]
                book_chunks = parsed.get(book["id"], {})
                if not book_chunks:
                    continue
                f.write(f"BOOK: {name}\n")
                for chap in range(1, chap_count + 1):
                    chapter_chunks = book_chunks.get(chap, [])
                    if chapter_chunks:
                        f.write(f"  └─ Chapter {chap} ({len(chapter_chunks)} chunks)\n")
                        for ch in chapter_chunks:
                            f.write(
                                f"      {ch['reference']}: {ch['text'][:40]}...\n"
                            )
                f.write("\n")
        print("✅ Created bible_structure_tree.txt")

    def show_chunk_stats(self) -> None:
        if not self.chunks:
            print("No chunks to analyze.")
            return
        lengths = [c["text_length"] for c in self.chunks]
        total = sum(lengths)
        avg = total / len(lengths)
        longest = max(lengths)
        shortest = min(lengths)
        print("\n📊 CHUNK SIZE STATS:")
        print(f"  Total Chunks: {len(lengths)}")
        print(f"  Total Characters: {total}")
        print(f"  Average Chunk Length: {avg:.2f} chars")
        print(f"  Shortest Chunk: {shortest} chars")
        print(f"  Longest Chunk: {longest} chars")


def main() -> None:
    default_path = "/Users/daniellefreeman/Downloads/bible_nrsvce"
    html_directory = input(
        f"Enter HTML directory path (or press Enter for '{default_path}'): "
    ).strip()
    if not html_directory:
        html_directory = default_path
    manifest_path = input(
        "Enter manifest.json path (or press Enter for 'manifest.json'): "
    ).strip() or "manifest.json"
    if not os.path.exists(manifest_path):
        alt_manifest_path = os.path.join(html_directory, "manifest.json")
        if os.path.exists(alt_manifest_path):
            manifest_path = alt_manifest_path
            print(f"Using manifest found in HTML directory: {manifest_path}")
        else:
            print(f"❌ Manifest file not found: {manifest_path}")
            print(f"Also checked: {alt_manifest_path}")
            return
    if not os.path.exists(html_directory):
        print(f"❌ HTML directory not found: {html_directory}")
        return
    # Ask user for optional chunking parameters
    try:
        threshold_input = input(
            f"Enter token threshold per chunk (default {250}): "
        ).strip()
        token_threshold = int(threshold_input) if threshold_input else 250
    except ValueError:
        token_threshold = 250
    try:
        overlap_input = input(
            f"Enter token overlap between chunks (default {0}): "
        ).strip()
        token_overlap = int(overlap_input) if overlap_input else 0
    except ValueError:
        token_overlap = 0
    parser = BibleHTMLParser(
        html_directory,
        manifest_path,
        token_threshold=token_threshold,
        token_overlap=token_overlap,
    )
    chunks = parser.process_all_files()
    if chunks:
        print("\n🎉 SUCCESS! Processed Bible content:")
        print(f"  📦 Total chunks: {len(chunks)}")
        print(f"  📁 Source directory: {html_directory}")
        print("\nFiles created:")
        print("  1. bible_structured.json - Complete verse data")
        print("  2. bible_summary_report.txt - Processing summary")
        print("  3. bible_structure_tree.txt - Structure overview")
    else:
        print("❌ No content was successfully processed")


if __name__ == "__main__":
    main()