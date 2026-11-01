//! Level-2 synthesis search, ported from malbolge-generator 0.1.0's
//! `generate_for_string` onto the canonical Classic tape that `mbc.zig` runs.
//!
//! Usage: mbsearch --target-file F [--out P] [--stats P] [--depth N]
//!                 [--choices op*] [--seed N] [--budget N]
//!
//! The machine is Classic, exactly as `mbc.zig` implements it: 59,049 fixed
//! cells filled at load by the crazy recurrence, `c`/`d` wrapping at 59,048,
//! `in` with no stdin yielding 59,048, and a non-printable cell under the
//! program counter being a stall rather than a NOP. The loader and step loop
//! are reproduced here instead of imported because the search needs two things
//! a one-shot runner does not: writes tracked in a delta log, so a rejected
//! candidate is undone without touching 59,049 cells, and a per-candidate halt
//! threshold.
//!
//! That threshold is the one deliberate deviation from Classic, and it is what
//! makes the port a port of the reference rather than a new searcher. The
//! reference never lets a candidate run to completion: it stops as soon as `c`
//! reaches `len(tape) + len(suffix)`, which the toolkit reports as
//! `halt_reason = "program_end"`. Measured over 101,404 candidate evaluations
//! on this corpus: 101,403 ended at `program_end` and one at the `v` halt,
//! steps per candidate were 1..6, and `len(tape)` equalled the opcode count at
//! every call, so no candidate ever read a cell past its own program. An
//! emulated threshold therefore chooses the search's trajectory without
//! changing what a finished program does, because a finished program reaches
//! its own `v` long before `c` could reach the threshold.
//!
//! Where Classic and the toolkit could still part company, this port follows
//! Classic and counts the event, so a divergence shows up in `--stats` instead
//! of passing silently: `stall` (toolkit: raises, aborting the whole
//! generation), `/` with no stdin (toolkit: raises), a budget-exhausted
//! candidate (toolkit: no limit at all), and `peak` beyond the opcode count
//! (toolkit: tail cells grown lazily from different neighbours than the
//! load-time recurrence would give).
//!
//! Pruning keeps the reference's two-level state tables and its exact decision
//! order: accepted / prefix-mismatch / repeated-state / collision. The state
//! cache is dropped rather than faked -- it is keyed by program string and
//! returns states identical to recomputation, so it can only change speed, and
//! the reference measured 0 hits across 101,404 evaluations.
//!
//! Acceptance is the envelope: the emitted program must print `--target-file`'s
//! bytes exactly, and it is checked twice -- once in-process by
//! `verifyCanonical`, which loads the finished program and runs it with no
//! threshold at all, and once outside by `mbc` in `tools/mbsearch_gate.py`.
//! Byte-equality with `generate_for_string` is a separate question, and it has
//! no RNG-free configuration: the reference reaches `rng.choice` on every
//! corpus target whatever the cap (234 calls at `--depth 5`, still 8 at
//! `--depth 12`, because a target byte sometimes needs a non-printing state
//! change rather than a longer candidate word). The gate therefore pins both
//! sides to one stream -- `SharedStream` in `tools/mbsearch_gate.py` is this
//! file's `Rng` copied into Python -- and measures 12/12 identical programs at
//! `--depth 5` and 30/30 at `--depth 3`, with equal `evaluations` and equal
//! choice counts per target.

const std = @import("std");

const MEMORY_SIZE: usize = 59049;
const WRAP_LAST: usize = 59048;
const EOF_VALUE: u16 = 59048; // 3^padwidth - 1
const SIG_TAIL: usize = 8; // generator.SIGNATURE_TAPE_WIDTH
const CAND_CAP: usize = 15; // a frontier word is `depth` opcodes long
const DELTA_CAP: usize = 8192;
const BOOTSTRAP_OPS: usize = 100; // "i" + "o" * 99
const BOOTSTRAP_PREFIX = "io";
const VALID_OPCODES = "ji*p</vo";

