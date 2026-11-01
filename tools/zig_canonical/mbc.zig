//! Canonical Classic Malbolge engine, byte-for-byte with the pinned oracles.
//!
//! Usage: mbc <program.mal> [max_steps] < input > output
//! Exit codes mirror vendor/oracles/mb_ref.c:
//!   0 halt   1 bad args/loader   2 budget exhausted   3 stall   4 stdio failure
//!
//! The specification is the oracle source, not any toolkit interpreter. Three
//! details are where the toolkits part company with Classic, and each is
//! implemented here exactly as the C does:
//!   * `c` and `d` wrap at 59048 (mod 59,049); an engine that grows the tape or
//!     refuses the address instead cannot run a stdin-fed program past the edge.
//!   * `in` at end of stream yields 3^padwidth - 1 = 59048, not 0 and not -1.
//!   * a non-printable cell under the program counter, or left behind by the
//!     post-instruction encryption, is a STALL with exit 3 -- never a NOP.
//! The 9x9 crazy table is indexed [y digit][x digit]; swapped operands are a
//! different algebra, so `crazy(x, y)` keeps the oracle's argument order and its
//! table orientation together.
//!
//! `step` counts instructions that completed the loop body, so the halting `v`
//! is counted; that matches the step counts pinned in
//! manifest/translation_manifest.json and reported by the other engines.

const std = @import("std");

const MEMORY_SIZE: usize = 59049;
const WRAP_LAST: usize = 59048;
const EOF_VALUE: u16 = 59048; // 3^padwidth - 1
const DEFAULT_STEPS: u64 = 100_000_000;

const XLAT1_RAW: []const u8 = "+b(29e*j1VMEKLyC})8&m#~W>qxdRp0wkrUo[D7,XTcA\"lI" ++
    ".v%{gJh4G\\-=O@5`_3i<?Z';FNQuY]szf$!BS/|t:Pn6^Ha";
const XLAT2_RAW: []const u8 = "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1C" ++
    "B6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";

const VALID_OPCODES = "ji*p</vo";

const CRAZY: [9][9]u8 = .{
    .{ 4, 3, 3, 1, 0, 0, 1, 0, 0 },
    .{ 4, 3, 5, 1, 0, 2, 1, 0, 2 },
    .{ 5, 5, 4, 2, 2, 1, 2, 2, 1 },
    .{ 4, 3, 3, 1, 0, 0, 7, 6, 6 },
    .{ 4, 3, 5, 1, 0, 2, 7, 6, 8 },
    .{ 5, 5, 4, 2, 2, 1, 8, 8, 7 },
    .{ 7, 6, 6, 7, 6, 6, 4, 3, 3 },
    .{ 7, 6, 8, 7, 6, 8, 4, 3, 5 },
    .{ 8, 8, 7, 8, 8, 7, 5, 5, 4 },
};

fn translation(comptime raw: []const u8) [94]u8 {
    if (raw.len != 94) @compileError("translation table must be exactly 94 bytes");
    var table: [94]u8 = undefined;
    for (raw, 0..) |byte, index| table[index] = byte;
    if (std.mem.indexOfScalar(u8, &table, 0) != null) @compileError("table contains NUL");
    return table;
}

const XLAT1 = translation(XLAT1_RAW);
const XLAT2 = translation(XLAT2_RAW);

fn crazy(x: u16, y: u16) u16 {
    var result: u16 = 0;
    var place: u16 = 1;
    var i: usize = 0;
    while (i < 5) : (i += 1) {
        const x_digit: usize = @intCast((x / place) % 9);
        const y_digit: usize = @intCast((y / place) % 9);
        result += @as(u16, CRAZY[y_digit][x_digit]) * place;
        place *= 9;
    }
    return result;
}

fn rot(value: u16) u16 {
    return value / 3 + (value % 3) * 19683;
}

/// Encode an opcode letter for a given cell position, the inverse of the
/// loader's decode. Kept here because the corpus generator depends on it.
fn opcode_cell(op: u8, position: usize) u8 {
    const index = std.mem.indexOfScalar(u8, &XLAT1, op) orelse unreachable;
    return @intCast((index + 94 - (position % 94)) % 94 + 33);
}

var mem: [MEMORY_SIZE]u16 = undefined;
var io_ref: std.Io = undefined;

fn note(comptime fmt: []const u8, args: anytype) void {
    var buffer: [512]u8 = undefined;
    const message = std.fmt.bufPrint(&buffer, fmt, args) catch return;
    std.Io.File.stderr().writeStreamingAll(io_ref, message) catch {};
}

fn finish(code: u8) noreturn {
    std.process.exit(code);
}

const Reason = enum { halt, budget, stall, stdio };

const Halt = struct {
    steps: u64,
    reason: Reason,

    fn label(self: Halt) []const u8 {
        return switch (self.reason) {
            .halt => "halt",
            .budget => "budget",
            .stall => "stall",
            .stdio => "stdio",
        };
    }
};

