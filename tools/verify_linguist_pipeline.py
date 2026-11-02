#!/usr/bin/env python3
"""Sweep the level-2 corpus through the real linguist pipeline.

For every committed .mal artifact this tool executes the FILE under two pinned
Malbolge engines, decodes the MALRT1 envelope it prints with the repo codec, and
then hands the bytes to the linguist that is vendored inside the snapshot itself
(vendor/source_snapshot, version read from its VERSION file) for classification.

Six variants are classified per file, all at the SAME logical path unless stated:
  source          the snapshot file as it sits on disk
  source_repeat   same blob classified twice, to measure determinism of the harness
  from_mal        bytes produced by executing the .mal and decoding it
  envelope        the raw stdout of the .mal (the MALRT1 envelope, undecoded)
  malprog         the .mal program text, at its own path (rel + ".mal")
  empty           zero bytes, as a negative control

  python3 tools/verify_linguist_pipeline.py [--limit N] [--evidence DIR]

The linguist runtime (native tokenizer + generated classifier DB) is built in a
work dir OUTSIDE the repository; the vendored snapshot is never modified.
"""
from __future__ import annotations

import argparse
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
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = REPO_ROOT / "vendor" / "source_snapshot"
MIRROR_DIR = REPO_ROOT / "mirror"
MALBOLGE_DIR = REPO_ROOT / "malbolge"
ORACLE_DIR = REPO_ROOT / "vendor" / "oracles"
MANIFEST = REPO_ROOT / "manifest" / "translation_manifest.json"
INVENTORY = REPO_ROOT / "manifest" / "source_inventory.json"
WORKER_RB = REPO_ROOT / "tools" / "gate_adapters" / "linguist_classify.rb"
GEN_RB = REPO_ROOT / "tools" / "gate_adapters" / "linguist_gen_samples.rb"

sys.path.insert(0, str(REPO_ROOT / "vendor"))
from malbolge_translator.roundtrip import decode_roundtrip_detailed  # noqa: E402

ORACLE_PINS = {
    "mb_ref.c": "a8ce19c2dc93e36f8c9c24a271c4187d68f922b9455262c7199a009763fe3ad3",
    "olmstead_original.c":
        "05abd38e78b266050c5a5e8cc5b36584daa5bbdeb404bfb351de7ea6fa26b510",
}

# Files the classification depends on. They are part of the pinned snapshot, so the
# sweep refuses to run if any of them drifted from manifest/source_inventory.json.
LINGUIST_CRITICAL = [
    "lib/linguist.rb",
    "lib/linguist/language.rb",
    "lib/linguist/blob.rb",
    "lib/linguist/blob_helper.rb",
    "lib/linguist/languages.yml",
    "lib/linguist/classifier.rb",
    "lib/linguist/tokenizer.rb",
    "lib/linguist/samples.rb",
    "lib/linguist/heuristics.yml",
    "lib/linguist/generated.rb",
    "lib/linguist/vendor.yml",
    "lib/linguist/documentation.yml",
]

EXIT_REASON = {0: "HALT", 1: "BAD_SOURCE", 2: "BUDGET_EXHAUSTED",
               3: "STALL", 4: "IO_ERROR", "TIMEOUT": "PROCESS_TIMEOUT"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def sh(cmd: list[str], cwd: Path | None = None) -> str:
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f"command failed rc={p.returncode}: {' '.join(map(str, cmd))}\n"
                         f"stdout:\n{p.stdout}\nstderr:\n{p.stderr}")
    return p.stdout


def check_ruby_deps(ruby: str) -> dict:
    """Fail closed with the exact install command; never install into the host silently."""
    probe = sh([ruby, "-e",
                "require 'charlock_holmes'; require 'mini_mime'; "
                "puts CharlockHolmes::VERSION; puts MiniMime::VERSION"],
               cwd=Path("/tmp"))
    lines = probe.split()
    return {"charlock_holmes": lines[0], "mini_mime": lines[1]}


