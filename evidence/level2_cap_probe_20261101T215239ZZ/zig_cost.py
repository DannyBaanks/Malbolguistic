#!/usr/bin/env python3
"""Zig search cost across source-size bands: wall time, peak RSS, program size,
and byte-exact re-execution with the canonical Zig machine.

Both binaries are rebuilt here from the committed sources, so the pack records
exactly what ran:
  zig build-exe -O ReleaseFast -femit-bin=<work>/mbc      tools/zig_canonical/mbc.zig
  zig build-exe -O ReleaseFast -femit-bin=<work>/mbsearch tools/zig_canonical/mbsearch.zig
  ZIG           zig driver (default: zig)
  ZIG_GUARD_MB / ZIG_WALL_S  safety guards (default 6000 / 900)

Programs produced here are NOT stored in the pack: the port is deterministic, so
rerunning this driver on the same sources regenerates them byte for byte.
Usage: python3 zig_cost.py <out-dir> [min-B:max-B ...]
"""
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
ZIG = os.environ.get("ZIG", "zig")
GUARD_MB = int(os.environ.get("ZIG_GUARD_MB", "6000"))
WALL_S = float(os.environ.get("ZIG_WALL_S", "900"))
BANDS = [tuple(int(x) for x in a.split(":")) for a in sys.argv[2:]] or [(60, 128), (129, 180)]

OUT = pathlib.Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
# Binarios y programas generados viven fuera del pack: son reconstruibles de forma
# determinista a partir del fuente commiteado, y meter 8 MB de binarios aqui no.
work = pathlib.Path(tempfile.mkdtemp(prefix="mbcap_"))

MBSEARCH = str(work / "mbsearch")
MBC = str(work / "mbc")
build_info = {"zig_version": subprocess.run([ZIG, "version"], capture_output=True).stdout.decode().strip()}
for name, src_zig in (("mbc", "mbc.zig"), ("mbsearch", "mbsearch.zig")):
    source = REPO / "tools" / "zig_canonical" / src_zig
    subprocess.run([ZIG, "build-exe", "-O", "ReleaseFast",
                    "-femit-bin=" + str(work / name), str(source)], check=True,
                   capture_output=True)
    build_info[src_zig] = {
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "binary_sha256": hashlib.sha256((work / name).read_bytes()).hexdigest()}
print(json.dumps({"engine": "build", **build_info}), flush=True)

manifest = json.loads((REPO / "manifest" / "translation_manifest.json").read_text())
rows = []
for e in manifest:
    if not e["mirror"]["artifact"].endswith(".malrt1"):
        continue
    p = REPO / "vendor" / "source_snapshot" / e["source"]
    if p.is_file():
        rows.append((e["source"], p.stat().st_size, e["mirror"]["artifact"]))

for lo, hi in BANDS:
    sel = sorted(r for r in rows if lo <= r[1] <= hi)
    if not sel:
        continue
    # deterministic picks: smallest, median, largest of the band
    picks = list(dict.fromkeys([sel[0], sel[len(sel) // 2], sel[-1]]))
    for src, sz, envrel in picks:
        env = REPO / envrel
        env_bytes = env.read_bytes()
        for depth in (5, 8):
            tag = f"{sz}_d{depth}"
            t = time.time()
            peak = 0
            killed = False
            p = subprocess.Popen(
                [MBSEARCH, "--target-file", str(env), "--out", str(work / f"{tag}.mal"),
                 "--stats", str(work / f"{tag}.json"), "--depth", str(depth)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            while p.poll() is None:
                try:
                    for line in open(f"/proc/{p.pid}/status"):
                        if line.startswith("VmRSS:"):
                            peak = max(peak, int(line.split()[1]) // 1024)
                            if peak > GUARD_MB:
                                p.kill()
                                killed = True
                except (FileNotFoundError, ProcessLookupError, ValueError):
                    pass
                if time.time() - t > WALL_S:
                    p.kill()
                    killed = True
                    break
                time.sleep(0.2)
            _so, se = p.communicate()
            wall = time.time() - t
            stats_file = work / f"{tag}.json"
            st = json.loads(stats_file.read_text()) if stats_file.exists() else None
            mbc_ok = None
            if p.returncode == 0:
                try:
                    c = subprocess.run([MBC, str(work / f"{tag}.mal"), "5000000000"],
                                       capture_output=True, timeout=900)
                    mbc_ok = (c.returncode == 0 and c.stdout == env_bytes)
                except subprocess.TimeoutExpired:
                    mbc_ok = "TIMEOUT_900S"
            print(json.dumps({
                "engine": "zig", "source": src, "source_bytes": sz,
                "envelope_chars": len(env_bytes), "depth": depth, "rc": p.returncode,
                "wall_s": round(wall, 2), "peak_rss_mb": peak, "guard_killed": killed,
                "program_chars": (st or {}).get("program_chars"),
                "expansion": (st or {}).get("expansion_ratio"),
                "evaluations": (st or {}).get("evaluations"),
                "mbc_byte_exact": mbc_ok, "stderr": se.decode().strip()[:120]}), flush=True)
