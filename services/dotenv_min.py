"""Minimal stdlib .env loader (no dependency).

Loads `<repo-root>/.env` into os.environ as KEY=VALUE lines so the Python
pipeline (swarm, story, case assembly) picks up secrets like ANTHROPIC_API_KEY
from a file instead of requiring a manual `export`. Already-set environment
variables win (so a real `export` still overrides the file).
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_root_env(path: str | os.PathLike | None = None) -> None:
    p = Path(path) if path else ROOT / ".env"
    if not p.exists():
        return
    for raw in p.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)
