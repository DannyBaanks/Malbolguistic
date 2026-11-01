#!/usr/bin/env python3
"""Adapter: run a Classic .mal text file through a BOLG1 cell-dump engine.

Usage: bolg1_runner.py <artifact.mal> [max_steps]
  env: BOLGE_EXE (required), BOLG1_INPUT_FILE (optional stdin bytes)
Prints the machine output on stdout; exit 0 = engine reported halt.
"""
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

exe = os.environ.get("BOLGE_EXE", "")
if not exe or not Path(exe).is_file():
    sys.exit("BOLGE_EXE must point at the engine binary")

cells = list(Path(sys.argv[1]).read_bytes())
max_steps = int(sys.argv[2]) if len(sys.argv) > 2 else 100_000_000
input_bytes = Path(os.environ["BOLG1_INPUT_FILE"]).read_bytes() if "BOLG1_INPUT_FILE" in os.environ else b""
payload = bytearray(b"BOLG1")
payload += struct.pack("<Q", 1)
payload += struct.pack("<I", len(cells))
for cell in cells:
    payload += struct.pack("<I", cell)
payload += struct.pack("<I", len(input_bytes))
payload += input_bytes
payload += struct.pack("<I", max_steps)

with tempfile.TemporaryDirectory() as tmp:
    in_p, out_p = Path(tmp) / "in.bin", Path(tmp) / "out.bin"
    in_p.write_bytes(payload)
    res = subprocess.run([exe, str(in_p), str(out_p)], capture_output=True)
    if res.returncode != 0:
        sys.stderr.write(res.stderr.decode("latin-1", "replace")[:200])
        sys.exit(2)
    data = out_p.read_bytes()
    pos = 5 + 8
    out_len = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    out_bytes = data[pos:pos + out_len]
    pos += out_len
    steps, term, reason, fc, fa, fd = struct.unpack_from("<QBBIII", data, pos)

sys.stdout.buffer.write(out_bytes)
sys.stderr.write(f"steps={steps} term={term} reason={reason}\n")
sys.exit(0 if term == 1 else 3)
