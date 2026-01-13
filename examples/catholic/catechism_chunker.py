import PyPDF2
import json
import re
from tqdm import tqdm

class CatechismPDFParser:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.chunks = []
        # Track current position in hierarchy
        self.current_hierarchy = {
            'part': '',
            'part_title': '',
            'section': '',
            'section_title': '',
            'chapter': '',
            'chapter_title': '',
            'article': '',
            'article_title': '',
            'subsection': ''
        }
        
    def extract_text_with_structure(self):
        """Extract text while tracking structure"""
        print(f"Opening PDF: {self.pdf_path}")
        
        structured_text = []
        
        try:
            with open(self.pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                
                print(f"PDF has {total_pages} pages")
                
                # Process page by page to maintain structure
                for page_num in tqdm(range(total_pages), desc="Reading pages"):
                    try:
                        page = pdf_reader.pages[page_num]
                        text = page.extract_text()
                        
                        # Store with page number for structure tracking
                        structured_text.append({
                            'page': page_num + 1,
                            'text': text
                        })
                        
                    except Exception as e:
                        print(f"Error on page {page_num}: {e}")
                        continue
                
                return structured_text
                
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return None
    
    def update_hierarchy(self, text):
        """Check text for hierarchy markers and update current position"""
        
        # PART detection
        part_match = re.search(r'PART\s+(ONE|TWO|THREE|FOUR|I|II|III|IV)\s*[:\n]\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if part_match:
            part_num = part_match.group(1)
            part_title = part_match.group(2).strip() if len(part_match.groups()) > 1 else ''
            self.current_hierarchy['part'] = f"PART {part_num}"
            self.current_hierarchy['part_title'] = part_title
            # Reset lower levels
            self.current_hierarchy['section'] = ''
            self.current_hierarchy['chapter'] = ''
            self.current_hierarchy['article'] = ''
            print(f"  Found: PART {part_num}: {part_title[:50]}")
        
        # SECTION detection
        section_match = re.search(r'SECTION\s+(ONE|TWO|THREE|FOUR|I|II|III|IV)\s*[:\n]\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if section_match:
            section_num = section_match.group(1)
            section_title = section_match.group(2).strip() if len(section_match.groups()) > 1 else ''
            self.current_hierarchy['section'] = f"SECTION {section_num}"
            self.current_hierarchy['section_title'] = section_title
            # Reset lower levels
            self.current_hierarchy['chapter'] = ''
            self.current_hierarchy['article'] = ''
            print(f"    Found: SECTION {section_num}: {section_title[:50]}")
        
        # CHAPTER detection
        chapter_match = re.search(r'CHAPTER\s+([A-Z]+|\d+)\s*[:\n]\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if chapter_match:
            chapter_num = chapter_match.group(1)
            chapter_title = chapter_match.group(2).strip() if len(chapter_match.groups()) > 1 else ''
            self.current_hierarchy['chapter'] = f"CHAPTER {chapter_num}"
            self.current_hierarchy['chapter_title'] = chapter_title
            # Reset article
            self.current_hierarchy['article'] = ''
            print(f"      Found: CHAPTER {chapter_num}: {chapter_title[:50]}")
        
        # ARTICLE detection
        article_match = re.search(r'ARTICLE\s+(\d+)\s*[:\n]\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if article_match:
            article_num = article_match.group(1)
            article_title = article_match.group(2).strip() if len(article_match.groups()) > 1 else ''
            self.current_hierarchy['article'] = f"ARTICLE {article_num}"
            self.current_hierarchy['article_title'] = article_title
            print(f"        Found: ARTICLE {article_num}: {article_title[:50]}")
        
        # Subsection detection (like "IN BRIEF")
        if 'IN BRIEF' in text.upper():
            self.current_hierarchy['subsection'] = 'IN BRIEF'
    
    def parse_with_structure(self, structured_text):
        """Parse paragraphs while maintaining hierarchical structure"""
        print("\nParsing paragraphs with hierarchical structure...")
        
        all_paragraphs = {}
        
        # Process each page
        for page_data in tqdm(structured_text, desc="Processing structure"):
            text = page_data['text']
            page_num = page_data['page']
            
            # Update hierarchy based on headers found
            self.update_hierarchy(text)
            
            # Split into lines for paragraph detection
            lines = text.split('\n')
            
            for i, line in enumerate(lines):
                # Look for paragraph numbers
                para_match = re.match(r'^\s*§?\s*(\d{1,4})\.?\s+(.+)', line)
                
                if para_match:
                    try:
                        para_num = int(para_match.group(1))
                        
                        if 1 <= para_num <= 2865:
                            # Get the rest of the paragraph (may span multiple lines)
                            para_text = para_match.group(2)
                            
                            # Look ahead for continuation lines
                            j = i + 1
                            while j < len(lines) and j < i + 10:  # Check next 10 lines max
                                next_line = lines[j].strip()
                                # Stop if we hit another paragraph number
                                if re.match(r'^\s*§?\s*(\d{1,4})\.?\s+', next_line):
                                    break
                                # Stop if we hit a section header
                                if re.match(r'^(PART|SECTION|CHAPTER|ARTICLE)\s+', next_line, re.IGNORECASE):
                                    break
                                if next_line:
                                    para_text += " " + next_line
                                j += 1
                            
                            # Clean up text
                            para_text = re.sub(r'\s+', ' ', para_text).strip()
                            
                            # Store with hierarchy
                            if para_num not in all_paragraphs or len(para_text) > len(all_paragraphs[para_num]['text']):
                                all_paragraphs[para_num] = {
                                    'text': para_text,
                                    'hierarchy': self.current_hierarchy.copy(),
                                    'page': page_num
                                }
                    except:
                        continue
        
        print(f"Found {len(all_paragraphs)} paragraphs with structure")
        
        # Show structure coverage
        structure_stats = {
            'with_part': 0,
            'with_section': 0,
            'with_chapter': 0,
            'with_article': 0
        }
        
        for para_data in all_paragraphs.values():
            if para_data['hierarchy']['part']:
                structure_stats['with_part'] += 1
            if para_data['hierarchy']['section']:
                structure_stats['with_section'] += 1
            if para_data['hierarchy']['chapter']:
                structure_stats['with_chapter'] += 1
            if para_data['hierarchy']['article']:
                structure_stats['with_article'] += 1
        
        print(f"\nStructure coverage:")
        print(f"  Paragraphs with PART: {structure_stats['with_part']}")
        print(f"  Paragraphs with SECTION: {structure_stats['with_section']}")
        print(f"  Paragraphs with CHAPTER: {structure_stats['with_chapter']}")
        print(f"  Paragraphs with ARTICLE: {structure_stats['with_article']}")
        
        # Convert to final format
        chunks = []
        for para_num in sorted(all_paragraphs.keys()):
            para_data = all_paragraphs[para_num]
            
            chunk = {
                'paragraph_id': para_num,
                'text': para_data['text'],
                'hierarchy': para_data['hierarchy'],
                'page': para_data['page'],
                'text_length': len(para_data['text']),
                'cross_references': self.extract_cross_references(para_data['text']),
                'scripture_references': self.extract_scripture_references(para_data['text'])
            }
            chunks.append(chunk)
        
        return chunks
    
    def extract_cross_references(self, text):
        """Extract references to other paragraphs"""
        refs = []
        patterns = [
            r'cf\.\s*(?:§\s*)?(\d+)',
            r'see\s*(?:§\s*)?(\d+)',
            r'§§?\s*(\d+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            refs.extend([int(m) for m in matches if m.isdigit() and 1 <= int(m) <= 2865])
        
        return list(set(refs))
    
    def extract_scripture_references(self, text):
        """Extract biblical references"""
        pattern = r'\b(?:[1-3]\s*)?[A-Z][a-z]+\.?\s*\d+[:]\d+(?:-\d+)?'
        matches = re.findall(pattern, text)
        return list(set(matches))
    
    def process_pdf(self):
        """Main processing function"""
        print("="*60)
        print("CATECHISM PDF PARSER WITH FULL HIERARCHY")
        print("="*60)
        
        # Extract text with structure tracking
        structured_text = self.extract_text_with_structure()
        
        if structured_text:
            # Parse with hierarchy
            self.chunks = self.parse_with_structure(structured_text)
            
            if self.chunks:
                # Save with full structure
                output_file = "catechism_hierarchical.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(self.chunks, f, indent=2, ensure_ascii=False)
                
                print(f"\n✓ Saved {len(self.chunks)} paragraphs to {output_file}")
                
                # Show samples with structure
                print("\nSample paragraphs with hierarchy:")
                samples_shown = 0
                for chunk in self.chunks:
                    if chunk['hierarchy']['part'] and samples_shown < 5:
                        print(f"\n§{chunk['paragraph_id']}:")
                        print(f"  Part: {chunk['hierarchy']['part']} - {chunk['hierarchy']['part_title'][:30]}")
                        print(f"  Section: {chunk['hierarchy']['section']} - {chunk['hierarchy']['section_title'][:30]}")
                        print(f"  Chapter: {chunk['hierarchy']['chapter']} - {chunk['hierarchy']['chapter_title'][:30]}")
                        print(f"  Article: {chunk['hierarchy']['article']} - {chunk['hierarchy']['article_title'][:30]}")
                        print(f"  Text: {chunk['text'][:100]}...")
                        samples_shown += 1
                
                # Create structured summary
                self.create_hierarchy_report()
                
                return self.chunks
            else:
                print("❌ No paragraphs found")
        
        return None
    
    def create_hierarchy_report(self):
        """Create a report showing the hierarchical structure"""
        with open("catechism_hierarchy_report.txt", "w") as f:
            f.write("CATECHISM HIERARCHICAL STRUCTURE\n")
            f.write("="*60 + "\n\n")
            
            # Track unique structure combinations
            unique_structures = {}
            
            for chunk in self.chunks:
                h = chunk['hierarchy']
                structure_key = f"{h['part']}|{h['section']}|{h['chapter']}|{h['article']}"
                
                if structure_key not in unique_structures:
                    unique_structures[structure_key] = {
                        'hierarchy': h,
                        'paragraphs': []
                    }
                unique_structures[structure_key]['paragraphs'].append(chunk['paragraph_id'])
            
            # Write structure tree
            f.write("STRUCTURE TREE:\n\n")
            
            current_part = ""
            current_section = ""
            current_chapter = ""
            
            for key in sorted(unique_structures.keys()):
                struct = unique_structures[key]
                h = struct['hierarchy']
                para_range = f"{min(struct['paragraphs'])}-{max(struct['paragraphs'])}"
                
                if h['part'] != current_part:
                    current_part = h['part']
                    f.write(f"\n{h['part']}: {h['part_title']}\n")
                
                if h['section'] != current_section:
                    current_section = h['section']
                    if h['section']:
                        f.write(f"  └─ {h['section']}: {h['section_title']}\n")
                
                if h['chapter'] != current_chapter:
                    current_chapter = h['chapter']
                    if h['chapter']:
                        f.write(f"      └─ {h['chapter']}: {h['chapter_title']}\n")
                
                if h['article']:
                    f.write(f"          └─ {h['article']}: {h['article_title']} [§{para_range}]\n")
            
            f.write(f"\n\nTotal unique structures: {len(unique_structures)}")
            f.write(f"\nTotal paragraphs: {len(self.chunks)}")
        
        print("✓ Created catechism_hierarchy_report.txt")

# Main
def main():
    import os
    
    pdf_path = input("Enter PDF path (or press Enter for 'catechism.pdf'): ").strip()
    if not pdf_path:
        pdf_path = "catechism.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        return
    
    parser = CatechismPDFParser(pdf_path)
    chunks = parser.process_pdf()
    
    if chunks:
        print(f"\nSuccessfully extracted {len(chunks)} paragraphs with full hierarchy!")
        print("\nFiles created:")
        print("  1. catechism_hierarchical.json - Full data with structure")
        print("  2. catechism_hierarchy_report.txt - Structure tree visualization")

if __name__ == "__main__":
    main()