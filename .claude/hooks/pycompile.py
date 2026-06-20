#!/usr/bin/env python3
"""PostToolUse: byte-compila i .py modificati per beccare subito gli errori di sintassi.
Sostituisce la mancanza di una test suite: feedback immediato dopo ogni edit."""
import json
import py_compile
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

path = (data.get("tool_input", {}) or {}).get("file_path", "") or ""
if not path.endswith(".py"):
    sys.exit(0)

try:
    py_compile.compile(path, doraise=True)
except py_compile.PyCompileError as e:
    print(f"Errore di sintassi in {path}:\n{e}", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
