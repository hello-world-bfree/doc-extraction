const errors = @import("errors");
const handles = @import("handles");
const document = @import("document.zig");

pub fn getMetadata(doc: *document.DeDocument, key: [*:0]const u8, buf: [*]u8, buf_len: i32) i32 {
    return doc.getMetadata(key, buf, buf_len);
}
