"""Verify the Redis sponsor integration from YOUR machine.

The agent's sandbox often can't reach a cloud Redis on a non-standard port (its
egress is HTTP-only), so the cache there degrades to a clean miss. Run this from a
normal shell to confirm the real round-trip:

    python scripts/redis_check.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services"))
from dotenv_min import load_root_env  # noqa: E402

load_root_env()

import os  # noqa: E402

url = os.environ.get("REDIS_URL")
if not url:
    print("❌ REDIS_URL not set in .env")
    sys.exit(1)

try:
    import redis
except ImportError:
    print("❌ pip install redis")
    sys.exit(1)

try:
    r = redis.from_url(url, socket_connect_timeout=5, socket_timeout=5)
    t0 = time.time()
    print("PING:", r.ping(), f"({(time.time()-t0)*1000:.0f} ms)")
    r.set("dossier:__check__", json.dumps({"ok": True}), ex=60)
    got = json.loads(r.get("dossier:__check__"))
    print("round-trip set/get:", got)
    r.delete("dossier:__check__")
    print("✅ Redis cache is reachable and working from this machine.")
except Exception as e:  # noqa: BLE001
    print(f"❌ Redis error: {type(e).__name__}: {str(e)[:160]}")
    print("   Check: DB shows Active in Redis Cloud · URL has user:pass · try rediss:// · firewall allowlist.")
    sys.exit(1)
