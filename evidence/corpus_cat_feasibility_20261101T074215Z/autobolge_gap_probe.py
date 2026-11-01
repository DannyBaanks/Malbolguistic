#!/usr/bin/env python3
"""Autobolge conveyor feasibility: does the O(N) constructive synthesizer reach
the corpus, and are its artifacts accepted by the canonical strict loaders?

Env: AUTOBOLGE_ROOT (checkout with relational/), MB_REF, OLMSTEAD.
Usage: autobolge_gap_probe.py <snapshot-dir> <source_inventory.json> <out-prefix>
"""
import base64
import hashlib
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(os.environ["AUTOBOLGE_ROOT"]).resolve()))
from relational.synthesizer import RECIPES, synthesize_text  # noqa: E402

SNAP = pathlib.Path(sys.argv[1]).resolve()
INVENTORY = pathlib.Path(sys.argv[2]).resolve()
PREFIX = sys.argv[3]
COST = {"rot": 2, "rot_crazy": 3, "rot_crazy_crazy": 4}
D_START, C_START = 121, 3315
ALLOWED = set(b"ji*p</vo")
MB_REF = os.environ.get("MB_REF", "mb_ref")
OLMSTEAD = os.environ.get("OLMSTEAD", "olmstead")


def envelope_for(raw: bytes) -> str:
    return "MALRT1:" + base64.b64encode(raw).decode("ascii") + ":" + hashlib.sha256(raw).hexdigest()


rows = []
for entry in json.loads(INVENTORY.read_text()):
    if entry["classification"] != "TEXT":
        continue
    raw = (SNAP / entry["path"]).read_bytes()
    env = envelope_for(raw).encode("latin-1")
    unemittable = [b for b in env if b not in RECIPES]
    cells = sum(COST[RECIPES[b][0]] for b in env if b in RECIPES)
    rows.append({"path": entry["path"], "bytes": len(raw), "envelope_chars": len(env),
                 "unemittable_bytes": len(unemittable), "data_cells_end": D_START + cells,
                 "fits_gap": D_START + cells <= C_START})

fit = [r for r in rows if r["fits_gap"] and not r["unemittable_bytes"]]
analysis = {"layout": {"D_START": D_START, "C_START": C_START, "sterile_gap_cells": C_START - D_START},
            "recipe_cells_per_output_byte": {"newline": 2, "printable_other": 3, "plus": 4},
            "text_files": len(rows), "fits_sterile_gap": len(fit),
            "envelopes_with_unemittable_bytes": sum(1 for r in rows if r["unemittable_bytes"]),
            "largest_fitting_source_bytes": max((r["bytes"] for r in fit), default=None),
            "source_bytes_reachable": sum(r["bytes"] for r in fit),
            "source_bytes_unreachable": sum(r["bytes"] for r in rows if r not in fit),
            "rows": rows}
pathlib.Path(f"{PREFIX}_gap_analysis.json").write_text(json.dumps(analysis, indent=1) + "\n")

probes = sorted(fit, key=lambda r: r["bytes"])
picks = [probes[0], probes[len(probes) // 2], probes[-1]]
accepted = []
for pick in picks:
    env = envelope_for((SNAP / pick["path"]).read_bytes())
    res = synthesize_text(env, verify=False)
    art = pathlib.Path(f"{PREFIX}_{pick['bytes']}.mal")
    art.write_bytes(res.program_bytes)
    rec = {"path": pick["path"], "envelope_chars": len(env), "data_cells": res.data_cells,
           "program_bytes": len(res.program_bytes), "synthesis_ms": round(res.elapsed_ms, 2),
           "sha256": res.sha256,
           "loader_illegal_cells": sum(1 for b in res.program_bytes if b not in ALLOWED),
           "engines": {}}
    for name, cmd in (("mb_ref", [MB_REF, str(art), "300000000"]), ("olmstead", [OLMSTEAD, str(art)])):
        run = subprocess.run(cmd, input=b"", capture_output=True, timeout=600)
        rec["engines"][name] = {"rc": run.returncode,
                                "stdout_is_envelope": run.stdout == env.encode("latin-1"),
                                "stderr": run.stderr.decode("latin-1", "replace")[:80].strip()}
    accepted.append(rec)
pathlib.Path(f"{PREFIX}_canonical_acceptance.json").write_text(json.dumps(accepted, indent=1) + "\n")
print(json.dumps({"text_files": len(rows), "fits_sterile_gap": len(fit), "probes": accepted}, indent=1))
sys.exit(0 if any(r["engines"]["mb_ref"]["stdout_is_envelope"] for r in accepted) else 1)
