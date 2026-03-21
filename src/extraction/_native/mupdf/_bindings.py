import ctypes
import logging
from typing import ClassVar

from .._loader import load_library
from . import _prototypes
from ._types import DeTextSpan, DeTextBlock, DeOutlineEntry, DeImageInfo

LOGGER = logging.getLogger(__name__)

_lib: ctypes.CDLL | None = None


def get_lib() -> ctypes.CDLL:
    global _lib
    if _lib is not None:
        return _lib

    lib = load_library("de_mupdf")
    _prototypes.bind(lib)

    _validate_struct_sizes(lib)

    _lib = lib
    LOGGER.debug("MuPDF native library loaded and validated")
    return _lib


def _validate_struct_sizes(lib: ctypes.CDLL) -> None:
    checks = [
        ("DeTextSpan", ctypes.sizeof(DeTextSpan), lib.de_sizeof_span()),
        ("DeTextBlock", ctypes.sizeof(DeTextBlock), lib.de_sizeof_block()),
        ("DeOutlineEntry", ctypes.sizeof(DeOutlineEntry), lib.de_sizeof_outline_entry()),
        ("DeImageInfo", ctypes.sizeof(DeImageInfo), lib.de_sizeof_image_info()),
    ]
    for name, py_size, zig_size in checks:
        if py_size != zig_size:
            raise RuntimeError(
                f"Struct size mismatch for {name}: Python={py_size}, Zig={zig_size}. "
                "Rebuild the native library or regenerate _types.py."
            )
