pub const c = @cImport({
    @cInclude("mupdf/fitz.h");
    @cInclude("mupdf/pdf.h");
    @cInclude("shim.h");
});

pub const fz_context = c.fz_context;
pub const fz_document = c.fz_document;
pub const fz_page = c.fz_page;
pub const fz_stext_page = c.fz_stext_page;
pub const fz_stext_block = c.fz_stext_block;
pub const fz_stext_line = c.fz_stext_line;
pub const fz_stext_char = c.fz_stext_char;
pub const fz_outline = c.fz_outline;
pub const fz_rect = c.fz_rect;
pub const fz_matrix = c.fz_matrix;
pub const fz_font = c.fz_font;
pub const fz_stext_options = c.fz_stext_options;
pub const fz_alloc_context = c.fz_alloc_context;

pub const FZ_STORE_DEFAULT: usize = 256 << 20;
pub const FZ_STEXT_BLOCK_TEXT: c_int = 0;

pub const fz_new_context = c.fz_new_context;
pub const fz_drop_context = c.fz_drop_context;
pub const fz_count_pages = c.fz_count_pages;
pub const fz_bound_page = c.fz_bound_page;
pub const fz_drop_page = c.fz_drop_page;
pub const fz_drop_stext_page = c.fz_drop_stext_page;
pub const fz_drop_document = c.fz_drop_document;
pub const fz_drop_outline = c.fz_drop_outline;
pub const fz_lookup_metadata = c.fz_lookup_metadata;
pub const de_font_name = c.de_font_name;
pub const de_font_is_bold = c.de_font_is_bold;
pub const de_font_is_italic = c.de_font_is_italic;
pub const de_font_is_monospaced = c.de_font_is_monospaced;

pub const de_shim_result = c.de_shim_result;
pub const de_shim_open_document = c.de_shim_open_document;
pub const de_shim_load_page = c.de_shim_load_page;
pub const de_shim_new_stext_page_from_page = c.de_shim_new_stext_page_from_page;
pub const de_shim_load_outline = c.de_shim_load_outline;
pub const de_shim_lookup_metadata = c.de_shim_lookup_metadata;
pub const de_shim_count_pages = c.de_shim_count_pages;
pub const de_shim_bound_page = c.de_shim_bound_page;
pub const de_shim_register_handlers = c.de_shim_register_handlers;

pub const de_flat_outline_entry = c.de_flat_outline_entry;
pub const de_shim_flatten_outline = c.de_shim_flatten_outline;

pub const de_stext_first_block = c.de_stext_first_block;
pub const de_stext_block_next = c.de_stext_block_next;
pub const de_stext_block_type = c.de_stext_block_type;
pub const de_stext_block_bbox = c.de_stext_block_bbox;
pub const de_stext_block_first_line = c.de_stext_block_first_line;
pub const de_stext_line_next = c.de_stext_line_next;
pub const de_stext_line_first_char = c.de_stext_line_first_char;
pub const de_stext_char_next = c.de_stext_char_next;
pub const de_stext_char_c = c.de_stext_char_c;
pub const de_stext_char_size = c.de_stext_char_size;
pub const de_stext_char_font = c.de_stext_char_font;
pub const de_stext_char_argb = c.de_stext_char_argb;
pub const de_stext_char_quad = c.de_stext_char_quad;