const XLAT1_RAW: []const u8 = "+b(29e*j1VMEKLyC})8&m#~W>qxdRp0wkrUo[D7,XTcA\"lI" ++
    ".v%{gJh4G\\-=O@5`_3i<?Z';FNQuY]szf$!BS/|t:Pn6^Ha";
const XLAT2_RAW: []const u8 = "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1C" ++
    "B6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";

fn translation(comptime raw: []const u8) [94]u8 {
    if (raw.len != 94) @compileError("translation table must be exactly 94 bytes");
    var table: [94]u8 = undefined;
    for (raw, 0..) |byte, index| table[index] = byte;
    return table;
}

const XLAT1 = translation(XLAT1_RAW);
const XLAT2 = translation(XLAT2_RAW);

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

/// `encoding.reverse_normalize` for one opcode at one cell position: the
/// inverse of the loader's decode, so the cell always reads back as `op`.
fn opcodeCell(op: u8, position: usize) u8 {
    const index = std.mem.indexOfScalar(u8, &XLAT1, op) orelse unreachable;
    return @intCast((index + 94 - (position % 94)) % 94 + 33);
}

fn decodeOpcode(cell: u16, position: usize) u8 {
    return XLAT1[(@as(usize, cell) - 33 + position) % 94];
}

/// Stand-in for `random.Random(seed).choice`. The reference draws through
/// CPython's MT19937, so this matches it in shape -- an unbiased draw below
/// `n`, with `n` the number of live frontier words -- but not in which word
/// comes out. It only matters inside the `depth >= max_search_depth` branch.
const Rng = struct {
    state: u64,

    fn init(seed: u64) Rng {
        return .{ .state = seed +% 0x9E3779B97F4A7C15 };
    }

    fn next(self: *Rng) u64 {
        self.state +%= 0x9E3779B97F4A7C15;
        var z = self.state;
        z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9;
        z = (z ^ (z >> 27)) * 0x94D049BB133111EB;
        return z ^ (z >> 31);
    }

    fn below(self: *Rng, n: u64) u64 {
        const limit = std.math.maxInt(u64) - (std.math.maxInt(u64) % n);
        var value = self.next();
        while (value >= limit) value = self.next();
        return value % n;
    }
};

/// One frontier word: opcodes appended to the accepted prefix, no terminator.
const Cand = struct {
    n: u8 = 0,
    chars: [CAND_CAP]u8 = std.mem.zeroes([CAND_CAP]u8),

    fn slice(self: *const Cand) []const u8 {
        return self.chars[0..self.n];
    }
};

/// Dead-program key. The reference keys on `prefix_opcodes ++ candidate ++ "<"`;
/// inside one generation the accepted prefix is unique per length, so
/// (prefix length, candidate, terminator) is the same bijection without copying
/// two kilobytes per lookup.
const DeadKey = struct {
    plen: u32,
    cand: Cand,
    halt: bool,
};

/// `_fallback_signature` (a whole) and `_state_signature` (a folded to 8 bits):
/// one tuple shape, two tables, as in the reference.
const Sig = struct {
    peak: u32,
    a: u32,
    c: u32,
    d: u32,
    tail: [SIG_TAIL]u16 = std.mem.zeroes([SIG_TAIL]u16),
};

const DeadMap = std.array_hash_map.Auto(DeadKey, void);
const SigMap = std.array_hash_map.Auto(Sig, u32);

const Term = enum(u8) {
    program_end,
    halt,
    stall,
    budget,

    fn label(self: Term) []const u8 {
        return switch (self) {
            .program_end => "program_end",
            .halt => "halt_opcode",
            .stall => "stall",
            .budget => "budget",
        };
    }
};

const Run = struct {
    term: Term = .program_end,
    steps: u64 = 0,
    a: u16 = 0,
    c: usize = 0,
    d: usize = 0,
    peak: u32 = 0,
};

