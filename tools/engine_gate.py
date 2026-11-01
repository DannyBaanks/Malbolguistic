#!/usr/bin/env python3
"""Semantics gate: does a third engine agree with the pinned canonical oracles?

TIER 1 (corpus control set). For every committed level-2 artifact, every engine
must exit 0 (clean halt) and print byte-identically the envelope that artifact
prints. All of those programs read no stdin and grow no tape.

TIER 2 (negative controls). --control ART=INPUT runs a stdin-consuming program
(the streaming Cat) with real input, where expected stdout == the input bytes.
Agreement on zero-input programs does not establish semantic agreement; this
tier separates the two, because it exercises input, tape growth and EOF.

Engines are NAME=argv-template with {art} for the artifact path and {steps} for
the per-case budget; an empty template argument is dropped (Olmstead takes none):

  python3 tools/engine_gate.py \
    --engine zig_bolg1="python3 tools/gate_adapters/bolg1_runner.py {art} {steps}" \
    --engine toolkit_python="python3 tools/gate_adapters/interpreter_runner.py {art} {steps}" \
    --control ../BolgeForge/artifacts/cat_compact.mal=/tmp/input_8k.bin

Evidence is written to a fresh dated directory; existing paths are never reused.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shlex
import subprocess
import sys
import tempfile
import time

REPO = pathlib.Path(__file__).resolve().parent.parent
ORACLES = REPO / "vendor" / "oracles"
MANIFEST = REPO / "manifest" / "translation_manifest.json"
ORACLE_PINS = {
    "mb_ref.c": "a8ce19c2dc93e36f8c9c24a271c4187d68f922b9455262c7199a009763fe3ad3",
    "olmstead_original.c": "05abd38e78b266050c5a5e8cc5b36584daa5bbdeb404bfb351de7ea6fa26b510",
}
ADAPTER_INPUT = "BOLG1_INPUT_FILE"


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def build(source: str, outdir: pathlib.Path, extra=()) -> pathlib.Path:
    got = sha256_file(ORACLES / source)
    if got != ORACLE_PINS[source]:
        raise SystemExit(f"ORACLE_PIN_MISMATCH {source}: expected {ORACLE_PINS[source]} got {got}")
    exe = outdir / source.replace(".c", "")
    subprocess.run(["gcc", "-O2", "-std=c11", *extra, "-o", str(exe), str(ORACLES / source)],
                   check=True, capture_output=True)
    return exe


def run_engine(argv: list[str], timeout: int, stdin_bytes: bytes, env: dict) -> dict:
    try:
        res = subprocess.run(argv, input=stdin_bytes, capture_output=True, timeout=timeout, env=env)
        return {"rc": res.returncode, "stdout": res.stdout,
                "stderr": res.stderr.decode("latin-1", "replace")[:200].strip()}
    except subprocess.TimeoutExpired:
        return {"rc": "TIMEOUT", "stdout": b"", "stderr": ""}


def expand(cmd: list[str], art: pathlib.Path, steps: int) -> list[str]:
    filled = [part.replace("{art}", str(art)).replace("{steps}", str(steps)) for part in cmd]
    return [part for part in filled if part]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", action="append", default=[], metavar="NAME=ARGV",
                    help="third engine under test; repeatable")
    ap.add_argument("--control", action="append", default=[], metavar="ART=INPUT",
                    help="tier-2 control: expected stdout == INPUT bytes; repeatable")
    ap.add_argument("--limit", type=int, default=0, help="only the N smallest artifacts (smoke run)")
    ap.add_argument("--steps", type=int, default=100_000_000, help="step budget for tier 1")
    ap.add_argument("--control-steps", type=int, default=3_000_000_000, help="step budget for tier 2")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    engines = []
    for spec in args.engine:
        name, _, argv = spec.partition("=")
        engines.append((name, shlex.split(argv)))

    outdir = pathlib.Path(args.out) if args.out else (
        REPO / "evidence" / f"engine_canonical_gate_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}Z")
    if outdir.exists():
        raise SystemExit(f"REFUSED: evidence path already exists (paths are never reused): {outdir}")
    outdir.mkdir(parents=True)
    work = pathlib.Path(tempfile.mkdtemp(prefix="gate-"))

    manifest = json.loads(MANIFEST.read_text())
    entries = [e for e in manifest if e["malbolge"].get("artifact")]
    if args.limit:
        entries.sort(key=lambda e: e["malbolge"].get("chars", 0))
        entries = entries[:args.limit]

    cases = []
    for entry in entries:
        cases.append({"tier": 1, "label": entry["malbolge"]["artifact"],
                      "art": REPO / entry["malbolge"]["artifact"], "input": b"",
                      "expected": (REPO / entry["mirror"]["artifact"]).read_bytes(),
                      "steps": args.steps})
    for spec in args.control:
        art_s, _, in_s = spec.partition("=")
        art = pathlib.Path(art_s).resolve()
        data = pathlib.Path(in_s).read_bytes()
        input_file = work / f"input_{len(data)}.bin"
        input_file.write_bytes(data)
        cases.append({"tier": 2, "label": f"CONTROL {art.name} <- {len(data)}B", "art": art,
                      "input": data, "expected": data, "steps": args.control_steps,
                      "input_file": input_file})

    controls = [("oracle_mb_ref", [str(build("mb_ref.c", work)), "{art}", "{steps}"]),
                ("oracle_olmstead", [str(build("olmstead_original.c", work, extra=("-w",))), "{art}"])]
    all_engines = controls + engines
    tally = {name: {"halt": 0, "expected_exact": 0, "tier1_exact": 0, "tier2_exact": 0,
                    "agrees_with_oracles": 0, "failures": []} for name, _ in all_engines}
    started = time.time()
    raw = outdir / "raw.jsonl"
    with raw.open("w") as sink:
        for idx, case in enumerate(cases, 1):
            env = dict(os.environ)
            if "input_file" in case:
                env[ADAPTER_INPUT] = str(case["input_file"])
            else:
                env.pop(ADAPTER_INPUT, None)
            record = {"tier": case["tier"], "case": case["label"],
                      "artifact_bytes": case["art"].stat().st_size,
                      "input_bytes": len(case["input"]), "expected_bytes": len(case["expected"])}
            outputs = {}
            for name, cmd in all_engines:
                res = run_engine(expand(cmd, case["art"], case["steps"]), args.timeout,
                                 case["input"], env)
                exact = res["rc"] == 0 and res["stdout"] == case["expected"]
                outputs[name] = res["stdout"]
                bucket = tally[name]
                bucket["halt"] += res["rc"] == 0
                bucket["expected_exact"] += exact
                bucket[f"tier{case['tier']}_exact"] += exact
                if not exact:
                    bucket["failures"].append([case["label"], f"rc={res['rc']}", res["stderr"][:70]])
                record[name] = {"rc": res["rc"], "stdout_bytes": len(res["stdout"]), "exact": exact}
            for name, _ in engines:
                tally[name]["agrees_with_oracles"] += (
                    outputs[name] == outputs["oracle_mb_ref"] == outputs["oracle_olmstead"])
            record["all_engines_agree"] = all(outputs[n] == case["expected"] for n, _ in all_engines)
            sink.write(json.dumps(record) + "\n")
            if idx % 100 == 0:
                print(f"{idx}/{len(cases)} {time.time() - started:.0f}s", file=sys.stderr, flush=True)

    tier1 = sum(1 for c in cases if c["tier"] == 1)
    summary = {
        "cases": {"tier1_corpus_artifacts": tier1, "tier2_negative_controls": len(cases) - tier1},
        "elapsed_s": round(time.time() - started, 1),
        "oracle_pins": ORACLE_PINS,
        "engines": {name: {**{k: v for k, v in bucket.items() if k != "failures"},
                           "failed_count": len(bucket["failures"]),
                           "first_failures": bucket["failures"][:8]}
                    for name, bucket in tally.items()},
        "verdicts": {name: ("CONTROL" if name in dict(controls) else
                            ("CANONICAL_AGREEMENT" if bucket["expected_exact"] == len(cases)
                             else "DIVERGENT"))
                     for name, bucket in tally.items()},
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