/// One value read from stdin, with the oracle's sticky end-of-stream: once the
/// stream is done, every later read yields EOF_VALUE without another syscall.
const Input = struct {
    source: std.Io.File.Reader,
    ended: bool = false,

    fn value(self: *Input) u16 {
        if (self.ended) return EOF_VALUE;
        const byte = self.source.interface.takeByte() catch |err| {
            self.ended = true;
            if (err != error.EndOfStream) note("INPUT_ERROR\n", .{});
            return EOF_VALUE;
        };
        return byte;
    }
};

/// Strict unsigned decimal, like the oracle's strspn + strtoull pair.
fn parse_budget(text: []const u8) ?u64 {
    if (text.len == 0) return null;
    for (text) |byte| {
        if (byte < '0' or byte > '9') return null;
    }
    return std.fmt.parseInt(u64, text, 10) catch null;
}

fn is_space(byte: u8) bool {
    return switch (byte) {
        9, 10, 11, 12, 13, 32 => true,
        else => false,
    };
}

const LoaderError = error{
    Open,
    InvalidCharacter,
    TooLong,
    InvalidOpcode,
    ReadError,
    TooShort,
};

/// The oracle's loader, including the order of its checks: whitespace is not a
/// cell at all, the range test comes before the length test, and every loaded
/// cell must decode to one of the eight legal opcodes at its own position.
fn load(path: []const u8, buffer: []u8) LoaderError!void {
    const io = io_ref;
    var file = std.Io.Dir.cwd().openFile(io, path, .{}) catch {
        note("Cannot open {s}\n", .{path});
        return LoaderError.Open;
    };
    defer file.close(io);

    var file_reader = file.reader(io, buffer);
    var count: usize = 0;
    while (true) {
        const byte = file_reader.interface.takeByte() catch |err| switch (err) {
            error.EndOfStream => break,
            else => {
                note("READ_ERROR\n", .{});
                return LoaderError.ReadError;
            },
        };
        if (is_space(byte)) continue;
        if (byte < 33 or byte > 126) {
            note("Invalid character 0x{x:0>2}\n", .{byte});
            return LoaderError.InvalidCharacter;
        }
        if (count == MEMORY_SIZE) {
            note("Input program too long\n", .{});
            return LoaderError.TooLong;
        }
        const opcode = XLAT1[(@as(usize, byte) - 33 + count) % 94];
        if (std.mem.indexOfScalar(u8, VALID_OPCODES, opcode) == null) {
            note("INVALID_OPCODE: cell {d}\n", .{count});
            return LoaderError.InvalidOpcode;
        }
        mem[count] = byte;
        count += 1;
    }
    if (count < 2) {
        note("TOO_SHORT: need at least two cells\n", .{});
        return LoaderError.TooShort;
    }
    while (count < MEMORY_SIZE) : (count += 1) {
        mem[count] = crazy(mem[count - 1], mem[count - 2]);
    }
}

fn stallAddress(target: u16, step: u64) Halt {
    note("INVALID_ADDRESS: value {d} step {d}\n", .{ target, step });
    return .{ .steps = step, .reason = .stall };
}

/// The machine. `d` and `c` are addresses into the fixed tape; both wrap at the
/// last cell, which is what makes a stdin-fed program keep running.
fn run(max_steps: u64, input: *Input, out: *std.Io.File.Writer) Halt {
    var a: u16 = 0;
    var c: usize = 0;
    var d: usize = 0;
    var step: u64 = 0;
    while (step < max_steps) : (step += 1) {
        const pc: usize = @intCast(mem[c]);
        if (pc < 33 or pc > 126) {
            note("NONPRINTABLE_PC: cell {d} value {d} step {d}\n", .{ c, pc, step });
            return .{ .steps = step, .reason = .stall };
        }
        switch (XLAT1[(pc - 33 + c) % 94]) {
            'j' => {
                const target = mem[d];
                if (target > WRAP_LAST) return stallAddress(target, step);
                d = target;
            },
            'i' => {
                const target = mem[d];
                if (target > WRAP_LAST) return stallAddress(target, step);
                c = target;
            },
            '*' => {
                a = rot(mem[d]);
                mem[d] = a;
            },
            'p' => {
                a = crazy(a, mem[d]);
                mem[d] = a;
            },
            '<' => {
                out.interface.writeByte(@intCast(a & 0xFF)) catch {
                    note("OUTPUT_ERROR\n", .{});
                    return .{ .steps = step + 1, .reason = .stdio };
                };
            },
            '/' => {
                a = input.value();
            },
            'v' => return .{ .steps = step + 1, .reason = .halt },
            else => {},
        }
        const encrypted: usize = @intCast(mem[c]);
        if (encrypted < 33 or encrypted > 126) {
            note("INVALID_ENCRYPTION: cell {d} value {d} step {d}\n", .{ c, encrypted, step });
            return .{ .steps = step, .reason = .stall };
        }
        mem[c] = XLAT2[encrypted - 33];
        c = if (c == WRAP_LAST) 0 else c + 1;
        d = if (d == WRAP_LAST) 0 else d + 1;
    }
    note("MAX_STEPS: {d} (HALT not reached)\n", .{max_steps});
    return .{ .steps = step, .reason = .budget };
}

