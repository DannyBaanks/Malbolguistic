#!/usr/bin/env python3
"""Extend level 2 beyond the generator's practical ceiling, with the Zig port.

Why this tool exists: `tools/build_malboguistic.py` synthesizes level 2 with the
Python generator, and that path needs >3 GB of RSS for a 96 B source and >5.5 GB
at 97 B on this host (evidence/level2_cap_probe_20261101T215239ZZ/). The port
(`tools/zig_canonical/mbsearch.zig`) does the same acceptance contract at
1.11 ms per envelope char with a 165 MB ceiling, so it can reach what the
generator cannot.

What it does, per TEXT entry with a source <= --cap-bytes that has no committed
`.mal` yet:
  1. rebuild `mbsearch` and `mbc` from the committed Zig sources and pin their SHA-256
  2. synthesize against `mirror/<rel>.malrt1` (the envelope IS the acceptance target)
  3. execute the produced FILE under both pinned C oracles (mb_ref, Olmstead 1998) and
     require: halt, stdout == envelope bytes, both engines byte-identical
  4. only then write `malbolge/<rel>.mal`, and only if that path does not already exist

Nothing is overwritten and nothing is synthesized in place: without
`--apply-manifest` the tool runs the full pipeline into scratch and touches neither
`malbolge/` nor `manifest/`, so the blast radius can be read before it is real.

Lineage: artifacts produced here come from the Zig port, NOT from the Python
generator. They are marked `"lineage": "zig_port"` and `"synthesizer": "mbsearch.zig"`
in the manifest, next to the generator-made ones. The port does not reproduce the
committed corpus (0/379 byte-identical, evidence/zig_search_port_gate_20261101T204229ZZ/),
so a mixed `malbolge/` tree is two lineages by construction, not one.

Afterwards, the whole tree (generator-made and port-made) is re-verified by the
sealed tool: `python3 tools/verify_corpus.py`.

Usage:
    python3 tools/extend_level2_zig.py --evidence evidence/level2_zig_extend_<UTC> \
        [--cap-bytes 1024] [--depth 5] [--limit N] [--apply-manifest]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

import verify_corpus as vc  # noqa: E402  (reuse oracle pins, build, engine runner)

SNAPSHOT_DIR = REPO_ROOT / "vendor" / "source_snapshot"
MIRROR_DIR = REPO_ROOT / "mirror"
MALBOLGE_DIR = REPO_ROOT / "malbolge"
MANIFEST = REPO_ROOT / "manifest" / "translation_manifest.json"
ZIG_DIR = REPO_ROOT / "tools" / "zig_canonical"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_zig(work: pathlib.Path) -> dict:
    """Rebuild the port from committed sources; return the pins of what actually ran."""
    info = {"zig_version": subprocess.run(["zig", "version"], capture_output=True)
            .stdout.decode().strip()}
    out = {}
    for name, src in (("mbc", "mbc.zig"), ("mbsearch", "mbsearch.zig")):
        path = ZIG_DIR / src
        exe = work / name
        subprocess.run(["zig", "build-exe", "-O", "ReleaseFast",
                        "-femit-bin=" + str(exe), str(path)],
                       check=True, capture_output=True)
        out[name] = str(exe)
        info[src] = {"source_sha256": sha256_bytes(path.read_bytes()),
                     "binary_sha256": sha256_bytes(exe.read_bytes())}
    return {"pins": info, "bins": out}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True, help="new pack dir (never reused)")
    ap.add_argument("--cap-bytes", type=int, default=1024)
    ap.add_argument("--depth", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0, help="first N candidates only (0 = all)")
    ap.add_argument("--max-steps", type=int, default=500_000_000)
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--apply-manifest", action="store_true",
                    help="write .mal artifacts and extend the manifest (default: dry run)")
    args = ap.parse_args()

    ev_dir = pathlib.Path(args.evidence)
    if not ev_dir.is_absolute():
        ev_dir = REPO_ROOT / ev_dir
    if ev_dir.exists():
        print(f"REFUSING: evidence dir already exists: {ev_dir}", file=sys.stderr)
        return 2
    ev_dir.mkdir(parents=True)

    manifest = json.loads(MANIFEST.read_text())
    by_source = {e["source"]: e for e in manifest}
    candidates = []
    for e in manifest:
        rel = e["source"]
        if e["malbolge"]["status"] == "PASS":
            continue
        env_path = MIRROR_DIR / (rel + ".malrt1")
        snap = SNAPSHOT_DIR / rel
        if not env_path.is_file() or not snap.is_file():
            continue
        size = snap.stat().st_size
        if size > args.cap_bytes:
            continue
        if (MALBOLGE_DIR / (rel + ".mal")).exists():
            continue
        candidates.append((rel, size, env_path))
    candidates.sort(key=lambda c: (-c[1], c[0]))
    if args.limit:
        candidates = candidates[: args.limit]

    print(f"[select] cap={args.cap_bytes}B depth={args.depth} "
          f"candidates={len(candidates)} apply={args.apply_manifest}")

    work = pathlib.Path(tempfile.mkdtemp(prefix="mbextend_"))
    scratch = work / "scratch"
    scratch.mkdir()
    zig = build_zig(work)
    for k, v in zig["pins"].items():
        print(f"[zig] {k}: {v}" if not isinstance(v, dict) else
              f"[zig] {k} src={v['source_sha256'][:12]} bin={v['binary_sha256'][:12]}")

    try:
        mb_ref = vc.build_oracle("mb_ref.c", work)
        olmstead = vc.build_oracle("olmstead_original.c", work)
    except SystemExit as e:
        print(f"ORACLE PROBLEM: {e}", file=sys.stderr)
        shutil.rmtree(work, ignore_errors=True)
        return 2

    t_start = time.time()
    raw = (ev_dir / "raw.jsonl").open("w")
    results = []
    for i, (rel, size, env_path) in enumerate(candidates, 1):
        env_bytes = env_path.read_bytes()
        snap = SNAPSHOT_DIR / rel
        rec = {"source": rel, "source_bytes": size,
               "envelope_artifact": f"mirror/{rel}.malrt1",
               "envelope_chars": len(env_bytes),
               "envelope_sha256": sha256_bytes(env_bytes),
               "engine": "zig/mbsearch", "depth": args.depth, "seed": args.seed}
        prog_out = scratch / "cand.mal"
        stats_out = scratch / "cand.json"
        if prog_out.exists():
            prog_out.unlink()
        t0 = time.time()
        p = subprocess.run([zig["bins"]["mbsearch"], "--target-file", str(env_path),
                            "--out", str(prog_out), "--stats", str(stats_out),
                            "--depth", str(args.depth), "--seed", str(args.seed)],
                           capture_output=True, timeout=args.timeout)
        rec["search_wall_s"] = round(time.time() - t0, 3)
        if p.returncode != 0:
            rec["status"] = "SYNTH_FAIL"
            rec["mbsearch_stderr"] = p.stderr.decode().strip()[:200]
            results.append(rec)
            raw.write(json.dumps(rec) + "\n")
            print(f"  [{i}/{len(candidates)}] SYNTH_FAIL {rel}: {rec['mbsearch_stderr']}")
            continue
        st = json.loads(stats_out.read_text()) if stats_out.exists() else {}
        program = prog_out.read_text()
        prog_bytes = prog_out.read_bytes()
        rec.update({"program_chars": len(program),
                    "program_sha256": sha256_bytes(prog_bytes),
                    "expansion_ratio": round(len(program) / len(env_bytes), 2),
                    "evaluations": st.get("evaluations"),
                    "canonical_ok_in_process": st.get("canonical_ok")})
        art_path = MALBOLGE_DIR / (rel + ".mal")
        tmp_art = work / "art.mal"
        tmp_art.write_bytes(prog_bytes)
        checks = {}
        for name, exe, extra in (("mb_ref", mb_ref, [str(args.max_steps)]),
                                 ("olmstead_1998", olmstead, [])):
            code, out, dur = vc.run_engine(exe, tmp_art, extra, args.timeout)
            checks[f"{name}_halt"] = (code == 0)
            checks[f"{name}_output_is_envelope"] = (out == env_bytes)
            rec.setdefault("oracles", {})[name] = {
                "exit": code, "exit_reason": vc.EXIT_REASON.get(code, str(code)),
                "wall_ms": round(dur * 1000, 2)}
            if name == "mb_ref":
                rec["mb_ref_stdout_sha256"] = sha256_bytes(out)
            else:
                rec["olmstead_stdout_sha256"] = sha256_bytes(out)
        checks["differential_engines_agree"] = (
            rec["mb_ref_stdout_sha256"] == rec["olmstead_stdout_sha256"])
        parts = env_bytes.decode("latin-1").split(":")
        payload = base64.b64decode(parts[1]) if len(parts) >= 3 else b""
        checks["envelope_self_consistent"] = (
            len(parts) >= 3 and sha256_bytes(payload) == parts[2])
        checks["envelope_decode_matches_snapshot"] = (payload == snap.read_bytes())
        checks["artifact_not_already_committed"] = not art_path.exists()
        rec["checks"] = checks
        rec["pass"] = all(checks.values()) and bool(st.get("canonical_ok", True))
        rec["status"] = "PASS" if rec["pass"] else "FAILED"
        if rec["pass"] and args.apply_manifest:
            art_path.parent.mkdir(parents=True, exist_ok=True)
            art_path.write_bytes(prog_bytes)
        results.append(rec)
        raw.write(json.dumps(rec) + "\n")
        if i % 50 == 0 or not rec["pass"]:
            done = sum(1 for r in results if r["status"] == "PASS")
            print(f"  [{i}/{len(candidates)}] pass={done} fail="
                  f"{len(results) - done} wall={time.time() - t_start:.0f}s")
    raw.close()
    wall = time.time() - t_start

    passed = [r for r in results if r["status"] == "PASS"]
    failed = [r for r in results if r["status"] != "PASS"]
    summary = {
        "run_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool": "tools/extend_level2_zig.py",
        "mode": "apply" if args.apply_manifest else "dry-run",
        "cap_bytes": args.cap_bytes, "depth": args.depth, "seed": args.seed,
        "candidates": len(candidates), "passed": len(passed), "failed": len(failed),
        "wall_s": round(wall, 1),
        "zig_pins": zig["pins"],
        "oracle_pins": vc.ORACLE_PINS,
        "program_chars_total": sum(r.get("program_chars", 0) for r in passed),
        "evaluations_total": sum(r.get("evaluations") or 0 for r in passed),
        "median_search_wall_s": (sorted(r["search_wall_s"] for r in passed)[len(passed) // 2]
                                 if passed else None),
        "lineage": "zig_port",
        "failure_reasons": [
            {"source": r["source"], "status": r["status"],
             "failed_checks": [k for k, v in (r.get("checks") or {}).items() if not v],
             "mbsearch_stderr": r.get("mbsearch_stderr")}
            for r in failed][:50],
        "not_claimed": [
            "byte-identity with the generator-made corpus: the port is a second lineage "
            "(0/379 identical, zig_search_port_gate_20261101T204229ZZ/)",
            "reproducibility of the generator path: level 2 synthesis is not byte-reproducible",
        ],
    }
    (ev_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    if args.apply_manifest and passed:
        for r in passed:
            e = by_source[r["source"]]
            e["malbolge"] = {
                "status": "PASS",
                "artifact": f"malbolge/{r['source']}.mal",
                "sha256": r["program_sha256"],
                "chars": r["program_chars"],
                "expansion_ratio": r["expansion_ratio"],
                "execution_status": "halt_opcode",
                "steps": None,
                "end_to_end_roundtrip": "PASS",
                "codec_roundtrip": "PASS",
                "synthesis": "PASS",
                "search_depth": args.depth,
                "duration_s": r["search_wall_s"],
                "lineage": "zig_port",
                "synthesizer": "tools/zig_canonical/mbsearch.zig",
                "synthesizer_binary_sha256": zig["pins"]["mbsearch.zig"]["binary_sha256"],
                "evaluations": r["evaluations"],
                "verified_by": ["mb_ref", "olmstead_1998"],
            }
        text = json.dumps(manifest, indent=1) + "\n"
        before = sha256_bytes(MANIFEST.read_bytes())
        tmp = MANIFEST.with_suffix(".json.tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, MANIFEST)
        after = sha256_bytes(MANIFEST.read_bytes())
        (ev_dir / "manifest_transition.json").write_text(json.dumps({
            "before_sha256": before, "after_sha256": after,
            "entries_added": len(passed),
            "previous_pointer": (REPO_ROOT / "evidence" / "manifest_sha256.txt").read_text(),
        }, indent=2) + "\n")
        print(f"[manifest] {before[:12]} -> {after[:12]} (+{len(passed)} entries)")

    shutil.rmtree(work, ignore_errors=True)
    sums = [f"{sha256_bytes(p.read_bytes())}  {p.relative_to(ev_dir)}"
            for p in sorted(ev_dir.rglob("*")) if p.is_file() and p.name != "SHA256SUMS.txt"]
    (ev_dir / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n")
    try:
        shown = ev_dir.relative_to(REPO_ROOT)
    except ValueError:
        shown = ev_dir
    print(f"[done] passed={len(passed)} failed={len(failed)} wall={wall:.0f}s")
    print(f"evidence -> {shown}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