const Stats = struct {
    evaluations: u64 = 0,
    steps_total: u64 = 0,
    max_steps: u64 = 0,
    pruned: u64 = 0,
    repeated_state_pruned: u64 = 0,
    dead_cache_hits: u64 = 0,
    collisions: u64 = 0,
    rng_choices: u64 = 0,
    rng_pruned: u64 = 0,
    stalls: u64 = 0,
    budgets: u64 = 0,
    slashes: u64 = 0,
    peak_gaps: u64 = 0,
    delta_overflows: u64 = 0,
    wraps: u64 = 0,
};

var mem: [MEMORY_SIZE]u16 = undefined;
var checkpoint: [MEMORY_SIZE]u16 = undefined;
var delta_index: [DELTA_CAP]u32 = undefined;
var delta_value: [DELTA_CAP]u16 = undefined;
var delta_len: usize = 0;
var delta_overflow = false;
var overflows_total: u64 = 0;

/// Every write to the tape is logged with the value it replaced, which is what
/// makes a rejected candidate cost a handful of stores instead of a 118 KB copy.
inline fn trackCell(index: usize, value: u16) void {
    if (delta_len < DELTA_CAP) {
        delta_index[delta_len] = @intCast(index);
        delta_value[delta_len] = mem[index];
        delta_len += 1;
    } else {
        if (!delta_overflow) overflows_total += 1;
        delta_overflow = true;
    }
    mem[index] = value;
}

fn rollbackCells() void {
    if (delta_overflow) {
        delta_overflow = false;
        @memcpy(&mem, &checkpoint);
        delta_len = 0;
        return;
    }
    var k = delta_len;
    while (k > 0) {
        k -= 1;
        mem[delta_index[k]] = delta_value[k];
    }
    delta_len = 0;
}

