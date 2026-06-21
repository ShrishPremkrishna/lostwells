"""The `well_investigator` subagent: one Claude agent per well.

Official ``anthropic`` SDK + Anthropic's server-side **web_search** tool, with two
upgrades over the original thin version:
  - **Doctrine prompt** (BROWSER_BASED_AGENT_TRAINING.md): geolocate→county/API#
    first, ladder queries, rank by source authority, pivot on entities,
    triangulate, strict ``<dossier>`` JSON output (matches the live route).
  - **browse_page** custom tool (Browserbase): the agent escalates to a real
    browser for JS/WAF-walled pages web_search can't read; the session-replay URL
    becomes a sourced provenance artifact.
Wrapped by a **Redis** dossier cache (services/swarm/web/cache.py) shared with the
live route. Streaming (server search holds the connection open) + ``pause_turn`` /
``tool_use`` continuation. Returns a sentinel dossier on failure (never raises).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys

import anthropic

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "web"))
import cache  # noqa: E402 — services/swarm/web/cache.py (Redis, graceful)
import browserbase_client  # noqa: E402 — services/swarm/web/browserbase_client.py

MODEL = os.environ.get("SWARM_MODEL", "claude-sonnet-4-6")
MAX_USES = int(os.environ.get("SWARM_MAX_USES", "4"))
SEARCH_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": MAX_USES},
    {"type": "web_search_20250305", "name": "web_search", "max_uses": MAX_USES},
]
BROWSE_TOOL = {
    "name": "browse_page",
    "description": (
        "Fetch a JS-rendered or WAF/login-walled page with a real browser when "
        "web_search cannot read it (county assessor viewers, Secretary-of-State "
        "entity search, Recorder-of-Deeds, skip-trace). Returns the page's visible "
        "text. Use sparingly — only when plain search hits a wall."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"url": {"type": "string", "description": "absolute URL to load"}},
        "required": ["url"],
    },
}

SYSTEM = (
    "You are an investigative analyst building a case file on a likely undocumented "
    "orphaned oil or gas well. Doctrine: (1) GEOLOCATE FIRST — a raw lat/long is "
    "invisible to search; resolve it to county + municipality (and an API well number "
    "if findable) before searching those names. (2) Prefer authoritative databases "
    "(state O&G regulator, SoS corporate registry, county records) over open web. "
    "(3) Ladder each question 3–5 ways; rank by authority (gov/regulator > court/SoS > "
    "news > aggregators). (4) Pivot on entities: operator → officers → bankruptcy → "
    "successor → current responsible party. (5) Triangulate; never invent an operator, "
    "date, or citation — say 'Not found on the record.' when unproven. Undocumented "
    "wells usually have NO named operator; that itself is a finding. If a needed page "
    "is JS-rendered or blocks search, call browse_page(url).\n\n"
    "OUTPUT — STRICT: after at most 4 searches, reply with ONLY a JSON object wrapped "
    "in <dossier> and </dossier>. No preamble, no markdown, no headers. Exactly these "
    "string keys: \"narrative\" (2–3 plain sentences for a decision-maker), "
    "\"operator_history\", \"bankruptcy_findings\", \"news_findings\". Use "
    "\"Not found on the record.\" for anything unproven."
)


def _well_brief(well: dict) -> str:
    e = well.get("enrichment", {}) or {}
    hero = well.get("hero")
    lines = [
        f"Well id: {well.get('well_id')}",
        f"Location: {well.get('lat'):.5f}, {well.get('lon'):.5f} "
        f"({e.get('county') or well.get('county_group')}, {well.get('state')})",
        f"Type: {well.get('type_norm')}  Status: {well.get('status_norm')}",
    ]
    if well.get("quad_name"):
        lines.append(
            f"Detected on the {well.get('quad_year')} {well.get('quad_name')} "
            f"1:{well.get('quad_scale')} USGS topographic quad (U-Net)."
        )
    if hero:
        lines.append(f"Known site: {hero.get('title')} — {hero.get('place')}. {hero.get('blurb')}")
    if e.get("population_1mi") is not None or e.get("population") is not None:
        lines.append(f"~{e.get('population_1mi') or e.get('population')} people within 1 mi, "
                     f"{e.get('schools_within_1mi', 0)} schools within 1 mi"
                     + (f" (nearest: {e['nearest_school']})" if e.get('nearest_school') else ""))
    return "\n".join(lines)


def _extract(message) -> tuple[str, list[dict]]:
    text_parts: list[str] = []
    sources: list[dict] = []
    seen: set[str] = set()

    def add_source(url, title):
        if url and url not in seen:
            seen.add(url)
            sources.append({"title": (title or url)[:90], "url": url})

    for block in message.content:
        btype = getattr(block, "type", None)
        if btype == "text":
            text_parts.append(getattr(block, "text", "") or "")
            for c in (getattr(block, "citations", None) or []):
                add_source(getattr(c, "url", None), getattr(c, "title", None))
        elif btype == "web_search_tool_result":
            results = getattr(block, "content", None)
            if isinstance(results, list):
                for r in results:
                    add_source(getattr(r, "url", None), getattr(r, "title", None))
    return "\n".join(p for p in text_parts if p), sources


def _parse_dossier(text: str) -> dict:
    m = re.search(r"<dossier>(.*?)</dossier>", text, re.DOTALL)
    blob = m.group(1).strip() if m else None
    if blob:
        try:
            return json.loads(blob)
        except json.JSONDecodeError:
            try:
                return json.loads(blob[blob.index("{"): blob.rindex("}") + 1])
            except Exception:  # noqa: BLE001
                pass
    return {"narrative": text.strip()[:600]}


def _run_browse_tools(message) -> list[dict]:
    """Execute any browse_page tool_use blocks; return tool_result + replay sources."""
    results, replay_sources = [], []
    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "browse_page":
            url = (getattr(block, "input", None) or {}).get("url", "")
            page = browserbase_client.fetch_page(url) if url else None
            if page:
                replay_sources.append({"title": f"Browser session · {url[:55]}", "url": page["replay_url"]})
                content = page["text"][:6000]
            else:
                content = f"Could not load {url} via browser."
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": content})
    return results, replay_sources


def investigate_well(well: dict, timeout: int = 200) -> dict:
    """Run one investigator agent. Returns a dossier dict (never raises)."""
    wid = well.get("well_id")
    base = {
        "well_id": wid,
        "generated_by": MODEL,
        "investigated_utc": dt.datetime.utcnow().isoformat() + "Z",
    }
    cached = cache.get(wid)  # Redis (graceful) — shared with the live route
    if cached and cached.get("status") in ("complete", "partial"):
        cached["from_cache"] = True
        return cached

    client = anthropic.Anthropic(timeout=float(timeout), max_retries=0)
    last_err = None
    for search_tool in SEARCH_TOOLS:
        try:
            tools = [search_tool, BROWSE_TOOL]
            messages = [{"role": "user", "content": _well_brief(well)}]
            message = None
            browse_sources: list[dict] = []
            for _ in range(6):  # follow pause_turn (server search) + tool_use (browse_page)
                with client.messages.stream(
                    model=MODEL, max_tokens=3000, system=SYSTEM, messages=messages, tools=tools,
                ) as stream:
                    message = stream.get_final_message()
                sr = message.stop_reason
                if sr == "pause_turn":
                    messages.append({"role": "assistant", "content": message.content})
                    continue
                if sr == "tool_use":
                    messages.append({"role": "assistant", "content": message.content})
                    results, replay = _run_browse_tools(message)
                    browse_sources.extend(replay)
                    messages.append({"role": "user", "content": results or "continue"})
                    continue
                break
            text, sources = _extract(message)
            dossier = _parse_dossier(text)
            dossier.update(base)
            dossier["sources"] = (sources + browse_sources)[:10]
            dossier["status"] = "complete" if (sources or dossier.get("narrative")) else "partial"
            cache.set(wid, dossier)
            return dossier
        except Exception as e:  # noqa: BLE001 — try next tool variant, else sentinel
            last_err = e
            continue
    return {**base, "status": "error", "error": str(last_err),
            "narrative": "Investigation could not be completed for this well."}


if __name__ == "__main__":
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
    from dotenv_min import load_root_env
    load_root_env()
    sample = {"well_id": "test", "lat": 39.281361, "lon": -81.556764, "state": "West Virginia",
              "county_group": "Wood_WV", "type_norm": "unknown", "status_norm": "undocumented",
              "quad_name": "Parkersburg", "quad_year": "1969", "quad_scale": "24000",
              "enrichment": {"population_1mi": 6306, "schools_within_1mi": 2}}
    print(json.dumps(investigate_well(sample), indent=2))
