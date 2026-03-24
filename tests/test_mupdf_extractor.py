import ctypes
import json
import pytest
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "sample_pdfs"
PHOTON_PDF = FIXTURES / "sigmod_photon.pdf"
REDBOOK_PDF = FIXTURES / "redbook-5th-edition.pdf"

try:
    from extraction._native.mupdf._bindings import get_lib
    from extraction._native.mupdf import MuPdfDocument, MuPdfPage, SpanData, OutlineEntry
    from extraction.extractors.pdf_mupdf import MuPdfPdfExtractor
    from extraction.extractors.configs import MuPdfPdfExtractorConfig
    from extraction.analyzers.generic import GenericAnalyzer
    get_lib()
    SKIP = False
except Exception:
    SKIP = True

pytestmark = pytest.mark.skipif(SKIP, reason="MuPDF native library not available")


class TestAbiValidation:

    def test_abi_version(self):
        lib = get_lib()
        assert lib.de_abi_version() == 1

    def test_struct_sizes_match(self):
        from extraction._native.mupdf._types import DeTextSpan, DeTextBlock, DeOutlineEntry, DeImageInfo
        lib = get_lib()
        assert ctypes.sizeof(DeTextSpan) == lib.de_sizeof_span()
        assert ctypes.sizeof(DeTextBlock) == lib.de_sizeof_block()
        assert ctypes.sizeof(DeOutlineEntry) == lib.de_sizeof_outline_entry()
        assert ctypes.sizeof(DeImageInfo) == lib.de_sizeof_image_info()


class TestContextLifecycle:

    def test_init_destroy(self):
        lib = get_lib()
        ctx = lib.de_init(0)
        assert ctx
        lib.de_destroy(ctx)

    def test_init_with_memory_limit(self):
        lib = get_lib()
        ctx = lib.de_init(100 * 1024 * 1024)
        assert ctx
        lib.de_destroy(ctx)


class TestHandleValidation:

    def test_null_context(self):
        lib = get_lib()
        result = lib.de_open_document(None, b"test.pdf")
        assert result is None

    def test_null_document(self):
        lib = get_lib()
        assert lib.de_page_count(None) < 0

    def test_invalid_path(self):
        with pytest.raises(FileNotFoundError):
            with MuPdfDocument("/nonexistent/path.pdf") as doc:
                pass

    def test_double_close_safe(self):
        with MuPdfDocument(str(PHOTON_PDF)) as doc:
            pass
        doc.close()


class TestPhotonPdf:

    @pytest.fixture
    def doc(self):
        d = MuPdfDocument(str(PHOTON_PDF))
        d.open()
        yield d
        d.close()

    def test_page_count(self, doc):
        assert doc.page_count == 14

    def test_metadata_title(self, doc):
        title = doc.get_metadata("info:Title")
        assert title and "Photon" in title

    def test_outline_present(self, doc):
        outline = doc.get_outline()
        assert len(outline) > 10
        assert all(isinstance(e, OutlineEntry) for e in outline)
        titles = [e.title for e in outline]
        assert any("Introduction" in t for t in titles)

    def test_page_dimensions(self, doc):
        with doc.load_page(0) as page:
            assert 500 < page.width < 700
            assert 700 < page.height < 900

    def test_span_extraction(self, doc):
        with doc.load_page(0) as page:
            spans = page.get_all_spans()
            assert len(spans) > 50
            assert all(isinstance(s, SpanData) for s in spans)

    def test_span_has_font_info(self, doc):
        with doc.load_page(0) as page:
            spans = page.get_all_spans()
            title_span = spans[0]
            assert title_span.font_size > 14
            assert title_span.is_bold
            assert len(title_span.font_name) > 0
            assert len(title_span.text) > 0

    def test_span_text_survives_page_close(self, doc):
        with doc.load_page(0) as page:
            spans = page.get_all_spans()
            texts = [s.text for s in spans[:5]]
        assert all(len(t) > 0 for t in texts)
        assert "Photon" in texts[0]

    def test_all_pages_extractable(self, doc):
        for i in range(doc.page_count):
            with doc.load_page(i) as page:
                spans = page.get_all_spans()
                assert isinstance(spans, list)

    def test_page_out_of_range(self, doc):
        with pytest.raises(RuntimeError):
            doc.load_page(999)

    def test_page_negative_index(self, doc):
        with pytest.raises(RuntimeError):
            doc.load_page(-1)


class TestRedbookPdf:

    @pytest.fixture
    def doc(self):
        d = MuPdfDocument(str(REDBOOK_PDF))
        d.open()
        yield d
        d.close()

    def test_page_count(self, doc):
        assert doc.page_count == 54

    def test_no_metadata(self, doc):
        assert doc.get_metadata("info:Title") is None

    def test_outline(self, doc):
        outline = doc.get_outline()
        assert len(outline) >= 10
        titles = [e.title for e in outline]
        assert any("Preface" in t for t in titles)

    def test_title_page_fonts(self, doc):
        with doc.load_page(0) as page:
            spans = page.get_all_spans()
            sizes = {round(s.font_size, 1) for s in spans}
            assert max(sizes) >= 60

    def test_body_page_mixed_fonts(self, doc):
        with doc.load_page(5) as page:
            spans = page.get_all_spans()
            fonts = {s.font_name for s in spans}
            assert len(fonts) >= 2

    def test_italic_detection(self, doc):
        with doc.load_page(5) as page:
            spans = page.get_all_spans()
            has_italic = any(s.is_italic for s in spans)
            assert has_italic