def build_linguist_runtime(workdir: Path, ruby: str, rebuild: bool) -> dict:
    """Copy the vendored linguist out of the snapshot and complete the build steps
    its Rakefile would run (native lexer + serialized samples DB). Repo stays clean."""
    lib = workdir / "lib"
    info: dict = {"workdir": str(workdir)}
    if rebuild or not (lib / "linguist" / "linguist.so").exists() \
            or not (lib / "linguist" / "samples_data.rb").exists():
        if workdir.exists():
            shutil.rmtree(workdir)
        workdir.mkdir(parents=True)
        for d in ("lib", "samples", "ext"):
            shutil.copytree(SNAPSHOT_DIR / d, workdir / d)
        ext = workdir / "ext" / "linguist"
        sh([ruby, "extconf.rb"], cwd=ext)
        sh(["make", f"-j{max(1, min(4, (os.cpu_count() or 2)))}"], cwd=ext)
        so = ext / "linguist.so"
        if not so.is_file():
            raise SystemExit(f"tokenizer no construido: {so} no existe")
        shutil.copy2(so, lib / "linguist" / "linguist.so")

        # Generate the serialized classifier DB twice: if it is not byte-stable the
        # pack says so instead of pretending the model is pinned.
        db = lib / "linguist" / "samples_data.rb"
        t0 = time.perf_counter()
        sh([ruby, "-I", str(lib), str(GEN_RB), str(db)], cwd=workdir)
        first = sha256_file(db)
        sh([ruby, "-I", str(lib), str(GEN_RB), str(db)], cwd=workdir)
        second = sha256_file(db)
        info["samples_data_regenerated"] = True
        info["samples_data_deterministic"] = (first == second)
        info["samples_data_seconds"] = round(time.perf_counter() - t0, 2)
    info["linguist_lib_sha256_of_entrypoint"] = sha256_file(lib / "linguist.rb")
    info["linguist_so_sha256"] = sha256_file(lib / "linguist" / "linguist.so")
    info["samples_data_sha256"] = sha256_file(lib / "linguist" / "samples_data.rb")
    info["samples_data_bytes"] = (lib / "linguist" / "samples_data.rb").stat().st_size
    info["linguist_version"] = (lib / "linguist" / "VERSION").read_text().strip()
    return info


def host_path_needles() -> list[str]:
    """Absolute paths of THIS host that must never be sealed (public repo).

    Concrete prefixes only: a generic '/home/' would trip on the tool's own source,
    which is copied into every pack.
    """
    return sorted(set(n for n in (str(REPO_ROOT), str(Path.home())) if n and n != "/"))


def sanitize_for_pack(text: str, stage: Path, workdir: Path) -> str:
    """Replace absolute host paths in pack artifacts with documented tokens."""
    for prefix, token in ((str(SNAPSHOT_DIR), "{SNAPSHOT}"),
                          (str(MALBOLGE_DIR), "{MALBOLGE}"),
                          (str(MIRROR_DIR), "{MIRROR}"),
                          (str(stage), "{STAGE}"),
                          (str(workdir), "{WORKDIR}"),
                          (str(REPO_ROOT), "{REPO}")):
        text = text.replace(prefix, token)
    return text


def hygiene_offenders(ev_dir: Path) -> list[tuple[str, str]]:
    """Tripwire: any sealed file that still carries a host absolute path."""
    needles = host_path_needles()
    offenders = []
    for p in sorted(ev_dir.rglob("*")):
        if not p.is_file():
            continue
        try:
            text = p.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for needle in needles:
            if needle in text:
                offenders.append((str(p.relative_to(ev_dir)), needle))
    return offenders


