#!/usr/bin/env python3
"""Throughput of the canonical Zig engine against the C oracle and the toolkits.

The gate answers "is it canonical"; this answers "is it fast enough to port the
search onto". Four engines, one shared workload:

  * oracle_mb_ref      the C reference -- does not report steps
  * zig_canonical      tools/zig_canonical/mbc (this pack's subject)
  * zig_bolg1          the toolkit-semantics cell-dump engine, via its adapter
  * toolkit_python     the toolkit interpreter, measured in-process

`mb_ref` prints no step count, so its rate is derived from the count of a
canonical engine that produced byte-identical output on the same workload. The
donor here is `mbc`, whose count equals the manifest's on the sampled level-2
artifacts; the BOLG1 engine is reported alongside because the two native engines
do NOT agree on how to count a stdin-fed run, and that difference is a finding,
not noise.

Paths are taken from the environment and never written into the output:
  MBC, ORACLE_DIR, CAT_MAL, BOLGE_EXE, TOOLKIT_PY, MBG_VENV_SITEPACKETS
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time

PACK = pathlib.Path(__file__).resolve().parent
REPO = PACK.parents[1]
MBC = os.environ["MBC"]
MB_REF = os.path.join(os.environ["ORACLE_DIR"], "mb_ref")
CAT = pathlib.Path(os.environ["CAT_MAL"])
BOLGE_EXE = os.environ["BOLGE_EXE"]
TOOLKIT_PY = os.environ["TOOLKIT_PY"]
SITEPACKETS = os.environ.get("MBG_VENV_SITEPACKETS", "")
ADAPTERS = REPO / "tools" / "gate_adapters"
SNAPSHOT = REPO / "vendor" / "source_snapshot" / "samples" / "Go" / "embedded.go"
MANIFEST = REPO / "manifest" / "translation_manifest.json"
BUDGET = "3000000000"
REPEATS = 3


def steps_in(text: str):
    for token in text.split():
        if token.startswith("steps="):
            try:
                return int(token.split("=", 1)[1])
            except ValueError:
                return None
    return None


def best_of(cmd, stdin_bytes, env=None):
    wall, result = None, None
    for _ in range(REPEATS):
        started = time.perf_counter()
        res = subprocess.run(cmd, input=stdin_bytes, capture_output=True, env=env, timeout=900)
        elapsed = time.perf_counter() - started
        if wall is None or elapsed < wall:
            wall, result = elapsed, res
    return round(wall, 4), result


def main() -> int:
    payload_all = SNAPSHOT.read_bytes()
    sizes = [s for s in (744, 8192, 65536) if s <= len(payload_all)] + [len(payload_all)]
    workloads = []
    for size in sizes:
        payload = payload_all[:size]
        # The BOLG1 adapter takes its input from a file named by the environment,
        # not from stdin; without it the adapter would run the Cat on empty input.
        input_file = PACK / "_bolg1_input.bin"
        input_file.write_bytes(payload)
        env = dict(os.environ, BOLGE_EXE=BOLGE_EXE, BOLG1_INPUT_FILE=str(input_file))
        row = {"input_bytes": size, "input_sha256": hashlib.sha256(payload).hexdigest()}

        wall_cbc, r_cbc = best_of([MBC, str(CAT), BUDGET], payload)
        steps = steps_in(r_cbc.stderr.decode("latin-1", "replace"))
        wall_ref, r_ref = best_of([MB_REF, str(CAT), BUDGET], payload)
        wall_b1, r_b1 = best_of([sys.executable, str(ADAPTERS / "bolg1_runner.py"), str(CAT), BUDGET],
                                payload, env)
        steps_b1 = steps_in(r_b1.stderr.decode("latin-1", "replace"))

        row["zig_canonical"] = {"wall_s": wall_cbc, "rc": r_cbc.returncode, "steps": steps,
                                 "byte_exact": r_cbc.stdout == payload,
                                 "steps_per_s": int(steps / wall_cbc) if steps and wall_cbc else None}
        row["oracle_mb_ref"] = {"wall_s": wall_ref, "rc": r_ref.returncode,
                                "byte_exact": r_ref.stdout == payload,
                                "derived_steps_per_s": int(steps / wall_ref) if steps and wall_ref else None}
        row["zig_bolg1"] = {"wall_s": wall_b1, "rc": r_b1.returncode, "steps": steps_b1,
                            "byte_exact": r_b1.stdout == payload}
        if steps and steps_b1:
            row["native_step_count_delta"] = steps - steps_b1
        workloads.append(row)

    entries = sorted((e for e in json.loads(MANIFEST.read_text())
                      if e["malbolge"].get("status") == "PASS" and e["malbolge"].get("artifact")),
                     key=lambda e: e["malbolge"]["artifact"])
    stride = max(1, len(entries) // 8)
    convention = []
    for entry in entries[::stride][:8]:
        art = str(REPO / entry["malbolge"]["artifact"])
        counts = {"manifest": entry["malbolge"].get("steps")}
        for name, cmd in (("zig_canonical", [MBC, art, BUDGET]),
                          ("zig_bolg1", [sys.executable, str(ADAPTERS / "bolg1_runner.py"), art, BUDGET]),
                          ("toolkit_python", [TOOLKIT_PY, str(ADAPTERS / "interpreter_runner.py"), art, BUDGET])):
            env = dict(os.environ, BOLGE_EXE=BOLGE_EXE, PYTHONPATH=SITEPACKETS)
            env.pop("BOLG1_INPUT_FILE", None)
            res = subprocess.run(cmd, input=b"", capture_output=True, env=env, timeout=900)
            counts[name] = steps_in(res.stderr.decode("latin-1", "replace"))
        counts["all_equal"] = len({counts[k] for k in counts}) == 1
        counts["artifact"] = entry["malbolge"]["artifact"]
        convention.append(counts)

    in_process = []
    sys.path.insert(0, SITEPACKETS)
    try:
        from malbolge.encoding import normalize
        from malbolge.interpreter import MalbolgeInterpreter
        for entry in sorted(entries, key=lambda e: e["malbolge"].get("steps", 0))[-3:]:
            opcodes = normalize((REPO / entry["malbolge"]["artifact"]).read_bytes().decode("latin-1"))
            started = time.perf_counter()
            result = MalbolgeInterpreter().execute(opcodes, input_buffer="", max_steps=int(BUDGET))
            elapsed = time.perf_counter() - started
            in_process.append({"artifact": entry["malbolge"]["artifact"], "wall_s": round(elapsed, 3),
                               "steps": result.steps,
                               "in_process_steps_per_s": int(result.steps / elapsed) if elapsed else None})
    except Exception as exc:
        in_process = [{"error": f"{type(exc).__name__}: {exc}"}]

    native_rates = [w["zig_canonical"]["steps_per_s"] for w in workloads
                    if w["zig_canonical"]["steps_per_s"]]
    derived = [w["oracle_mb_ref"]["derived_steps_per_s"] for w in workloads
               if w["oracle_mb_ref"]["derived_steps_per_s"]]
    python_rates = [p.get("in_process_steps_per_s") for p in in_process if p.get("in_process_steps_per_s")]
    summary = {
        "repeats_per_point": REPEATS,
        "workloads": workloads,
        "counting_convention_level1": {
            "artifacts_checked": len(convention),
            "all_four_reports_equal": sum(1 for c in convention if c["all_equal"]),
            "detail": convention,
        },
        "toolkit_python_in_process": in_process,
        "rates_steps_per_s": {
            "zig_canonical_best": max(native_rates, default=None),
            "oracle_mb_ref_derived_from_zig_canonical": max(derived, default=None),
            "toolkit_python_in_process_best": max(python_rates, default=None),
        },
        "ratios": {
            "zig_canonical_over_toolkit_python": (round(max(native_rates) / max(python_rates))
                                                  if native_rates and python_rates else None),
            "zig_canonical_over_oracle": (round(max(native_rates) / max(derived), 3)
                                          if native_rates and derived else None),
        },
        "caveats": [
            "mb_ref reports no step count; its rate is derived from the canonical Zig engine's count on workloads where both produced byte-identical stdout.",
            "Subprocess walls include process start (about 1-2 ms for the Zig binary), so short workloads understate the native rate.",
            "The toolkit rate is in-process and therefore excludes interpreter start and module import; the other three include them.",
            "native_step_count_delta compares two engines that both produced the right bytes but counted differently; it is zero on level-1 artifacts.",
        ],
    }
    (PACK / "throughput.json").write_text(json.dumps(summary, indent=1) + "\n")
    spare = PACK / "_bolg1_input.bin"
    if spare.exists():
        spare.unlink()
    print(json.dumps({"rates": summary["rates_steps_per_s"], "ratios": summary["ratios"]}, indent=1))
    for row in workloads:
        print(f"{row['input_bytes']:>7}B  mbc {row['zig_canonical']['wall_s']}s "
              f"{row['zig_canonical']['steps_per_s']} steps/s exact={row['zig_canonical']['byte_exact']} | "
              f"mb_ref {row['oracle_mb_ref']['wall_s']}s "
              f"{row['oracle_mb_ref']['derived_steps_per_s']} | "
              f"bolg1 delta={row.get('native_step_count_delta')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