class TestMuPdfExtractorPhoton:

    @pytest.fixture
    def extractor(self):
        config = MuPdfPdfExtractorConfig()
        ext = MuPdfPdfExtractor(str(PHOTON_PDF), config, GenericAnalyzer())
        ext.load()
        ext.parse()
        return ext

    def test_provenance(self, extractor):
        p = extractor.provenance
        assert p.parser_version == "3.0.0-mupdf"
        assert len(p.content_hash) == 40
        assert len(p.doc_id) == 16

    def test_chunks_produced(self, extractor):
        assert len(extractor.chunks) > 20

    def test_quality_route_a(self, extractor):
        assert extractor.route == "A"
        assert extractor.quality_score > 0.7

    def test_heading_hierarchy(self, extractor):
        has_heading = any(
            c.hierarchy.get("level_1") for c in extractor.chunks
        )
        assert has_heading

    def test_metadata(self, extractor):
        meta = extractor.extract_metadata()
        assert "Photon" in meta.title

    def test_output_schema(self, extractor):
        extractor.extract_metadata()
        output = extractor.get_output_data()
        assert "metadata" in output
        assert "chunks" in output
        assert "extraction_info" in output
        assert output["extraction_info"]["total_chunks"] == len(extractor.chunks)

    def test_chunks_have_sentences(self, extractor):
        for chunk in extractor.chunks:
            assert chunk.sentence_count >= 1
            assert len(chunk.sentences) >= 1

    def test_stable_ids_unique(self, extractor):
        ids = [c.stable_id for c in extractor.chunks]
        assert len(ids) == len(set(ids))


class TestMuPdfExtractorRedbook:

    @pytest.fixture
    def extractor(self):
        config = MuPdfPdfExtractorConfig()
        ext = MuPdfPdfExtractor(str(REDBOOK_PDF), config, GenericAnalyzer())
        ext.load()
        ext.parse()
        return ext

    def test_chunks_produced(self, extractor):
        assert len(extractor.chunks) > 50

    def test_outline_seeds_hierarchy(self, extractor):
        chapter_headings = set()
        for c in extractor.chunks:
            h = c.hierarchy.get("level_1", "")
            if h:
                chapter_headings.add(h)
        assert any("Background" in h for h in chapter_headings)
        assert any("Query Optimization" in h for h in chapter_headings)

    def test_metadata_fallback_to_filename(self, extractor):
        meta = extractor.extract_metadata()
        assert "redbook" in meta.title.lower()

    def test_full_output_json_serializable(self, extractor):
        extractor.extract_metadata()
        output = extractor.get_output_data()
        serialized = json.dumps(output)
        assert len(serialized) > 1000


RUST_PDF = FIXTURES / "The Rust Programming Language.pdf"


@pytest.mark.skipif(not RUST_PDF.exists(), reason="Rust book PDF not available")
class TestRustBookPdf:

    @pytest.fixture
    def doc(self):
        d = MuPdfDocument(str(RUST_PDF))
        d.open()
        yield d
        d.close()

    def test_page_count(self, doc):
        assert doc.page_count > 700

    def test_no_outline(self, doc):
        assert len(doc.get_outline()) == 0

    def test_monospace_code_detected(self, doc):
        with doc.load_page(50) as page:
            spans = page.get_all_spans()
            has_mono = any(s.is_mono for s in spans)
            assert has_mono

    def test_mixed_fonts_on_code_page(self, doc):
        with doc.load_page(50) as page:
            spans = page.get_all_spans()
            fonts = {s.font_name for s in spans}
            assert len(fonts) >= 2


@pytest.mark.skipif(not RUST_PDF.exists(), reason="Rust book PDF not available")
class TestMuPdfExtractorRustBook:

    @pytest.fixture
    def extractor(self):
        config = MuPdfPdfExtractorConfig()
        ext = MuPdfPdfExtractor(str(RUST_PDF), config, GenericAnalyzer())
        ext.load()
        ext.parse()
        return ext

    def test_chunks_produced(self, extractor):
        assert len(extractor.chunks) > 300

    def test_font_based_headings_without_toc(self, extractor):
        level_1 = set()
        for c in extractor.chunks:
            h = c.hierarchy.get("level_1", "")
            if h:
                level_1.add(h)
        assert len(level_1) > 50

    def test_no_monospace_headings(self, extractor):
        for c in extractor.chunks:
            for k in ["level_1", "level_2"]:
                h = c.hierarchy.get(k, "")
                assert h != "usize"
                assert h != "b"

    def test_code_chunks_present(self, extractor):
        code_chunks = [c for c in extractor.chunks if "fn " in c.text]
        assert len(code_chunks) > 50

    def test_total_words(self, extractor):
        total = sum(c.word_count for c in extractor.chunks)
        assert total > 100_000
