#!/usr/bin/env python3
"""Project cost and reachability per level-2 source cap, from the real inventory
and the constants measured in this pack (raw_zig.jsonl).

Envelope length is the exact MALRT1 formula: "MALRT1:" + base64(source) + ":" + sha256hex.
Reachability: the canonical machine has 3^10 = 59049 cells, so a program longer
than the tape can never load (the port reports error.ProgramTooLong). Expansion
(chars of program per char of envelope) is taken from the measured runs per depth.

Usage: python3 cap_table.py <raw_zig.jsonl> <out-summary.json>
"""
import json
import pathlib
import statistics
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
TAPE = 59049
B64 = lambda n: 4 * ((n + 2) // 3)
envelope_chars = lambda n: 7 + B64(n) + 1 + 64

raw = [json.loads(l) for l in pathlib.Path(sys.argv[1]).read_text().splitlines() if l.strip()]
per_depth = {}
for r in raw:
    if r.get("rc") == 0 and r.get("expansion"):
        d = per_depth.setdefault(r["depth"], {"exp": [], "ms": [], "rss": []})
        d["exp"].append(r["expansion"])
        d["ms"].append(1000.0 * r["wall_s"] / r["envelope_chars"])
        d["rss"].append(r["peak_rss_mb"])
const = {}
for d, v in per_depth.items():
    const[d] = {"expansion_median": round(statistics.median(v["exp"]), 2),
                "ms_per_envelope_char": round(statistics.median(v["ms"]), 3),
                "peak_rss_mb_max": max(v["rss"]),
                "n": len(v["exp"])}

manifest = json.loads((REPO / "manifest" / "translation_manifest.json").read_text())
sizes = []
for e in manifest:
    if not e["mirror"]["artifact"].endswith(".malrt1"):
        continue
    p = REPO / "vendor" / "source_snapshot" / e["source"]
    if p.is_file():
        sizes.append(p.stat().st_size)

table = []
for cap in (128, 256, 512, 1024, 1536, 1792, 2048, 3072, 4096, 8192, 65536):
    sel = [s for s in sizes if s <= cap]
    env_total = sum(envelope_chars(s) for s in sel)
    row = {"cap_bytes": cap, "eligible_files": len(sel),
           "eligible_pct_of_text": round(100.0 * len(sel) / len(sizes), 1),
           "envelope_chars_total": env_total}
    for d, c in const.items():
        reach = sum(1 for s in sel if envelope_chars(s) * c["expansion_median"] <= TAPE)
        row[f"depth{d}"] = {
            "reachable_files": reach,
            "unreachable_files": len(sel) - reach,
            "projected_wall_s": round(env_total * c["ms_per_envelope_char"] / 1000.0, 1),
            "projected_store_mb": round(env_total * c["expansion_median"] / 1e6, 1),
            "peak_rss_mb_observed_max": c["peak_rss_mb_max"],
        }
    table.append(row)

out = {"tool": "cap_table.py", "tape_cells": TAPE,
       "text_files_on_disk": len(sizes),
       "measured_constants_by_depth": const,
       "source_raw": pathlib.Path(sys.argv[1]).name,
       "formula": "MALRT1:<base64>:<sha256hex>; envelope_chars = 7 + 4*ceil(n/3) + 1 + 64",
       "projection_basis": "mediana de ms/char y expansion medidas en este pack; "
                           "lineal en caracteres de envoltura (el search es por caracter)",
       "table": table}
pathlib.Path(sys.argv[2]).write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=2))
