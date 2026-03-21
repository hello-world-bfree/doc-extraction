const std = @import("std");
const errors = @import("errors");
const c = @import("c.zig");
const types = @import("types.zig");
const page_mod = @import("page.zig");

const builtin = @import("builtin");

fn fontFlags(ctx: anytype, font: anytype) u32 {
    var flags: u32 = 0;
    if (c.de_font_is_bold(ctx, font) != 0) flags |= 1;
    if (c.de_font_is_italic(ctx, font) != 0) flags |= 2;
    if (c.de_font_is_monospaced(ctx, font) != 0) flags |= 4;
    return flags;
}

fn copyFontName(dest: *[128]u8, ctx: anytype, font: anytype) void {
    const name_ptr = c.de_font_name(ctx, font);
    if (name_ptr) |ptr| {
        const name = std.mem.sliceTo(ptr, 0);
        const n = @min(name.len, 127);
        @memcpy(dest[0..n], name[0..n]);
        dest[n] = 0;
    } else {
        dest[0] = 0;
    }
}

pub fn getAllSpans(pg: *page_mod.DePage, out_spans: *?[*]types.DeTextSpan, out_count: *i32) i32 {
    var result: c.de_shim_result = undefined;
    const stext_raw = c.de_shim_new_stext_page_from_page(pg.doc.ctx.fz_ctx, pg.fz_page, &result);
    if (result.error_code != 0) {
        errors.setError(std.mem.sliceTo(&result.error_msg, 0));
        return errors.DE_ERR_MUPDF;
    }
    if (stext_raw == null) {
        errors.setError("stext page is null");
        return errors.DE_ERR_MUPDF;
    }
    defer c.fz_drop_stext_page(pg.doc.ctx.fz_ctx, stext_raw);

    var span_count: usize = 0;
    var block = c.de_stext_first_block(stext_raw);
    while (block != null) : (block = c.de_stext_block_next(block)) {
        if (c.de_stext_block_type(block) != 0) continue;
        var line = c.de_stext_block_first_line(block);
        while (line != null) : (line = c.de_stext_line_next(line)) {
            var ch = c.de_stext_line_first_char(line);
            if (ch != null) span_count += 1;
            var prev_font: ?*c.fz_font = if (ch != null) c.de_stext_char_font(ch) else null;
            var prev_size: f32 = if (ch != null) c.de_stext_char_size(ch) else 0;
            while (ch != null) : (ch = c.de_stext_char_next(ch)) {
                const cur_font = c.de_stext_char_font(ch);
                const cur_size = c.de_stext_char_size(ch);
                if (cur_font != prev_font or cur_size != prev_size) {
                    span_count += 1;
                    prev_font = cur_font;
                    prev_size = cur_size;
                }
            }
        }
    }

    if (span_count == 0) {
        out_spans.* = null;
        out_count.* = 0;
        return errors.DE_OK;
    }

    const spans = std.heap.c_allocator.alloc(types.DeTextSpan, span_count) catch {
        errors.setError("allocation failed for spans");
        return errors.DE_ERR_ALLOC;
    };

    var idx: usize = 0;
    var block_idx: i32 = 0;
    block = c.de_stext_first_block(stext_raw);
    while (block != null) : (block = c.de_stext_block_next(block)) {
        if (c.de_stext_block_type(block) != 0) continue;
        var line_idx: i32 = 0;
        var line = c.de_stext_block_first_line(block);
        while (line != null) : (line = c.de_stext_line_next(line)) {
            var ch = c.de_stext_line_first_char(line);
            if (ch == null) {
                line_idx += 1;
                continue;
            }

            var prev_font = c.de_stext_char_font(ch);
            var prev_size = c.de_stext_char_size(ch);
            var start_color = c.de_stext_char_argb(ch);
            var char_count: i32 = 0;
            const start_quad = c.de_stext_char_quad(ch);
            var span_bbox = c.c.fz_rect{
                .x0 = start_quad.ul.x,
                .y0 = start_quad.ul.y,
                .x1 = start_quad.lr.x,
                .y1 = start_quad.lr.y,
            };

            var text_buf = std.array_list.Managed(u8).init(std.heap.c_allocator);
            defer text_buf.deinit();

            while (ch != null) : (ch = c.de_stext_char_next(ch)) {
                const cur_font = c.de_stext_char_font(ch);
                const cur_size = c.de_stext_char_size(ch);

                if (cur_font != prev_font or cur_size != prev_size) {
                    if (idx < span_count) {
                        const text_slice = text_buf.toOwnedSlice() catch &[_]u8{};
                        fillSpan(&spans[idx], span_bbox, pg.doc.ctx.fz_ctx, prev_font.?, prev_size, start_color, block_idx, line_idx, text_slice);
                        idx += 1;
                    }
                    prev_font = cur_font;
                    prev_size = cur_size;
                    start_color = c.de_stext_char_argb(ch);
                    char_count = 0;
                    const q = c.de_stext_char_quad(ch);
                    span_bbox = c.c.fz_rect{
                        .x0 = q.ul.x,
                        .y0 = q.ul.y,
                        .x1 = q.lr.x,
                        .y1 = q.lr.y,
                    };
                    text_buf = std.array_list.Managed(u8).init(std.heap.c_allocator);
                }

                const code: u21 = @intCast(c.de_stext_char_c(ch));
                var utf8_buf: [4]u8 = undefined;
                const len = std.unicode.utf8Encode(code, &utf8_buf) catch 0;
                text_buf.appendSlice(utf8_buf[0..len]) catch {};

                const q = c.de_stext_char_quad(ch);
                if (q.ul.x < span_bbox.x0) span_bbox.x0 = q.ul.x;
                if (q.ul.y < span_bbox.y0) span_bbox.y0 = q.ul.y;
                if (q.lr.x > span_bbox.x1) span_bbox.x1 = q.lr.x;
                if (q.lr.y > span_bbox.y1) span_bbox.y1 = q.lr.y;
                char_count += 1;
            }

            if (char_count > 0 and idx < span_count) {
                const text_slice = text_buf.toOwnedSlice() catch &[_]u8{};
                fillSpan(&spans[idx], span_bbox, pg.doc.ctx.fz_ctx, prev_font.?, prev_size, start_color, block_idx, line_idx, text_slice);
                idx += 1;
            }

            line_idx += 1;
        }
        block_idx += 1;
    }

    out_spans.* = spans.ptr;
    out_count.* = @intCast(idx);
    return errors.DE_OK;
}