const Searcher = struct {
    gpa: std.mem.Allocator,
    choices: []const u8,
    depth_cap: u32,
    budget: u64,
    rng: Rng,
    stats: Stats = .{},

    opcodes: std.ArrayList(u8) = .empty,
    output: std.ArrayList(u8) = .empty,
    frontier: std.ArrayList(Cand) = .empty,
    spare: std.ArrayList(Cand) = .empty,
    viable: std.ArrayList(Cand) = .empty,
    dead: DeadMap = .empty,
    seen: SigMap = .empty,
    canonical: SigMap = .empty,
    suffix_buffer: [CAND_CAP + 1]u8 = std.mem.zeroes([CAND_CAP + 1]u8),

    /// The reference's `prefix_state.machine`: the accepted tape plus the
    /// scalars it halted on, from which every candidate is evaluated.
    cp_a: u16 = 0,
    cp_c: usize = 0,
    cp_d: usize = 0,
    cp_peak: u32 = 0,

    fn deinit(self: *Searcher) void {
        self.opcodes.deinit(self.gpa);
        self.output.deinit(self.gpa);
        self.frontier.deinit(self.gpa);
        self.spare.deinit(self.gpa);
        self.viable.deinit(self.gpa);
        self.dead.deinit(self.gpa);
        self.seen.deinit(self.gpa);
        self.canonical.deinit(self.gpa);
    }

    /// Classic load of the bootstrap, then the reference's first run: the tape
    /// is 100 cells long, so `_program_length` is 100.
    fn loadBootstrap(self: *Searcher) !Run {
        try self.opcodes.append(self.gpa, 'i');
        for (0..99) |_| try self.opcodes.append(self.gpa, 'o');
        for (self.opcodes.items, 0..) |op, position| {
            mem[position] = opcodeCell(op, position);
        }
        var count: usize = BOOTSTRAP_OPS;
        while (count < MEMORY_SIZE) : (count += 1) {
            mem[count] = crazy(mem[count - 1], mem[count - 2]);
        }
        const run = self.execute("", BOOTSTRAP_OPS);
        // The reference counts only candidate extensions; dropping this one
        // keeps `evaluations` directly comparable with `generate_for_string`.
        self.stats.evaluations -= 1;
        return run;
    }

    /// Evaluate one candidate. Leaves its writes on the tape and its bytes in
    /// `output`; the caller either `commit`s them or rolls them back.
    fn execute(self: *Searcher, suffix: []const u8, start_peak: u32) Run {
        const threshold: u64 = @as(u64, start_peak) + suffix.len;
        var run = Run{ .a = self.cp_a, .c = self.cp_c, .d = self.cp_d, .peak = start_peak };
        delta_len = 0;
        delta_overflow = false;
        for (suffix, 0..) |op, offset| {
            const pos = start_peak + offset;
            trackCell(pos, opcodeCell(op, pos));
            if (pos + 1 > run.peak) run.peak = @intCast(pos + 1);
        }
        while (run.steps < self.budget) : (run.steps += 1) {
            if (run.c >= threshold) {
                run.term = .program_end;
                break;
            }
            if (run.c + 1 > run.peak) run.peak = @intCast(run.c + 1);
            const pc = mem[run.c];
            if (pc < 33 or pc > 126) {
                run.term = .stall;
                self.stats.stalls += 1;
                break;
            }
            switch (decodeOpcode(pc, run.c)) {
                'j' => {
                    if (run.d + 1 > run.peak) run.peak = @intCast(run.d + 1);
                    const target = mem[run.d];
                    if (target > WRAP_LAST) {
                        run.term = .stall;
                        self.stats.stalls += 1;
                        break;
                    }
                    run.d = target;
                    if (run.d + 1 > run.peak) run.peak = @intCast(run.d + 1);
                },
                'i' => {
                    if (run.d + 1 > run.peak) run.peak = @intCast(run.d + 1);
                    const target = mem[run.d];
                    if (target > WRAP_LAST) {
                        run.term = .stall;
                        self.stats.stalls += 1;
                        break;
                    }
                    run.c = target;
                    if (run.c + 1 > run.peak) run.peak = @intCast(run.c + 1);
                },
                '*' => {
                    if (run.d + 1 > run.peak) run.peak = @intCast(run.d + 1);
                    run.a = rot(mem[run.d]);
                    trackCell(run.d, run.a);
                },
                'p' => {
                    if (run.d + 1 > run.peak) run.peak = @intCast(run.d + 1);
                    run.a = crazy(run.a, mem[run.d]);
                    trackCell(run.d, run.a);
                },
                '<' => self.output.append(self.gpa, @intCast(run.a & 0xFF)) catch {
                    run.term = .stall;
                    break;
                },
                '/' => {
                    run.a = EOF_VALUE;
                    self.stats.slashes += 1;
                },
                'v' => {
                    run.steps += 1;
                    run.term = .halt;
                    break;
                },
                else => {},
            }
            const encrypted = mem[run.c];
            if (encrypted < 33 or encrypted > 126) {
                run.term = .stall;
                self.stats.stalls += 1;
                break;
            }
            trackCell(run.c, XLAT2[encrypted - 33]);
            if (run.c == WRAP_LAST or run.d == WRAP_LAST) self.stats.wraps += 1;
            run.c = if (run.c == WRAP_LAST) 0 else run.c + 1;
            run.d = if (run.d == WRAP_LAST) 0 else run.d + 1;
        } else {
            run.term = .budget;
            self.stats.budgets += 1;
        }
        self.stats.evaluations += 1;
        self.stats.steps_total += run.steps;
        if (run.steps > self.stats.max_steps) self.stats.max_steps = run.steps;
        if (run.peak > self.opcodes.items.len + suffix.len) self.stats.peak_gaps += 1;
        return run;
    }

    fn signature(run: Run, fold_a: bool) Sig {
        var sig = Sig{
            .peak = run.peak,
            .a = if (fold_a) run.a % 256 else run.a,
            .c = @intCast(run.c),
            .d = @intCast(run.d),
        };
        const width: usize = @min(SIG_TAIL, run.peak);
        const base: usize = run.peak - width;
        for (0..width) |i| sig.tail[i] = mem[base + i];
        return sig;
    }

    fn commit(self: *Searcher, suffix: []const u8, run: Run) !void {
        @memcpy(&checkpoint, &mem);
        self.cp_a = run.a;
        self.cp_c = run.c;
        self.cp_d = run.d;
        self.cp_peak = run.peak;
        delta_len = 0;
        delta_overflow = false;
        try self.opcodes.appendSlice(self.gpa, suffix);
    }

    fn discard(self: *Searcher, saved_output: usize) void {
        rollbackCells();
        self.output.shrinkRetainingCapacity(saved_output);
    }

    fn fits(self: *Searcher, extra: usize) bool {
        return self.opcodes.items.len + extra <= MEMORY_SIZE;
    }

    fn candidateSuffix(self: *Searcher, cand: Cand, terminator: ?u8) []const u8 {
        const head = cand.slice();
        @memcpy(self.suffix_buffer[0..head.len], head);
        if (terminator) |ch| {
            self.suffix_buffer[head.len] = ch;
            return self.suffix_buffer[0 .. head.len + 1];
        }
        return self.suffix_buffer[0..head.len];
    }

    fn isDead(self: *Searcher, cand: Cand, halt: bool) bool {
        return self.dead.get(.{
            .plen = @intCast(self.opcodes.items.len),
            .cand = cand,
            .halt = halt,
        }) != null;
    }

    fn markDead(self: *Searcher, cand: Cand, halt: bool) !void {
        try self.dead.put(self.gpa, .{
            .plen = @intCast(self.opcodes.items.len),
            .cand = cand,
            .halt = halt,
        }, {});
    }

    /// The reference stores `max(known, length)` into both tables, creating the
    /// entry with `length` when it has not been seen.
    fn remember(self: *Searcher, sig: Sig, table: *SigMap, length: u32) !void {
        const gop = try table.getOrPut(self.gpa, sig);
        if (gop.found_existing) {
            if (length > gop.value_ptr.*) gop.value_ptr.* = length;
        } else {
            gop.value_ptr.* = length;
        }
    }

    fn baseFrontier(self: *Searcher) !void {
        self.frontier.clearRetainingCapacity();
        for (self.choices) |op| {
            var cand: Cand = .{};
            cand.chars[0] = op;
            cand.n = 1;
            try self.frontier.append(self.gpa, cand);
        }
    }

    fn growFrontier(self: *Searcher) !void {
        self.spare.clearRetainingCapacity();
        for (self.frontier.items) |base| {
            if (base.n >= CAND_CAP) return error.CandidateTooLong;
            for (self.choices) |op| {
                var next = base;
                next.chars[next.n] = op;
                next.n += 1;
                if (self.isDead(next, false)) continue;
                try self.spare.append(self.gpa, next);
            }
        }
        std.mem.swap(std.ArrayList(Cand), &self.frontier, &self.spare);
    }

    fn liveCandidates(self: *Searcher) ![]const Cand {
        self.viable.clearRetainingCapacity();
        for (self.frontier.items) |cand| {
            if (self.isDead(cand, false)) continue;
            try self.viable.append(self.gpa, cand);
        }
        return self.viable.items;
    }

    /// The per-target-byte search, statement for statement with the reference's
    /// inner loop: try the frontier, deepen it if nothing printed this byte, and
    /// let the RNG step sideways once `depth` reaches the cap.
    fn searchChar(self: *Searcher, target: []const u8, index: usize) !void {
        const wanted: u32 = @intCast(index + 1);
        var depth: u32 = 0;
        try self.baseFrontier();

        while (true) {
            depth += 1;
            for (self.frontier.items) |cand| {
                if (self.isDead(cand, false)) {
                    self.stats.pruned += 1;
                    self.stats.dead_cache_hits += 1;
                    continue;
                }
                const terminator: u8 = '<';
                const suffix = self.candidateSuffix(cand, terminator);
                if (!self.fits(suffix.len)) return error.ProgramTooLong;
                const saved_output = self.output.items.len;
                const run = self.execute(suffix, self.cp_peak);
                const length: u32 = @intCast(self.output.items.len);
                const printed = self.output.items;
                const fallback = signature(run, false);
                const exact = signature(run, true);
                const known = self.seen.get(fallback);
                const previous = self.canonical.get(exact);
                const is_new = known == null or length > known.?;
                const is_new_by_signature = previous == null or length > previous.?;
                const valid_prefix = length <= target.len and
                    std.mem.eql(u8, printed[0..length], target[0..length]);

                if (valid_prefix and length == wanted) {
                    try self.remember(fallback, &self.seen, @max(known orelse 0, length));
                    try self.remember(exact, &self.canonical, @max(previous orelse 0, length));
                    try self.commit(suffix, run);
                    return;
                }
                if (!valid_prefix) {
                    self.stats.pruned += 1;
                    try self.markDead(cand, false);
                    self.discard(saved_output);
                    continue;
                }
                if (!is_new) {
                    self.stats.pruned += 1;
                    self.stats.repeated_state_pruned += 1;
                    try self.markDead(cand, false);
                    self.discard(saved_output);
                    continue;
                }
                if (!is_new_by_signature) self.stats.collisions += 1;
                try self.remember(fallback, &self.seen, length);
                try self.remember(exact, &self.canonical, length);
                self.discard(saved_output);
            }

            try self.growFrontier();
            if (self.frontier.items.len == 0) return error.SearchExhausted;

            if (depth < self.depth_cap) continue;
            const viable = try self.liveCandidates();
            if (viable.len == 0) {
                try self.baseFrontier();
                depth = 0;
                continue;
            }
            const pick = viable[self.rng.below(viable.len)];
            self.stats.rng_choices += 1;
            const sideways = self.candidateSuffix(pick, null);
            if (!self.fits(sideways.len)) return error.ProgramTooLong;
            const saved_output = self.output.items.len;
            const run = self.execute(sideways, self.cp_peak);
            const length: u32 = @intCast(self.output.items.len);
            const fallback = signature(run, false);
            const known = self.seen.get(fallback);
            if (known != null and length <= known.?) {
                self.stats.pruned += 1;
                self.stats.repeated_state_pruned += 1;
                self.stats.rng_pruned += 1;
                self.discard(saved_output);
                try self.baseFrontier();
                depth = 0;
                continue;
            }
            const exact = signature(run, true);
            const previous = self.canonical.get(exact);
            if (previous != null and length <= previous.?) self.stats.collisions += 1;
            try self.remember(fallback, &self.seen, length);
            try self.remember(exact, &self.canonical, length);
            try self.commit(sideways, run);
            try self.baseFrontier();
            depth = 0;
        }
    }

    /// Reference: after every target byte, extend with "v" and take that as the
    /// program. Unlike the reference, this port reports what the machine
    /// actually did with it.
    fn finish(self: *Searcher) !Run {
        const halt = [_]u8{'v'};
        if (!self.fits(halt.len)) return error.ProgramTooLong;
        const run = self.execute(&halt, self.cp_peak);
        const length: u32 = @intCast(self.output.items.len);
        const fallback = signature(run, false);
        const exact = signature(run, true);
        try self.remember(fallback, &self.seen, length);
        try self.remember(exact, &self.canonical, length);
        try self.commit(&halt, run);
        return run;
    }

    /// One target string, start to finish, matching `generate_for_string`.
    fn generate(self: *Searcher, target: []const u8) !struct { run: Run, program: []u8 } {
        const boot = try self.loadBootstrap();
        try self.commit("", boot);
        try self.remember(signature(boot, false), &self.seen, 0);
        try self.remember(signature(boot, true), &self.canonical, 0);

        for (0..target.len) |index| try self.searchChar(target, index);
        const run = try self.finish();
        const program = try self.encodeProgram();
        return .{ .run = run, .program = program };
    }

    fn encodeProgram(self: *Searcher) ![]u8 {
        const program = try self.gpa.alloc(u8, self.opcodes.items.len);
        errdefer self.gpa.free(program);
        for (self.opcodes.items, 0..) |op, position| {
            program[position] = opcodeCell(op, position);
        }
        return program;
    }
};

