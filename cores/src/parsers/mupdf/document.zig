const std = @import("std");
const handles = @import("handles");
const errors = @import("errors");
const c = @import("c.zig");
const context = @import("context.zig");

pub const DeDocument = struct {
    header: handles.HandleHeader,
    fz_doc: *c.fz_document,
    ctx: *context.DeContext,
    page_count: i32,

    pub fn open(ctx_h: *context.DeContext, path: [*:0]const u8) ?*DeDocument {
        var result: c.de_shim_result = undefined;
        const fz_doc = c.de_shim_open_document(ctx_h.fz_ctx, path, &result);
        if (result.error_code != 0) {
            errors.setError(std.mem.sliceTo(&result.error_msg, 0));
            return null;
        }
        const doc = fz_doc orelse return null;

        var count_result: c.de_shim_result = undefined;
        const count = c.de_shim_count_pages(ctx_h.fz_ctx, doc, &count_result);
        if (count_result.error_code != 0) {
            errors.setError(std.mem.sliceTo(&count_result.error_msg, 0));
            c.fz_drop_document(ctx_h.fz_ctx, doc);
            return null;
        }

        const self = std.heap.c_allocator.create(DeDocument) catch {
            c.fz_drop_document(ctx_h.fz_ctx, doc);
            errors.setError("allocation failed for DeDocument");
            return null;
        };
        self.* = .{
            .header = handles.HandleHeader.init(),
            .fz_doc = doc,
            .ctx = ctx_h,
            .page_count = count,
        };
        return self;
    }

    pub fn close(self: *DeDocument) void {
        c.fz_drop_document(self.ctx.fz_ctx, self.fz_doc);
        self.header.poison();
        std.heap.c_allocator.destroy(self);
    }

    pub fn getMetadata(self: *DeDocument, key: [*:0]const u8, buf: [*]u8, buf_len: i32) i32 {
        var result: c.de_shim_result = undefined;
        const len = c.de_shim_lookup_metadata(self.ctx.fz_ctx, self.fz_doc, key, buf, buf_len, &result);
        if (result.error_code != 0) {
            errors.setError(std.mem.sliceTo(&result.error_msg, 0));
            return errors.DE_ERR_MUPDF;
        }
        return len;
    }
};
