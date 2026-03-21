const std = @import("std");
const handles = @import("handles");
const errors = @import("errors");
const types = @import("types.zig");
const context = @import("context.zig");
const document = @import("document.zig");
const page_mod = @import("page.zig");
const stext = @import("stext.zig");
const outline_mod = @import("outline.zig");

const ABI_VERSION: u32 = 1;

// ── ABI validation ──

export fn de_abi_version() u32 {
    return ABI_VERSION;
}

export fn de_sizeof_span() i32 {
    return @intCast(@sizeOf(types.DeTextSpan));
}

export fn de_sizeof_block() i32 {
    return @intCast(@sizeOf(types.DeTextBlock));
}

export fn de_sizeof_outline_entry() i32 {
    return @intCast(@sizeOf(types.DeOutlineEntry));
}

export fn de_sizeof_image_info() i32 {
    return @intCast(@sizeOf(types.DeImageInfo));
}

// ── Lifecycle ──

export fn de_init(max_memory_bytes: i64) ?*context.DeContext {
    return context.DeContext.init(max_memory_bytes);
}

export fn de_destroy(ctx: ?*context.DeContext) void {
    const c = handles.validateHandle(context.DeContext, ctx) orelse return;
    c.deinit();
}

export fn de_get_error_message(ctx: ?*context.DeContext) [*:0]const u8 {
    _ = ctx;
    return errors.getErrorPtr();
}

// ── Document ──

export fn de_open_document(ctx: ?*context.DeContext, path: ?[*:0]const u8) ?*document.DeDocument {
    const c = handles.validateHandle(context.DeContext, ctx) orelse {
        errors.setError("invalid context handle");
        return null;
    };
    const p = path orelse {
        errors.setError("path is null");
        return null;
    };
    return document.DeDocument.open(c, p);
}

export fn de_close_document(doc: ?*document.DeDocument) void {
    const d = handles.validateHandle(document.DeDocument, doc) orelse return;
    d.close();
}

export fn de_page_count(doc: ?*document.DeDocument) i32 {
    const d = handles.validateHandle(document.DeDocument, doc) orelse return errors.DE_ERR_INVALID_HANDLE;
    return d.page_count;
}

export fn de_get_metadata(doc: ?*document.DeDocument, key: ?[*:0]const u8, buf: ?[*]u8, buf_len: i32) i32 {
    const d = handles.validateHandle(document.DeDocument, doc) orelse return errors.DE_ERR_INVALID_HANDLE;
    const k = key orelse return errors.DE_ERR_INVALID_ARG;
    const b = buf orelse return errors.DE_ERR_INVALID_ARG;
    return d.getMetadata(k, b, buf_len);
}

export fn de_get_outline(doc: ?*document.DeDocument, out_entries: ?*?[*]types.DeOutlineEntry, out_count: ?*i32) i32 {
    const d = handles.validateHandle(document.DeDocument, doc) orelse return errors.DE_ERR_INVALID_HANDLE;
    const entries_ptr = out_entries orelse return errors.DE_ERR_INVALID_ARG;
    const count_ptr = out_count orelse return errors.DE_ERR_INVALID_ARG;
    return outline_mod.getOutline(d, entries_ptr, count_ptr);
}

export fn de_free_outline(entries: ?[*]types.DeOutlineEntry, count: i32) void {
    outline_mod.freeOutline(entries, count);
}

// ── Page ──

export fn de_load_page(doc: ?*document.DeDocument, page_num: i32) ?*page_mod.DePage {
    const d = handles.validateHandle(document.DeDocument, doc) orelse {
        errors.setError("invalid document handle");
        return null;
    };
    if (page_num < 0 or page_num >= d.page_count) {
        errors.setErrorFmt("page {d} out of range [0, {d})", .{ page_num, d.page_count });
        return null;
    }
    return page_mod.DePage.load(d, page_num);
}

export fn de_drop_page(pg: ?*page_mod.DePage) void {
    const p = handles.validateHandle(page_mod.DePage, pg) orelse return;
    p.drop();
}

export fn de_page_width(pg: ?*page_mod.DePage) f32 {
    const p = handles.validateHandle(page_mod.DePage, pg) orelse return 0;
    return p.width;
}

export fn de_page_height(pg: ?*page_mod.DePage) f32 {
    const p = handles.validateHandle(page_mod.DePage, pg) orelse return 0;
    return p.height;
}

// ── Structured Text ──

export fn de_get_all_spans(pg: ?*page_mod.DePage, out_spans: ?*?[*]types.DeTextSpan, out_count: ?*i32) i32 {
    const p = handles.validateHandle(page_mod.DePage, pg) orelse return errors.DE_ERR_INVALID_HANDLE;
    const spans_ptr = out_spans orelse return errors.DE_ERR_INVALID_ARG;
    const count_ptr = out_count orelse return errors.DE_ERR_INVALID_ARG;
    return stext.getAllSpans(p, spans_ptr, count_ptr);
}

export fn de_free_spans(spans: ?[*]types.DeTextSpan, count: i32) void {
    stext.freeSpans(spans, count);
}

export fn de_get_text_blocks(pg: ?*page_mod.DePage, out_blocks: ?*?[*]types.DeTextBlock, out_count: ?*i32) i32 {
    const p = handles.validateHandle(page_mod.DePage, pg) orelse return errors.DE_ERR_INVALID_HANDLE;
    const blocks_ptr = out_blocks orelse return errors.DE_ERR_INVALID_ARG;
    const count_ptr = out_count orelse return errors.DE_ERR_INVALID_ARG;
    return stext.getTextBlocks(p, blocks_ptr, count_ptr);
}

export fn de_free_text_blocks(blocks: ?[*]types.DeTextBlock, count: i32) void {
    stext.freeTextBlocks(blocks, count);
}
