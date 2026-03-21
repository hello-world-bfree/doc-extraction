const std = @import("std");
const mupdf = @import("c.zig");
const errors = @import("errors");


pub const MemoryTracker = struct {
    allocated: std.atomic.Value(i64),
    limit: i64,

    pub fn init(limit: i64) MemoryTracker {
        return .{
            .allocated = std.atomic.Value(i64).init(0),
            .limit = limit,
        };
    }

    pub fn canAllocate(self: *MemoryTracker, size: usize) bool {
        if (self.limit <= 0) return true;
        const current = self.allocated.load(.monotonic);
        return current + @as(i64, @intCast(size)) <= self.limit;
    }

    pub fn trackAlloc(self: *MemoryTracker, size: usize) void {
        _ = self.allocated.fetchAdd(@intCast(size), .monotonic);
    }

    pub fn trackFree(self: *MemoryTracker, size: usize) void {
        _ = self.allocated.fetchSub(@intCast(size), .monotonic);
    }
};

pub fn createTrackedContext(max_memory: i64) ?*mupdf.fz_context {
    if (max_memory <= 0) {
        return mupdf.fz_new_context(null, null, mupdf.FZ_STORE_DEFAULT);
    }

    const tracker = std.heap.c_allocator.create(MemoryTracker) catch return null;
    tracker.* = MemoryTracker.init(max_memory);

    const alloc = std.heap.c_allocator.create(mupdf.fz_alloc_context) catch {
        std.heap.c_allocator.destroy(tracker);
        return null;
    };
    alloc.* = .{
        .user = tracker,
        .malloc = trackedMalloc,
        .realloc = trackedRealloc,
        .free = trackedFree,
    };

    return mupdf.fz_new_context(alloc, null, mupdf.FZ_STORE_DEFAULT);
}

fn trackedMalloc(user: ?*anyopaque, size: usize) callconv(.c) ?*anyopaque {
    const tracker: *MemoryTracker = @ptrCast(@alignCast(user));
    if (!tracker.canAllocate(size + @sizeOf(usize))) return null;

    const full_size = size + @sizeOf(usize);
    const raw = std.c.malloc(full_size) orelse return null;
    const header: *usize = @ptrCast(@alignCast(raw));
    header.* = size;
    tracker.trackAlloc(full_size);
    return @ptrFromInt(@intFromPtr(raw) + @sizeOf(usize));
}

fn trackedRealloc(user: ?*anyopaque, old: ?*anyopaque, size: usize) callconv(.c) ?*anyopaque {
    const tracker: *MemoryTracker = @ptrCast(@alignCast(user));

    if (old == null) return trackedMalloc(user, size);

    const old_raw = @as(*anyopaque, @ptrFromInt(@intFromPtr(old.?) - @sizeOf(usize)));
    const old_header: *usize = @ptrCast(@alignCast(old_raw));
    const old_size = old_header.*;

    if (size > old_size) {
        const delta = size - old_size;
        if (!tracker.canAllocate(delta)) return null;
    }

    const full_size = size + @sizeOf(usize);
    const raw = std.c.realloc(old_raw, full_size) orelse return null;
    const header: *usize = @ptrCast(@alignCast(raw));

    tracker.trackFree(old_size + @sizeOf(usize));
    header.* = size;
    tracker.trackAlloc(full_size);

    return @ptrFromInt(@intFromPtr(raw) + @sizeOf(usize));
}

fn trackedFree(user: ?*anyopaque, ptr: ?*anyopaque) callconv(.c) void {
    if (ptr == null) return;
    const tracker: *MemoryTracker = @ptrCast(@alignCast(user));
    const raw = @as(*anyopaque, @ptrFromInt(@intFromPtr(ptr.?) - @sizeOf(usize)));
    const header: *usize = @ptrCast(@alignCast(raw));
    const size = header.*;
    tracker.trackFree(size + @sizeOf(usize));
    std.c.free(raw);
}
