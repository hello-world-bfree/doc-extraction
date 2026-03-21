import ctypes
from ctypes import Structure, c_float, c_int32, c_uint32, c_char, c_void_p

class DeTextBlock(Structure):
    _fields_ = [
        ("bbox_x0", c_float),
        ("bbox_y0", c_float),
        ("bbox_x1", c_float),
        ("bbox_y1", c_float),
        ("block_type", c_int32),
        ("line_count", c_int32),
    ]

class DeTextSpan(Structure):
    _fields_ = [
        ("bbox_x0", c_float),
        ("bbox_y0", c_float),
        ("bbox_x1", c_float),
        ("bbox_y1", c_float),
        ("font_name", c_char * 128),
        ("font_size", c_float),
        ("font_flags", c_uint32),
        ("color", c_uint32),
        ("block_idx", c_int32),
        ("line_idx", c_int32),
        ("text_ptr", c_void_p),
        ("text_len", c_int32),
    ]

class DeOutlineEntry(Structure):
    _fields_ = [
        ("level", c_int32),
        ("title", c_char * 512),
        ("page_num", c_int32),
    ]

class DeImageInfo(Structure):
    _fields_ = [
        ("bbox_x0", c_float),
        ("bbox_y0", c_float),
        ("bbox_x1", c_float),
        ("bbox_y1", c_float),
        ("width", c_int32),
        ("height", c_int32),
        ("image_type", c_int32),
    ]
