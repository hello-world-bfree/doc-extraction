#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Vatican archive web scraper for document discovery.

Navigates the Vatican archive structure to discover all English HTML documents.
Implements multi-layered English detection and respectful rate limiting.
"""

import logging
import re
import time
from dataclasses import dataclass
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .index import VaticanDocument

LOGGER = logging.getLogger("vatican.scraper")


@dataclass
class Section:
    """Represents a main archive section."""
    name: str
    url: str
    description: str = ""


class VaticanArchiveScraper:
    """
    Web scraper for Vatican archive.

    Discovers all English HTML documents by navigating the archive structure.
    Implements respectful crawling with rate limiting.
    """

    def __init__(self,
                 base_url: str = "https://www.vatican.va/archive/index.htm",
                 rate_limit: float = 1.0):
        """
        Initialize scraper.

        Args:
            base_url: Vatican archive entry point
            rate_limit: Minimum seconds between requests
        """
        self.base_url = base_url
        self.rate_limit = rate_limit
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'VaticanArchiveExtractor/2.0 (Catholic Document Research)'
        })
        self.last_request_time = 0
        self.visited_urls: Set[str] = set()

    def discover_all_documents(self, sections_filter: Optional[List[str]] = None) -> List[VaticanDocument]:
        """
        Main entry point: discovers all English documents.

        Args:
            sections_filter: Optional list of section names to filter (e.g., ["BIBLE", "CATECHISM"])

        Returns:
            List of discovered VaticanDocument objects
        """
        LOGGER.info("Starting document discovery from: %s", self.base_url)

        if sections_filter:
            LOGGER.info("Filtering to sections: %s", sections_filter)

        all_documents = []

        # Special case: if only BIBLE requested, skip section discovery
        if sections_filter == ["BIBLE"]:
            LOGGER.info("Using direct Bible scraper")
            all_documents = self.scrape_bible_section()
            LOGGER.info("Discovery complete: %d Bible documents found", len(all_documents))
            return all_documents

        # Special case: if only CATECHISM requested, skip section discovery
        if sections_filter == ["CATECHISM"]:
            LOGGER.info("Using direct Catechism scraper")
            all_documents = self.scrape_catechism_section()
            LOGGER.info("Discovery complete: %d Catechism documents found", len(all_documents))
            return all_documents

        # Special case: if only CANON_LAW requested, skip section discovery
        if sections_filter == ["CANON_LAW"]:
            LOGGER.info("Using direct Canon Law scraper")
            all_documents = self.scrape_canon_law_section()
            LOGGER.info("Discovery complete: %d Canon Law documents found", len(all_documents))
            return all_documents

        # Special case: if only COUNCILS requested, skip section discovery
        if sections_filter == ["COUNCILS"]:
            LOGGER.info("Using direct Councils scraper")
            all_documents = self.scrape_councils_section()
            LOGGER.info("Discovery complete: %d Council documents found", len(all_documents))
            return all_documents

        # Special case: if only MAGISTERIUM requested, skip section discovery
        if sections_filter == ["MAGISTERIUM"]:
            LOGGER.info("Using direct Magisterium scraper")
            all_documents = self.scrape_magisterium_section()
            LOGGER.info("Discovery complete: %d Magisterium documents found", len(all_documents))
            return all_documents

        # Special case: if only SOCIAL requested, skip section discovery
        if sections_filter == ["SOCIAL"]:
            LOGGER.info("Using direct Social scraper")
            all_documents = self.scrape_social_section()
            LOGGER.info("Discovery complete: %d Social documents found", len(all_documents))
            return all_documents

        # Get main sections
        sections = self.get_main_sections()
        LOGGER.info("Found %d main sections to scrape", len(sections))

        # Filter sections if requested
        if sections_filter:
            sections = [s for s in sections if s.name in sections_filter]
            LOGGER.info("Filtered to %d sections", len(sections))

        # Scrape each section
        for section in sections:
            LOGGER.info("Scraping section: %s (%s)", section.name, section.url)
            try:
                # Use section-specific scrapers
                if section.name == "BIBLE":
                    section_docs = self.scrape_bible_section()
                elif section.name == "CATECHISM":
                    section_docs = self.scrape_catechism_section()
                elif section.name == "CANON_LAW":
                    section_docs = self.scrape_canon_law_section()
                elif section.name == "COUNCILS":
                    section_docs = self.scrape_councils_section()
                elif section.name == "MAGISTERIUM":
                    section_docs = self.scrape_magisterium_section()
                elif section.name == "SOCIAL":
                    section_docs = self.scrape_social_section()
                else:
                    section_docs = self.scrape_section(section)
                all_documents.extend(section_docs)
                LOGGER.info("Section %s: discovered %d documents", section.name, len(section_docs))
            except Exception as e:
                LOGGER.error("Failed to scrape section %s: %s", section.name, e, exc_info=True)

        LOGGER.info("Discovery complete: %d total documents found", len(all_documents))
        return all_documents

    def get_main_sections(self) -> List[Section]:
        """
        Extract 6 main archive sections from index page.

        Returns:
            List of Section objects
        """
        soup = self._fetch_and_parse(self.base_url)
        if not soup:
            return []

        sections = []

        # Look for main section links in the index page
        # Vatican archive typically has links like:
        # - THE BIBLE
        # - CATECHISM OF THE CATHOLIC CHURCH
        # - CODES OF CANON LAW
        # - ECUMENICAL COUNCILS
        # - OFFICIAL ACTS OF THE HOLY SEE
        # - COMPENDIUM OF THE SOCIAL DOCTRINE

        # Find all major links (typically in uppercase or bold)
        for link in soup.find_all('a', href=True):
            link_text = link.get_text().strip().upper()
            href = link['href']

            # Match known section patterns
            if any(pattern in link_text for pattern in [
                'BIBLE', 'CATECHISM', 'CANON LAW', 'COUNCIL', 'ACTS', 'DOCTRINE', 'SOCIAL'
            ]):
                full_url = urljoin(self.base_url, href)

                # Determine section name
                if 'BIBLE' in link_text:
                    section_name = 'BIBLE'
                elif 'CATECHISM' in link_text:
                    section_name = 'CATECHISM'
                elif 'CANON' in link_text or 'LAW' in link_text:
                    section_name = 'CANON_LAW'
                elif 'COUNCIL' in link_text:
                    section_name = 'COUNCILS'
                elif 'ACTS' in link_text or 'HOLY SEE' in link_text:
                    section_name = 'MAGISTERIUM'
                elif 'SOCIAL' in link_text or 'DOCTRINE' in link_text:
                    section_name = 'SOCIAL'
                else:
                    section_name = 'OTHER'

                # Avoid duplicates
                if not any(s.name == section_name for s in sections):
                    sections.append(Section(
                        name=section_name,
                        url=full_url,
                        description=link_text
                    ))

        LOGGER.info("Identified %d main sections", len(sections))
        return sections

    def scrape_bible_section(self) -> List[VaticanDocument]:
        """
        Scrape the Bible section specifically.

        The Vatican Bible has a specific structure:
        - English Bible index: /archive/ENG0839/_INDEX.HTM
        - Chapter links use pattern: __P*.HTM

        Returns:
            List of Bible chapter documents
        """
        bible_index_url = "https://www.vatican.va/archive/ENG0839/_INDEX.HTM"
        documents = []

        LOGGER.info("Scraping English Bible from: %s", bible_index_url)

        # Fetch Bible index
        soup = self._fetch_and_parse(bible_index_url)
        if not soup:
            LOGGER.error("Failed to fetch Bible index")
            return documents

        # Find all chapter links (pattern: __P*.HTM)
        chapter_links = soup.find_all('a', href=lambda href: href and '__P' in href and href.endswith('.HTM'))

        LOGGER.info("Found %d potential chapter links", len(chapter_links))

        for link in chapter_links:
            href = link['href']
            # Make absolute URL
            chapter_url = urljoin(bible_index_url, href)

            # Extract chapter title from link text
            link_text = link.get_text().strip()

            # Skip if this looks like navigation or non-content link
            if not link_text or len(link_text) > 100:
                continue

            # Create document
            doc = VaticanDocument(
                url=chapter_url,
                title=f"Bible - {link_text}",
                section="BIBLE",
                document_type="Scripture",
                language="en"
            )
            documents.append(doc)

        LOGGER.info("Extracted %d Bible chapter documents", len(documents))
        return documents

    def scrape_catechism_section(self) -> List[VaticanDocument]:
        """
        Scrape the Catechism of the Catholic Church section specifically.

        The Vatican Catechism has a specific structure:
        - English Catechism index: /archive/ENG0015/_INDEX.HTM
        - Document links use pattern: __P*.HTM (same as Bible)

        Returns:
            List of Catechism documents
        """
        catechism_index_url = "https://www.vatican.va/archive/ENG0015/_INDEX.HTM"
        documents = []

        LOGGER.info("Scraping English Catechism from: %s", catechism_index_url)

        # Fetch Catechism index
        soup = self._fetch_and_parse(catechism_index_url)
        if not soup:
            LOGGER.error("Failed to fetch Catechism index")
            return documents

        # Find all document links (pattern: __P*.HTM)
        doc_links = soup.find_all('a', href=lambda href: href and '__P' in href and href.endswith('.HTM'))

        LOGGER.info("Found %d potential document links", len(doc_links))

        for link in doc_links:
            href = link['href']
            # Make absolute URL
            doc_url = urljoin(catechism_index_url, href)

            # Extract title from link text
            link_text = link.get_text().strip()

            # Skip if this looks like navigation or non-content link
            if not link_text or len(link_text) > 150:
                continue

            # Create document
            doc = VaticanDocument(
                url=doc_url,
                title=f"Catechism - {link_text}",
                section="CATECHISM",
                document_type="Catechism",
                language="en"
            )
            documents.append(doc)

        LOGGER.info("Extracted %d Catechism documents", len(documents))
        return documents

    def scrape_canon_law_section(self) -> List[VaticanDocument]:
        """
        Scrape the Canon Law (Code of Canon Law) section specifically.

        The Vatican Canon Law has a specific structure:
        - English Canon Law index: /archive/cod-iuris-canonici/cic_index_en.html
        - Document links pattern: cic_lib[#]-cann[#-#]_en.html

        Returns:
            List of Canon Law documents
        """
        canon_law_index_url = "https://www.vatican.va/archive/cod-iuris-canonici/cic_index_en.html"
        documents = []

        LOGGER.info("Scraping English Canon Law from: %s", canon_law_index_url)

        # Fetch Canon Law index
        soup = self._fetch_and_parse(canon_law_index_url)
        if not soup:
            LOGGER.error("Failed to fetch Canon Law index")
            return documents

        # Find all document links that match the English Canon Law pattern
        # Pattern: /archive/cod-iuris-canonici/eng/documents/cic_*_en.html
        doc_links = soup.find_all('a', href=lambda href:
            href and
            'cod-iuris-canonici' in href and
            'cic_' in href and
            '_en.html' in href
        )

        LOGGER.info("Found %d potential Canon Law document links", len(doc_links))

        seen_urls = set()
        for link in doc_links:
            href = link['href']

            # Remove anchor fragments (e.g., #TITLE_I.)
            base_href = href.split('#')[0]

            # Make absolute URL
            doc_url = urljoin(canon_law_index_url, base_href)

            # Skip duplicates
            if doc_url in seen_urls:
                continue
            seen_urls.add(doc_url)

            # Extract title from link text
            link_text = link.get_text().strip()

            # Skip if this looks like navigation or non-content link
            if not link_text or len(link_text) > 200:
                continue

            # Create document
            doc = VaticanDocument(
                url=doc_url,
                title=f"Canon Law - {link_text}",
                section="CANON_LAW",
                document_type="Canon Law",
                language="en"
            )
            documents.append(doc)

        LOGGER.info("Extracted %d Canon Law documents", len(documents))
        return documents

    def scrape_councils_section(self) -> List[VaticanDocument]:
        """
        Scrape the Ecumenical Councils section specifically.

        The Vatican Councils archive has:
        - Vatican I: /archive/hist_councils/i-vatican-council/
        - Vatican II: /archive/hist_councils/ii_vatican_council/
        - Document pattern: vat-[i|ii]_[type]_[date]_[name]_en.html

        Returns:
            List of Council documents
        """
        documents = []

        # Vatican II (more documents)
        vat2_index_url = "https://www.vatican.va/archive/hist_councils/ii_vatican_council/index.htm"
        LOGGER.info("Scraping Vatican II from: %s", vat2_index_url)

        soup = self._fetch_and_parse(vat2_index_url)
        if soup:
            # Find all links matching Vatican II English pattern
            doc_links = soup.find_all('a', href=lambda href:
                href and
                'vat-ii_' in href and
                '_en.html' in href
            )

            LOGGER.info("Found %d Vatican II document links", len(doc_links))

            for link in doc_links:
                href = link['href']
                doc_url = urljoin(vat2_index_url, href)
                link_text = link.get_text().strip()

                if link_text and len(link_text) < 200:
                    doc = VaticanDocument(
                        url=doc_url,
                        title=f"Vatican II - {link_text}",
                        section="COUNCILS",
                        document_type="Council Document",
                        language="en"
                    )
                    documents.append(doc)

        # Vatican I
        vat1_index_url = "https://www.vatican.va/archive/hist_councils/i-vatican-council/index.htm"
        LOGGER.info("Scraping Vatican I from: %s", vat1_index_url)

        soup = self._fetch_and_parse(vat1_index_url)
        if soup:
            # Find all links matching Vatican I English pattern
            doc_links = soup.find_all('a', href=lambda href:
                href and
                'vat-i_' in href and
                '_en.html' in href
            )

            LOGGER.info("Found %d Vatican I document links", len(doc_links))

            for link in doc_links:
                href = link['href']
                doc_url = urljoin(vat1_index_url, href)
                link_text = link.get_text().strip()

                if link_text and len(link_text) < 200:
                    doc = VaticanDocument(
                        url=doc_url,
                        title=f"Vatican I - {link_text}",
                        section="COUNCILS",
                        document_type="Council Document",
                        language="en"
                    )
                    documents.append(doc)

        LOGGER.info("Extracted %d Council documents total", len(documents))
        return documents

    def scrape_magisterium_section(self) -> List[VaticanDocument]:
        """
        Scrape papal magisterial documents from modern popes.

        Structure: /content/[pope-slug]/en/[doc-type].index.html
        - Popes: francesco, benedict-xvi, john-paul-ii, john-paul-i, paul-vi, etc.
        - Document types: encyclicals, apost_exhortations, apost_letters,
                         apost_constitutions, motu_proprio, bulls

        Returns:
            List of papal magisterial documents
        """
        documents = []

        # Focus on popes with substantial magisterial documents (20th-21st century)
        popes = [
            ("francesco", "Francis"),
            ("benedict-xvi", "Benedict XVI"),
            ("john-paul-ii", "John Paul II"),
            ("john-paul-i", "John Paul I"),
            ("paul-vi", "Paul VI"),
            ("john-xxiii", "John XXIII"),
            ("pius-xii", "Pius XII"),
            ("pius-xi", "Pius XI"),
            ("benedict-xv", "Benedict XV"),
            ("pius-x", "Pius X"),
            ("leo-xiii", "Leo XIII"),
        ]

        # Major magisterial document types
        doc_types = [
            ("encyclicals", "Encyclical"),
            ("apost_exhortations", "Apostolic Exhortation"),
            ("apost_letters", "Apostolic Letter"),
            ("apost_constitutions", "Apostolic Constitution"),
            ("motu_proprio", "Motu Proprio"),
            ("bulls", "Papal Bull"),
        ]

        for pope_slug, pope_name in popes:
            for doc_type_slug, doc_type_name in doc_types:
                index_url = f"https://www.vatican.va/content/{pope_slug}/en/{doc_type_slug}.index.html"

                LOGGER.debug("Checking %s - %s: %s", pope_name, doc_type_name, index_url)

                soup = self._fetch_and_parse(index_url)
                if not soup:
                    continue

                # Find all document links in the documents/ subdirectory (English only)
                doc_links = soup.find_all('a', href=lambda href:
                    href and
                    '/documents/' in href and
                    href.endswith('.html') and
                    '/en/' in href and  # English-only filter
                    'biography' not in href.lower() and  # Exclude biographies
                    'index' not in href.lower()  # Exclude index pages
                )

                if not doc_links:
                    LOGGER.debug("No documents found for %s - %s", pope_name, doc_type_name)
                    continue

                LOGGER.info("Found %d documents for %s - %s", len(doc_links), pope_name, doc_type_name)

                seen_urls = set()
                for link in doc_links:
                    href = link['href']
                    doc_url = urljoin(index_url, href)

                    # Skip duplicates
                    if doc_url in seen_urls:
                        continue
                    seen_urls.add(doc_url)

                    # Extract title from link text
                    link_text = link.get_text().strip()
                    if not link_text or len(link_text) > 250:
                        # Try to extract from URL if link text is bad
                        import re
                        url_match = re.search(r'/([^/]+)\.html$', doc_url)
                        if url_match:
                            link_text = url_match.group(1).replace('-', ' ').replace('_', ' ').title()
                        else:
                            link_text = "Untitled Document"

                    doc = VaticanDocument(
                        url=doc_url,
                        title=f"{pope_name} - {link_text}",
                        section="MAGISTERIUM",
                        document_type=doc_type_name,
                        language="en"
                    )
                    documents.append(doc)

        # Also scrape Roman Curia documents (Dicastery for Doctrine of the Faith)
        LOGGER.info("Scraping Roman Curia documents...")
        curia_docs = self._scrape_curia_documents()
        documents.extend(curia_docs)

        LOGGER.info("Extracted %d Magisterium documents total (papal + curia)", len(documents))
        return documents

    def _scrape_curia_documents(self) -> List[VaticanDocument]:
        """
        Scrape Roman Curia documents (Dicasteries/Congregations).

        Currently scrapes:
        - Dicastery for the Doctrine of the Faith
          Index: /roman_curia/congregations/cfaith/doc_doc_index.htm
          Pattern: /roman_curia/congregations/cfaith/documents/rc_*_doc_*_en.html
        - Congregation for Divine Worship and the Discipline of the Sacraments
          Index: /roman_curia/congregations/ccdds/index_en.htm
          Pattern: /documents/rc_con_ccdds_doc_*_en.html

        Returns:
            List of Roman Curia documents
        """
        documents = []

        # Dicastery for the Doctrine of the Faith
        ddf_index_url = "https://www.vatican.va/roman_curia/congregations/cfaith/doc_doc_index.htm"
        LOGGER.info("Scraping Dicastery for Doctrine of the Faith: %s", ddf_index_url)

        soup = self._fetch_and_parse(ddf_index_url)
        if soup:
            # Find all English document links in the /documents/ subdirectory
            doc_links = soup.find_all('a', href=lambda href:
                href and
                '/documents/' in href and
                href.endswith('_en.html') and  # English-only
                'rc_' in href  # Roman Curia document pattern
            )

            LOGGER.info("Found %d Doctrine of the Faith documents", len(doc_links))

            seen_urls = set()
            for link in doc_links:
                href = link['href']
                doc_url = urljoin(ddf_index_url, href)

                # Skip duplicates
                if doc_url in seen_urls:
                    continue
                seen_urls.add(doc_url)

                # Extract title from link text
                link_text = link.get_text().strip()
                if not link_text or len(link_text) > 250:
                    # Try to extract from URL if link text is bad
                    import re
                    url_match = re.search(r'_([^_/]+)_en\.html$', doc_url)
                    if url_match:
                        link_text = url_match.group(1).replace('-', ' ').title()
                    else:
                        link_text = "Untitled Document"

                doc = VaticanDocument(
                    url=doc_url,
                    title=f"DDF - {link_text}",
                    section="MAGISTERIUM",
                    document_type="Dicastery Document",
                    language="en"
                )
                documents.append(doc)

        # Congregation for Divine Worship and the Discipline of the Sacraments
        ccdds_index_url = "https://www.vatican.va/roman_curia/congregations/ccdds/index_en.htm"
        LOGGER.info("Scraping Congregation for Divine Worship: %s", ccdds_index_url)

        soup = self._fetch_and_parse(ccdds_index_url)
        if soup:
            # Find all English document links in the /documents/ subdirectory
            doc_links = soup.find_all('a', href=lambda href:
                href and
                '/documents/' in href and
                href.endswith('_en.html') and  # English-only
                'rc_con_ccdds_doc_' in href  # Divine Worship document pattern
            )

            LOGGER.info("Found %d Divine Worship documents", len(doc_links))

            seen_urls = set()
            for link in doc_links:
                href = link['href']
                doc_url = urljoin(ccdds_index_url, href)

                # Skip duplicates
                if doc_url in seen_urls:
                    continue
                seen_urls.add(doc_url)

                # Extract title from link text
                link_text = link.get_text().strip()
                if not link_text or len(link_text) > 250:
                    # Try to extract from URL if link text is bad
                    import re
                    url_match = re.search(r'_([^_/]+)_en\.html$', doc_url)
                    if url_match:
                        link_text = url_match.group(1).replace('-', ' ').title()
                    else:
                        link_text = "Untitled Document"

                doc = VaticanDocument(
                    url=doc_url,
                    title=f"Divine Worship - {link_text}",
                    section="MAGISTERIUM",
                    document_type="Dicastery Document",
                    language="en"
                )
                documents.append(doc)

        LOGGER.info("Extracted %d Roman Curia documents total", len(documents))
        return documents

    def scrape_social_section(self) -> List[VaticanDocument]:
        """
        Scrape the Social Doctrine section.

        The Vatican archive's SOCIAL section primarily contains:
        - Compendium of the Social Doctrine of the Church (2004)

        Social encyclicals (Rerum Novarum, Laborem Exercens, etc.) are
        already covered in the MAGISTERIUM section as papal encyclicals.

        URL: /roman_curia/pontifical_councils/justpeace/documents/rc_pc_justpeace_doc_20060526_compendio-dott-soc_en.html

        Returns:
            List of Social Doctrine documents
        """
        documents = []

        # The main Compendium document
        compendium_url = "https://www.vatican.va/roman_curia/pontifical_councils/justpeace/documents/rc_pc_justpeace_doc_20060526_compendio-dott-soc_en.html"

        LOGGER.info("Scraping Social Doctrine Compendium: %s", compendium_url)

        # Verify the document exists
        soup = self._fetch_and_parse(compendium_url)
        if soup:
            doc = VaticanDocument(
                url=compendium_url,
                title="Compendium of the Social Doctrine of the Church",
                section="SOCIAL",
                document_type="Compendium",
                language="en"
            )
            documents.append(doc)
            LOGGER.info("Found Compendium of Social Doctrine")

        LOGGER.info("Extracted %d Social Doctrine documents total", len(documents))
        return documents

    def scrape_section(self, section: Section, max_depth: int = 3) -> List[VaticanDocument]:
        """
        Recursively scrape a section for document URLs.

        Args:
            section: Section to scrape
            max_depth: Maximum link depth to follow

        Returns:
            List of discovered documents
        """
        documents = []
        to_visit = [(section.url, 0)]  # (url, depth)
        visited = set()

        while to_visit:
            url, depth = to_visit.pop(0)

            # Skip if already visited or max depth exceeded
            if url in visited or depth > max_depth:
                continue

            visited.add(url)

            # Fetch page
            soup = self._fetch_and_parse(url)
            if not soup:
                continue

            # Check if this is a document page
            if self.is_document_page(soup, url):
                # Check if it's English
                if self.is_english_document(url, soup):
                    doc = self._extract_document_metadata(url, soup, section)
                    if doc:
                        documents.append(doc)

            # Find links to follow
            for link in soup.find_all('a', href=True):
                next_url = urljoin(url, link['href'])

                # Only follow Vatican URLs
                if 'vatican.va' in next_url and next_url not in visited:
                    # Add HTML links to visit queue
                    if next_url.endswith(('.htm', '.html')) or '/ENG' in next_url:
                        to_visit.append((next_url, depth + 1))

        return documents

    def is_document_page(self, soup: BeautifulSoup, url: str) -> bool:
        """
        Determine if page is a document (vs index/navigation page).

        Args:
            soup: BeautifulSoup of page
            url: Page URL

        Returns:
            True if document page, False if index/navigation
        """
        # Documents typically have substantial text content
        paragraphs = soup.find_all('p')
        if len(paragraphs) < 3:
            return False

        # Check for document content indicators
        text = soup.get_text()
        word_count = len(text.split())

        # Documents typically have >100 words (lowered threshold for short documents)
        if word_count < 100:
            return False

        # Index pages often have lots of links, few paragraphs
        links = soup.find_all('a')
        if len(links) > len(paragraphs) * 3:
            return False

        return True

    def is_english_document(self, url: str, soup: BeautifulSoup) -> bool:
        """
        Determine if document is in English using multi-strategy detection.

        Args:
            url: Document URL
            soup: BeautifulSoup of page

        Returns:
            True if English, False otherwise
        """
        # Strategy 1: URL pattern matching
        if self._is_english_url(url):
            return True

        # Strategy 2: HTML lang attribute
        html_tag = soup.find('html')
        if html_tag:
            lang = html_tag.get('lang', '').lower()
            if lang.startswith('en'):
                return True
            elif lang and not lang.startswith('en'):
                # Explicitly non-English language attribute
                return False

        # Strategy 3: Meta tags
        meta_lang = soup.find('meta', attrs={'http-equiv': 'content-language'})
        if meta_lang and 'en' in meta_lang.get('content', '').lower():
            return True

        meta_lang_alt = soup.find('meta', attrs={'name': 'language'})
        if meta_lang_alt and 'en' in meta_lang_alt.get('content', '').lower():
            return True

        # Strategy 4: Check for English indicators in title or headers
        title = soup.find('title')
        if title:
            title_text = title.get_text().lower()
            if any(indicator in title_text for indicator in [
                'english', 'new american bible', 'catechism'
            ]):
                return True

        # Strategy 5: Language selection links (exclude if non-English is default)
        # Look for language indicators showing this is NOT English
        lang_links = soup.find_all('a', href=True)
        for link in lang_links:
            href = link['href'].lower()
            text = link.get_text().lower()
            # If we see links to English version, this is probably NOT English
            if '_en.htm' in href or 'english' in text:
                # But check if current URL is the English version
                if '_en.htm' in url.lower() or '/eng' in url.upper():
                    return True
                else:
                    return False

        # Default: if URL or content doesn't clearly indicate language, be conservative
        return False

    def _is_english_url(self, url: str) -> bool:
        """
        Check if URL indicates English document.

        Args:
            url: Document URL

        Returns:
            True if URL pattern indicates English
        """
        url_lower = url.lower()
        url_upper = url.upper()

        # Common English URL patterns in Vatican archive
        patterns = [
            r'/ENG\d+/',  # /ENG0015/ pattern
            r'_en\.html?$',  # ends with _en.html or _en.htm
            r'/en/',  # /en/ in path
            r'/english/',  # /english/ in path
        ]

        for pattern in patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True

        return False

    def _extract_document_metadata(self,
                                   url: str,
                                   soup: BeautifulSoup,
                                   section: Section) -> Optional[VaticanDocument]:
        """
        Extract metadata from document page.

        Args:
            url: Document URL
            soup: BeautifulSoup of page
            section: Parent section

        Returns:
            VaticanDocument if metadata extracted, None otherwise
        """
        # Extract title
        title = "Untitled"
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()
        else:
            # Try h1 as fallback
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text().strip()

        # Clean title
        title = title.replace('\n', ' ').replace('\r', ' ')
        title = re.sub(r'\s+', ' ', title).strip()

        # Infer document type
        document_type = self._infer_document_type(title, soup)

        # Create document
        doc = VaticanDocument(
            url=url,
            title=title,
            section=section.name,
            document_type=document_type,
            language="en",
        )

        return doc

    def _infer_document_type(self, title: str, soup: BeautifulSoup) -> str:
        """
        Infer document type from title and content.

        Args:
            title: Document title
            soup: BeautifulSoup of page

        Returns:
            Document type string
        """
        title_lower = title.lower()

        # Check title for document type keywords
        type_patterns = {
            'Encyclical': r'encyclical',
            'Apostolic Letter': r'apostolic letter',
            'Apostolic Exhortation': r'apostolic exhortation',
            'Apostolic Constitution': r'apostolic constitution',
            'Motu Proprio': r'motu proprio',
            'Bull': r'bull',
            'Decree': r'decree',
            'Declaration': r'declaration',
            'Instruction': r'instruction',
            'Catechism': r'catechism',
            'Compendium': r'compendium',
            'Canon Law': r'canon law|code',
            'Constitution': r'constitution',
            'Scripture': r'bible|genesis|exodus|matthew|john',
        }

        for doc_type, pattern in type_patterns.items():
            if re.search(pattern, title_lower):
                return doc_type

        return "Document"

    def _fetch_and_parse(self, url: str) -> Optional[BeautifulSoup]:
        """
        Fetch URL and parse with BeautifulSoup.

        Implements rate limiting and error handling.

        Args:
            url: URL to fetch

        Returns:
            BeautifulSoup object if successful, None otherwise
        """
        # Respect rate limit
        self._respect_rate_limit()

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            return soup

        except requests.RequestException as e:
            LOGGER.warning("Failed to fetch %s: %s", url, e)
            return None

    def _respect_rate_limit(self) -> None:
        """Ensure rate limit compliance by sleeping if needed."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            sleep_time = self.rate_limit - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()