fn fillSpan(span: *types.DeTextSpan, bbox: c.c.fz_rect, ctx: anytype, font: anytype, size: f32, color: u32, block_idx: i32, line_idx: i32, text: []const u8) void {
    span.bbox_x0 = bbox.x0;
    span.bbox_y0 = bbox.y0;
    span.bbox_x1 = bbox.x1;
    span.bbox_y1 = bbox.y1;
    copyFontName(&span.font_name, ctx, font);
    span.font_size = size;
    span.font_flags = fontFlags(ctx, font);
    span.color = color;
    span.block_idx = block_idx;
    span.line_idx = line_idx;
    span.text_ptr = text.ptr;
    span.text_len = @intCast(text.len);
}

pub fn freeSpans(spans: ?[*]types.DeTextSpan, count: i32) void {
    if (spans == null or count <= 0) return;
    const slice = spans.?[0..@intCast(count)];

    for (slice) |*span| {
        if (span.text_ptr) |ptr| {
            if (span.text_len > 0) {
                const text_slice = ptr[0..@intCast(span.text_len)];
                std.heap.c_allocator.free(text_slice);
            }
        }
        if (builtin.mode == .Debug) {
            @memset(std.mem.asBytes(span), 0xDE);
        }
    }

    std.heap.c_allocator.free(slice);
}

pub fn getTextBlocks(pg: *page_mod.DePage, out_blocks: *?[*]types.DeTextBlock, out_count: *i32) i32 {
    var result: c.de_shim_result = undefined;
    const stext_raw = c.de_shim_new_stext_page_from_page(pg.doc.ctx.fz_ctx, pg.fz_page, &result);
    if (result.error_code != 0) {
        errors.setError(std.mem.sliceTo(&result.error_msg, 0));
        return errors.DE_ERR_MUPDF;
    }
    if (stext_raw == null) {
        errors.setError("stext page is null");
        return errors.DE_ERR_MUPDF;
    }
    defer c.fz_drop_stext_page(pg.doc.ctx.fz_ctx, stext_raw);

    var block_count: usize = 0;
    var blk = c.de_stext_first_block(stext_raw);
    while (blk != null) : (blk = c.de_stext_block_next(blk)) {
        block_count += 1;
    }

    if (block_count == 0) {
        out_blocks.* = null;
        out_count.* = 0;
        return errors.DE_OK;
    }

    const blocks = std.heap.c_allocator.alloc(types.DeTextBlock, block_count) catch {
        errors.setError("allocation failed for blocks");
        return errors.DE_ERR_ALLOC;
    };

    var bi: usize = 0;
    var block = c.de_stext_first_block(stext_raw);
    while (block != null) : (block = c.de_stext_block_next(block)) {
        const bbox = c.de_stext_block_bbox(block);
        const btype = c.de_stext_block_type(block);
        blocks[bi] = .{
            .bbox_x0 = bbox.x0,
            .bbox_y0 = bbox.y0,
            .bbox_x1 = bbox.x1,
            .bbox_y1 = bbox.y1,
            .block_type = if (btype == 0) @as(i32, 0) else @as(i32, 1),
            .line_count = blk2: {
                if (btype != 0) break :blk2 0;
                var lc: i32 = 0;
                var lp = c.de_stext_block_first_line(block);
                while (lp != null) : (lp = c.de_stext_line_next(lp)) lc += 1;
                break :blk2 lc;
            },
        };
        bi += 1;
    }

    out_blocks.* = blocks.ptr;
    out_count.* = @intCast(bi);
    return errors.DE_OK;
}

pub fn freeTextBlocks(blocks: ?[*]types.DeTextBlock, count: i32) void {
    if (blocks == null or count <= 0) return;
    std.heap.c_allocator.free(blocks.?[0..@intCast(count)]);
}
