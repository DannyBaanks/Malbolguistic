#!/usr/bin/env python3
"""Level 3: the whole catalog reproduced byte-exact by ONE canonical Malbolge program.

CONTRACT_CAT_FED — a single vendored streaming Cat (`vendor/cat/cat_compact.mal`) takes
each catalog file on stdin and must print those exact bytes on stdout, under two
independent Classic engines. This complements (it does not replace) level 2's
CONTRACT_SELF_CONTAINED, where each .mal holds its own file's envelope.

  python3 tools/verify_level3.py [--evidence DIR] [--max-steps N] [--timeout S]
                                 [--sample N] [--cat PATH]
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = REPO_ROOT / "vendor" / "source_snapshot"
ORACLE_DIR = REPO_ROOT / "vendor" / "oracles"
CAT_PATH = REPO_ROOT / "vendor" / "cat" / "cat_compact.mal"
INVENTORY = REPO_ROOT / "manifest" / "source_inventory.json"

# Pins from vendor/cat/PROVENANCE.txt and vendor/oracles/PROVENANCE.txt.
CAT_SHA256 = "dd8f9b106dd4b25cf190a2fa1cf7f1b03db08d2cb30d4144f8791d46a347079b"
ORACLE_PINS = {
    "mb_ref.c": "a8ce19c2dc93e36f8c9c24a271c4187d68f922b9455262c7199a009763fe3ad3",
    "olmstead_original.c":
        "05abd38e78b266050c5a5e8cc5b36584daa5bbdeb404bfb351de7ea6fa26b510",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_oracle(name: str, extra_flags: list[str], build_dir: Path) -> Path:
    src = ORACLE_DIR / name
    if sha256_file(src) != ORACLE_PINS[name]:
        raise SystemExit(f"ORACLE_PIN_MISMATCH {name}")
    exe = build_dir / name.removesuffix(".c")
    subprocess.run(["gcc", "-O2", *extra_flags, "-std=c11",
                    "-o", str(exe), str(src)], check=True, capture_output=True)
    return exe


def run_cat(exe: Path, extra: list[str], payload: bytes, timeout: float):
    t0 = time.perf_counter()
    try:
        p = subprocess.run([str(exe), str(CAT_RUN), *extra], input=payload,
                           capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "TIMEOUT", b"", b"", time.perf_counter() - t0
    return p.returncode, p.stdout, p.stderr, time.perf_counter() - t0


@contextlib.contextmanager
def scratch():
    d = Path(tempfile.mkdtemp(prefix="lvl3_"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


CAT_RUN = CAT_PATH  # replaced by --cat at runtime


def main() -> int:
    global CAT_RUN
    ap = argparse.ArgumentParser(description="canonical level-3 Cat sweep")
    ap.add_argument("--evidence", default=None,
                    help="output dir; must not exist (evidence paths are never reused)")
    ap.add_argument("--max-steps", type=int, default=300_000_000,
                    help="step budget for mb_ref (olmstead has none; uses --timeout)")
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--sample", type=int, default=0,
                    help="only the first N catalog paths (smoke run; never a sealed claim)")
    ap.add_argument("--cat", default=None,
                    help="alternative Cat .mal to probe; the vendor pin is skipped for it")
    args = ap.parse_args()

    cat = Path(args.cat).resolve() if args.cat else CAT_PATH.resolve()
    if not cat.is_file():
        raise SystemExit(f"MISSING cat program: {cat}")
    cat_sha = sha256_file(cat)
    if cat == CAT_PATH.resolve() and cat_sha != CAT_SHA256:
        raise SystemExit(f"CAT_PIN_MISMATCH: expected {CAT_SHA256} got {cat_sha}")
    CAT_RUN = cat

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ev_dir = Path(args.evidence) if args.evidence else (
        REPO_ROOT / "evidence" / f"level3_cat_sweep_{stamp}")
    if ev_dir.exists():
        raise SystemExit(f"REFUSING to overwrite existing evidence path: {ev_dir}")
    ev_dir.mkdir(parents=True)

    inventory = json.loads(INVENTORY.read_text())
    catalog = sorted((i for i in inventory if i["classification"] == "TEXT"),
                     key=lambda i: i["path"])
    scope_full = len(catalog)
    if args.sample:
        catalog = catalog[: args.sample]

    t0 = time.perf_counter()
    results: list[dict] = []
    with scratch() as bdir:
        cmd_sets = {
            "mb_ref": [build_oracle("mb_ref.c", [], bdir), str(args.max_steps)],
            "olmstead": [build_oracle("olmstead_original.c", ["-w"], bdir)],
        }
        names = list(cmd_sets)
        exact = {n: 0 for n in names}
        for entry in catalog:
            src = SNAPSHOT_DIR / entry["path"]
            rec = {"path": entry["path"], "bytes": None, "inventory_sha_ok": False}
            if not src.is_file():
                rec["fatal"] = "SNAPSHOT_MISSING"
                results.append(rec)
                continue
            data = src.read_bytes()
            rec["bytes"] = len(data)
            rec["inventory_sha_ok"] = hashlib.sha256(data).hexdigest() == entry["sha256"]
            for n in names:
                code, out, err, dur = run_cat(
                    Path(cmd_sets[n][0]), cmd_sets[n][1:], data, args.timeout)
                rec[n] = {"rc": code, "out_bytes": len(out),
                          "exact": code == 0 and out == data,
                          "wall_s": round(dur, 3),
                          "err": err.decode("latin-1", "replace")[:80].strip()}
                if rec[n]["exact"]:
                    exact[n] += 1
            rec["engines_agree"] = all(rec[n]["exact"] for n in names)
            results.append(rec)
    wall = time.perf_counter() - t0

    measured = sum(1 for r in results if r["bytes"] is not None)
    bytes_covered = sum(r["bytes"] or 0 for r in results)
    sha_bad = [r["path"] for r in results if not r["inventory_sha_ok"]]
    failed = [r for r in results if not r.get("engines_agree", False)]
    missing = [r["path"] for r in results if r.get("fatal")]

    summary = {
        "run_utc": stamp,
        "contract": "CONTRACT_CAT_FED",
        "level": 3,
        "snapshot_commit": "befd3af35e70150b76458085208435eef9286bb3",
        "cat": {"artifact": str(cat.relative_to(REPO_ROOT))
                if cat.is_relative_to(REPO_ROOT) else cat.name,
                "sha256": cat_sha, "bytes": cat.stat().st_size,
                "pinned": cat == CAT_PATH.resolve()},
        "engines": names,
        "oracle_pins": ORACLE_PINS,
        "mb_ref_step_budget": args.max_steps,
        "per_process_timeout_s": args.timeout,
        "inventory_text_entries": scope_full,
        "files_in_scope": len(catalog),
        "files_measured": measured,
        "bytes_covered": bytes_covered,
        "exact_by_engine": exact,
        "engines_agree": sum(1 for r in results if r.get("engines_agree")),
        "inventory_sha_mismatch": len(sha_bad),
        "missing_from_snapshot": len(missing),
        "failures": [{"path": r["path"],
                      "why": [n for n in names if not r.get(n, {}).get("exact")]}
                     for r in failed],
        "environment": {
            "system": platform.system(), "release": platform.release(),
            "machine": platform.machine(), "python": sys.version.split()[0],
            "gcc": subprocess.run(["gcc", "--version"], capture_output=True)
                   .stdout.decode().splitlines()[0],
            "cpu_count": os.cpu_count()},
        "wall_seconds": round(wall, 2),
    }
    (ev_dir / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    with (ev_dir / "raw.jsonl").open("w") as sink:
        for r in results:
            sink.write(json.dumps(r) + "\n")

    complete = (not failed and not sha_bad and not missing
                and measured == len(catalog))
    (ev_dir / "VERDICT.md").write_text(
        f"# Nivel 3 — corpus reproducido por Cat canónico ({stamp})\n\n"
        f"Un solo programa Malbolge Classic, `cat_compact.mal` "
        f"({summary['cat']['bytes']} bytes, sha256 `{cat_sha}`), con cada archivo del "
        f"catálogo por stdin.\n\n"
        f"Motor: {', '.join(names)} (fuentes .c pinneadas, recompiladas con gcc -O2 "
        f"antes de la corrida). Cinta canónica 59049 = 3^10; `in` en EOF = 59048.\n\n"
        f"| Medida | Valor |\n|---|---|\n"
        f"| archivos en scope | {len(catalog)} |\n"
        f"| medidos | {measured} |\n"
        f"| bytes cubiertos | {bytes_covered} |\n"
        + "\n".join(f"| exacto bajo `{n}` | {exact[n]} |" for n in names)
        + f"\n| acuerdo entre motores | {summary['engines_agree']} |\n"
        f"| fallos | {len(failed)} |\n"
        f"| sha256 vs inventory | {len(sha_bad)} |\n"
        f"| pared (s) | {summary['wall_seconds']} |\n\n"
        f"- CONTRACT_CAT_FED_COVERS Catalog TEXT = "
        f"{'DEMONSTRATED' if complete and len(catalog) == scope_full else 'PARTIAL' if complete else 'NOT_DEMONSTRATED'}"
        f" ({summary['engines_agree']}/{len(catalog)})\n"
        f"- Scope: entradas `TEXT` del catálogo. Las 20 `BINARY` y 3 `SYMLINK` de "
        f"`manifest/source_inventory.json` NO entran en esta corrida.\n"
        f"- Este nivel NO sustituye al nivel 2: el Cat no incorpora los bytes del "
        f"archivo en el programa, así que no hay artefacto por archivo aquí.\n")

    sums = sorted(
        f"{sha256_file(p)}  {p.relative_to(ev_dir)}"
        for p in ev_dir.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt")
    (ev_dir / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n")

    print(f"scope={len(catalog)} measured={measured} bytes={bytes_covered} "
          f"agree={summary['engines_agree']} failures={len(failed)} wall={wall:.1f}s")
    for n in names:
        print(f"  {n}: exact={exact[n]}/{len(catalog)}")
    for f in summary["failures"][:10]:
        print(f"  FAIL {f['path']}: {f['why']}")
    try:
        shown = ev_dir.relative_to(REPO_ROOT)
    except ValueError:
        shown = ev_dir
    print(f"evidence -> {shown}")
    return 0 if complete else 1


if __name__ == "__main__":
    sys.exit(main())
