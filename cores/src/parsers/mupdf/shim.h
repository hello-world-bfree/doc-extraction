#ifndef DE_SHIM_H
#define DE_SHIM_H

#include "mupdf/fitz.h"
#include "mupdf/pdf.h"

typedef struct {
    int error_code;
    char error_msg[512];
} de_shim_result;

typedef struct {
    int level;
    char title[512];
    int page_num;
} de_flat_outline_entry;

fz_document *de_shim_open_document(fz_context *ctx, const char *path, de_shim_result *result);
fz_page *de_shim_load_page(fz_context *ctx, fz_document *doc, int page_num, de_shim_result *result);
fz_stext_page *de_shim_new_stext_page_from_page(fz_context *ctx, fz_page *page, de_shim_result *result);
fz_outline *de_shim_load_outline(fz_context *ctx, fz_document *doc, de_shim_result *result);
int de_shim_lookup_metadata(fz_context *ctx, fz_document *doc, const char *key, char *buf, int size, de_shim_result *result);
int de_shim_count_pages(fz_context *ctx, fz_document *doc, de_shim_result *result);
fz_rect de_shim_bound_page(fz_context *ctx, fz_page *page, de_shim_result *result);

int de_shim_flatten_outline(fz_context *ctx, fz_document *doc, de_flat_outline_entry *out, int max_entries, de_shim_result *result);

fz_stext_block *de_stext_first_block(fz_stext_page *page);
fz_stext_block *de_stext_block_next(fz_stext_block *block);
int de_stext_block_type(fz_stext_block *block);
fz_rect de_stext_block_bbox(fz_stext_block *block);
fz_stext_line *de_stext_block_first_line(fz_stext_block *block);
fz_stext_line *de_stext_line_next(fz_stext_line *line);
fz_stext_char *de_stext_line_first_char(fz_stext_line *line);
fz_stext_char *de_stext_char_next(fz_stext_char *ch);
int de_stext_char_c(fz_stext_char *ch);
float de_stext_char_size(fz_stext_char *ch);
fz_font *de_stext_char_font(fz_stext_char *ch);
unsigned int de_stext_char_argb(fz_stext_char *ch);
fz_quad de_stext_char_quad(fz_stext_char *ch);

void de_shim_register_handlers(fz_context *ctx, de_shim_result *result);

const char *de_font_name(fz_context *ctx, fz_font *font);
int de_font_is_bold(fz_context *ctx, fz_font *font);
int de_font_is_italic(fz_context *ctx, fz_font *font);
int de_font_is_monospaced(fz_context *ctx, fz_font *font);

#endif