/// The gate that decides whether the port is worth anything: run the finished
/// program the way `mbc` would, with no threshold and no emulation, and check
/// it prints the target. A search that drifts away from Classic fails here
/// rather than shipping a program that only its own engine believes in.
fn verifyCanonical(program: []const u8, target: []const u8, budget: u64) !bool {
    if (program.len < 2) return error.TooShort;
    for (program, 0..) |byte, position| {
        if (byte < 33 or byte > 126) return error.InvalidCharacter;
        if (std.mem.indexOfScalar(u8, VALID_OPCODES, decodeOpcode(byte, position)) == null) {
            return error.InvalidOpcode;
        }
        mem[position] = byte;
    }
    var count: usize = program.len;
    while (count < MEMORY_SIZE) : (count += 1) {
        mem[count] = crazy(mem[count - 1], mem[count - 2]);
    }
    var a: u16 = 0;
    var c: usize = 0;
    var d: usize = 0;
    var printed: usize = 0;
    var steps: u64 = 0;
    while (steps < budget) : (steps += 1) {
        const pc = mem[c];
        if (pc < 33 or pc > 126) return false;
        switch (decodeOpcode(pc, c)) {
            'j' => {
                const target_cell = mem[d];
                if (target_cell > WRAP_LAST) return false;
                d = target_cell;
            },
            'i' => {
                const target_cell = mem[d];
                if (target_cell > WRAP_LAST) return false;
                c = target_cell;
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
                if (printed >= target.len or target[printed] != @as(u8, @truncate(a))) return false;
                printed += 1;
            },
            '/' => a = EOF_VALUE,
            'v' => return printed == target.len,
            else => {},
        }
        const encrypted = mem[c];
        if (encrypted < 33 or encrypted > 126) return false;
        mem[c] = XLAT2[encrypted - 33];
        c = if (c == WRAP_LAST) 0 else c + 1;
        d = if (d == WRAP_LAST) 0 else d + 1;
    }
    return false;
}

