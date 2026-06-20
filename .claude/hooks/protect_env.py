#!/usr/bin/env python3
"""PreToolUse: blocca scritture su file con segreti o stato runtime.
Copre .env e varianti, i sidecar SQLite (-wal/-shm/-journal), config.json, backup_*.
Allineato al .gitignore: questi file non devono essere ne' modificati a mano ne' committati."""
import json
import sys

ALLOWED = {".env.example", ".env.sample"}


def is_protected(name):
    n = name.lower()
    if n in ALLOWED:
        return False
    if n == ".env" or n.startswith(".env.") or n == ".envrc":
        return True
    if n == "data.db" or n.startswith("data.db"):  # -wal / -shm / -journal
        return True
    if n == "config.json" or n.startswith("backup_"):
        return True
    return False


try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

path = (data.get("tool_input", {}) or {}).get("file_path", "") or ""
name = path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
if is_protected(name):
    print(
        f"Bloccato: '{name}' contiene segreti o stato runtime - non va modificato qui "
        "ne' committato. Per i placeholder usa .env.example.",
        file=sys.stderr,
    )
    sys.exit(2)
sys.exit(0)