def main() -> int:
    ap = argparse.ArgumentParser(description="level-2 corpus through the linguist pipeline")
    ap.add_argument("--evidence", default=None,
                    help="output dir; must not exist (evidence paths are never reused)")
    ap.add_argument("--limit", type=int, default=0,
                    help="only the N smallest-path artifacts (0 = all PASS artifacts)")
    ap.add_argument("--workdir", default=str(Path(tempfile.gettempdir()) / "malboguidstic_linguist_rt"),
                    help="scratch copy of linguist; OUTSIDE the repo")
    ap.add_argument("--rebuild-linguist", action="store_true")
    ap.add_argument("--max-steps", type=int, default=100_000_000)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--ruby", default="ruby")
    ap.add_argument("--no-differential", action="store_true")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ev_dir = Path(args.evidence) if args.evidence else (
        REPO_ROOT / "evidence" / f"linguist_pipeline_sweep_{stamp}")
    if ev_dir.exists():
        raise SystemExit(f"REFUSING to overwrite existing evidence path: {ev_dir}")
    workdir = Path(args.workdir)
    stage = workdir / "stage"

    entries_all = json.loads(MANIFEST.read_text())
    entries = {e["source"]: e for e in entries_all}
    selected = sorted(e["source"] for e in entries_all
                      if e["malbolge"]["status"] == "PASS")
    if args.limit:
        selected = selected[:args.limit]
    if not selected:
        raise SystemExit("no PASS artifacts selected")

    # Provenance: the classifier we are about to trust must be the pinned snapshot's.
    inventory = {i["path"]: i for i in json.loads(INVENTORY.read_text())}
    drift = []
    for rel in LINGUIST_CRITICAL:
        inv = inventory.get(rel)
        disk = SNAPSHOT_DIR / rel
        if inv is None or not disk.is_file():
            drift.append(f"{rel}: sin pin o ausente")
        elif sha256_file(disk) != inv["sha256"]:
            drift.append(f"{rel}: sha != inventario")
    if drift:
        raise SystemExit("LINGUIST_PROVENANCE_MISMATCH\n  " + "\n  ".join(drift))

    ruby_version = sh([args.ruby, "--version"]).strip()
    gems = check_ruby_deps(args.ruby)
    rt = build_linguist_runtime(workdir, args.ruby, args.rebuild_linguist)
    print(f"[linguist] version={rt['linguist_version']} so={rt['linguist_so_sha256'][:12]} "
          f"samples_data={rt['samples_data_sha256'][:12]} "
          f"deterministica={rt.get('samples_data_deterministic')}")

    if stage.exists():
        shutil.rmtree(stage)
    (stage / "from_mal").mkdir(parents=True)
    (stage / "envelope").mkdir(parents=True)

    build_dir = Path(tempfile.mkdtemp(prefix="malboguidstic_linguist_oracles_"))
    exec_rows: dict[str, dict] = {}
    jobs: list[dict] = []
    t_start = time.time()
    try:
        mb_ref = build_oracle("mb_ref.c", build_dir)
        engines = [("mb_ref", mb_ref, [str(args.max_steps)])]
        if not args.no_differential:
            engines.append(("olmstead_1998", build_oracle("olmstead_original.c", build_dir), []))

        for rel in selected:
            entry = entries[rel]
            art = REPO_ROOT / entry["malbolge"]["artifact"]
            snap_path = SNAPSHOT_DIR / rel
            env_path = MIRROR_DIR / (rel + ".malrt1")
            rec = {"source": rel, "artifact": entry["malbolge"]["artifact"]}
            checks = {}

            checks["artifact_sha_matches_manifest"] = (
                art.is_file() and sha256_file(art) == entry["malbolge"]["sha256"])
            if not (art.is_file() and snap_path.is_file() and env_path.is_file()):
                checks["files_present"] = False
                exec_rows[rel] = {"checks": checks, "pass": False, "engines": {}}
                continue
            checks["files_present"] = True
            checks["snapshot_sha_matches_manifest"] = (
                sha256_file(snap_path) == entry["source_sha256"])

            outs = []
            for name, exe, extra in engines:
                code, out, dur = run_engine(exe, art, extra, args.timeout)
                outs.append(out)
                checks[f"{name}_halt"] = (code == 0)
                rec.setdefault("engines", {})[name] = {
                    "exit": code, "exit_reason": EXIT_REASON.get(code, str(code)),
                    "stdout_bytes": len(out), "wall_ms": round(dur * 1000, 2)}
            if len(engines) > 1:
                checks["differential_engines_agree"] = all(o == outs[0] for o in outs)

            envelope = outs[0]
            checks["output_is_committed_envelope"] = (envelope == env_path.read_bytes())
            decoded = decode_roundtrip_detailed(envelope.decode("latin-1"))
            payload = decoded.original_bytes or b""
            checks["envelope_decodes_valid"] = (decoded.status.value == "VALID")
            checks["decoded_matches_snapshot"] = (payload == snap_path.read_bytes())
            checks["decoded_sha_matches_manifest"] = (
                sha256_bytes(payload) == entry["source_sha256"])

            # Stage for the classifier: same logical path, different content.
            fm = stage / "from_mal" / rel
            fm.parent.mkdir(parents=True, exist_ok=True)
            fm.write_bytes(payload)
            en = stage / "envelope" / rel
            en.parent.mkdir(parents=True, exist_ok=True)
            en.write_bytes(envelope)

            jobs.append({"id": rel, "v": [
                ["source", str(snap_path), rel],
                ["source_repeat", str(snap_path), rel],
                ["from_mal", str(fm), rel],
                ["envelope", str(en), rel],
                ["malprog", str(art), rel + ".mal"],
                ["empty", "-", rel],
            ]})
            rec["checks"] = checks
            rec["pass"] = all(checks.values())
            exec_rows[rel] = rec
    finally:
        shutil.rmtree(build_dir, ignore_errors=True)
    exec_wall = time.time() - t_start

    jobs_path = workdir / f"jobs_{stamp}.jsonl"
    with jobs_path.open("w") as fh:
        for j in jobs:
            fh.write(json.dumps(j) + "\n")
    results_path = workdir / f"linguist_{stamp}.jsonl"
    t0 = time.perf_counter()
    env = dict(os.environ, LINGUIST_LIB=str(workdir / "lib"))
    proc = subprocess.run([args.ruby, str(WORKER_RB), str(jobs_path), str(results_path)],
                          capture_output=True, text=True, env=env)
    ruby_wall = time.perf_counter() - t0
    if proc.returncode != 0:
        raise SystemExit(f"worker ruby rc={proc.returncode}\n{proc.stderr[-4000:]}")

    classifications = {}
    with results_path.open() as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
                classifications[row["id"]] = row["v"]

    ev_dir.mkdir(parents=True)
    raw = (ev_dir / "raw.jsonl").open("w")
    agree = Counter()
    langs = Counter()
    malprog_langs = Counter()
    strategies = Counter()
    n_class = len(selected)

    for rel in selected:
        rec = dict(exec_rows[rel])
        v = classifications.get(rel, {})
        rec["linguist"] = v
        if not v:
            # Sin clasificaciones no hay nada que concordar: no contar como acuerdo.
            agree["without_classifications"] += 1
            raw.write(json.dumps(rec) + "\n")
            continue
        src, frm, envl, mlp, emp = (v.get("source") or {}), (v.get("from_mal") or {}), \
            (v.get("envelope") or {}), (v.get("malprog") or {}), (v.get("empty") or {})
        agree["source_classified"] += src.get("language") is not None
        agree["from_mal_equals_source"] += frm.get("language") == src.get("language")
        agree["from_mal_flags_equal"] += all(
            frm.get(k) == src.get(k) for k in ("generated", "documentation", "vendored", "type", "group"))
        agree["envelope_equals_source"] += envl.get("language") == src.get("language")
        agree["envelope_differs_from_source"] += envl.get("language") != src.get("language")
        agree["malprog_classified"] += mlp.get("language") is not None
        agree["empty_is_nil"] += emp.get("language") is None
        agree["determinism_repeat_equals"] += (v.get("source_repeat") or {}).get("language") == src.get("language")
        agree["content_sha_matches"] += src.get("sha256") == frm.get("sha256")
        langs[src.get("language") or "NIL"] += 1
        malprog_langs[mlp.get("language") or "NIL"] += 1
        strategies[src.get("strategy") or "?"] += 1
        raw.write(json.dumps(rec) + "\n")
    raw.close()

    exec_pass = [r for r in exec_rows.values() if r.get("pass")]
    exec_fail = [{"source": rel, "failed_checks": [k for k, x in r["checks"].items() if not x]}
                 for rel, r in sorted(exec_rows.items()) if not r.get("pass")]
    walls = [e["wall_ms"] for r in exec_rows.values() for e in (r.get("engines") or {}).values()]

    summary = {
        "run_utc": stamp,
        "scope": {"selected_pass_artifacts": n_class, "limit": args.limit,
                  "total_pass_in_manifest": sum(1 for e in entries_all
                                                if e["malbolge"]["status"] == "PASS")},
        "environment": {
            "system": platform.system(), "release": platform.release(),
            "machine": platform.machine(), "python": sys.version.split()[0],
            "ruby": ruby_version, "gems": gems,
            "gcc": subprocess.run(["gcc", "--version"], capture_output=True)
                   .stdout.decode().splitlines()[0],
            "cpu_count": os.cpu_count()},
        "oracle_pins": ORACLE_PINS,
        "engines": [name for name, _, _ in engines],
        "max_steps": args.max_steps,
        "linguist_runtime": rt,
        "linguist_provenance": {"critical_files_checked": len(LINGUIST_CRITICAL),
                                "drift": drift,
                                "repository_require_dropped": True,
                                "pack_paths_tokenized": ["{REPO}", "{SNAPSHOT}", "{MIRROR}",
                                                          "{MALBOLGE}", "{WORKDIR}", "{STAGE}"],
                                "jobs_absolute_copy": str(jobs_path)},
        "execution": {
            "artifacts": n_class,
            "passed": len(exec_pass),
            "failed": len(exec_fail),
            "wall_seconds": round(exec_wall, 2),
            "engine_wall_ms_mean": round(statistics.mean(walls), 2) if walls else None,
            "engine_wall_ms_max": round(max(walls), 2) if walls else None,
            "failures": exec_fail},
        "classification": {
            "wall_seconds": round(ruby_wall, 2),
            "blobs": n_class * 6,
            "agree": dict(agree),
            "source_language_distribution_top20": langs.most_common(20),
            "source_languages_distinct": len([k for k in langs if k != "NIL"]),
            "malprog_language_distribution_top20": malprog_langs.most_common(20),
            "strategy_distribution": strategies.most_common()},
    }
    (ev_dir / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    # jobs.jsonl viaja al pack con las rutas de host tokenizadas: el repo es publico.
    (ev_dir / "jobs.jsonl").write_text("".join(
        sanitize_for_pack(line, stage, workdir)
        for line in jobs_path.read_text().splitlines(keepends=True)))
    shutil.copy2(results_path, ev_dir / "linguist_raw.jsonl")
    shutil.copy2(__file__, ev_dir / Path(__file__).name)
    shutil.copy2(WORKER_RB, ev_dir / WORKER_RB.name)
    shutil.copy2(GEN_RB, ev_dir / GEN_RB.name)

    chain_keys = ["files_present", "artifact_sha_matches_manifest",
                  "snapshot_sha_matches_manifest", "output_is_committed_envelope",
                  "envelope_decodes_valid", "decoded_matches_snapshot",
                  "decoded_sha_matches_manifest", "differential_engines_agree"] + \
                 [f"{n}_halt" for n, _, _ in engines]

    def count(k: str) -> int:
        return sum(1 for r in exec_rows.values() if r.get("checks", {}).get(k))

    verdict_lines = []
    verdict_lines.append(f"- LEVEL2_ARTIFACTS_EXECUTE_AND_REPRODUCE = "
                         f"{'DEMONSTRATED' if len(exec_pass) == n_class else 'PARTIAL'}"
                         f" ({len(exec_pass)}/{n_class})")
    verdict_lines.append(f"- LINGUIST_CLASSIFICATION_PRESERVED_THROUGH_MALBOLGE = "
                         f"{'DEMONSTRATED' if agree['from_mal_equals_source'] == n_class else 'PARTIAL'}"
                         f" ({agree['from_mal_equals_source']}/{n_class})")
    verdict_lines.append(f"- LINGUIST_DECISION_FLAGS_PRESERVED (generated/docs/vendored/type/group) = "
                         f"{'DEMONSTRATED' if agree['from_mal_flags_equal'] == n_class else 'PARTIAL'}"
                         f" ({agree['from_mal_flags_equal']}/{n_class})")
    sens = agree["envelope_differs_from_source"]
    verdict_lines.append(f"- CONTROL_SENSIBILIDAD_AL_CONTENIDO (sobre envoltura sin decodificar) = "
                         f"{sens}/{n_class} cambian de idioma "
                         f"({'el pipeline SI mira el contenido' if sens > n_class * 0.1 else 'dominado por la ruta: '
                          'la concordancia anterior NO demuestra fidelidad de contenido por si sola'})")
    verdict_lines.append(f"- CONTROL_NEGATIVO (contenido vacio) = "
                         f"{'DEMONSTRATED' if agree['empty_is_nil'] == n_class else 'PARTIAL'}"
                         f" ({agree['empty_is_nil']}/{n_class} devuelven NIL)")
    verdict_lines.append(f"- CONTROL_DETERMINISMO (mismo blob dos veces) = "
                         f"{'DEMONSTRATED' if agree['determinism_repeat_equals'] == n_class else 'PARTIAL'}"
                         f" ({agree['determinism_repeat_equals']}/{n_class})")
    known = n_class - malprog_langs.get("NIL", 0)
    verdict_lines.append(f"- MALBOLGE_RECOGNIZED_BY_LINGUIST = "
                         f"{'NEGATIVE' if known == 0 else 'DEMONSTRATED'}"
                         f" (los {n_class} programas .mal clasificados como idioma: {known})")
    verdict_lines.append(f"- LINGUIST_CLASSIFIES_SOURCE (no NIL) = "
                         f"{agree['source_classified']}/{n_class}")

    (ev_dir / "VERDICT.md").write_text(
        f"# Barrido del corpus nivel 2 por el pipeline linguist — {stamp}\n\n"
        f"Ejecuta los artefactos `.mal` commiteados bajo {', '.join(summary['engines'])} "
        f"(pinned por SHA-256), decodifica la envoltura con el codec del repo y clasifica "
        f"el resultado con **linguist {rt['linguist_version']}**, la copia vendorada en "
        f"`vendor/source_snapshot` (no la gema publicada).\n\n"
        f"El runtime de linguist se construyo en `{workdir}` (fuera del repo): lexer nativo "
        f"`linguist.so` + `samples_data.rb` generado ({rt['samples_data_bytes']} B, "
        f"byte-estable entre dos corridas: {rt.get('samples_data_deterministic')}).\n\n"
        f"## Cadena de ejecucion (por artefacto)\n\n"
        f"| Eslabon | Conteo sobre {n_class} |\n|---|---|\n"
        + "\n".join(f"| {k} | {count(k)} |" for k in chain_keys)
        + f"\n\n## Afirmaciones\n\n" + "\n".join(verdict_lines)
        + f"\n\n## Alcance y limites\n\n"
          f"- Poblacion: artefactos con `malbolge.status == PASS` en el manifest commiteado"
          f"{' (recortado con --limit)' if args.limit else ''}.\n"
          f"- Los {len(entries_all) - summary['scope']['total_pass_in_manifest']} archivos "
          f"SKIPPED_TOO_LARGE no tienen programa propio y no entran en este barrido.\n"
          f"- `from_mal` se clasifica en la MISMA ruta logica que `source` y con los MISMOS bytes, "
          f"asi que su concordancia esta implicada por la paridad byte a byte: valida el banco de "
          f"pruebas, no es evidencia independiente de fidelidad.\n"
          f"- Clasificar la envoltura sin decodificar mide cuanto depende linguist de la ruta: "
          f"{sens}/{n_class} de los archivos cambiaron de idioma.\n"
          f"- `jobs.jsonl` viaja al pack con las rutas de host sustituidas por tokens "
          f"(`{{SNAPSHOT}}`, `{{STAGE}}`, `{{REPO}}`…); la copia absoluta queda en el workdir. "
          f"El pack se niega a sellarse si algún archivo conserva una ruta absoluta del host.\n"
          f"- No se midio el costo de sintesis; este tool no llama a `malbolge-generator`.\n"
          f"- NOT_DEMONSTRATED: que un clasificador externo a este repositorio (la gema publicada "
          f"`github-linguist`) de el mismo resultado; aqui solo se usa la version del snapshot.\n")

    (ev_dir / "BUILD_RECIPE.sh").write_text(
        "#!/bin/sh\n"
        "# Reconstruye exactamente el runtime usado en esta corrida (fuera del repo).\n"
        f"# 1. gemas de usuario que este tool NO instala por su cuenta:\n"
        "#    gem install --user-install charlock_holmes mini_mime\n"
        "# 2. copia del linguist pinned + lexer nativo + DB de samples:\n"
        "# desde la raiz del repo (sin rutas de host: el repositorio es publico):\n"
        "SNAP='vendor/source_snapshot'\n"
        'W="${TMPDIR:-/tmp}/malboguidstic_linguist_rt"\n'
        "rm -rf \"$W\"; mkdir -p \"$W\"\n"
        "cp -r \"$SNAP/lib\" \"$SNAP/samples\" \"$SNAP/ext\" \"$W/\"\n"
        "cd \"$W/ext/linguist\" && ruby extconf.rb && make -j4\n"
        "cp linguist.so \"$W/lib/linguist/\"\n"
        "ruby -I\"$W/lib\" tools/gate_adapters/linguist_gen_samples.rb "
        "\"$W/lib/linguist/samples_data.rb\"\n"
        "# 3. barrido:\n"
        f"python3 tools/verify_linguist_pipeline.py --workdir \"$W\"\n"
        f"# Pins de esta corrida:\n"
        f"#   linguist.so      {rt['linguist_so_sha256']}\n"
        f"#   samples_data.rb  {rt['samples_data_sha256']}\n"
        f"#   linguist.rb      {rt['linguist_lib_sha256_of_entrypoint']}\n"
        f"#   mb_ref.c         {ORACLE_PINS['mb_ref.c']}\n"
        f"#   olmstead_1998.c  {ORACLE_PINS['olmstead_original.c']}\n")

    offenders = hygiene_offenders(ev_dir)
    if offenders:
        for name, needle in offenders[:10]:
            print(f"  !! RUTA_DE_HOST_EN_EVIDENCIA {name} contiene {needle}")
        raise SystemExit("El pack NO se sella: hay rutas absolutas del host en la evidencia.")

    sums = sorted(f"{sha256_file(p)}  {p.relative_to(ev_dir)}"
                  for p in ev_dir.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt")
    (ev_dir / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n")

    print(f"exec: artefactos={n_class} pass={len(exec_pass)} fallados={len(exec_fail)} "
          f"wall={exec_wall:.2f}s | clasificacion wall={ruby_wall:.2f}s "
          f"({n_class * 6} blobs)")
    for k in chain_keys:
        v = count(k)
        print(f"  {'ok ' if v == n_class else '!! '}{k}={v}/{n_class}")
    for k, v in sorted(agree.items()):
        print(f"  linguist {k}={v}/{n_class}")
    print(f"  malprog distribucion: {malprog_langs.most_common(5)}")
    print(f"  estrategias: {strategies.most_common(5)}")
    for f in exec_fail[:10]:
        print(f"  FAIL {f['source']}: {f['failed_checks']}")
    try:
        print(f"evidence -> {ev_dir.relative_to(REPO_ROOT)}")
    except ValueError:
        print(f"evidence -> {ev_dir}")
    return 0 if (not exec_fail and not drift) else 1


if __name__ == "__main__":
    sys.exit(main())
