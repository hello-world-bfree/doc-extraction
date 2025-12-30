#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
R2 storage manager for uploading processed documents.

Manages uploads to Cloudflare R2 bucket with organized path structure.
"""

import logging
import re
from pathlib import Path
from typing import List, Optional

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

from .index import VaticanDocument

LOGGER = logging.getLogger("vatican.storage")


class R2StorageManager:
    """
    Manages uploads to S3-compatible storage (AWS S3 or Cloudflare R2).

    Uses boto3 S3 client. Works with:
    - AWS S3 (when endpoint_url is None)
    - Cloudflare R2 (when endpoint_url is provided)
    - Any S3-compatible storage

    Organizes documents by section and provides consistent path structure.
    """

    def __init__(self,
                 bucket_name: str,
                 access_key_id: str,
                 secret_access_key: str,
                 endpoint_url: Optional[str] = None,
                 region_name: str = 'us-east-1'):
        """
        Initialize S3-compatible storage manager.

        Args:
            bucket_name: S3/R2 bucket name
            access_key_id: AWS access key ID or R2 access key ID
            secret_access_key: AWS secret access key or R2 secret access key
            endpoint_url: Custom endpoint URL for R2 or S3-compatible storage
                         (e.g., https://[account-id].r2.cloudflarestorage.com)
                         Set to None for AWS S3 (uses default endpoint)
            region_name: AWS region (default: us-east-1). R2 uses 'auto'

        Raises:
            ImportError: If boto3 not installed
            ValueError: If credentials are invalid
        """
        if not BOTO3_AVAILABLE:
            raise ImportError(
                "boto3 is required for S3/R2 storage. "
                "Install with: uv pip install boto3"
            )

        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.is_r2 = endpoint_url is not None and 'r2.cloudflarestorage.com' in endpoint_url
        self.is_aws_s3 = endpoint_url is None

        # Determine region (R2 uses 'auto', AWS uses specified region)
        if self.is_r2:
            region_name = 'auto'

        # Initialize S3 client
        try:
            client_kwargs = {
                'aws_access_key_id': access_key_id,
                'aws_secret_access_key': secret_access_key,
                'region_name': region_name
            }

            # Add endpoint URL only if provided (for R2 or custom S3)
            if endpoint_url:
                client_kwargs['endpoint_url'] = endpoint_url

            self.s3_client = boto3.client('s3', **client_kwargs)

            # Verify credentials by checking if the bucket is accessible
            # Note: Using head_bucket instead of list_buckets to avoid requiring
            # the s3:ListAllMyBuckets permission
            try:
                self.s3_client.head_bucket(Bucket=bucket_name)
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code == '404':
                    LOGGER.warning("Bucket '%s' does not exist", bucket_name)
                elif error_code == '403':
                    LOGGER.warning("Access denied to bucket '%s' - will try to upload anyway", bucket_name)
                # Continue anyway - the actual upload will fail if there are permission issues

            storage_type = "R2" if self.is_r2 else ("AWS S3" if self.is_aws_s3 else "S3-compatible")
            LOGGER.info("%s storage initialized: bucket=%s, region=%s",
                       storage_type, bucket_name, region_name)
            if endpoint_url:
                LOGGER.info("Using custom endpoint: %s", endpoint_url)

        except ClientError as e:
            raise ValueError(f"Failed to initialize S3 client: {e}")

    def upload_document_outputs(self,
                                local_json: str,
                                local_ndjson: str,
                                doc: VaticanDocument) -> List[str]:
        """
        Upload JSON and NDJSON files to R2.

        Args:
            local_json: Path to local JSON file
            local_ndjson: Path to local NDJSON file
            doc: Document metadata

        Returns:
            List of R2 paths for uploaded files
        """
        uploaded_paths = []

        # Upload JSON
        json_r2_path = self.generate_r2_path(doc, ".json")
        if self._upload_file(local_json, json_r2_path):
            uploaded_paths.append(json_r2_path)

        # Upload NDJSON
        ndjson_r2_path = self.generate_r2_path(doc, ".ndjson")
        if self._upload_file(local_ndjson, ndjson_r2_path):
            uploaded_paths.append(ndjson_r2_path)

        LOGGER.info("Uploaded %d files for: %s", len(uploaded_paths), doc.title[:50])
        return uploaded_paths

    def upload_index(self, local_index_path: str) -> Optional[str]:
        """
        Upload master index to R2.

        Args:
            local_index_path: Path to local index JSON

        Returns:
            R2 path if successful, None otherwise
        """
        r2_path = "vatican/index.json"
        if self._upload_file(local_index_path, r2_path):
            LOGGER.info("Uploaded master index to R2: %s", r2_path)
            return r2_path
        return None

    def generate_r2_path(self, doc: VaticanDocument, suffix: str) -> str:
        """
        Generate organized R2 path for document.

        Structure:
        vatican/bible/genesis_chapter_01_abc123.json
        vatican/catechism/ccc_def456.json
        vatican/councils/lumen_gentium_ghi789.json

        Args:
            doc: Document metadata
            suffix: File suffix (.json or .ndjson)

        Returns:
            R2 path string
        """
        import hashlib

        # Base path
        base = "vatican"

        # Section subdirectory
        section_map = {
            "BIBLE": "bible",
            "CATECHISM": "catechism",
            "CANON_LAW": "canon_law",
            "COUNCILS": "councils",
            "MAGISTERIUM": "magisterium",
            "SOCIAL": "social_teaching"
        }
        section_dir = section_map.get(doc.section, "other")

        # For Bible documents, try to extract book/chapter from HTML
        if doc.section == "BIBLE" and doc.download_path:
            filename = self._generate_bible_filename(doc)
        # For Catechism documents, try to extract part/section/chapter from HTML
        elif doc.section == "CATECHISM" and doc.download_path:
            filename = self._generate_catechism_filename(doc)
        # For Canon Law documents, extract book and canon numbers from URL/title
        elif doc.section == "CANON_LAW":
            filename = self._generate_canon_law_filename(doc)
        # For Council documents, extract council and document info from URL
        elif doc.section == "COUNCILS":
            filename = self._generate_council_filename(doc)
        # For Magisterium documents, extract pope and document type from URL
        elif doc.section == "MAGISTERIUM":
            filename = self._generate_magisterium_filename(doc)
        # For Social documents (Compendium), use simple descriptive name
        elif doc.section == "SOCIAL":
            filename = "compendium_social_doctrine"
        else:
            # Generate clean filename from title
            filename = self._sanitize_filename(doc.title)

        # Add URL hash to ensure uniqueness (prevent overwrites from duplicate titles)
        url_hash = hashlib.md5(doc.url.encode()).hexdigest()[:8]
        filename = f"{filename}_{url_hash}"

        # Combine into path
        r2_path = f"{base}/{section_dir}/{filename}{suffix}"

        return r2_path

    def _generate_bible_filename(self, doc: VaticanDocument) -> str:
        """
        Generate structured filename for Bible documents from HTML metadata.

        Extracts book and chapter from <meta name="part"> tag like:
        "The Prophetic Books > Baruch > Chapter 3"

        Args:
            doc: Vatican document

        Returns:
            Filename like "baruch_chapter_03" or sanitized title if parsing fails
        """
        from pathlib import Path
        from bs4 import BeautifulSoup
        import re

        try:
            # Read HTML file
            html_path = Path(doc.download_path)
            if not html_path.exists():
                return self._sanitize_filename(doc.title)

            with open(html_path, 'rb') as f:
                soup = BeautifulSoup(f, 'html.parser')

            # Find meta tag with part information
            meta_part = soup.find('meta', {'name': 'part'})
            if not meta_part or not meta_part.get('content'):
                return self._sanitize_filename(doc.title)

            # Parse: "The Prophetic Books > Baruch > Chapter 3"
            part_content = meta_part['content']
            parts = [p.strip() for p in part_content.split('>')]

            if len(parts) >= 2:
                book = parts[-2]  # Second-to-last is book name
                chapter_info = parts[-1] if len(parts) >= 3 else ""

                # Sanitize book name
                book_clean = re.sub(r'[^\w\s-]', '', book.lower())
                book_clean = re.sub(r'[-\s]+', '_', book_clean)

                # Extract chapter number if present
                chapter_match = re.search(r'chapter\s+(\d+)', chapter_info, re.IGNORECASE)
                if chapter_match:
                    chapter_num = int(chapter_match.group(1))
                    return f"{book_clean}_chapter_{chapter_num:02d}"
                else:
                    return book_clean

            return self._sanitize_filename(doc.title)

        except Exception as e:
            LOGGER.warning("Failed to extract Bible metadata from %s: %s", doc.url, e)
            return self._sanitize_filename(doc.title)

    def _generate_catechism_filename(self, doc: VaticanDocument) -> str:
        """
        Generate structured filename for Catechism documents from HTML metadata.

        Extracts part/section/chapter from <meta name="part"> tag or breadcrumb navigation.
        Examples:
        - "Part One > Section One > Chapter One > Article 1"
        - "Part Two > The Celebration of the Paschal Mystery > The Sacramental Economy"

        Args:
            doc: Vatican document

        Returns:
            Filename like "part_1_section_1_chapter_1" or sanitized title if parsing fails
        """
        from pathlib import Path
        from bs4 import BeautifulSoup
        import re

        try:
            # Read HTML file
            html_path = Path(doc.download_path)
            if not html_path.exists():
                return self._sanitize_filename(doc.title)

            with open(html_path, 'rb') as f:
                soup = BeautifulSoup(f, 'html.parser')

            # Try to find meta tag with part information (like Bible)
            meta_part = soup.find('meta', {'name': 'part'})
            if meta_part and meta_part.get('content'):
                part_content = meta_part['content']
                parts = [p.strip() for p in part_content.split('>')]

                filename_parts = []

                # Extract part number
                part_match = re.search(r'part\s+(\w+)', ' '.join(parts), re.IGNORECASE)
                if part_match:
                    part_num = part_match.group(1).lower()
                    filename_parts.append(f"part_{part_num}")

                # Extract section number if present
                section_match = re.search(r'section\s+(\w+)', ' '.join(parts), re.IGNORECASE)
                if section_match:
                    section_num = section_match.group(1).lower()
                    filename_parts.append(f"section_{section_num}")

                # Extract chapter number if present
                chapter_match = re.search(r'chapter\s+(\w+)', ' '.join(parts), re.IGNORECASE)
                if chapter_match:
                    chapter_num = chapter_match.group(1).lower()
                    filename_parts.append(f"chapter_{chapter_num}")

                # Extract article number if present
                article_match = re.search(r'article\s+(\d+)', ' '.join(parts), re.IGNORECASE)
                if article_match:
                    article_num = article_match.group(1)
                    filename_parts.append(f"article_{article_num}")

                if filename_parts:
                    return '_'.join(filename_parts)

            # Fallback: try to extract from breadcrumb list items
            breadcrumbs = soup.find_all('li')
            if breadcrumbs:
                breadcrumb_text = ' > '.join(li.get_text().strip() for li in breadcrumbs)

                # Try to extract structured parts
                filename_parts = []
                part_match = re.search(r'part\s+(\w+)', breadcrumb_text, re.IGNORECASE)
                if part_match:
                    filename_parts.append(f"part_{part_match.group(1).lower()}")

                section_match = re.search(r'section\s+(\w+)', breadcrumb_text, re.IGNORECASE)
                if section_match:
                    filename_parts.append(f"section_{section_match.group(1).lower()}")

                if filename_parts:
                    return '_'.join(filename_parts)

            return self._sanitize_filename(doc.title)

        except Exception as e:
            LOGGER.warning("Failed to extract Catechism metadata from %s: %s", doc.url, e)
            return self._sanitize_filename(doc.title)

    def _generate_canon_law_filename(self, doc: VaticanDocument) -> str:
        """
        Generate structured filename for Canon Law documents from URL.

        Canon Law URLs follow pattern:
        /archive/cod-iuris-canonici/eng/documents/cic_lib[#]-cann[#-#]_en.html

        Examples:
        - cic_lib1-cann1-6_en.html → book_1_canons_1_6
        - cic_lib4-cann834-878_en.html → book_4_canons_834_878

        Args:
            doc: Vatican document

        Returns:
            Filename like "book_1_canons_1_6" or sanitized title if parsing fails
        """
        import re

        try:
            # Extract from URL: cic_lib1-cann1-6_en.html
            url_match = re.search(r'cic_lib(\d+)-cann([\d-]+)_en\.html', doc.url)
            if url_match:
                book_num = url_match.group(1)
                canon_range = url_match.group(2).replace('-', '_')
                return f"book_{book_num}_canons_{canon_range}"

            # Fallback: try to extract from title
            # "Canon Law - BOOK I. GENERAL NORMS (Cann. 1 - 6)"
            title_match = re.search(r'book\s+([ivxlcdm]+).*cann?\.\s*([\d\s-]+)', doc.title, re.IGNORECASE)
            if title_match:
                book_roman = title_match.group(1).lower()
                canon_numbers = title_match.group(2).strip().replace(' ', '').replace('-', '_')
                return f"book_{book_roman}_canons_{canon_numbers}"

            return self._sanitize_filename(doc.title)

        except Exception as e:
            LOGGER.warning("Failed to extract Canon Law metadata from %s: %s", doc.url, e)
            return self._sanitize_filename(doc.title)

    def _generate_council_filename(self, doc: VaticanDocument) -> str:
        """
        Generate structured filename for Council documents from URL.

        Council URLs follow pattern:
        vat-[i|ii]_[type]_[date]_[name]_en.html

        Examples:
        - vat-ii_const_19651118_dei-verbum_en.html → vatican_ii_const_dei_verbum
        - vat-i_const_18700424_dei-filius_en.html → vatican_i_const_dei_filius

        Args:
            doc: Vatican document

        Returns:
            Filename like "vatican_ii_const_dei_verbum" or sanitized title if parsing fails
        """
        import re

        try:
            # Extract from URL: vat-ii_const_19651118_dei-verbum_en.html
            url_match = re.search(r'vat-(i+)_(const|decl|decree)_\d+_([a-z-]+)_en\.html', doc.url)
            if url_match:
                council = url_match.group(1)  # i or ii
                doc_type = url_match.group(2)  # const, decl, decree
                doc_name = url_match.group(3).replace('-', '_')
                return f"vatican_{council}_{doc_type}_{doc_name}"

            # Fallback: sanitize title
            return self._sanitize_filename(doc.title)

        except Exception as e:
            LOGGER.warning("Failed to extract Council metadata from %s: %s", doc.url, e)
            return self._sanitize_filename(doc.title)

    def _generate_magisterium_filename(self, doc: VaticanDocument) -> str:
        """
        Generate structured filename for Magisterium documents from URL.

        Two patterns:
        1. Papal documents: /content/[pope-slug]/en/[doc-type]/documents/[prefix]_[date]_[title-slug].html
        2. Roman Curia documents: /roman_curia/congregations/cfaith/documents/rc_[code]_doc_[date]_[title]_en.html

        Examples:
        - hf_ben-xvi_enc_20051225_deus-caritas-est.html → benedict_xvi_enc_deus_caritas_est
        - papa-francesco_20201003_enciclica-fratelli-tutti.html → francis_enc_fratelli_tutti
        - rc_ddf_doc_20250128_antiqua-et-nova_en.html → ddf_antiqua_et_nova

        Args:
            doc: Vatican document

        Returns:
            Filename like "francis_enc_laudato_si" or sanitized title if parsing fails
        """
        import re

        try:
            # Check if this is a Roman Curia document
            if '/roman_curia/' in doc.url:
                # Pattern 1: rc_[dicastery]_doc_[date]_[title]_en.html (e.g., DDF)
                # Pattern 2: rc_con_[dicastery]_doc_[date]_[title]_en.html (e.g., Divine Worship)
                curia_match = re.search(r'rc_(?:con_)?([a-z]+)_doc_\d{8}_([a-z-]+)_en\.html', doc.url)
                if curia_match:
                    dicastery_code = curia_match.group(1)  # e.g., "ddf" or "ccdds"
                    title_slug = curia_match.group(2).replace('-', '_')
                    return f"{dicastery_code}_{title_slug}"
                else:
                    # Fallback: sanitize title
                    return self._sanitize_filename(doc.title)

            # Extract pope slug from URL path (papal documents)
            pope_match = re.search(r'/content/([^/]+)/en/', doc.url)
            if not pope_match:
                return self._sanitize_filename(doc.title)

            pope_slug = pope_match.group(1)

            # Normalize pope name for filename
            pope_map = {
                'francesco': 'francis',
                'benedict-xvi': 'benedict_xvi',
                'john-paul-ii': 'john_paul_ii',
                'john-paul-i': 'john_paul_i',
                'paul-vi': 'paul_vi',
                'john-xxiii': 'john_xxiii',
                'pius-xii': 'pius_xii',
                'pius-xi': 'pius_xi',
                'benedict-xv': 'benedict_xv',
                'pius-x': 'pius_x',
                'leo-xiii': 'leo_xiii',
            }
            pope_name = pope_map.get(pope_slug, pope_slug.replace('-', '_'))

            # Extract document type abbreviation from URL or doc.document_type
            doc_type_abbrev = ''
            if 'encyclical' in doc.url.lower() or doc.document_type == 'Encyclical':
                doc_type_abbrev = 'enc'
            elif 'apost_exhortation' in doc.url or doc.document_type == 'Apostolic Exhortation':
                doc_type_abbrev = 'apost_exh'
            elif 'apost_letter' in doc.url or doc.document_type == 'Apostolic Letter':
                doc_type_abbrev = 'apost_letter'
            elif 'apost_constitution' in doc.url or doc.document_type == 'Apostolic Constitution':
                doc_type_abbrev = 'apost_const'
            elif 'motu_proprio' in doc.url or doc.document_type == 'Motu Proprio':
                doc_type_abbrev = 'motu_proprio'
            elif 'bull' in doc.url.lower() or doc.document_type == 'Papal Bull':
                doc_type_abbrev = 'bull'

            # Extract document title slug from filename
            # Pattern: [prefix]_[date]_[title-slug].html
            # Examples:
            # - hf_ben-xvi_enc_20051225_deus-caritas-est.html
            # - papa-francesco_20201003_enciclica-fratelli-tutti.html
            filename_match = re.search(r'/([^/]+)\.html$', doc.url)
            if filename_match:
                filename_part = filename_match.group(1)

                # Try to extract title portion (after date or after second underscore)
                # Pattern 1: prefix_date_title
                title_match = re.search(r'_(\d{8})_(.+)$', filename_part)
                if title_match:
                    title_slug = title_match.group(2).replace('-', '_')
                else:
                    # Pattern 2: prefix_date_word_title (e.g., papa-francesco_20201003_enciclica-fratelli-tutti)
                    parts = filename_part.split('_')
                    if len(parts) >= 3:
                        # Take last part as title (after removing date and type indicators)
                        title_slug = parts[-1].replace('-', '_')
                    else:
                        title_slug = filename_part.replace('-', '_')

                # Build final filename
                if doc_type_abbrev:
                    return f"{pope_name}_{doc_type_abbrev}_{title_slug}"
                else:
                    return f"{pope_name}_{title_slug}"

            # Fallback: sanitize title
            return self._sanitize_filename(doc.title)

        except Exception as e:
            LOGGER.warning("Failed to extract Magisterium metadata from %s: %s", doc.url, e)
            return self._sanitize_filename(doc.title)

    def _sanitize_filename(self, title: str, max_length: int = 100) -> str:
        """
        Sanitize title for use as filename.

        Args:
            title: Document title
            max_length: Maximum filename length

        Returns:
            Sanitized filename (without extension)
        """
        # Convert to lowercase
        filename = title.lower()

        # Remove special characters
        filename = re.sub(r'[^\w\s-]', '', filename)

        # Replace spaces and repeated hyphens with single underscore
        filename = re.sub(r'[-\s]+', '_', filename)

        # Trim to max length
        filename = filename[:max_length].strip('_')

        # Ensure non-empty
        if not filename:
            filename = "untitled"

        return filename

    def _upload_file(self, local_path: str, r2_path: str) -> bool:
        """
        Upload a single file to R2.

        Args:
            local_path: Local file path
            r2_path: R2 destination path

        Returns:
            True if successful, False otherwise
        """
        local_file = Path(local_path)
        if not local_file.exists():
            LOGGER.error("Local file not found: %s", local_path)
            return False

        try:
            # Determine content type
            content_type = "application/json"  # Both .json and .ndjson
            if local_path.endswith('.ndjson'):
                content_type = "application/x-ndjson"

            # Upload
            self.s3_client.upload_file(
                str(local_file),
                self.bucket_name,
                r2_path,
                ExtraArgs={
                    'ContentType': content_type,
                    'CacheControl': 'public, max-age=31536000',  # 1 year cache
                }
            )

            LOGGER.debug("Uploaded: %s -> s3://%s/%s",
                        local_file.name, self.bucket_name, r2_path)
            return True

        except ClientError as e:
            LOGGER.error("Failed to upload %s: %s", local_path, e)
            return False

    def file_exists(self, r2_path: str) -> bool:
        """
        Check if file exists in R2.

        Args:
            r2_path: R2 file path

        Returns:
            True if exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=r2_path)
            return True
        except ClientError:
            return False

    def list_files(self, prefix: str = "vatican/") -> List[str]:
        """
        List files in R2 with given prefix.

        Args:
            prefix: Path prefix to filter

        Returns:
            List of R2 paths
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )

            if 'Contents' not in response:
                return []

            return [obj['Key'] for obj in response['Contents']]

        except ClientError as e:
            LOGGER.error("Failed to list files: %s", e)
            return []

    def get_storage_stats(self) -> dict:
        """
        Get storage statistics for Vatican documents.

        Returns:
            Dictionary with storage statistics
        """
        try:
            # List all Vatican files
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix="vatican/"
            )

            if 'Contents' not in response:
                return {
                    "total_files": 0,
                    "total_size_mb": 0,
                    "by_section": {}
                }

            # Aggregate stats
            total_files = 0
            total_size = 0
            by_section = {}

            for obj in response['Contents']:
                key = obj['Key']
                size = obj['Size']

                total_files += 1
                total_size += size

                # Extract section from path (vatican/section/...)
                parts = key.split('/')
                if len(parts) >= 2:
                    section = parts[1]
                    if section not in by_section:
                        by_section[section] = {"files": 0, "size_mb": 0}
                    by_section[section]["files"] += 1
                    by_section[section]["size_mb"] += size / 1024 / 1024

            return {
                "total_files": total_files,
                "total_size_mb": total_size / 1024 / 1024,
                "by_section": by_section
            }

        except ClientError as e:
            LOGGER.error("Failed to get storage stats: %s", e)
            return {
                "total_files": 0,
                "total_size_mb": 0,
                "by_section": {},
                "error": str(e)
            }
