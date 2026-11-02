#!/usr/bin/env python3
"""Python generator cost across the same source-size bands, using exactly the
call the build makes: MalbolgeTranslator(max_search_depth=5).translate_and_verify_roundtrip().

Peak RSS is sampled from /proc, not from the process itself, so the guard can
stop a job before it takes the host down.

Env:
  PY_GEN      interpreter with malbolge-generator installed (default: python3)
  PY_GUARD_MB kill above this RSS in MB   (default 5500)
  PY_WALL_S   kill above this wall time   (default 600)
Bands are `min-B:max-B` and the median file of each band is measured. A band
written `@<path-in-snapshot>` measures that specific file instead, so a single
target can be re-measured exactly:

    python3 py_cost.py . @.github/CODEOWNERS
"""
import json
import os
import pathlib
import subprocess
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
PY = os.environ.get("PY_GEN", sys.executable)
GUARD_MB = int(os.environ.get("PY_GUARD_MB", "5500"))
WALL_S = float(os.environ.get("PY_WALL_S", "600"))
RAW_ARGS = sys.argv[2:] or ["60:128"]
PINNED = [a[1:] for a in RAW_ARGS if a.startswith("@")]
BANDS = [tuple(int(x) for x in a.split(":")) for a in RAW_ARGS if not a.startswith("@")]

CHILD = r'''
import json, os, pathlib, sys, time
sys.path.insert(0, os.environ["VENDOR"])
from malbolge_translator import MalbolgeTranslator
text = pathlib.Path(sys.argv[1]).read_bytes().decode("utf-8", errors="replace")
t = time.time()
tr = MalbolgeTranslator(max_search_depth=5)
res, ver = tr.translate_and_verify_roundtrip(text, max_steps=5000000)
prog = res.translation.full_program if ver.roundtrip_pass else None
print(json.dumps({"chars": len(prog) if prog else None, "wall_s": round(time.time()-t, 2),
                  "pass": bool(ver.roundtrip_pass), "error": ver.error}))
'''

OUT = pathlib.Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
manifest = json.loads((REPO / "manifest" / "translation_manifest.json").read_text())
rows = []
for e in manifest:
    p = REPO / "vendor" / "source_snapshot" / e["source"]
    if p.is_file():
        rows.append((e["source"], p.stat().st_size, e["mirror"]["artifact"]))

picks = []
for rel in PINNED:
    p = REPO / "vendor" / "source_snapshot" / rel
    if p.is_file():
        picks.append((rel, p.stat().st_size, None))
for lo, hi in BANDS:
    sel = sorted(r for r in rows if lo <= r[1] <= hi and r[2].endswith(".malrt1"))
    if sel:
        picks.append(sel[len(sel) // 2])

env = dict(os.environ, VENDOR=str(REPO / "vendor"))
for src, sz, _art in picks:
    path = REPO / "vendor" / "source_snapshot" / src
    t = time.time()
    peak = 0
    killed = False
    traj = []
    p = subprocess.Popen([PY, "-c", CHILD, str(path)], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, env=env)
    while p.poll() is None:
        try:
            for line in open(f"/proc/{p.pid}/status"):
                if line.startswith("VmRSS:"):
                    mb = int(line.split()[1]) // 1024
                    peak = max(peak, mb)
                    if len(traj) < 40:
                        traj.append(mb)
                    if mb > GUARD_MB:
                        p.kill()
                        killed = True
        except (FileNotFoundError, ProcessLookupError, ValueError):
            pass
        if time.time() - t > WALL_S:
            p.kill()
            killed = True
            break
        time.sleep(0.25)
    so, se = p.communicate()
    print(json.dumps({
        "engine": "python", "source": src, "source_bytes": sz,
        "peak_rss_mb": peak, "guard_mb": GUARD_MB, "guard_killed": killed,
        "wall_s": round(time.time() - t, 1), "rc": p.returncode,
        "child": so.decode().strip()[:200], "stderr": se.decode().strip()[-160:],
        "rss_trajectory_mb": traj[:24]}), flush=True)

# tiny control: the same API on a 2-byte input, to separate "expensive" from "broken"
path = OUT / "control_hi.txt"
path.write_text("hi")
t = time.time()
p = subprocess.Popen([PY, "-c", CHILD, str(path)], stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, env=env)
peak = 0
while p.poll() is None:
    try:
        for line in open(f"/proc/{p.pid}/status"):
            if line.startswith("VmRSS:"):
                peak = max(peak, int(line.split()[1]) // 1024)
    except (FileNotFoundError, ProcessLookupError, ValueError):
        pass
    time.sleep(0.25)
so, se = p.communicate()
print(json.dumps({"engine": "python", "source": "<control: 'hi'>", "source_bytes": 2,
                  "peak_rss_mb": peak, "guard_killed": False,
                  "wall_s": round(time.time() - t, 1), "rc": p.returncode,
                  "child": so.decode().strip()[:200], "stderr": se.decode().strip()[-160:]}),
      flush=True)
