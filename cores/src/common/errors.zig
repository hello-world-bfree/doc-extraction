pub const DE_OK: i32 = 0;
pub const DE_ERR_NULL_HANDLE: i32 = -1;
pub const DE_ERR_INVALID_HANDLE: i32 = -2;
pub const DE_ERR_FILE_NOT_FOUND: i32 = -3;
pub const DE_ERR_PAGE_RANGE: i32 = -5;
pub const DE_ERR_ALLOC: i32 = -6;
pub const DE_ERR_MUPDF: i32 = -7;
pub const DE_ERR_INVALID_ARG: i32 = -8;

const ERROR_BUF_LEN = 512;

threadlocal var error_buf: [ERROR_BUF_LEN]u8 = [_]u8{0} ** ERROR_BUF_LEN;
threadlocal var error_len: usize = 0;

pub fn setError(msg: []const u8) void {
    const n = @min(msg.len, ERROR_BUF_LEN - 1);
    @memcpy(error_buf[0..n], msg[0..n]);
    error_buf[n] = 0;
    error_len = n;
}

pub fn setErrorFmt(comptime fmt: []const u8, args: anytype) void {
    const n = std.fmt.bufPrint(&error_buf, fmt, args) catch {
        setError("error message too long");
        return;
    };
    error_buf[n.len] = 0;
    error_len = n.len;
}

pub fn getErrorPtr() [*:0]const u8 {
    return @ptrCast(&error_buf);
}

pub fn clearError() void {
    error_buf[0] = 0;
    error_len = 0;
}

const std = @import("std");
