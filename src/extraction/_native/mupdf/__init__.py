import ctypes
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator

from ._bindings import get_lib
from ._types import DeTextSpan, DeOutlineEntry

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SpanData:
    bbox: tuple[float, float, float, float]
    font_name: str
    font_size: float
    is_bold: bool
    is_italic: bool
    is_mono: bool
    color: int
    block_idx: int
    line_idx: int
    text: str


@dataclass(frozen=True, slots=True)
class OutlineEntry:
    level: int
    title: str
    page_num: int


class MuPdfPage:
    def __init__(self, handle, doc: "MuPdfDocument"):
        self._handle = handle
        self._doc = doc
        self._closed = False

    @property
    def width(self) -> float:
        if self._closed:
            raise RuntimeError("Page already closed")
        return get_lib().de_page_width(self._handle)

    @property
    def height(self) -> float:
        if self._closed:
            raise RuntimeError("Page already closed")
        return get_lib().de_page_height(self._handle)

    def get_all_spans(self) -> list[SpanData]:
        if self._closed:
            raise RuntimeError("Page already closed")
        lib = get_lib()

        spans_ptr = ctypes.POINTER(DeTextSpan)()
        count = ctypes.c_int32(0)
        rc = lib.de_get_all_spans(
            self._handle,
            ctypes.byref(spans_ptr),
            ctypes.byref(count),
        )
        if rc != 0:
            msg = lib.de_get_error_message(self._doc._ctx_handle)
            raise RuntimeError(f"de_get_all_spans failed ({rc}): {msg}")

        result = []
        try:
            for i in range(count.value):
                raw = spans_ptr[i]
                font_bytes = bytes(raw.font_name)
                font_name = font_bytes.split(b"\x00", 1)[0].decode("utf-8", errors="replace")
                text = ctypes.string_at(raw.text_ptr, raw.text_len).decode("utf-8", errors="replace") if raw.text_ptr and raw.text_len > 0 else ""
                flags = raw.font_flags
                result.append(SpanData(
                    bbox=(raw.bbox_x0, raw.bbox_y0, raw.bbox_x1, raw.bbox_y1),
                    font_name=font_name,
                    font_size=raw.font_size,
                    is_bold=bool(flags & 1),
                    is_italic=bool(flags & 2),
                    is_mono=bool(flags & 4),
                    color=raw.color,
                    block_idx=raw.block_idx,
                    line_idx=raw.line_idx,
                    text=text,
                ))
        finally:
            if spans_ptr:
                lib.de_free_spans(spans_ptr, count)

        return result

    def close(self):
        if not self._closed:
            get_lib().de_drop_page(self._handle)
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class MuPdfDocument:
    def __init__(self, path: str, *, max_memory_mb: int = 0):
        self._path = path
        self._max_memory = max_memory_mb * 1024 * 1024 if max_memory_mb > 0 else 0
        self._ctx_handle = None
        self._doc_handle = None
        self._closed = False

    def open(self):
        lib = get_lib()
        self._ctx_handle = lib.de_init(self._max_memory)
        if not self._ctx_handle:
            raise RuntimeError("Failed to create MuPDF context")

        path_bytes = self._path.encode("utf-8")
        self._doc_handle = lib.de_open_document(self._ctx_handle, path_bytes)
        if not self._doc_handle:
            msg = lib.de_get_error_message(self._ctx_handle)
            lib.de_destroy(self._ctx_handle)
            self._ctx_handle = None
            raise FileNotFoundError(f"Failed to open PDF: {msg}")

    @property
    def page_count(self) -> int:
        if self._closed:
            raise RuntimeError("Document already closed")
        return get_lib().de_page_count(self._doc_handle)

    def load_page(self, page_num: int) -> MuPdfPage:
        if self._closed:
            raise RuntimeError("Document already closed")
        lib = get_lib()
        handle = lib.de_load_page(self._doc_handle, page_num)
        if not handle:
            msg = lib.de_get_error_message(self._ctx_handle)
            raise RuntimeError(f"Failed to load page {page_num}: {msg}")
        return MuPdfPage(handle, self)

    def get_metadata(self, key: str) -> str | None:
        if self._closed:
            raise RuntimeError("Document already closed")
        lib = get_lib()
        buf = ctypes.create_string_buffer(1024)
        rc = lib.de_get_metadata(
            self._doc_handle,
            key.encode("utf-8"),
            buf,
            1024,
        )
        if rc < 0:
            return None
        return buf.value.decode("utf-8", errors="replace")

    def get_outline(self) -> list[OutlineEntry]:
        if self._closed:
            raise RuntimeError("Document already closed")
        lib = get_lib()

        entries_ptr = ctypes.POINTER(DeOutlineEntry)()
        count = ctypes.c_int32(0)
        rc = lib.de_get_outline(
            self._doc_handle,
            ctypes.byref(entries_ptr),
            ctypes.byref(count),
        )
        if rc != 0:
            msg = lib.de_get_error_message(self._ctx_handle)
            raise RuntimeError(f"de_get_outline failed ({rc}): {msg}")

        result = []
        try:
            for i in range(count.value):
                raw = entries_ptr[i]
                title_bytes = bytes(raw.title)
                title = title_bytes.split(b"\x00", 1)[0].decode("utf-8", errors="replace")
                result.append(OutlineEntry(
                    level=raw.level,
                    title=title,
                    page_num=raw.page_num,
                ))
        finally:
            if entries_ptr:
                lib.de_free_outline(entries_ptr, count)

        return result

    def close(self):
        if not self._closed:
            lib = get_lib()
            if self._doc_handle:
                lib.de_close_document(self._doc_handle)
                self._doc_handle = None
            if self._ctx_handle:
                lib.de_destroy(self._ctx_handle)
                self._ctx_handle = None
            self._closed = True

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()
