const std = @import("std");
const handles = @import("handles");
const errors = @import("errors");
const c = @import("c.zig");
const document = @import("document.zig");

pub const DePage = struct {
    header: handles.HandleHeader,
    fz_page: *c.fz_page,
    doc: *document.DeDocument,
    width: f32,
    height: f32,

    pub fn load(doc: *document.DeDocument, page_num: i32) ?*DePage {
        var result: c.de_shim_result = undefined;
        const fz_p = c.de_shim_load_page(doc.ctx.fz_ctx, doc.fz_doc, page_num, &result);
        if (result.error_code != 0) {
            errors.setError(std.mem.sliceTo(&result.error_msg, 0));
            return null;
        }
        const p = fz_p orelse return null;

        var bound_result: c.de_shim_result = undefined;
        const rect = c.de_shim_bound_page(doc.ctx.fz_ctx, p, &bound_result);

        const self = std.heap.c_allocator.create(DePage) catch {
            c.fz_drop_page(doc.ctx.fz_ctx, p);
            errors.setError("allocation failed for DePage");
            return null;
        };
        self.* = .{
            .header = handles.HandleHeader.init(),
            .fz_page = p,
            .doc = doc,
            .width = rect.x1 - rect.x0,
            .height = rect.y1 - rect.y0,
        };
        return self;
    }

    pub fn drop(self: *DePage) void {
        c.fz_drop_page(self.doc.ctx.fz_ctx, self.fz_page);
        self.header.poison();
        std.heap.c_allocator.destroy(self);
    }
};
