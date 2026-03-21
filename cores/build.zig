const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    const mupdf_prefix = "/opt/homebrew/opt/mupdf";

    const common_handles = b.createModule(.{
        .root_source_file = b.path("src/common/handles.zig"),
        .target = target,
        .optimize = optimize,
    });
    const common_errors = b.createModule(.{
        .root_source_file = b.path("src/common/errors.zig"),
        .target = target,
        .optimize = optimize,
    });

    // ── Shared library: de_mupdf ──

    const lib_mod = b.createModule(.{
        .root_source_file = b.path("src/parsers/mupdf/root.zig"),
        .target = target,
        .optimize = optimize,
        .link_libc = true,
        .imports = &.{
            .{ .name = "handles", .module = common_handles },
            .{ .name = "errors", .module = common_errors },
        },
    });

    lib_mod.addIncludePath(.{ .cwd_relative = mupdf_prefix ++ "/include" });
    lib_mod.addIncludePath(b.path("src/parsers/mupdf"));
    lib_mod.addLibraryPath(.{ .cwd_relative = mupdf_prefix ++ "/lib" });
    lib_mod.linkSystemLibrary("mupdf", .{});

    lib_mod.addCSourceFile(.{
        .file = b.path("src/parsers/mupdf/shim.c"),
        .flags = &.{"-I" ++ mupdf_prefix ++ "/include"},
    });

    const lib = b.addLibrary(.{
        .name = "de_mupdf",
        .linkage = .dynamic,
        .root_module = lib_mod,
    });

    b.installArtifact(lib);

    // Codegen: Python files are generated manually or via script
    // TODO: re-enable Zig codegen exe once Zig 0.16 fs/io APIs stabilize

    // ── Tests ──

    const test_mod = b.createModule(.{
        .root_source_file = b.path("src/parsers/mupdf/root.zig"),
        .target = target,
        .optimize = optimize,
        .link_libc = true,
        .imports = &.{
            .{ .name = "handles", .module = common_handles },
            .{ .name = "errors", .module = common_errors },
        },
    });

    test_mod.addIncludePath(.{ .cwd_relative = mupdf_prefix ++ "/include" });
    test_mod.addIncludePath(b.path("src/parsers/mupdf"));
    test_mod.addLibraryPath(.{ .cwd_relative = mupdf_prefix ++ "/lib" });
    test_mod.linkSystemLibrary("mupdf", .{});

    test_mod.addCSourceFile(.{
        .file = b.path("src/parsers/mupdf/shim.c"),
        .flags = &.{"-I" ++ mupdf_prefix ++ "/include"},
    });

    const tests = b.addTest(.{
        .root_module = test_mod,
    });

    const run_tests = b.addRunArtifact(tests);
    const test_step = b.step("test", "Run unit tests");
    test_step.dependOn(&run_tests.step);
}
