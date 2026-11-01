#!/usr/bin/env python3
"""Feed every catalog TEXT file to one canonical streaming Cat and require
byte-exact stdout under two independent Classic engines.

Roots/oracles are env-driven so no workstation path is recorded:
  MB_REF      compiled BolgeForge/oracle/mb_ref.c   (default ./mb_ref on PATH)
  OLMSTEAD    compiled vendor/oracles/olmstead_original.c
  CAT_CELLS   max_steps for mb_ref                  (default 300000000)
Usage: python3 cat_corpus_sweep.py <cat.mal> <snapshot-dir> <source_inventory.json>
"""
import json
import pathlib
import subprocess
import sys
import hashlib
import time
import os

CAT = pathlib.Path(sys.argv[1]).resolve()
SNAP = pathlib.Path(sys.argv[2]).resolve()
INVENTORY = pathlib.Path(sys.argv[3]).resolve()
MB_REF = os.environ.get("MB_REF", "mb_ref")
OLMSTEAD = os.environ.get("OLMSTEAD", "olmstead")
BUDGET = os.environ.get("CAT_CELLS", "300000000")

engines = [("mb_ref", [MB_REF, str(CAT), BUDGET]), ("olmstead", [OLMSTEAD, str(CAT)])]
catalog = [i for i in json.loads(INVENTORY.read_text()) if i["classification"] == "TEXT"]
t0 = time.time()
ok = {name: 0 for name, _ in engines}
failures = []
measured = 0
measured_bytes = 0
with open("raw.jsonl", "w") as sink:
    for entry in catalog:
        path = SNAP / entry["path"]
        if not path.is_file():
            failures.append([entry["path"], "MISSING"])
            continue
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            failures.append([entry["path"], "SHA_MISMATCH"])
            continue
        measured += 1
        measured_bytes += len(data)
        rec = {"path": entry["path"], "bytes": len(data)}
        for name, cmd in engines:
            try:
                res = subprocess.run(cmd, input=data, capture_output=True, timeout=600)
                exact = res.returncode == 0 and res.stdout == data
                rec[name] = {"rc": res.returncode, "out": len(res.stdout), "exact": exact,
                             "err": res.stderr.decode("latin-1", "replace")[:80].strip()}
                if exact:
                    ok[name] += 1
                else:
                    failures.append([entry["path"], f"{name}:{res.returncode}"])
            except subprocess.TimeoutExpired:
                rec[name] = {"timeout": True}
                failures.append([entry["path"], f"{name}:TIMEOUT"])
        sink.write(json.dumps(rec) + "\n")

summary = {
    "catalog_text_files": len(catalog),
    "files_measured": measured,
    "bytes_covered": measured_bytes,
    "engines_exact": ok,
    "failures": len(failures),
    "failed_paths": [f[0] for f in failures],
    "cat_sha256": hashlib.sha256(CAT.read_bytes()).hexdigest(),
    "cat_bytes": CAT.stat().st_size,
    "mb_ref_step_budget": int(BUDGET),
    "elapsed_s": round(time.time() - t0, 1),
}
pathlib.Path("summary.json").write_text(json.dumps(summary, indent=1) + "\n")
print(json.dumps(summary, indent=1))
sys.exit(0 if not failures and measured == len(catalog)
         and all(v == measured for v in ok.values()) else 1)
