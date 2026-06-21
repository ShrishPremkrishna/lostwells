"""Browserbase browser tool (§3.10) — the one browser-automation escalation.

`fetch_page(url)` drives a real remote Chromium (Browserbase) via Playwright
`connect_over_cdp` (no local browser install needed) and returns the page's visible
text + the Browserbase **session-replay URL** (the HANDOFF "provenance dividend":
the recorded session beside a browser-derived claim). For facts behind JS / a WAF
that plain web_search can't read. SQLite-cached; graceful (returns None on any
failure, e.g. if the sandbox proxy blocks the wss connect — works from a normal host).
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "data" / "cache"
CACHE.mkdir(parents=True, exist_ok=True)


def _db() -> sqlite3.Connection:
    db = sqlite3.connect(CACHE / "browserbase.sqlite")
    db.execute("CREATE TABLE IF NOT EXISTS page (k TEXT PRIMARY KEY, v TEXT)")
    return db


def fetch_page(url: str, max_chars: int = 8000, timeout_ms: int = 30000) -> Optional[dict]:
    """Return {url, text, replay_url, session_id} for a JS/WAF-walled page, or None."""
    db = _db()
    row = db.execute("SELECT v FROM page WHERE k=?", (url,)).fetchone()
    if row:
        return json.loads(row[0]) if row[0] != "null" else None

    result = None
    try:
        from browserbase import Browserbase
        from playwright.sync_api import sync_playwright

        bb = Browserbase(api_key=os.environ["BROWSERBASE_API_KEY"])
        session = bb.sessions.create(project_id=os.environ["BROWSERBASE_PROJECT_ID"])
        connect_url = getattr(session, "connect_url", None) or getattr(session, "connectUrl", None)
        replay = f"https://browserbase.com/sessions/{session.id}"
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(connect_url)
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            text = (page.inner_text("body") or "")[:max_chars]
            browser.close()
        result = {"url": url, "text": text, "replay_url": replay, "session_id": session.id}
    except Exception as e:  # noqa: BLE001 — proxy/site/SDK failure -> graceful None
        result = None
        print(f"[browserbase] fetch_page failed: {type(e).__name__}: {str(e)[:120]}")

    db.execute("INSERT OR REPLACE INTO page VALUES (?,?)", (url, json.dumps(result) if result else "null"))
    db.commit()
    return result


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT / "services"))
    from dotenv_min import load_root_env
    load_root_env()
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    r = fetch_page(target)
    if r:
        print("replay:", r["replay_url"])
        print("text[:300]:", r["text"][:300])
    else:
        print("fetch returned None (see error above)")
