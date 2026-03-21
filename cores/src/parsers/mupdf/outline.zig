const std = @import("std");
const errors = @import("errors");
const c = @import("c.zig");
const types = @import("types.zig");
const document = @import("document.zig");

const MAX_OUTLINE_ENTRIES = 4096;

pub fn getOutline(doc: *document.DeDocument, out_entries: *?[*]types.DeOutlineEntry, out_count: *i32) i32 {
    var flat_buf: [MAX_OUTLINE_ENTRIES]c.de_flat_outline_entry = undefined;
    var result: c.de_shim_result = undefined;

    const count = c.de_shim_flatten_outline(doc.ctx.fz_ctx, doc.fz_doc, &flat_buf, MAX_OUTLINE_ENTRIES, &result);
    if (result.error_code != 0) {
        errors.setError(std.mem.sliceTo(&result.error_msg, 0));
        return errors.DE_ERR_MUPDF;
    }

    if (count <= 0) {
        out_entries.* = null;
        out_count.* = 0;
        return errors.DE_OK;
    }

    const n: usize = @intCast(count);
    const entries = std.heap.c_allocator.alloc(types.DeOutlineEntry, n) catch {
        errors.setError("allocation failed for outline entries");
        return errors.DE_ERR_ALLOC;
    };

    for (0..n) |i| {
        entries[i].level = flat_buf[i].level;
        entries[i].page_num = flat_buf[i].page_num;
        entries[i].title = [_]u8{0} ** 512;
        const title_slice = std.mem.sliceTo(&flat_buf[i].title, 0);
        const tlen = @min(title_slice.len, 511);
        @memcpy(entries[i].title[0..tlen], title_slice[0..tlen]);
    }

    out_entries.* = entries.ptr;
    out_count.* = @intCast(n);
    return errors.DE_OK;
}

pub fn freeOutline(entries: ?[*]types.DeOutlineEntry, count: i32) void {
    if (entries == null or count <= 0) return;
    std.heap.c_allocator.free(entries.?[0..@intCast(count)]);
}