const Args = struct {
    target_file: []const u8 = "",
    out: []const u8 = "",
    stats: []const u8 = "",
    choices: []const u8 = "op*",
    depth: u32 = 5,
    seed: u64 = 42,
    budget: u64 = 65536,
};

const usage =
    \\Usage: mbsearch --target-file F [--out P] [--stats P] [--depth N]
    \\                [--choices op*] [--seed N] [--budget N]
    \\
;

fn parseArgs(argv: []const [:0]const u8) !Args {
    var args = Args{};
    var i: usize = 0;
    while (i < argv.len) {
        const flag = argv[i];
        i += 1;
        if (i >= argv.len) return error.MissingValue;
        const value: []const u8 = argv[i];
        i += 1;
        if (std.mem.eql(u8, flag, "--target-file")) {
            args.target_file = value;
        } else if (std.mem.eql(u8, flag, "--out")) {
            args.out = value;
        } else if (std.mem.eql(u8, flag, "--stats")) {
            args.stats = value;
        } else if (std.mem.eql(u8, flag, "--choices")) {
            args.choices = value;
        } else if (std.mem.eql(u8, flag, "--depth")) {
            args.depth = try std.fmt.parseInt(u32, value, 10);
        } else if (std.mem.eql(u8, flag, "--seed")) {
            args.seed = try std.fmt.parseInt(u64, value, 10);
        } else if (std.mem.eql(u8, flag, "--budget")) {
            args.budget = try std.fmt.parseInt(u64, value, 10);
        } else return error.UnknownFlag;
    }
    if (args.target_file.len == 0) return error.TargetRequired;
    if (args.choices.len == 0 or args.choices.len > CAND_CAP) return error.BadChoices;
    if (args.budget == 0) return error.BadBudget;
    for (args.choices) |op| {
        if (std.mem.indexOfScalar(u8, VALID_OPCODES, op) == null) return error.BadChoices;
    }
    return args;
}

