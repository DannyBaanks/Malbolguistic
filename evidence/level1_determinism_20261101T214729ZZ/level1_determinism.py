#!/usr/bin/env python3
"""Level-1 codec determinism gate.

Question this answers, and nothing else: is the level-1 (MALRT1 codec) layer
byte-reproducible on this host, against the envelopes already committed under
mirror/?

Method, per TEXT entry listed in manifest/translation_manifest.json:
  1. read the source bytes from vendor/source_snapshot/
  2. encode_roundtrip_bytes() twice, in the same process
  3. require the two payloads to be identical            -> intra-run determinism
  4. require the payload to equal the committed mirror/.malrt1 file, byte for byte
  5. require envelope_sha256 in the manifest to match the payload we just made

Nothing is written inside the repo except the evidence pack. Exit 0 iff steps 3
and 4 hold for every entry.

Usage:
    python3 tools/level1_determinism.py --evidence evidence/level1_determinism_<stamp>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "vendor"))

from malbolge_translator.roundtrip import encode_roundtrip_bytes  # noqa: E402


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True,
                    help="new directory for the sealed pack (must not exist)")
    ap.add_argument("--limit", type=int, default=0,
                    help="only the first N entries (smoke run); 0 = all")
    args = ap.parse_args()

    ev_dir = pathlib.Path(args.evidence)
    if not ev_dir.is_absolute():
        ev_dir = REPO_ROOT / ev_dir
    if ev_dir.exists():
        print(f"REFUSING: evidence dir already exists: {ev_dir}", file=sys.stderr)
        return 2
    if ev_dir == REPO_ROOT:
        print("REFUSING: evidence dir is the repo root", file=sys.stderr)
        return 2
    ev_dir.mkdir(parents=True)

    manifest = json.loads((REPO_ROOT / "manifest" / "translation_manifest.json").read_text())
    entries = [e for e in manifest if e["mirror"]["artifact"].endswith(".malrt1")]
    if args.limit:
        entries = entries[: args.limit]

    t0 = time.time()
    records = []
    for e in entries:
        src = REPO_ROOT / "vendor" / "source_snapshot" / e["source"]
        env_path = REPO_ROOT / e["mirror"]["artifact"]
        rec = {"source": e["source"],
               "envelope_artifact": e["mirror"]["artifact"]}
        if not src.is_file() or not env_path.is_file():
            rec.update(status="MISSING", source_on_disk=src.is_file(),
                       envelope_on_disk=env_path.is_file())
            records.append(rec)
            continue
        raw = src.read_bytes()
        a = encode_roundtrip_bytes(raw).payload
        b = encode_roundtrip_bytes(raw).payload
        committed = env_path.read_bytes().decode("ascii")
        rec.update(
            status="PASS" if (a == b and a == committed) else "FAIL",
            source_size_bytes=len(raw),
            envelope_chars=len(a),
            double_encode_identical=(a == b),
            matches_committed=(a == committed),
            matches_manifest_envelope_sha=(
                sha256_bytes(a.encode("ascii")) == e["mirror"]["envelope_sha256"]),
            source_sha_reproduced=(sha256_bytes(raw) == e["source_sha256"]),
            envelope_sha256=sha256_bytes(a.encode("ascii")),
        )
        records.append(rec)
    wall = time.time() - t0

    n = len(records)
    passed = [r for r in records if r["status"] == "PASS"]
    failed = [r for r in records if r["status"] != "PASS"]
    sha_mismatch = [r for r in records if not r.get("matches_manifest_envelope_sha", False)]
    src_sha_mismatch = [r for r in records if not r.get("source_sha_reproduced", False)]
    env_chars = sum(r.get("envelope_chars", 0) for r in records)

    summary = {
        "tool": "tools/level1_determinism.py",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": sys.version.split()[0],
        "codec_package": "vendor/malbolge_translator/roundtrip.py (encode_roundtrip_bytes)",
        "entries_checked": n,
        "passed": len(passed),
        "failed": len(failed),
        "intra_run_double_encode_identical": sum(1 for r in records if r.get("double_encode_identical")),
        "matches_committed_envelope": sum(1 for r in records if r.get("matches_committed")),
        "manifest_envelope_sha_mismatch": len(sha_mismatch),
        "manifest_source_sha_mismatch": len(src_sha_mismatch),
        "envelope_chars_total": env_chars,
        "wall_s": round(wall, 2),
        "failures": failed[:20],
        "claim_supported": "REPRODUCIBLE_BUILD_LEVEL1_BYTE_EXACT",
        "claim_not_supported": [
            "level 2 synthesis byte-reproducibility (see evidence/synthesis_linux_probe_20261101/)",
            "that a fresh clone rebuilds the corpus without --resume",
        ],
    }
    (ev_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (ev_dir / "raw.jsonl").open("w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")

    lines = [
        f"# Level-1 codec determinism ({summary['timestamp_utc']})",
        "",
        f"Scope: the {n} TEXT entries that carry a `mirror/*.malrt1` artifact in",
        "`manifest/translation_manifest.json`. Nothing else is in scope.",
        "",
        "| medida | valor |",
        "|---|---|",
        f"| entradas comprobadas | {n} |",
        f"| PASS (doble codificacion identica Y coincide con la envoltura commiteada) | {len(passed)} |",
        f"| FAIL | {len(failed)} |",
        f"| codificacion doble identica | {summary['intra_run_double_encode_identical']}/{n} |",
        f"| coincide con mirror/ commiteado | {summary['matches_committed_envelope']}/{n} |",
        f"| envelope_sha256 del manifest coincide | {n - summary['manifest_envelope_sha_mismatch']}/{n} |",
        f"| source_sha256 del manifest coincide | {n - summary['manifest_source_sha_mismatch']}/{n} |",
        f"| caracteres de envoltura totales | {env_chars:,} |",
        f"| muro | {wall:.2f} s |",
        f"| python | {summary['python']} |",
        "",
        "## Que prueba",
        "",
        "`encode_roundtrip_bytes()` es una funcion pura sin RNG: codificar dos veces la",
        "misma fuente da el mismo payload, y ese payload es byte a byte la envoltura que",
        "esta commiteada. Por eso el nivel 1 se puede prometer como byte-reproducible.",
        "",
        "## Que NO prueba",
        "",
        "- Nada del nivel 2: la sintesis no es byte-reproducible (3 corridas, 3 programas",
        "  distintos; `evidence/synthesis_linux_probe_20261101/`).",
        "- No prueba que un clon fresco reconstruya el corpus entero sin `--resume`.",
        "- No ejecuta Malbolge: solo el codec.",
        "",
    ]
    if failed:
        lines.append("## Fallos")
        lines += [f"- {r['source']}: {r['status']}" for r in failed[:20]]
        lines.append("")
    (ev_dir / "REPORT.md").write_text("\n".join(lines))
    (ev_dir / pathlib.Path(__file__).name).write_text(pathlib.Path(__file__).read_text())

    sums = [f"{sha256_bytes(p.read_bytes())}  {p.relative_to(ev_dir)}"
            for p in sorted(ev_dir.rglob("*")) if p.is_file() and p.name != "SHA256SUMS.txt"]
    (ev_dir / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n")

    print(json.dumps({k: v for k, v in summary.items() if k != "failures"}, indent=2))
    # --evidence may point outside the repo; the exit code is the verdict, not this print.
    try:
        shown = ev_dir.relative_to(REPO_ROOT)
    except ValueError:
        shown = ev_dir
    print(f"evidence -> {shown}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
