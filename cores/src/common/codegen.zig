const std = @import("std");

const TypeField = struct {
    name: []const u8,
    ct_type: []const u8,
    array_len: ?usize = null,
};

const StructDef = struct {
    name: []const u8,
    fields: []const TypeField,
};

const FuncProto = struct {
    name: []const u8,
    argtypes: []const []const u8,
    restype: []const u8,
};

const structs = [_]StructDef{
    .{
        .name = "DeTextBlock",
        .fields = &[_]TypeField{
            .{ .name = "bbox_x0", .ct_type = "c_float" },
            .{ .name = "bbox_y0", .ct_type = "c_float" },
            .{ .name = "bbox_x1", .ct_type = "c_float" },
            .{ .name = "bbox_y1", .ct_type = "c_float" },
            .{ .name = "block_type", .ct_type = "c_int32" },
            .{ .name = "line_count", .ct_type = "c_int32" },
        },
    },
    .{
        .name = "DeTextSpan",
        .fields = &[_]TypeField{
            .{ .name = "bbox_x0", .ct_type = "c_float" },
            .{ .name = "bbox_y0", .ct_type = "c_float" },
            .{ .name = "bbox_x1", .ct_type = "c_float" },
            .{ .name = "bbox_y1", .ct_type = "c_float" },
            .{ .name = "font_name", .ct_type = "c_char", .array_len = 128 },
            .{ .name = "font_size", .ct_type = "c_float" },
            .{ .name = "font_flags", .ct_type = "c_uint32" },
            .{ .name = "color", .ct_type = "c_uint32" },
            .{ .name = "block_idx", .ct_type = "c_int32" },
            .{ .name = "line_idx", .ct_type = "c_int32" },
            .{ .name = "text_ptr", .ct_type = "c_void_p" },
            .{ .name = "text_len", .ct_type = "c_int32" },
        },
    },
    .{
        .name = "DeOutlineEntry",
        .fields = &[_]TypeField{
            .{ .name = "level", .ct_type = "c_int32" },
            .{ .name = "title", .ct_type = "c_char", .array_len = 512 },
            .{ .name = "page_num", .ct_type = "c_int32" },
        },
    },
    .{
        .name = "DeImageInfo",
        .fields = &[_]TypeField{
            .{ .name = "bbox_x0", .ct_type = "c_float" },
            .{ .name = "bbox_y0", .ct_type = "c_float" },
            .{ .name = "bbox_x1", .ct_type = "c_float" },
            .{ .name = "bbox_y1", .ct_type = "c_float" },
            .{ .name = "width", .ct_type = "c_int32" },
            .{ .name = "height", .ct_type = "c_int32" },
            .{ .name = "image_type", .ct_type = "c_int32" },
        },
    },
};

