#!/usr/bin/env python3
"""Canonical re-verification of level 2: execute the committed .mal artifacts.

The build tool verifies by replaying the generator's in-memory opcode array. This
tool instead runs each artifact FILE through two independent Malbolge engines and
checks the whole evidence chain on disk. Requires no malbolge-generator.

  python3 tools/verify_corpus.py [--evidence DIR] [--max-steps N] [--no-differential]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = REPO_ROOT / "vendor" / "source_snapshot"
MIRROR_DIR = REPO_ROOT / "mirror"
MALBOLGE_DIR = REPO_ROOT / "malbolge"
ORACLE_DIR = REPO_ROOT / "vendor" / "oracles"
MANIFEST = REPO_ROOT / "manifest" / "translation_manifest.json"

# Pins from vendor/oracles/PROVENANCE.txt. A different byte => different engine.
ORACLE_PINS = {
    "mb_ref.c": "a8ce19c2dc93e36f8c9c24a271c4187d68f922b9455262c7199a009763fe3ad3",
    "olmstead_original.c":
        "05abd38e78b266050c5a5e8cc5b36584daa5bbdeb404bfb351de7ea6fa26b510",
}

EXIT_REASON = {0: "HALT", 1: "BAD_SOURCE", 2: "BUDGET_EXHAUSTED",
               3: "STALL", 4: "IO_ERROR", "TIMEOUT": "PROCESS_TIMEOUT"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_oracle(name: str, build_dir: Path) -> Path:
    src = ORACLE_DIR / name
    want = ORACLE_PINS[name]
    got = sha256_file(src)
    if got != want:
        raise SystemExit(f"ORACLE_PIN_MISMATCH {name}: expected {want} got {got}")
    exe = build_dir / name.removesuffix(".c")
    subprocess.run(["gcc", "-O2", "-std=c11", "-o", str(exe), str(src)],
                   check=True, capture_output=True)
    return exe


def run_engine(exe: Path, artifact: Path, extra: list[str], timeout: float):
    cmd = [str(exe), str(artifact)] + extra
    t0 = time.perf_counter()
    try:
        p = subprocess.run(cmd, capture_output=True, input=b"", timeout=timeout)
    except subprocess.TimeoutExpired:
        return "TIMEOUT", b"", time.perf_counter() - t0
    return p.returncode, p.stdout, time.perf_counter() - t0


def main() -> int:
    ap = argparse.ArgumentParser(description="canonical level-2 re-verification")
    ap.add_argument("--evidence", default=None,
                    help="output dir; must not exist (evidence paths are never reused)")
    ap.add_argument("--max-steps", type=int, default=100_000_000,
                    help="step budget for mb_ref (olmstead has none; uses --timeout)")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--no-differential", action="store_true",
                    help="run only mb_ref; skips the Olmstead 1998 engine")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ev_dir = Path(args.evidence) if args.evidence else (
        REPO_ROOT / "evidence" / f"canonical_reverify_{stamp}")
    if ev_dir.exists():
        raise SystemExit(f"REFUSING to overwrite existing evidence path: {ev_dir}")
    ev_dir.mkdir(parents=True)

    entries = {e["source"]: e for e in json.loads(MANIFEST.read_text())}
    inventory = json.loads((REPO_ROOT / "manifest" / "source_inventory.json").read_text())
    # Symlinks are recorded with null sha and deliberately not materialized (SOURCE_REPO.txt).
    exempt = {i["path"] for i in inventory if i["classification"] == "SYMLINK"}
    inv_bad = [i["path"] for i in inventory
               if i["path"] not in exempt and i["sha256"] is not None
               and (p := SNAPSHOT_DIR / i["path"]).exists()
               and sha256_file(p) != i["sha256"]]
    inv_missing = [i["path"] for i in inventory
                   if i["path"] not in exempt and i["sha256"] is not None
                   and not (SNAPSHOT_DIR / i["path"]).exists()]
    print(f"[inventory] entries={len(inventory)} symlinks_exempt={len(exempt)} "
          f"sha_mismatch={len(inv_bad)} missing={len(inv_missing)}")
    for x in (inv_bad + inv_missing)[:10]:
        print(f"  !! {x}")
    artifacts = sorted(MALBOLGE_DIR.rglob("*.mal"))
    if not artifacts:
        raise SystemExit("no .mal artifacts found under malbolge/")

    build_dir = Path(tempfile.mkdtemp(prefix="malboguidstic_oracles_"))
    try:
        mb_ref = build_oracle("mb_ref.c", build_dir)
        engines = [("mb_ref", mb_ref, [str(args.max_steps)])]
        if not args.no_differential:
            engines.append(("olmstead_1998",
                            build_oracle("olmstead_original.c", build_dir), []))

        results = []
        raw = (ev_dir / "raw.jsonl").open("w")
        t_start = time.time()
        for art in artifacts:
            rel = str(art.relative_to(MALBOLGE_DIR))[:-len(".mal")]
            rec = {"artifact": str(art.relative_to(REPO_ROOT)), "source": rel}
            entry = entries.get(rel)
            env_path = MIRROR_DIR / (rel + ".malrt1")
            snap_path = SNAPSHOT_DIR / rel

            rec["artifact_sha256"] = sha256_file(art)
            rec["artifact_sha_expected"] = (entry or {}).get("malbolge", {}).get("sha256")
            rec["artifact_sha_match"] = (rec["artifact_sha_expected"] is not None
                                         and rec["artifact_sha256"] == rec["artifact_sha_expected"])

            if not env_path.exists():
                rec["checks"] = {"envelope_present": False}
                rec["pass"] = False
                results.append(rec)
                raw.write(json.dumps(rec) + "\n")
                continue

            env_bytes = env_path.read_bytes()
            rec["envelope_sha256"] = hashlib.sha256(env_bytes).hexdigest()
            rec["envelope_sha_expected"] = (entry or {}).get("mirror", {}).get("envelope_sha256")
            parts = env_bytes.decode("latin-1").split(":")
            payload = base64.b64decode(parts[1]) if len(parts) >= 3 else b""
            rec["envelope_decode_sha"] = hashlib.sha256(payload).hexdigest()

            checks = {"envelope_present": True,
                      "envelope_sha_match_manifest": rec["envelope_sha_expected"] == rec["envelope_sha256"],
                      "envelope_self_consistent": rec["envelope_decode_sha"] == (parts[2] if len(parts) >= 3 else None)}
            if snap_path.exists():
                checks["snapshot_matches_envelope"] = (
                    snap_path.read_bytes() == payload
                    and hashlib.sha256(snap_path.read_bytes()).hexdigest()
                    == (entry or {}).get("source_sha256"))
            else:
                checks["snapshot_matches_envelope"] = False

            outs = []
            for name, exe, extra in engines:
                code, out, dur = run_engine(exe, art, extra, args.timeout)
                outs.append(out)
                checks[f"{name}_halt"] = (code == 0)
                checks[f"{name}_output_is_envelope"] = (out == env_bytes)
                rec.setdefault("engine", {})[name] = {
                    "exit": code, "exit_reason": EXIT_REASON.get(code, str(code)),
                    "wall_ms": round(dur * 1000, 2)}

            if len(engines) > 1:
                checks["differential_engines_agree"] = all(o == outs[0] for o in outs)
            rec["checks"] = checks
            rec["pass"] = all(checks.values()) and rec["artifact_sha_match"]
            results.append(rec)
            raw.write(json.dumps(rec) + "\n")
        raw.close()
        wall = time.time() - t_start
    finally:
        shutil.rmtree(build_dir, ignore_errors=True)

    passed = [r for r in results if r["pass"]]
    failed = [r for r in results if not r["pass"]]
    durations = [e["wall_ms"] for r in results for e in r.get("engine", {}).values()]

    def count(key: str) -> int:
        return sum(1 for r in results if r["checks"].get(key))

    summary = {
        "run_utc": stamp,
        "inventory": {"entries": len(inventory), "symlinks_exempt": len(exempt),
                      "sha_mismatch": inv_bad, "missing": inv_missing},
        "environment": {
            "system": platform.system(), "release": platform.release(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
            "gcc": subprocess.run(["gcc", "--version"], capture_output=True)
                   .stdout.decode().splitlines()[0],
            "cpu_count": os.cpu_count()},
        "oracle_pins": ORACLE_PINS,
        "engines": [name for name, _, _ in engines],
        "max_steps": args.max_steps,
        "artifacts": len(results),
        "passed": len(passed),
        "failed": len(failed),
        "wall_seconds": round(wall, 2),
        "engine_wall_ms_mean": round(statistics.mean(durations), 2) if durations else None,
        "engine_wall_ms_max": round(max(durations), 2) if durations else None,
        "chain": {
            "artifact_sha_matches_manifest":
                sum(1 for r in results if r["artifact_sha_match"]),
            "envelope_sha_matches_manifest": count("envelope_sha_match_manifest"),
            "envelope_self_consistent": count("envelope_self_consistent"),
            "snapshot_matches_envelope": count("snapshot_matches_envelope"),
            **{f"{name}_halt": count(f"{name}_halt") for name, _, _ in engines},
            **{f"{name}_output_is_envelope": count(f"{name}_output_is_envelope")
               for name, _, _ in engines},
            "differential_engines_agree": count("differential_engines_agree"),
        },
        "failures": [{"source": r["source"],
                      "failed_checks": [k for k, v in r["checks"].items() if not v]}
                     for r in failed],
    }
    (ev_dir / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")

    (ev_dir / "VERDICT.md").write_text(
        f"# Canonical re-verification {stamp}\n\n"
        f"Source commit befd3af35e70150b76458085208435eef9286bb3. "
        f"Engines: {', '.join(summary['engines'])} (pinned sha256, built with gcc -O2).\n\n"
        f"Executed the committed .mal FILES, not the generator's in-memory opcodes.\n\n"
        f"| Link in the chain | Count of {len(results)} |\n|---|---|\n"
        + "\n".join(f"| {k} | {v} |" for k, v in summary["chain"].items())
        + f"\n\n- LEVEL2_ARTIFACT_EXECUTES_CANONICALLY = "
        f"{'DEMONSTRATED' if len(passed) == len(results) else 'PARTIAL'}"
        f" ({len(passed)}/{len(results)})\n"
        f"- LEVEL2_DIFFERENTIAL_ENGINE_AGREEMENT = "
        f"{'DEMONSTRATED' if len(engines) > 1 and count('differential_engines_agree') == len(results) else 'NOT_RUN' if len(engines) == 1 else 'PARTIAL'}\n"
        f"- Snapshot / envelope / manifest byte-exactness = "
        f"{'DEMONSTRATED' if count('snapshot_matches_envelope') == len(results) else 'PARTIAL'}\n"
        f"- Synthesis throughput is NOT measured by this tool; it still requires "
        f"malbolge-generator.\n")

    sums = sorted(
        f"{sha256_file(p)}  {p.relative_to(ev_dir)}"
        for p in ev_dir.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt")
    (ev_dir / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n")

    print(f"artifacts={len(results)} passed={len(passed)} failed={len(failed)} "
          f"wall={wall:.2f}s")
    for k, v in summary["chain"].items():
        flag = "ok " if v == len(results) else "!! "
        print(f"  {flag}{k}={v}/{len(results)}")
    for f in summary["failures"][:10]:
        print(f"  FAIL {f['source']}: {f['failed_checks']}")
    # --evidence may point outside the repo; the exit code is the verdict, not this print.
    try:
        shown = ev_dir.relative_to(REPO_ROOT)
    except ValueError:
        shown = ev_dir
    print(f"evidence -> {shown}")
    return 0 if (not failed and not inv_bad and not inv_missing) else 1


if __name__ == "__main__":
    sys.exit(main())
