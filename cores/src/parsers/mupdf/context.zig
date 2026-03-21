const std = @import("std");
const handles = @import("handles");
const alloc_mod = @import("allocator.zig");
const mupdf = @import("c.zig");

pub const DeContext = struct {
    header: handles.HandleHeader,
    fz_ctx: *mupdf.fz_context,
    max_memory: i64,

    pub fn init(max_memory: i64) ?*DeContext {
        const fz_ctx = alloc_mod.createTrackedContext(max_memory) orelse return null;

        var reg_result: mupdf.de_shim_result = undefined;
        mupdf.de_shim_register_handlers(fz_ctx, &reg_result);
        if (reg_result.error_code != 0) {
            mupdf.fz_drop_context(fz_ctx);
            return null;
        }

        const self = std.heap.c_allocator.create(DeContext) catch {
            mupdf.fz_drop_context(fz_ctx);
            return null;
        };
        self.* = .{
            .header = handles.HandleHeader.init(),
            .fz_ctx = fz_ctx,
            .max_memory = max_memory,
        };
        return self;
    }

    pub fn deinit(self: *DeContext) void {
        mupdf.fz_drop_context(self.fz_ctx);
        self.header.poison();
        std.heap.c_allocator.destroy(self);
    }
};