const funcs = [_]FuncProto{
    .{ .name = "de_abi_version", .argtypes = &.{}, .restype = "c_uint32" },
    .{ .name = "de_sizeof_span", .argtypes = &.{}, .restype = "c_int32" },
    .{ .name = "de_sizeof_block", .argtypes = &.{}, .restype = "c_int32" },
    .{ .name = "de_sizeof_outline_entry", .argtypes = &.{}, .restype = "c_int32" },
    .{ .name = "de_sizeof_image_info", .argtypes = &.{}, .restype = "c_int32" },
    .{ .name = "de_init", .argtypes = &.{"c_int64"}, .restype = "c_void_p" },
    .{ .name = "de_destroy", .argtypes = &.{"c_void_p"}, .restype = "None" },
    .{ .name = "de_get_error_message", .argtypes = &.{"c_void_p"}, .restype = "c_char_p" },
    .{ .name = "de_open_document", .argtypes = &.{ "c_void_p", "c_char_p" }, .restype = "c_void_p" },
    .{ .name = "de_close_document", .argtypes = &.{"c_void_p"}, .restype = "None" },
    .{ .name = "de_page_count", .argtypes = &.{"c_void_p"}, .restype = "c_int32" },
    .{ .name = "de_get_metadata", .argtypes = &.{ "c_void_p", "c_char_p", "c_char_p", "c_int32" }, .restype = "c_int32" },
    .{ .name = "de_get_outline", .argtypes = &.{ "c_void_p", "POINTER(POINTER(DeOutlineEntry))", "POINTER(c_int32)" }, .restype = "c_int32" },
    .{ .name = "de_free_outline", .argtypes = &.{ "POINTER(DeOutlineEntry)", "c_int32" }, .restype = "None" },
    .{ .name = "de_load_page", .argtypes = &.{ "c_void_p", "c_int32" }, .restype = "c_void_p" },
    .{ .name = "de_drop_page", .argtypes = &.{"c_void_p"}, .restype = "None" },
    .{ .name = "de_page_width", .argtypes = &.{"c_void_p"}, .restype = "c_float" },
    .{ .name = "de_page_height", .argtypes = &.{"c_void_p"}, .restype = "c_float" },
    .{ .name = "de_get_all_spans", .argtypes = &.{ "c_void_p", "POINTER(POINTER(DeTextSpan))", "POINTER(c_int32)" }, .restype = "c_int32" },
    .{ .name = "de_free_spans", .argtypes = &.{ "POINTER(DeTextSpan)", "c_int32" }, .restype = "None" },
    .{ .name = "de_get_text_blocks", .argtypes = &.{ "c_void_p", "POINTER(POINTER(DeTextBlock))", "POINTER(c_int32)" }, .restype = "c_int32" },
    .{ .name = "de_free_text_blocks", .argtypes = &.{ "POINTER(DeTextBlock)", "c_int32" }, .restype = "None" },
};

pub fn generateTypes(writer: anytype) !void {
    try writer.writeAll("import ctypes\nfrom ctypes import Structure, c_float, c_int32, c_uint32, c_char, c_void_p\n\n");

    for (structs) |s| {
        try writer.print("class {s}(Structure):\n    _fields_ = [\n", .{s.name});
        for (s.fields) |f| {
            if (f.array_len) |len| {
                try writer.print("        (\"{s}\", {s} * {d}),\n", .{ f.name, f.ct_type, len });
            } else {
                try writer.print("        (\"{s}\", {s}),\n", .{ f.name, f.ct_type });
            }
        }
        try writer.writeAll("    ]\n\n");
    }
}

pub fn generatePrototypes(writer: anytype) !void {
    try writer.writeAll("from ctypes import c_int32, c_int64, c_uint32, c_float, c_char_p, c_void_p, POINTER\nfrom ._types import DeTextBlock, DeTextSpan, DeOutlineEntry, DeImageInfo\n\n\ndef bind(lib):\n");

    for (funcs) |f| {
        try writer.print("    lib.{s}.argtypes = [", .{f.name});
        for (f.argtypes, 0..) |a, i| {
            if (i > 0) try writer.writeAll(", ");
            try writer.print("{s}", .{a});
        }
        try writer.writeAll("]\n");
        try writer.print("    lib.{s}.restype = {s}\n", .{ f.name, f.restype });
    }
}

pub fn main(init: std.process.Init.Minimal) !void {
    var args_iter = init.args.iterate();
    _ = args_iter.skip();
    const mode = args_iter.next() orelse return error.MissingArg;
    const out_path = args_iter.next() orelse return error.MissingArg;

    const file = std.c.fopen(out_path.ptr, "w") orelse return error.FileOpenFailed;
    defer _ = std.c.fclose(file);

    var buf: [8192]u8 = undefined;
    var fbs = std.io.fixedBufferStream(&buf);
    const writer = fbs.writer();

    if (std.mem.eql(u8, mode, "types")) {
        try generateTypes(writer);
    } else if (std.mem.eql(u8, mode, "prototypes")) {
        try generatePrototypes(writer);
    } else {
        return error.UnknownMode;
    }

    const written = fbs.getWritten();
    _ = std.c.fwrite(written.ptr, 1, written.len, file);
}
