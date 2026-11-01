#!/usr/bin/env python3
"""Adapter: run a Classic .mal text file through the malbolge-generator interpreter.

The toolkit takes *opcode letters*, not file bytes: normalize() is its loader
decode, so the faithful feed is normalize(file_text). Exit 0 = halt reported by
the interpreter's own reason set; anything else is a divergence signal.

Usage: interpreter_runner.py <artifact.mal> [max_steps]
"""
import sys
from pathlib import Path

from malbolge.encoding import normalize
from malbolge.interpreter import MalbolgeInterpreter

art = Path(sys.argv[1])
max_steps = int(sys.argv[2]) if len(sys.argv) > 2 else 100_000_000
input_buffer = sys.stdin.buffer.read().decode("latin-1")

opcodes = normalize(art.read_bytes().decode("latin-1"))
interpreter = MalbolgeInterpreter()
try:
    result = interpreter.execute(opcodes, input_buffer=input_buffer, max_steps=max_steps)
except Exception as exc:  # runtime error is a divergence, not a crash of the gate
    sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
    sys.exit(4)

sys.stdout.buffer.write(result.output.encode("latin-1"))
sys.stderr.write(f"reason={result.halt_reason} steps={getattr(result, 'steps', '?')}\n")
sys.exit(0 if result.halted else 3)
