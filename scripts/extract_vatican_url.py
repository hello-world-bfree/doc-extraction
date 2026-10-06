#!/usr/bin/env python3
"""Fetch a Vatican HTML doc and extract it via doc-extraction."""

import json
import sys
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

from extraction.analyzers import CatholicAnalyzer
from extraction.extractors.html import HtmlExtractor


DEFAULT_URL = (
    "https://www.vatican.va/content/leo-xiv/en/encyclicals/documents/"
    "20260515-magnifica-humanitas.html"
)


def fetch(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "doc-extraction/1.0"})
    with urlopen(req, timeout=30) as resp:
        return resp.read()


def extract(url: str, out_path: Path) -> dict:
    html_bytes = fetch(url)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
        tmp.write(html_bytes)
        tmp_path = tmp.name

    try:
        ex = HtmlExtractor(tmp_path, analyzer=CatholicAnalyzer())
        ex.load()
        ex.parse()
        ex.extract_metadata()
        data = ex.get_output_data()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    data["provenance"] = {**data.get("provenance", {}), "source_url": url}

    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("vatican_extract.json")

    data = extract(url, out_path)
    chunks = data.get("chunks", [])
    meta = data.get("metadata", {})
    print(f"URL: {url}")
    print(f"Title: {meta.get('title', '?')}")
    print(f"Chunks: {len(chunks)}")
    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
