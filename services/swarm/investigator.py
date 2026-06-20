"""The `well_investigator` subagent: one Claude agent per well.

Uses the official ``anthropic`` SDK + Anthropic's **server-side web search tool**
(runs on Anthropic's infra via api.anthropic.com — no extra key/domain) to do
open-ended investigation: original operator, ownership/bankruptcy/shell-company
transfers, and local news. This open-ended search is the "real agent" showcase
(spec §2.2) — not deterministic API lookups.

Note: we drive Claude via the official ``anthropic`` SDK rather than
``langchain_anthropic.ChatAnthropic`` because the latter hangs in this sandbox's
network (the raw SDK + LangGraph orchestration are the reliable combination).
The LangGraph ``Send`` map-reduce graph (graph.py) is unchanged — this is just
the LLM client used inside each worker node.

Honest by design: undocumented wells rarely have a named operator, so the agent
is told to report county/field/regulatory context and say so when specifics
aren't found, rather than inventing an operator.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re

import anthropic

MODEL = os.environ.get("SWARM_MODEL", "claude-sonnet-4-6")  # Sonnet subagents (spec §2.4)
MAX_USES = int(os.environ.get("SWARM_MAX_USES", "4"))  # bound search count per well
# Latest server web-search variant (Sonnet 4.6+); falls back to the basic one.
SEARCH_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": MAX_USES},
    {"type": "web_search_20250305", "name": "web_search", "max_uses": MAX_USES},
]

SYSTEM = (
    "You are a meticulous investigative analyst building a dossier on a possibly "
    "undocumented orphaned oil or gas well in the United States. Use web search to "
    "investigate: (1) the original operator/driller and any ownership, bankruptcy, or "
    "shell-company transfers; (2) the state orphaned-well program and any documented "
    "spills, contamination, or enforcement near this location; (3) local news about "
    "wells in this county/field. Undocumented wells usually have NO named operator on "
    "record — when you can't find specifics for this exact well, say so plainly and "
    "report what IS known about orphaned wells in that county/state. Never invent an "
    "operator, date, or citation. Be concise and concrete. Limit yourself to at most "
    "3-4 web searches total, then write the dossier.\n\n"
    "After researching, end your reply with a JSON object between <dossier> and "
    "</dossier> tags with exactly these string keys: "
    '"narrative" (2-3 sentences for a decision-maker), '
    '"operator_history", "bankruptcy_findings", "news_findings". '
    "Use \"Not found on the record.\" for any field you couldn't substantiate."
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
            f"1:{well.get('quad_scale')} USGS topographic quad (LBNL U-Net)."
        )
    if hero:
        lines.append(f"Known site: {hero.get('title')} — {hero.get('place')}. {hero.get('blurb')}")
    if e.get("population") is not None:
        lines.append(f"Tract population ~{e.get('population')}, "
                     f"{e.get('schools_within_1mi', 0)} schools within 1 mile"
                     + (f" (nearest: {e['nearest_school']})" if e.get('nearest_school') else ""))
    return "\n".join(lines)


def _extract(message) -> tuple[str, list[dict]]:
    """Pull plain text + cited source URLs from an anthropic Message."""
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


def investigate_well(well: dict, timeout: int = 150) -> dict:
    """Run one investigator agent. Returns a dossier dict (never raises)."""
    base = {
        "well_id": well.get("well_id"),
        "generated_by": MODEL,
        "investigated_utc": dt.datetime.utcnow().isoformat() + "Z",
    }
    client = anthropic.Anthropic(timeout=float(timeout), max_retries=0)
    user = [{"role": "user", "content": _well_brief(well)}]
    last_err = None
    for tool in SEARCH_TOOLS:
        try:
            messages = list(user)
            message = None
            for _ in range(4):  # follow server-tool pause_turn continuations
                # Stream (not create): server-side web search holds the connection
                # open while searching; streaming keeps it alive so the sandbox's
                # egress proxy doesn't idle-drop it.
                with client.messages.stream(
                    model=MODEL, max_tokens=4096, system=SYSTEM,
                    messages=messages, tools=[tool],
                ) as stream:
                    message = stream.get_final_message()
                if message.stop_reason != "pause_turn":
                    break
                messages.append({"role": "assistant", "content": message.content})
            text, sources = _extract(message)
            dossier = _parse_dossier(text)
            dossier.update(base)
            dossier["sources"] = sources[:8]
            dossier["status"] = "complete" if (sources or dossier.get("narrative")) else "partial"
            return dossier
        except Exception as e:  # noqa: BLE001 — try the next tool variant, else sentinel
            last_err = e
            continue
    return {**base, "status": "error", "error": str(last_err),
            "narrative": "Investigation could not be completed for this well."}


if __name__ == "__main__":  # quick manual test
    sample = {"well_id": "test", "lat": 35.5, "lon": -97.5, "state": "Oklahoma",
              "county_group": "Oklahoma_OK", "type_norm": "oil", "status_norm": "undocumented",
              "quad_name": "Britton", "quad_year": "1951", "quad_scale": "24000",
              "enrichment": {"population": 5198, "schools_within_1mi": 6}}
    print(json.dumps(investigate_well(sample), indent=2))
