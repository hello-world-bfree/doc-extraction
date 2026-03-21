from ctypes import c_int32, c_int64, c_uint32, c_float, c_char_p, c_void_p, POINTER
from ._types import DeTextBlock, DeTextSpan, DeOutlineEntry, DeImageInfo


def bind(lib):
    lib.de_abi_version.argtypes = []
    lib.de_abi_version.restype = c_uint32
    lib.de_sizeof_span.argtypes = []
    lib.de_sizeof_span.restype = c_int32
    lib.de_sizeof_block.argtypes = []
    lib.de_sizeof_block.restype = c_int32
    lib.de_sizeof_outline_entry.argtypes = []
    lib.de_sizeof_outline_entry.restype = c_int32
    lib.de_sizeof_image_info.argtypes = []
    lib.de_sizeof_image_info.restype = c_int32
    lib.de_init.argtypes = [c_int64]
    lib.de_init.restype = c_void_p
    lib.de_destroy.argtypes = [c_void_p]
    lib.de_destroy.restype = None
    lib.de_get_error_message.argtypes = [c_void_p]
    lib.de_get_error_message.restype = c_char_p
    lib.de_open_document.argtypes = [c_void_p, c_char_p]
    lib.de_open_document.restype = c_void_p
    lib.de_close_document.argtypes = [c_void_p]
    lib.de_close_document.restype = None
    lib.de_page_count.argtypes = [c_void_p]
    lib.de_page_count.restype = c_int32
    lib.de_get_metadata.argtypes = [c_void_p, c_char_p, c_char_p, c_int32]
    lib.de_get_metadata.restype = c_int32
    lib.de_get_outline.argtypes = [c_void_p, POINTER(POINTER(DeOutlineEntry)), POINTER(c_int32)]
    lib.de_get_outline.restype = c_int32
    lib.de_free_outline.argtypes = [POINTER(DeOutlineEntry), c_int32]
    lib.de_free_outline.restype = None
    lib.de_load_page.argtypes = [c_void_p, c_int32]
    lib.de_load_page.restype = c_void_p
    lib.de_drop_page.argtypes = [c_void_p]
    lib.de_drop_page.restype = None
    lib.de_page_width.argtypes = [c_void_p]
    lib.de_page_width.restype = c_float
    lib.de_page_height.argtypes = [c_void_p]
    lib.de_page_height.restype = c_float
    lib.de_get_all_spans.argtypes = [c_void_p, POINTER(POINTER(DeTextSpan)), POINTER(c_int32)]
    lib.de_get_all_spans.restype = c_int32
    lib.de_free_spans.argtypes = [POINTER(DeTextSpan), c_int32]
    lib.de_free_spans.restype = None
    lib.de_get_text_blocks.argtypes = [c_void_p, POINTER(POINTER(DeTextBlock)), POINTER(c_int32)]
    lib.de_get_text_blocks.restype = c_int32
    lib.de_free_text_blocks.argtypes = [POINTER(DeTextBlock), c_int32]
    lib.de_free_text_blocks.restype = None
