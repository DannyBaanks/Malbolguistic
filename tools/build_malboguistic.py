#!/usr/bin/env python3
"""MALBOGUISTIC reproducible build.

Pipeline (two honest levels):

  LEVEL 1 - CODEC MIRROR (every TEXT file, mandatory):
      source bytes -> MALRT1 envelope -> decode -> SHA256 parity
      artifact: mirror/<path>.malrt1   (ASCII envelope; NOT a Malbolge program)

  LEVEL 2 - REAL MALBOLGE (bounded, best-effort under explicit budgets):
      source bytes -> MALRT1 envelope -> pure Malbolge synthesis
      -> canonical Malbolge execution -> recovered envelope -> decode
      -> SHA256 parity against source bytes
      artifact: malbolge/<path>.mal    (executable Malbolge program)

Nothing is faked: a .malrt1 envelope is never presented as a Malbolge program,
and a file only gets a .mal when synthesis+execution+decode verified PASS.

Exit code 0 iff every selected TEXT file has CODEC_ROUNDTRIP PASS and no
synthesized file failed verification. Budget exhaustion is not a failure;
it is reported as SKIPPED_BUDGET / SKIPPED_TOO_LARGE.

Usage:
    py tools/build_malboguistic.py [--e2e-max-bytes 128] [--e2e-budget-seconds 3600]
                                   [--workers N] [--level1-only] [--resume]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = REPO_ROOT / "vendor" / "source_snapshot"
VENDOR_PKG = REPO_ROOT / "vendor"
sys.path.insert(0, str(VENDOR_PKG))
MIRROR_DIR = REPO_ROOT / "mirror"
MALBOLGE_DIR = REPO_ROOT / "malbolge"
MANIFEST_DIR = REPO_ROOT / "manifest"
EVIDENCE_DIR = REPO_ROOT / "evidence"

# The three symlinks that exist in the pinned linguist tarball. bsdtar on this
# host cannot materialize them (Windows privilege), so they are recorded,
# hashed as link-target strings, and never translated.
KNOWN_SYMLINKS = {
    "samples/Ant Build System/filenames/build.xml": "ant.xml",
    "samples/Markdown/symlink.md": "README.mdown",
    "test/fixtures/SVG/alg_schema.link.svg": "alg_schema.svg",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


# ---------------------------------------------------------------------------
# Phase 2 - classification
# ---------------------------------------------------------------------------

def classify_file(path: Path):
    """Return (classification, encoding, reason)."""
    raw = path.read_bytes()
    if b"\x00" in raw:
        return "BINARY", "none", "contains NUL byte"
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return "BINARY", "none", "not valid UTF-8"
    return "TEXT", "utf-8", None


def build_inventory() -> list[dict]:
    inventory = []
    for p in sorted(SNAPSHOT_DIR.rglob("*")):
        rel = p.relative_to(SNAPSHOT_DIR).as_posix()
        if p.is_symlink():
            inventory.append({
                "path": rel, "size_bytes": 0, "classification": "SYMLINK",
                "encoding_detected": None, "sha256": None,
                "selected_for_translation": False,
                "skip_reason": f"symlink -> {os.readlink(p)}",
            })
            continue
        if not p.is_file():
            continue
        if rel in KNOWN_SYMLINKS:
            inventory.append({
                "path": rel, "size_bytes": 0, "classification": "SYMLINK",
                "encoding_detected": None, "sha256": None,
                "selected_for_translation": False,
                "skip_reason": f"symlink -> {KNOWN_SYMLINKS[rel]} "
                               "(not materializable on this host; recorded)",
            })
            continue
        raw = p.read_bytes()
        cls, enc, reason = classify_file(p)
        inventory.append({
            "path": rel,
            "size_bytes": len(raw),
            "classification": cls,
            "encoding_detected": enc,
            "sha256": sha256_bytes(raw),
            "selected_for_translation": cls == "TEXT",
            "skip_reason": None if cls == "TEXT" else reason,
        })
    # Symlinks that exist in the pinned tarball but could not be materialized
    # on this host: recorded explicitly so the inventory matches the source.
    for rel, target in KNOWN_SYMLINKS.items():
        if not (SNAPSHOT_DIR / rel).exists():
            inventory.append({
                "path": rel,
                "size_bytes": None,
                "classification": "SYMLINK",
                "encoding_detected": None,
                "sha256": None,
                "selected_for_translation": False,
                "skip_reason": f"symlink -> {target} "
                               "(not materializable on this host; recorded)",
            })
    inventory.sort(key=lambda e: e["path"])
    return inventory


# ---------------------------------------------------------------------------
# Level 1 - codec mirror
# ---------------------------------------------------------------------------

def level1_mirror(entry: dict) -> dict:
    """TEXT entry -> .malrt1 envelope artifact + codec roundtrip check."""
    src = SNAPSHOT_DIR / entry["path"]
    raw = src.read_bytes()
    from malbolge_translator.roundtrip import (
        encode_roundtrip_bytes, decode_roundtrip_bytes,
    )
    env = encode_roundtrip_bytes(raw)
    payload = env.payload
    out_rel = entry["path"] + ".malrt1"
    out_path = MIRROR_DIR / out_rel
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload, encoding="ascii", newline="")
    recovered = decode_roundtrip_bytes(payload)
    rec_sha = sha256_bytes(recovered)
    return {
        "source": entry["path"],
        "mirror_artifact": "mirror/" + out_rel,
        "source_sha256": sha256_bytes(raw),
        "envelope_sha256": sha256_bytes(payload.encode("ascii")),
        "recovered_sha256": rec_sha,
        "codec_roundtrip_equal": rec_sha == sha256_bytes(raw),
        "source_size_bytes": len(raw),
        "envelope_chars": len(payload),
    }


# ---------------------------------------------------------------------------
# Level 2 - real Malbolge, executed
# ---------------------------------------------------------------------------

_WORKER_TRANSLATOR = None
_WORKER_SEARCH_DEPTH = 5


def _init_worker(search_depth: int = 5):
    global _WORKER_TRANSLATOR, _WORKER_SEARCH_DEPTH
    _WORKER_SEARCH_DEPTH = search_depth
    from malbolge_translator import MalbolgeTranslator
    _WORKER_TRANSLATOR = MalbolgeTranslator(max_search_depth=search_depth)


def level2_synthesize(path_rel: str, src_sha: str, max_steps: int,
                      search_depth: int = 5) -> dict:
    """Runs in a worker process. Full E2E: synthesize + execute + verify."""
    translator = _WORKER_TRANSLATOR
    if (translator is None or _WORKER_SEARCH_DEPTH != search_depth):
        _init_worker(search_depth)
        translator = _WORKER_TRANSLATOR
    raw = (SNAPSHOT_DIR / path_rel).read_bytes()
    if sha256_bytes(raw) != src_sha:
        return {"source": path_rel, "level2_status": "FAILED",
                "error": "source sha changed between inventory and synthesis"}
    text = raw.decode("utf-8")
    t0 = time.time()
    try:
        result, ver = translator.translate_and_verify_roundtrip(text, max_steps=max_steps)
    except Exception as e:  # no fakes: explicit failure
        return {"source": path_rel, "level2_status": "FAILED",
                "error": f"{type(e).__name__}: {e}"}
    dur = time.time() - t0
    ok = bool(ver.roundtrip_pass)
    out = {
        "source": path_rel,
        "level2_status": "PASS" if ok else "FAILED",
        "source_bytes": len(raw),
        "search_depth": search_depth,
        "codec_roundtrip": ver.codec_roundtrip,
        "malbolge_synthesis": ver.malbolge_synthesis,
        "malbolge_execution_status": ver.malbolge_execution_status,
        "malbolge_steps": ver.malbolge_steps,
        "end_to_end_roundtrip": ver.end_to_end_roundtrip,
        "duration_s": round(dur, 3),
        "error": ver.error if not ok else None,
    }
    if ok:
        program = result.translation.full_program
        out_rel = path_rel + ".mal"
        out_path = MALBOLGE_DIR / out_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(program, encoding="ascii", newline="")
        out.update({
            "malbolge_artifact": "malbolge/" + out_rel,
            "malbolge_sha256": sha256_bytes(program.encode("ascii")),
            "malbolge_chars": len(program),
            "expansion_ratio": (round(len(program) / len(raw), 2) if raw else None),
        })
    return out


# ---------------------------------------------------------------------------
# Committed corpus & sealed level 3
# ---------------------------------------------------------------------------

# Provenance keys the corpus tools write; a rebuild carries them through instead
# of flattening them, so a Zig-extended entry stays distinguishable from a
# generator-made one across builds.
PASS_CARRY_KEYS = ("lineage", "synthesizer", "synthesizer_binary_sha256",
                   "evaluations", "verified_by")


def adopt_committed(text_entries: list[dict], l2_results: dict) -> set[str]:
    """Carry over every PASS the committed manifest declares, unmodified.

    Re-synthesizing a source that already has a verified .mal replaces sealed
    bytes with different ones: the Python generator is not byte-reproducible
    (evidence/synthesis_linux_probe_20261101/), and the Zig extension puts
    artifacts above --e2e-max-bytes that a rebuild would otherwise demote to
    SKIPPED_TOO_LARGE while leaving the file on disk. A PASS is carried over only
    if its artifact still hashes to the recorded sha256 and its source is
    unchanged; anything else falls through to normal synthesis.
    """
    manifest_path = MANIFEST_DIR / "translation_manifest.json"
    if not manifest_path.exists():
        return set()
    try:
        prior = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    by_path = {e["path"]: e for e in text_entries}
    adopted: set[str] = set()
    for entry in prior:
        mb = entry.get("malbolge") or {}
        src = by_path.get(entry.get("source", ""))
        if src is None or mb.get("status") != "PASS":
            continue
        art = (REPO_ROOT / str(mb.get("artifact", ""))).resolve()
        if MALBOLGE_DIR not in art.parents or not art.is_file():
            continue
        if sha256_file(art) != mb.get("sha256"):
            continue
        if entry.get("source_sha256") != src["sha256"]:
            continue
        if not (MIRROR_DIR / (src["path"] + ".malrt1")).is_file():
            continue
        rec = {
            "source": src["path"],
            "level2_status": "PASS",
            "source_bytes": src["size_bytes"],
            "source_sha256_cached": src["sha256"],
            "malbolge_artifact": mb["artifact"],
            "malbolge_sha256": mb["sha256"],
            "malbolge_chars": mb["chars"],
            "expansion_ratio": mb["expansion_ratio"],
            "malbolge_execution_status": mb["execution_status"],
            "malbolge_steps": mb["steps"],
            "end_to_end_roundtrip": mb["end_to_end_roundtrip"],
            "codec_roundtrip": mb["codec_roundtrip"],
            "malbolge_synthesis": mb["synthesis"],
            "search_depth": mb.get("search_depth"),
            "duration_s": mb.get("duration_s"),
        }
        for k in PASS_CARRY_KEYS:
            if k in mb:
                rec[k] = mb[k]
        l2_results[src["path"]] = rec
        adopted.add(src["path"])
    return adopted


def level3_sealed() -> dict:
    """Read the newest sealed level-3 Cat sweep that covers the whole catalog."""
    cat = REPO_ROOT / "vendor" / "cat" / "cat_compact.mal"
    pin = "dd8f9b106dd4b25cf190a2fa1cf7f1b03db08d2cb30d4144f8791d46a347079b"
    if not cat.is_file() or sha256_file(cat) != pin:
        return {"claim": "NOT_SEALED: vendor/cat/cat_compact.mal missing or off-pin"}
    packs = sorted(EVIDENCE_DIR.glob("level3_cat_sweep_*/summary.json"))
    best = None
    for path in packs:
        try:
            s = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if (s.get("contract") == "CONTRACT_CAT_FED"
                and s.get("cat", {}).get("sha256") == pin
                and s.get("failures") == []
                and s.get("files_measured") == s.get("inventory_text_entries")
                and s.get("files_measured", 0) > 0):
            best = (path, s)
    if best is None:
        return {"claim": f"NOT_SEALED: no full-catalog sweep under "
                         f"evidence/level3_cat_sweep_* ({len(packs)} pack(s))"}
    path, s = best
    return {
        "claim": f"DEMONSTRATED over {s['files_measured']}/{s['inventory_text_entries']} "
                 f"catalog TEXT files ({s['bytes_covered']} bytes) under "
                 f"{', '.join(s['engines'])} — sealed at {path.parent.name}",
        "evidence": str(path.parent.relative_to(REPO_ROOT)),
        "files": s["files_measured"],
        "bytes": s["bytes_covered"],
        "engines": s["engines"],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="MALBOGUISTIC reproducible build")
    ap.add_argument("--e2e-max-bytes", type=int, default=128,
                    help="max source bytes eligible for real Malbolge synthesis")
    ap.add_argument("--e2e-budget-seconds", type=float, default=3600.0,
                    help="global wall-clock budget for level 2")
    ap.add_argument("--workers", type=int, default=3,
                    help="measured: 7 workers thrash this host; 3 is safe")
    ap.add_argument("--stall-seconds", type=float, default=900.0,
                    help="abort level 2 if no file completes for this long")
    ap.add_argument("--search-depth", type=int, default=5,
                    help="generator max_search_depth; 3 measured ~2x faster "
                         "than 5 on ~120 B files (documented per file)")
    ap.add_argument("--max-steps", type=int, default=5_000_000)
    ap.add_argument("--level1-only", action="store_true")
    ap.add_argument("--serial", action="store_true",
                    help="level 2 in-process, fresh translator per file "
                         "(fallback when the process pool misbehaves)")
    ap.add_argument("--resume", action="store_true",
                    help="reuse prior PASS/FAILED level-2 results for unchanged sources")
    ap.add_argument("--no-adopt", dest="adopt", action="store_false",
                    help="re-synthesize sources that already have a committed .mal; "
                         "this replaces sealed bytes, and the generator is not "
                         "byte-reproducible")
    ap.set_defaults(adopt=True)
    args = ap.parse_args()

    t_start = time.time()
    MANIFEST_DIR.mkdir(exist_ok=True)
    EVIDENCE_DIR.mkdir(exist_ok=True)

    # ---- Phase 2: inventory -------------------------------------------------
    inventory = build_inventory()
    (MANIFEST_DIR / "source_inventory.json").write_text(
        json.dumps(inventory, indent=1) + "\n", encoding="utf-8")
    text_entries = [e for e in inventory if e["classification"] == "TEXT"]
    binary = [e for e in inventory if e["classification"] == "BINARY"]
    symlinks = [e for e in inventory if e["classification"] == "SYMLINK"]
    print(f"[inventory] TEXT={len(text_entries)} BINARY={len(binary)} "
          f"SYMLINK={len(symlinks)}", flush=True)

    # ---- Level 1: codec mirror ---------------------------------------------
    l1_results = []
    for i, e in enumerate(text_entries, 1):
        r = level1_mirror(e)
        l1_results.append(r)
        if i % 500 == 0:
            print(f"[level1] {i}/{len(text_entries)}", flush=True)
    codec_fails = [r for r in l1_results if not r["codec_roundtrip_equal"]]
    print(f"[level1] done: {len(l1_results)} mirrored, "
          f"mismatches={len(codec_fails)}", flush=True)

    # ---- Level 2: real Malbolge under budget --------------------------------
    candidates = sorted(
        (e for e in text_entries if e["size_bytes"] <= args.e2e_max_bytes),
        key=lambda e: (e["size_bytes"], e["path"]),
    )
    l2_results: dict[str, dict] = {}
    state_path = EVIDENCE_DIR / "level2_state.json"
    if args.resume and state_path.exists():
        prev = json.loads(state_path.read_text(encoding="utf-8"))
        by_path = {e["path"]: e for e in text_entries}
        for p, r in prev.items():
            cur = by_path.get(p)
            if (cur and r.get("source_sha256_cached") == cur["sha256"]
                    and r["level2_status"] in ("PASS", "FAILED")
                    and not str(r.get("error", "")).startswith("watchdog:")):
                l2_results[p] = r
        resumed = len(l2_results)
    else:
        resumed = 0

    # ---- carry over the committed corpus --------------------------------------
    adopted = adopt_committed(text_entries, l2_results) if args.adopt else set()
    print(f"[adopt] committed level-2 artifacts carried over: {len(adopted)} "
          f"(not re-synthesized)", flush=True)

    l2_done_paths = {p for p in l2_results}
    if not args.level1_only and candidates and args.serial:
        deadline = time.time() + args.e2e_budget_seconds
        todo = [e for e in candidates if e["path"] not in l2_results]
        print(f"[level2] SERIAL mode: todo={len(todo)}, "
              f"budget={args.e2e_budget_seconds}s", flush=True)
        for i, e in enumerate(todo, 1):
            if time.time() > deadline:
                break
            r = level2_synthesize(e["path"], e["sha256"], args.max_steps,
                                  args.search_depth)
            r["source_sha256_cached"] = e["sha256"]
            l2_results[e["path"]] = r
            print(f"[level2] {len(l2_results)}/{len(candidates)} "
                  f"{r['level2_status']} {e['size_bytes']}B {e['path']}",
                  flush=True)
            state_path.write_text(json.dumps(l2_results, indent=0),
                                  encoding="utf-8")
    elif not args.level1_only and candidates:
        from concurrent.futures import wait, FIRST_COMPLETED
        from concurrent.futures.process import BrokenProcessPool
        deadline = time.time() + args.e2e_budget_seconds
        todo = [e for e in candidates if e["path"] not in l2_results]
        print(f"[level2] candidates(<= {args.e2e_max_bytes}B): {len(candidates)}, "
              f"resumed: {resumed}, todo: {len(todo)}, "
              f"budget: {args.e2e_budget_seconds}s, workers: {args.workers}",
              flush=True)
        stall_limit = args.stall_seconds
        idx = 0  # next todo position to submit
        stop_submitting = False
        n_done_this_run = 0

        def persist_state():
            state_path.write_text(json.dumps(l2_results, indent=0),
                                  encoding="utf-8")

        with ProcessPoolExecutor(max_workers=args.workers,
                                 initializer=_init_worker,
                                 initargs=(args.search_depth,),
                                 max_tasks_per_child=1) as pool:
            futures: dict = {}
            last_progress = time.time()
            while (idx < len(todo) or futures):
                # fill the pipe
                while (not stop_submitting and idx < len(todo)
                       and len(futures) < args.workers
                       and time.time() < deadline):
                    e = todo[idx]
                    idx += 1
                    try:
                        fut = pool.submit(level2_synthesize, e["path"],
                                          e["sha256"], args.max_steps,
                                          args.search_depth)
                        futures[fut] = e
                    except (BrokenProcessPool, RuntimeError) as exc:
                        stop_submitting = True
                        l2_results[e["path"]] = {
                            "source": e["path"], "level2_status": "FAILED",
                            "error": f"pool broken at submit: {exc}",
                            "source_sha256_cached": e["sha256"],
                        }
                        break
                if time.time() >= deadline:
                    stop_submitting = True
                if not futures:
                    break
                done_set, _ = wait(tuple(futures), timeout=60,
                                   return_when=FIRST_COMPLETED)
                if not done_set:
                    if time.time() - last_progress > stall_limit:
                        print("[level2] STALLED: no completion for "
                              f"{stall_limit:.0f}s; aborting level 2",
                              flush=True)
                        for fut, e in futures.items():
                            fut.cancel()
                            l2_results[e["path"]] = {
                                "source": e["path"],
                                "level2_status": "FAILED",
                                "error": "watchdog: worker stalled beyond "
                                         f"{stall_limit:.0f}s (likely hung "
                                         "synthesis); worker killed",
                                "source_sha256_cached": e["sha256"],
                            }
                        futures.clear()
                        stop_submitting = True
                        # actually kill hung workers so pool.shutdown won't hang
                        for proc in list(getattr(pool, "_processes", {}).values()):
                            try:
                                proc.terminate()
                            except Exception:
                                pass
                        break
                    continue
                for fut in done_set:
                    e = futures.pop(fut)
                    try:
                        r = fut.result()
                    except (BrokenProcessPool, Exception) as exc:
                        r = {"source": e["path"], "level2_status": "FAILED",
                             "error": f"worker exception: {type(exc).__name__}: {exc}"}
                        stop_submitting = True  # pool may be dead; stop feeding
                    r.setdefault("source", e["path"])
                    r["source_sha256_cached"] = e["sha256"]
                    l2_results[e["path"]] = r
                    l2_done_paths.add(e["path"])
                    n_done_this_run += 1
                    last_progress = time.time()
                    st = r["level2_status"]
                    print(f"[level2] {resumed + n_done_this_run}/{len(candidates)} "
                          f"{st} {e['size_bytes']}B {e['path']}", flush=True)
                persist_state()
            # files still in `todo` beyond idx: SKIPPED_BUDGET (handled below)

    # mark skipped candidates honestly
    for e in candidates:
        if e["path"] not in l2_results:
            l2_results[e["path"]] = {
                "source": e["path"], "level2_status": "SKIPPED_BUDGET",
                "source_sha256_cached": e["sha256"],
            }
    for e in text_entries:
        if e["size_bytes"] > args.e2e_max_bytes and e["path"] not in adopted:
            l2_results[e["path"]] = {
                "source": e["path"], "level2_status": "SKIPPED_TOO_LARGE",
                "source_size_bytes": e["size_bytes"],
                "source_sha256_cached": e["sha256"],
            }

    state_path.write_text(json.dumps(l2_results, indent=0), encoding="utf-8")

    # ---- merge into translation manifest ------------------------------------
    l1_by_path = {r["source"]: r for r in l1_results}
    manifest = []
    for e in sorted(text_entries, key=lambda x: x["path"]):
        l1 = l1_by_path[e["path"]]
        l2 = l2_results[e["path"]]
        entry = {
            "source": e["path"],
            "source_sha256": l1["source_sha256"],
            "mirror": {
                "artifact": l1["mirror_artifact"],
                "envelope_sha256": l1["envelope_sha256"],
                "roundtrip_sha256": l1["recovered_sha256"],
                "roundtrip_equal": l1["codec_roundtrip_equal"],
            },
            "malbolge": {
                "status": l2["level2_status"],
            },
        }
        if l2["level2_status"] == "PASS":
            entry["malbolge"].update({
                "artifact": l2["malbolge_artifact"],
                "sha256": l2["malbolge_sha256"],
                "chars": l2["malbolge_chars"],
                "expansion_ratio": l2["expansion_ratio"],
                "execution_status": l2["malbolge_execution_status"],
                "steps": l2["malbolge_steps"],
                "end_to_end_roundtrip": l2["end_to_end_roundtrip"],
                "codec_roundtrip": l2["codec_roundtrip"],
                "synthesis": l2["malbolge_synthesis"],
                "search_depth": l2.get("search_depth"),
                "duration_s": l2["duration_s"],
                **{k: l2[k] for k in PASS_CARRY_KEYS if k in l2},
            })
        elif l2["level2_status"] == "FAILED":
            entry["malbolge"]["error"] = l2.get("error")
        manifest.append(entry)

    manifest_path = MANIFEST_DIR / "translation_manifest.json"
    committed_manifest = (manifest_path.read_bytes() if manifest_path.exists()
                          else None)
    manifest_text = json.dumps(manifest, indent=1) + "\n"
    manifest_path.write_text(manifest_text, encoding="utf-8", newline="")
    # hash the bytes actually on disk (never the in-memory string)
    manifest_sha = sha256_file(manifest_path)
    manifest_unchanged = (committed_manifest is not None
                          and manifest_path.read_bytes() == committed_manifest)
    (EVIDENCE_DIR / "manifest_sha256.txt").write_text(
        f"{manifest_sha}  manifest/translation_manifest.json\n", encoding="utf-8")

    # ---- evidence: roundtrip summary + metrics -------------------------------
    l2_pass = [r for r in l2_results.values() if r["level2_status"] == "PASS"]
    l2_fail = [r for r in l2_results.values() if r["level2_status"] == "FAILED"]
    l2_synth_ok = sum(1 for r in l2_results.values()
                      if r.get("malbolge_synthesis") == "PASS")

    roundtrip = {
        "FILES_TOTAL": len(inventory),
        "FILES_TEXT": len(text_entries),
        "FILES_BINARY": len(binary),
        "FILES_SYMLINK": len(symlinks),
        "FILES_SELECTED": len(text_entries),
        "LEVEL1_CODEC_MIRRORED": len(l1_results),
        "LEVEL1_CODEC_MISMATCH": len(codec_fails),
        "LEVEL2_ELIGIBLE_LE_MAX_BYTES": len(candidates),
        "LEVEL2_E2E_MAX_BYTES": args.e2e_max_bytes,
        "LEVEL2_BUDGET_SECONDS": args.e2e_budget_seconds,
        "MALBOLGE_SYNTHESIS_PASS": l2_synth_ok,
        "MALBOLGE_E2E_PASS": len(l2_pass),
        "MALBOLGE_E2E_FAILED": len(l2_fail),
        "LEVEL2_SKIPPED_BUDGET": sum(1 for r in l2_results.values()
                                     if r["level2_status"] == "SKIPPED_BUDGET"),
        "LEVEL2_SKIPPED_TOO_LARGE": sum(1 for r in l2_results.values()
                                        if r["level2_status"] == "SKIPPED_TOO_LARGE"),
        "ROUNDTRIP_MISMATCH": len(codec_fails) + len(l2_fail),
        "TRANSLATION_FAILURES": len(l2_fail),
        "BINARY_SKIPPED": len(binary),
    }
    (EVIDENCE_DIR / "roundtrip.json").write_text(
        json.dumps(roundtrip, indent=1) + "\n", encoding="utf-8")

    orig_bytes = sum(e["size_bytes"] for e in text_entries)
    mirror_bytes = sum(r["envelope_chars"] for r in l1_results)
    ratios = [r["expansion_ratio"] for r in l2_pass if r.get("expansion_ratio")]
    mal_bytes = sum(r["malbolge_chars"] for r in l2_pass)
    largest = sorted(l2_pass, key=lambda r: r["malbolge_chars"],
                     reverse=True)[:10]
    l3 = level3_sealed()
    metrics = {
        "source_commit": (REPO_ROOT / "SOURCE_COMMIT.txt").read_text().strip(),
        "LINGUIST_SOURCE_FILES": len(inventory),
        "TEXT_FILES": len(text_entries),
        "BINARY_FILES": len(binary),
        "SYMLINK_FILES": len(symlinks),
        "MIRRORED_FILES_LEVEL1": len(l1_results),
        "TRANSLATED_FILES_LEVEL2_REAL_MALBOLGE": len(l2_pass),
        "LEVEL2_ADOPTED_FROM_COMMITTED": len(adopted),
        "LEVEL2_SYNTHESIZED_THIS_RUN": len(l2_pass) - len(adopted),
        "LEVEL2_MAX_SOURCE_BYTES": (max(r["source_bytes"] for r in l2_pass)
                                    if l2_pass else None),
        "LEVEL3_CANONICAL_CAT": l3,
        "ORIGINAL_TEXT_BYTES": orig_bytes,
        "MIRROR_ENVELOPE_BYTES": mirror_bytes,
        "MIRROR_EXPANSION_RATIO": round(mirror_bytes / orig_bytes, 3) if orig_bytes else None,
        "MALBOLGE_REAL_PROGRAM_BYTES": mal_bytes,
        "E2E_TRANSLATED_SOURCE_BYTES": sum(r["source_bytes"] for r in l2_pass),
        "MIN_EXPANSION_RATIO": min(ratios) if ratios else None,
        "MAX_EXPANSION_RATIO": max(ratios) if ratios else None,
        "MEDIAN_EXPANSION_RATIO": statistics.median(ratios) if ratios else None,
        "LARGEST_TRANSLATED_FILES": [
            {"source": r["source"], "malbolge_chars": r["malbolge_chars"],
             "source_bytes": r["source_bytes"]} for r in largest
        ],
        "build_duration_s": round(time.time() - t_start, 1),
    }
    (EVIDENCE_DIR / "metrics.json").write_text(
        json.dumps(metrics, indent=1) + "\n", encoding="utf-8")

    # ---- verdicts -------------------------------------------------------------
    def verdict(cond):
        return "DEMONSTRATED" if cond else "NOT_DEMONSTRATED"

    too_large = roundtrip["LEVEL2_SKIPPED_TOO_LARGE"]
    verdicts = {
        "TRANSLATOR_ROUNDTRIP":
            verdict(roundtrip["LEVEL1_CODEC_MISMATCH"] == 0
                    and roundtrip["LEVEL1_CODEC_MIRRORED"] == roundtrip["FILES_TEXT"]),
        "LINGUIST_SNAPSHOT_PINNED": verdict(
            (REPO_ROOT / "SOURCE_COMMIT.txt").exists()
            and (REPO_ROOT / "SOURCE_REPO.txt").exists()
            and SNAPSHOT_DIR.is_dir()),
        "TEXT_BINARY_CLASSIFICATION": verdict(
            roundtrip["FILES_TOTAL"]
            == roundtrip["FILES_TEXT"] + roundtrip["FILES_BINARY"]
            + roundtrip["FILES_SYMLINK"]),
        "TREE_PRESERVED": verdict(True),  # artifacts mirror source tree 1:1 by construction
        "CODEC_MASS_MIRROR": verdict(
            roundtrip["LEVEL1_CODEC_MIRRORED"] == roundtrip["FILES_TEXT"]),
        "MASS_TRANSLATION_REAL_MALBOLGE": verdict(
            len(candidates) > 0
            and all(l2_results[e["path"]]["level2_status"] == "PASS"
                    for e in candidates)
            and len(l2_fail) == 0),
        "BYTE_EXACT_ROUNDTRIP_LEVEL1": verdict(
            roundtrip["LEVEL1_CODEC_MISMATCH"] == 0),
        "BYTE_EXACT_ROUNDTRIP_LEVEL2": verdict(
            len(l2_pass) > 0 and len(l2_fail) == 0),
        "ZERO_MISMATCH_LEVEL1": verdict(roundtrip["LEVEL1_CODEC_MISMATCH"] == 0),
        "ZERO_FAILED_EXECUTION_LEVEL2": verdict(len(l2_fail) == 0
                                                and len(l2_pass) > 0),
        # Nivel 1 es una funcion pura sin RNG y su paridad byte-exacta se mide en cada
        # corrida. Nivel 2 NO es byte-reproducible (medido), y "build reproducible" sin
        # decir el nivel se leia como una garantia que ninguna corrida sostiene.
        # Lo que SI se mide aqui: si el manifest reescrito es byte-identical al que
        # habia en disco, es decir que la corrida no movio ni un artefacto sellado.
        "REPRODUCIBLE_BUILD_LEVEL1_BYTE_EXACT": verdict(
            roundtrip["LEVEL1_CODEC_MISMATCH"] == 0
            and roundtrip["LEVEL1_CODEC_MIRRORED"] == roundtrip["FILES_TEXT"]),
        "REPRODUCIBLE_BUILD_LEVEL2_SYNTHESIS": (
            "NOT_CLAIMED: re-synthesizing a source yields a different program every "
            "run (evidence/synthesis_linux_probe_20261101/); the Zig port is "
            "deterministic but is a second lineage, not identical to the corpus "
            "(zig_search_port_gate_20261101T204229ZZ/)"),
        "REPRODUCIBLE_BUILD_COMMITTED_CORPUS_UNCHANGED": (
            f"{'DEMONSTRATED' if manifest_unchanged else 'NOT_DEMONSTRATED'}: "
            f"this run wrote manifest/translation_manifest.json byte-identical to "
            f"the one it started from (sha256 {manifest_sha})"
            if args.adopt else
            "SKIPPED: --no-adopt re-synthesizes and replaces sealed bytes"),
        "CONTRACT_LEVEL2_SELF_CONTAINED": (
            f"DEMONSTRATED: {len(l2_pass)} artifacts each hold their own file. "
            f"{len(adopted)} carried over from the committed corpus (checked by "
            f"sha256 on disk, not re-synthesized); "
            f"{len(l2_pass) - len(adopted)} synthesized by this run. Canonical "
            f"execution of the committed .mal FILES is tools/verify_corpus.py."),
        "CONTRACT_LEVEL3_CANONICAL_CAT": l3["claim"],
        "LICENSE_AUDIT": verdict(
            (REPO_ROOT / "THIRD_PARTY_NOTICES.md").exists()
            and (SNAPSHOT_DIR / "LICENSE").exists()
            and (REPO_ROOT / "vendor" / "malbolge_translator" / "LICENSE").exists()
            and (REPO_ROOT / "vendor" / "oracles" / "PROVENANCE.txt").exists()
            and (REPO_ROOT / "vendor" / "cat" / "PROVENANCE.txt").exists()),
        "LINGUIST_EXECUTES_IN_MALBOLGE": "NOT_CLAIMED",
        "GENERATED_CORPUS_IS_ORGANIC_USAGE": "NO",
    }
    lines = [
        "# VERDICTS",
        "",
        f"Build at {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC, "
        f"source commit {metrics['source_commit']}.",
        "",
        "| Claim | Verdict |",
        "|---|---|",
    ]
    for k, v in verdicts.items():
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        "Notes:",
        f"- Level 1 (codec mirror) covers ALL {roundtrip['FILES_TEXT']} text files, byte-exact.",
        f"- Level 2 (real, executed Malbolge) PASS={len(l2_pass)} "
        f"FAILED={len(l2_fail)} SKIPPED_BUDGET={roundtrip['LEVEL2_SKIPPED_BUDGET']} "
        f"SKIPPED_TOO_LARGE={too_large} (cap {args.e2e_max_bytes} B, "
        f"eligible={len(candidates)}, budget {args.e2e_budget_seconds} s).",
        "- MASS_TRANSLATION_REAL_MALBOLGE counts over the ELIGIBLE set: it is "
        "DEMONSTRATED only when every file <= the cap PASSes, so SKIPPED_BUDGET "
        "fails the row instead of hiding in it.",
        f"- Committed level-2 artifacts are carried over, never re-synthesized "
        f"(adopted={len(adopted)}). `--no-adopt` replaces sealed bytes with a fresh, "
        f"non-reproducible synthesis. `evidence/level2_state.json` is gitignored, so "
        f"`--resume` is host-local while adoption from the manifest works anywhere.",
        f"- Level 3 backs the corpus with ONE program plus the file on stdin "
        f"({l3.get('evidence', 'no sealed pack')}). It does not embed the file in "
        f"the program, so it is a different contract from level 2, not a bigger "
        f"level 2.",
        "- Synthesis cost is NOT measured by this run. The historical '~0.7 s per "
        "source byte' was one Windows host [HISTORICAL]; the Linux measurement is "
        "~6 s fixed + ~0.16 s per byte at depth 5, "
        "see evidence/synthesis_linux_probe_20261101/.",
        "- Verification method matters for level 2: this build replays the "
        "generator's in-memory opcodes for what it synthesizes here and checks only "
        "sha256 for what it adopts. Executing the committed .mal FILES under the "
        "pinned canonical oracles is tools/verify_corpus.py. When quoting a "
        f"{len(l2_pass)}/{len(l2_pass)}, quote the pack that produced it.",
        "- A `.malrt1` envelope is NOT a Malbolge program.",
        "- LINGUIST_EXECUTES_IN_MALBOLGE is NOT_CLAIMED and WILL stay that way.",
        "- This corpus is GENERATED, not organic Malbolge usage.",
    ]
    (EVIDENCE_DIR / "VERDICTS.md").write_text("\n".join(lines) + "\n",
                                              encoding="utf-8")

    print(json.dumps(roundtrip, indent=1))
    print(f"[done] manifest_sha256={manifest_sha}")
    if codec_fails or l2_fail:
        print("[FAIL] mismatches present; see evidence/roundtrip.json")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
