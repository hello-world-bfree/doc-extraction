#include "shim.h"
#include <string.h>

static void clear_result(de_shim_result *result) {
    result->error_code = 0;
    result->error_msg[0] = '\0';
}

static void set_error(de_shim_result *result, int code, const char *msg) {
    result->error_code = code;
    if (msg) {
        strncpy(result->error_msg, msg, sizeof(result->error_msg) - 1);
        result->error_msg[sizeof(result->error_msg) - 1] = '\0';
    }
}

fz_document *de_shim_open_document(fz_context *ctx, const char *path, de_shim_result *result) {
    fz_document *doc = NULL;
    clear_result(result);
    fz_try(ctx) {
        doc = fz_open_document(ctx, path);
    }
    fz_catch(ctx) {
        set_error(result, -7, fz_caught_message(ctx));
        return NULL;
    }
    return doc;
}

fz_page *de_shim_load_page(fz_context *ctx, fz_document *doc, int page_num, de_shim_result *result) {
    fz_page *page = NULL;
    clear_result(result);
    fz_try(ctx) {
        page = fz_load_page(ctx, doc, page_num);
    }
    fz_catch(ctx) {
        set_error(result, -7, fz_caught_message(ctx));
        return NULL;
    }
    return page;
}

fz_stext_page *de_shim_new_stext_page_from_page(fz_context *ctx, fz_page *page, de_shim_result *result) {
    fz_stext_page *stext = NULL;
    clear_result(result);
    fz_try(ctx) {
        fz_stext_options opts = { 0 };
        stext = fz_new_stext_page_from_page(ctx, page, &opts);
    }
    fz_catch(ctx) {
        set_error(result, -7, fz_caught_message(ctx));
        return NULL;
    }
    return stext;
}

fz_outline *de_shim_load_outline(fz_context *ctx, fz_document *doc, de_shim_result *result) {
    fz_outline *outline = NULL;
    clear_result(result);
    fz_try(ctx) {
        outline = fz_load_outline(ctx, doc);
    }
    fz_catch(ctx) {
        set_error(result, -7, fz_caught_message(ctx));
        return NULL;
    }
    return outline;
}

int de_shim_lookup_metadata(fz_context *ctx, fz_document *doc, const char *key, char *buf, int size, de_shim_result *result) {
    int len = -1;
    clear_result(result);
    fz_try(ctx) {
        len = fz_lookup_metadata(ctx, doc, key, buf, size);
    }
    fz_catch(ctx) {
        set_error(result, -7, fz_caught_message(ctx));
        return -1;
    }
    return len;
}

int de_shim_count_pages(fz_context *ctx, fz_document *doc, de_shim_result *result) {
    int count = 0;
    clear_result(result);
    fz_try(ctx) {
        count = fz_count_pages(ctx, doc);
    }
    fz_catch(ctx) {
        set_error(result, -7, fz_caught_message(ctx));
        return -1;
    }
    return count;
}

fz_rect de_shim_bound_page(fz_context *ctx, fz_page *page, de_shim_result *result) {
    fz_rect rect = { 0, 0, 0, 0 };
    clear_result(result);
    fz_try(ctx) {
        rect = fz_bound_page(ctx, page);
    }
    fz_catch(ctx) {
        set_error(result, -7, fz_caught_message(ctx));
    }
    return rect;
}

void de_shim_register_handlers(fz_context *ctx, de_shim_result *result) {
    clear_result(result);
    fz_try(ctx) {
        fz_register_document_handlers(ctx);
    }
    fz_catch(ctx) {
        set_error(result, -7, fz_caught_message(ctx));
    }
}

static void flatten_outline_recursive(fz_outline *node, de_flat_outline_entry *out, int max_entries, int *count, int level) {
    while (node && *count < max_entries) {
        out[*count].level = level;
        out[*count].page_num = node->page.page;
        out[*count].title[0] = '\0';
        if (node->title) {
            strncpy(out[*count].title, node->title, 511);
            out[*count].title[511] = '\0';
        }
        (*count)++;
        if (node->down)
            flatten_outline_recursive(node->down, out, max_entries, count, level + 1);
        node = node->next;
    }
}

int de_shim_flatten_outline(fz_context *ctx, fz_document *doc, de_flat_outline_entry *out, int max_entries, de_shim_result *result) {
    fz_outline *outline = NULL;
    int count = 0;
    clear_result(result);
    fz_try(ctx) {
        outline = fz_load_outline(ctx, doc);
    }
    fz_catch(ctx) {
        set_error(result, -7, fz_caught_message(ctx));
        return -1;
    }
    if (outline) {
        flatten_outline_recursive(outline, out, max_entries, &count, 0);
        fz_drop_outline(ctx, outline);
    }
    return count;
}

fz_stext_block *de_stext_first_block(fz_stext_page *page) {
    return page ? page->first_block : NULL;
}

fz_stext_block *de_stext_block_next(fz_stext_block *block) {
    return block ? block->next : NULL;
}

int de_stext_block_type(fz_stext_block *block) {
    return block ? block->type : -1;
}

fz_rect de_stext_block_bbox(fz_stext_block *block) {
    if (block) return block->bbox;
    fz_rect r = {0,0,0,0};
    return r;
}

fz_stext_line *de_stext_block_first_line(fz_stext_block *block) {
    if (!block || block->type != FZ_STEXT_BLOCK_TEXT) return NULL;
    return block->u.t.first_line;
}

fz_stext_line *de_stext_line_next(fz_stext_line *line) {
    return line ? line->next : NULL;
}

fz_stext_char *de_stext_line_first_char(fz_stext_line *line) {
    return line ? line->first_char : NULL;
}

fz_stext_char *de_stext_char_next(fz_stext_char *ch) {
    return ch ? ch->next : NULL;
}

int de_stext_char_c(fz_stext_char *ch) {
    return ch ? ch->c : 0;
}

float de_stext_char_size(fz_stext_char *ch) {
    return ch ? ch->size : 0;
}

fz_font *de_stext_char_font(fz_stext_char *ch) {
    return ch ? ch->font : NULL;
}

unsigned int de_stext_char_argb(fz_stext_char *ch) {
    return ch ? ch->argb : 0;
}

fz_quad de_stext_char_quad(fz_stext_char *ch) {
    if (ch) return ch->quad;
    fz_quad q = {{0,0},{0,0},{0,0},{0,0}};
    return q;
}

const char *de_font_name(fz_context *ctx, fz_font *font) {
    return fz_font_name(ctx, font);
}

int de_font_is_bold(fz_context *ctx, fz_font *font) {
    return fz_font_is_bold(ctx, font);
}

int de_font_is_italic(fz_context *ctx, fz_font *font) {
    return fz_font_is_italic(ctx, font);
}

int de_font_is_monospaced(fz_context *ctx, fz_font *font) {
    return fz_font_is_monospaced(ctx, font);
}
