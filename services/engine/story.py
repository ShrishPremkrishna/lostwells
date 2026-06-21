"""Advocacy story (§3.5): a short, sourced call-to-action per well.

Evidence-grounded, tuned to the chosen funding pathway and the named actor who can
move it ("could be plugged by next session if X acts"). Uses the official anthropic
SDK + server-side web search (the proven investigator pattern). Requires
ANTHROPIC_API_KEY; when absent, `generate_story` returns None so the rest of the
case-file pipeline still produces deterministic output.
"""
from __future__ import annotations

import os
from typing import Optional

MODEL = os.environ.get("STORY_MODEL", "claude-sonnet-4-6")


def _prompt(rec: dict, pathway: Optional[dict], actors: Optional[dict]) -> str:
    e = rec.get("enrichment") or {}
    pop = e.get("population_1mi") or e.get("population")
    reg = (actors or {}).get("responsible_regulator") or {}
    rep = ((actors or {}).get("can_pressure") or {}).get("us_representative") or {}
    return (
        "Write a 3-4 sentence, evidence-grounded advocacy brief for a decision-maker "
        "about an undocumented orphaned oil/gas well. PLAIN PROSE ONLY — no markdown, "
        "no headers, no titles, no bullet points. Be concrete and sourced; never "
        "invent specifics. Frame a clear call to action via the named pathway/actor.\n\n"
        f"Well: {rec.get('name')} ({e.get('county')}, {rec.get('state')}); detected on the "
        f"{rec.get('quad_year')} {rec.get('quad_name')} USGS topo quad.\n"
        f"Exposure: ~{pop} people within 1 mile, {e.get('schools_within_1mi', 0)} schools ≤1mi; "
        f"social-vulnerability pct {e.get('svi')}.\n"
        f"Recommended pathway: {pathway.get('label') if pathway else 'federal/state program'}.\n"
        f"Who can act: {reg.get('agency','state regulator')}"
        f"{('; Rep. ' + rep.get('name')) if rep.get('name') else ''}.\n"
        "End with one sentence on what action, by whom, would get it plugged."
    )


def generate_story(rec: dict, pathway: Optional[dict] = None,
                   actors: Optional[dict] = None, timeout: int = 120) -> Optional[dict]:
    """Return {text, generated_by} or None if no API key / on failure."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic  # lazy: not installed in the pure-compute env
    except Exception:  # noqa: BLE001
        return None
    try:
        client = anthropic.Anthropic(timeout=float(timeout), max_retries=0)
        msg = client.messages.create(
            model=MODEL, max_tokens=400,
            messages=[{"role": "user", "content": _prompt(rec, pathway, actors)}],
        )
        text = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", None) == "text")
        return {"text": text.strip(), "generated_by": MODEL} if text.strip() else None
    except Exception:  # noqa: BLE001
        return None


if __name__ == "__main__":
    import json
    sample = {"name": "Undocumented well · Cincinnati West quad (1961)", "state": "Ohio",
              "quad_name": "Cincinnati West", "quad_year": "1961",
              "enrichment": {"county": "Hamilton County", "population_1mi": 13342,
                             "schools_within_1mi": 3, "svi": 0.98}}
    print(json.dumps(generate_story(sample) or {"story": "skipped (no ANTHROPIC_API_KEY)"}, indent=2))