/// Reset the tape and load one program: the entry point the search port calls
/// when it wants a machine in a known state.
pub fn prepare(path: []const u8, buffer: []u8) LoaderError!void {
    @memset(&mem, 0);
    try load(path, buffer);
}

pub fn main(init: std.process.Init) noreturn {
    io_ref = init.io;
    const io = init.io;
    const arena = init.arena.allocator();

    const args = init.minimal.args.toSlice(arena) catch {
        note("Usage: mbc <program.mal> [max_steps]\n", .{});
        finish(1);
    };
    if (args.len < 2 or args.len > 3) {
        note("Usage: mbc <program.mal> [max_steps]\n", .{});
        finish(1);
    }
    var max_steps = DEFAULT_STEPS;
    if (args.len == 3) {
        max_steps = parse_budget(args[2]) orelse {
            note("INVALID_BUDGET: expected unsigned decimal integer\n", .{});
            finish(1);
        };
    }

    var load_buffer: [1 << 16]u8 = undefined;
    prepare(args[1], &load_buffer) catch finish(1);

    var out_buffer: [1 << 16]u8 = undefined;
    var out = std.Io.File.stdout().writer(io, &out_buffer);
    var stdin_buffer: [1 << 16]u8 = undefined;
    var input = Input{ .source = std.Io.File.stdin().readerStreaming(io, &stdin_buffer) };

    const halt = run(max_steps, &input, &out);
    out.interface.flush() catch {
        note("OUTPUT_ERROR\n", .{});
        finish(4);
    };
    note("steps={d} reason={s}\n", .{ halt.steps, halt.label() });
    finish(switch (halt.reason) {
        .halt => 0,
        .budget => 2,
        .stall => 3,
        .stdio => 4,
    });
}

test "crazy keeps the oracle's table orientation" {
    // Values are 5 base-9 digits (trit pairs); the all-4 result is the floor of
    // the table, and 59048 = 9^5 - 1 is its ceiling.
    try std.testing.expectEqual(@as(u16, 29524), crazy(0, 0));
    try std.testing.expectEqual(@as(u16, 29523), crazy(1, 0));
    try std.testing.expectEqual(@as(u16, 29523), crazy(2, 0));
    // Asymmetric: the digit pair is looked up [y][x], never [x][y].
    try std.testing.expectEqual(@as(u16, 29523), crazy(1, 4));
    try std.testing.expectEqual(@as(u16, 29520), crazy(4, 1));
    // 59048 is eight in every base-9 digit: as the y operand it drives the
    // table to its maximum, as the x operand it lands on the all-4 floor.
    try std.testing.expectEqual(@as(u16, 59048), crazy(0, 59048));
    try std.testing.expectEqual(@as(u16, 29524), crazy(59048, 59048));
    try std.testing.expectEqual(@as(u16, 59048), rot(59048));
}

test "rot stays inside the address space" {
    try std.testing.expectEqual(@as(u16, 0), rot(0));
    try std.testing.expectEqual(@as(u16, 19683), rot(1));
    try std.testing.expectEqual(@as(u16, 59048), rot(59048));
}

test "decode inverts the corpus encoder for every opcode" {
    for (VALID_OPCODES) |op| {
        var position: usize = 0;
        while (position < MEMORY_SIZE) : (position += 997) {
            const cell = opcode_cell(op, position);
            try std.testing.expectEqual(op, XLAT1[(@as(usize, cell) - 33 + position) % 94]);
        }
    }
}

test "exactly the eight legal opcodes occur in the decode table" {
    var legal: usize = 0;
    for (XLAT1) |opcode| {
        if (std.mem.indexOfScalar(u8, VALID_OPCODES, opcode) != null) legal += 1;
    }
    try std.testing.expectEqual(@as(usize, 8), legal);
    try std.testing.expectEqual(@as(u16, 59048), EOF_VALUE);
}

test "budget parsing is strict unsigned decimal" {
    try std.testing.expectEqual(@as(u64, 100), parse_budget("100"));
    try std.testing.expectEqual(@as(u64, 3000000000), parse_budget("3000000000"));
    try std.testing.expectEqual(@as(u64, 18446744073709551615), parse_budget("18446744073709551615"));
    try std.testing.expectEqual(@as(?u64, null), parse_budget(""));
    try std.testing.expectEqual(@as(?u64, null), parse_budget("1_0"));
    try std.testing.expectEqual(@as(?u64, null), parse_budget("-1"));
    try std.testing.expectEqual(@as(?u64, null), parse_budget("12x"));
    try std.testing.expectEqual(@as(?u64, null), parse_budget("18446744073709551616"));
}
