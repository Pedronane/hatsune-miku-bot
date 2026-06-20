#!/usr/bin/env python3
"""PreToolUse: blocca scritture su .env, data.db e backup_* (segreti / stato runtime)."""
import json
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

path = (data.get("tool_input", {}) or {}).get("file_path", "") or ""
name = path.replace("\\", "/").rsplit("/", 1)[-1]
if name == ".env" or name == "data.db" or name.startswith("backup_"):
    print(
        f"Bloccato: '{name}' contiene segreti o stato runtime — non va modificato qui "
        "(e non deve finire su git). Usa .env.example per i placeholder.",
        file=sys.stderr,
    )
    sys.exit(2)
sys.exit(0)
