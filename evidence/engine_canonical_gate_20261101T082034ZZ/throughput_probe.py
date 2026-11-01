#!/usr/bin/env python3
"""Throughput of the canonical reference versus the engines considered for the Zig port.

The gate says WHICH engines agree with canonical semantics; this probe says HOW FAST
they are, because the port decision (step 2 of the plan) is a steps-per-second question.

Two quantities are measured and must not be conflated:

  * wall-clock per run, per engine, on a shared workload (the canonical Cat program
    fed with pinned snapshot prefixes);
  * executed-instruction counts, which only some engines report. `mb_ref` halts
    silently, so its steps/s figure is DERIVED: it is only meaningful if the counting
    convention is shared, and that is checked here rather than assumed -- three
    independent reports of the same step count on the committed level-2 artifacts
    (manifest, cell-dump engine, toolkit interpreter).

The Python figure is also taken in-process, so it excludes interpreter startup and
module import; the subprocess figures include them.

Environment (paths are never written into the evidence):
  ORACLE_DIR   directory holding the built `mb_ref` binary
  CAT_MAL      canonical Cat artifact (outside this repo by default)
  BOLGE_EXE    cell-dump engine binary
  TOOLKIT_PY   python interpreter that can import `malbolge`
  MBG_VENV_SITEPACKETS  optional site-packages dir for TOOLKIT_PY

Writes throughput.json next to this file.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time

PACK = pathlib.Path(__file__).resolve().parent
REPO = PACK.parents[1]
CAT = pathlib.Path(os.environ["CAT_MAL"])
ORACLE_DIR = os.environ["ORACLE_DIR"]
BOLGE_EXE = os.environ["BOLGE_EXE"]
TOOLKIT_PY = os.environ["TOOLKIT_PY"]
ADAPTERS = REPO / "tools" / "gate_adapters"
SNAPSHOT_FILE = REPO / "vendor" / "source_snapshot" / "samples" / "Go" / "embedded.go"
MANIFEST = REPO / "manifest" / "translation_manifest.json"
BUDGET = 3_000_000_000
CONTROL_SIZES = (744, 8192, 65536)


def engine_env(input_bytes: bytes) -> dict:
    tmp = PACK / "_input.bin"
    tmp.write_bytes(input_bytes)
    return dict(os.environ, BOLGE_EXE=BOLGE_EXE, BOLG1_INPUT_FILE=str(tmp))


def timed(cmd, *, stdin_bytes=b"", env=None):
    t0 = time.perf_counter()
    res = subprocess.run(cmd, input=stdin_bytes, capture_output=True, env=env, timeout=600)
    return round(time.perf_counter() - t0, 3), res


def reported_steps(stderr_text: str) -> int | None:
    for token in stderr_text.split():
        if token.startswith("steps="):
            try:
                return int(token.split("=", 1)[1])
            except ValueError:
                return None
    return None


def main() -> int:
    payload_all = SNAPSHOT_FILE.read_bytes()
    sizes = [s for s in CONTROL_SIZES if s <= len(payload_all)] + [len(payload_all)]
    rows = []
    for size in sizes:
        payload = payload_all[:size]
        row = {"workload": "cat_compact.mal <- pinned snapshot prefix",
               "input_bytes": size,
               "input_sha256": __import__("hashlib").sha256(payload).hexdigest()}

        s_mb, r_mb = timed([f"{ORACLE_DIR}/mb_ref", str(CAT), str(BUDGET)], stdin_bytes=payload)
        row["oracle_mb_ref"] = {"wall_s": s_mb, "rc": r_mb.returncode,
                               "stdout_is_input": r_mb.stdout == payload}

        s_zig, r_zig = timed([sys.executable, str(ADAPTERS / "bolg1_runner.py"), str(CAT), str(BUDGET)],
                             env=engine_env(payload))
        zerr = r_zig.stderr.decode("latin-1", "replace").strip()
        zig_steps = reported_steps(zerr)
        row["zig_bolg1"] = {"wall_s": s_zig, "rc": r_zig.returncode, "steps": zig_steps,
                            "stdout_is_input": r_zig.stdout == payload, "note": zerr[:60]}

        if zig_steps and r_mb.stdout == payload and r_zig.stdout == payload and r_mb.returncode == 0:
            row["oracle_mb_ref"]["derived_steps_per_s"] = int(zig_steps / s_mb) if s_mb else None
            row["zig_bolg1"]["steps_per_s"] = int(zig_steps / s_zig) if s_zig else None
        else:
            row["steps_derivable"] = False
        rows.append(row)

    # --- counting-convention check: three reports of the same step count -------------
    manifest = json.loads(MANIFEST.read_text())
    passed = sorted((e for e in manifest if e["malbolge"].get("status") == "PASS"
                     and e["malbolge"].get("artifact")),
                    key=lambda e: e["malbolge"]["artifact"])
    stride = max(1, len(passed) // 8)
    sample = passed[::stride][:8]
    convention = []
    for entry in sample:
        art = REPO / entry["malbolge"]["artifact"]
        _, r_zig = timed([sys.executable, str(ADAPTERS / "bolg1_runner.py"), str(art), str(BUDGET)],
                         env=engine_env(b""))
        env2 = dict(os.environ, PYTHONPATH=os.environ.get("MBG_VENV_SITEPACKETS", ""))
        _, r_py = timed([TOOLKIT_PY, str(ADAPTERS / "interpreter_runner.py"), str(art), str(BUDGET)], env=env2)
        zig_steps = reported_steps(r_zig.stderr.decode("latin-1", "replace"))
        py_steps = reported_steps(r_py.stderr.decode("latin-1", "replace"))
        convention.append({"artifact": entry["malbolge"]["artifact"],
                           "manifest_steps": entry["malbolge"].get("steps"),
                           "zig_bolg1_steps": zig_steps,
                           "toolkit_python_steps": py_steps,
                           "all_equal": zig_steps == py_steps == entry["malbolge"].get("steps")})
    agreeing = [c for c in convention if c["all_equal"]]

    # --- toolkit stepping rate measured in-process (no interpreter startup) ----------
    heavy = sorted(passed, key=lambda e: e["malbolge"].get("steps", 0))[-3:]
    python_rows = []
    if agreeing:
        sys.path.insert(0, os.environ.get("MBG_VENV_SITEPACKETS", ""))
        try:
            from malbolge.encoding import normalize
            from malbolge.interpreter import MalbolgeInterpreter
            for entry in heavy:
                opcodes = normalize((REPO / entry["malbolge"]["artifact"]).read_bytes().decode("latin-1"))
                t0 = time.perf_counter()
                result = MalbolgeInterpreter().execute(opcodes, input_buffer="", max_steps=BUDGET)
                elapsed = time.perf_counter() - t0
                python_rows.append({"artifact": entry["malbolge"]["artifact"],
                                    "wall_s": round(elapsed, 3), "steps": result.steps,
                                    "halted": result.halted,
                                    "in_process_steps_per_s": int(result.steps / elapsed)})
        except Exception as exc:
            python_rows = [{"error": f"{type(exc).__name__}: {exc}"}]

    fastest = max((r["in_process_steps_per_s"] for r in python_rows if "in_process_steps_per_s" in r),
                  default=None)
    mb_rates = [r["oracle_mb_ref"].get("derived_steps_per_s") for r in rows]
    mb_rates = [v for v in mb_rates if v]
    summary = {
        "workloads": rows,
        "counting_convention": {
            "artifacts_checked": len(convention),
            "all_three_reports_equal": len(agreeing),
            "detail": convention,
            "verdict": ("SHARED" if len(agreeing) == len(convention) and convention else
                        "NOT_DEMONSTRATED"),
        },
        "toolkit_python_in_process": python_rows,
        "rates_steps_per_s": {
            "oracle_mb_ref_derived": max(mb_rates, default=None),
            "zig_bolg1": max((r["zig_bolg1"].get("steps_per_s", 0) or 0) for r in rows),
            "toolkit_python_in_process": fastest,
        },
        "caveats": [
            "mb_ref does not report steps; its rate is derived from the cell-dump engine's count on workloads where both produced byte-identical stdout.",
            "The derivation is only valid under the counting-convention verdict above.",
            "Subprocess walls include Python interpreter startup plus adapter cell-packaging; the in-process Python rate excludes them.",
            "The largest control is where the cell-dump engine diverges (see summary.json), so no rate is derived from it.",
        ],
    }
    (PACK / "throughput.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary["rates_steps_per_s"], indent=1))
    print(json.dumps(summary["counting_convention"]["detail"], indent=1))
    for row in rows:
        print(f"{row['input_bytes']:>7}B  mb_ref {row['oracle_mb_ref']['wall_s']}s "
              f"{row['oracle_mb_ref'].get('derived_steps_per_s', '-')} steps/s | "
              f"zig {row['zig_bolg1']['wall_s']}s {row['zig_bolg1'].get('steps_per_s', '-')} steps/s "
              f"exact={row['zig_bolg1']['stdout_is_input']}", file=sys.stderr)
    tmp = PACK / "_input.bin"
    if tmp.exists():
        tmp.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
