const std = @import("std");

pub const HANDLE_MAGIC: u64 = 0xDECAFE01_DECADE01;
pub const POISONED_MAGIC: u64 = 0xDEAD_DEAD_DEAD_DEAD;
pub const POISONED_GENERATION: u32 = 0xFFFF_FFFF;

var global_generation: std.atomic.Value(u32) = std.atomic.Value(u32).init(0);

pub const HandleHeader = struct {
    magic: u64 = HANDLE_MAGIC,
    generation: u32,

    pub fn init() HandleHeader {
        return .{
            .magic = HANDLE_MAGIC,
            .generation = global_generation.fetchAdd(1, .monotonic),
        };
    }

    pub fn validate(self: *const HandleHeader) bool {
        return self.magic == HANDLE_MAGIC and self.generation != POISONED_GENERATION;
    }

    pub fn poison(self: *HandleHeader) void {
        self.magic = POISONED_MAGIC;
        self.generation = POISONED_GENERATION;
    }
};

pub fn validateHandle(comptime T: type, ptr: ?*T) ?*T {
    const p = ptr orelse return null;
    if (!p.header.validate()) return null;
    return p;
}
