"""Redis dossier cache (§3.9) — the one Redis integration, used by the batch swarm
and (via its TS twin) the live route, so both share one cache.

Key-value by well_id (JSON, 30-day TTL). Deliberately graceful: a tight 1.5s
timeout and try/except on every op, and a one-shot disable after the first failure
so an unreachable Redis never adds latency. (From some sandboxed shells the RESP
socket is blocked even though TCP connects — this degrades to a clean miss; real
caching works from any normal host. Verify with scripts/redis_check.py.)
"""
from __future__ import annotations

import json
import os
from typing import Optional

KEY = "dossier:{}"
TTL = 60 * 60 * 24 * 30  # 30 days
TIMEOUT = 1.5

_client = None
_disabled = False


def _redis():
    global _client, _disabled
    if _disabled:
        return None
    if _client is not None:
        return _client
    url = os.environ.get("REDIS_URL")
    if not url:
        _disabled = True
        return None
    try:
        import redis
        c = redis.from_url(url, socket_connect_timeout=TIMEOUT, socket_timeout=TIMEOUT)
        c.ping()
        _client = c
        return c
    except Exception:  # noqa: BLE001 — unreachable Redis -> disable, never retry/hang
        _disabled = True
        return None


def available() -> bool:
    return _redis() is not None


def get(well_id: str) -> Optional[dict]:
    c = _redis()
    if not c:
        return None
    try:
        v = c.get(KEY.format(well_id))
        return json.loads(v) if v else None
    except Exception:  # noqa: BLE001
        return None


def set(well_id: str, dossier: dict, ttl: int = TTL) -> None:  # noqa: A001
    c = _redis()
    if not c:
        return
    try:
        c.set(KEY.format(well_id), json.dumps(dossier, default=str), ex=ttl)
    except Exception:  # noqa: BLE001
        pass