fn writeAll(io: std.Io, path: []const u8, bytes: []const u8) !void {
    var file = try std.Io.Dir.cwd().createFile(io, path, .{});
    defer file.close(io);
    try file.writeStreamingAll(io, bytes);
}

pub fn main(init: std.process.Init) !void {
    const gpa = init.gpa;
    const io = init.io;
    var errbuf: [512]u8 = undefined;
    var errout = std.Io.File.stderr().writer(io, &errbuf);

    const argv = try init.minimal.args.toSlice(init.arena.allocator());
    if (argv.len < 3) {
        errout.interface.writeAll(usage) catch {};
        return error.Usage;
    }
    const args = parseArgs(argv[1..]) catch |err| {
        errout.interface.writeAll(usage) catch {};
        errout.interface.print("error: {s}\n", .{@errorName(err)}) catch {};
        return err;
    };

    const target = try std.Io.Dir.cwd().readFileAlloc(io, args.target_file, gpa, .limited(1 << 20));
    defer gpa.free(target);
    if (target.len == 0) return error.EmptyTarget;

    var search = Searcher{
        .gpa = gpa,
        .choices = args.choices,
        .depth_cap = args.depth,
        .budget = args.budget,
        .rng = Rng.init(args.seed),
    };
    defer search.deinit();

    const started = std.Io.Timestamp.now(io, .awake).nanoseconds;
    const made = try search.generate(target);
    const elapsed: u64 = @intCast(std.Io.Timestamp.now(io, .awake).nanoseconds - started);

    if (!std.mem.eql(u8, search.output.items, target)) return error.MachineOutputMismatch;
    const canonical_ok = try verifyCanonical(made.program, target, 1_000_000);
    const canonical_label: []const u8 = if (canonical_ok) "true" else "false";

    if (args.out.len != 0) {
        try writeAll(io, args.out, made.program);
    } else {
        try std.Io.File.stdout().writeStreamingAll(io, made.program);
    }

    const stats = search.stats;
    const text = try std.fmt.allocPrint(gpa,
        \\{{"target_bytes": {d}, "opcode_chars": {d}, "program_chars": {d},
        \\ "expansion_ratio": {d:.2}, "evaluations": {d}, "steps_total": {d},
        \\ "max_steps": {d}, "pruned": {d}, "repeated_state_pruned": {d},
        \\ "dead_cache_hits": {d}, "signature_collisions": {d}, "rng_choices": {d},
        \\ "rng_pruned": {d}, "stalls": {d}, "budget_exhausted": {d},
        \\ "slash_executed": {d}, "peak_gaps": {d}, "delta_overflows": {d},
        \\ "wraps": {d}, "halt_term": "{s}", "canonical_ok": {s},
        \\ "duration_ns": {d}, "config": {{"depth": {d}, "choices": "{s}",
        \\ "seed": {d}, "budget": {d}}}, "program_fingerprint": "{x}"}}
        \\
    , .{
        target.len,
        search.opcodes.items.len,
        made.program.len,
        @as(f64, @floatFromInt(made.program.len)) / @as(f64, @floatFromInt(target.len)),
        stats.evaluations,
        stats.steps_total,
        stats.max_steps,
        stats.pruned,
        stats.repeated_state_pruned,
        stats.dead_cache_hits,
        stats.collisions,
        stats.rng_choices,
        stats.rng_pruned,
        stats.stalls,
        stats.budgets,
        stats.slashes,
        stats.peak_gaps,
        overflows_total,
        stats.wraps,
        made.run.term.label(),
        canonical_label,
        elapsed,
        args.depth,
        args.choices,
        args.seed,
        args.budget,
        std.hash.Wyhash.hash(0, made.program),
    });
    defer gpa.free(text);
    if (args.stats.len != 0) {
        try writeAll(io, args.stats, text);
    } else {
        try std.Io.File.stderr().writeStreamingAll(io, text);
    }
    if (!canonical_ok) return error.NotCanonical;
}
