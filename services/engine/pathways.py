"""Funding pathways (§3.4): how could THIS well actually get plugged?

Pure, deterministic ranking from fields the pipeline already computes — no network.
Each pathway carries a rationale, a rough timeline, and a confidence so the case
file can lead with the most credible route. Positioning: we *route*, we don't plug.

Inputs (all optional, degrade gracefully):
  state_abbr            : two-letter state
  cejst_disadvantaged   : Justice40 / CEJST flag (bool) -> federal set-aside leverage
  carbon_viable         : from carbon.py tiering -> carbon-funded-plugging candidate
  carbon_tier           : "self_funding" | "partial" | "negligible"
  near_people           : exposure proxy (schools≤1mi>0 or pop_1mi high) -> charity fit
  has_surface_owner     : a named surface owner was resolved (agentic) -> landowner path
"""
from __future__ import annotations

from typing import Optional

# Every USGS-DOW / detection state participates in the $4.7B BIL formula program.
BIL_FUND_USD = 4_700_000_000


def pathways_for(
    *,
    state_abbr: Optional[str] = None,
    cejst_disadvantaged: Optional[bool] = None,
    carbon_viable: bool = False,
    carbon_tier: Optional[str] = None,
    near_people: bool = False,
    has_surface_owner: bool = False,
) -> list[dict]:
    """Return funding pathways for one well, ranked best-first."""
    out: list[dict] = []

    # 1. Federal BIL / IIJA — the default route for an undocumented orphan well.
    j40 = bool(cejst_disadvantaged)
    out.append({
        "key": "federal_bil",
        "label": "Federal BIL / IIJA orphan-well program",
        "eligible": True,
        "rationale": (
            "State receives Bipartisan Infrastructure Law formula grants from the "
            f"${BIL_FUND_USD/1e9:.1f}B federal orphan-well fund"
            + (" — Justice40 prioritizes this disadvantaged community." if j40
               else ".")
        ),
        "timeline": "Months–years (state plugging queue once the well is registered)",
        "actor": "state_regulator",
        "confidence": "high" if j40 else "medium",
        "priority": 0 if j40 else 1,
    })

    # 2. State plugging program (the operational arm of the federal money).
    if state_abbr:
        out.append({
            "key": "state_program",
            "label": "State orphan/abandoned-well plugging program",
            "eligible": True,
            "rationale": "State regulator runs the plugging program and the bid queue.",
            "timeline": "Months–years",
            "actor": "state_regulator",
            "confidence": "high",
            "priority": 1,
        })

    # 3. Carbon-funded plugging — only the heavy-emitter tail (measured flux).
    if carbon_viable:
        out.append({
            "key": "carbon_credit",
            "label": "Carbon-credit-funded plugging (ACR methodology)",
            "eligible": True,
            "rationale": (
                "High modeled methane makes this a candidate for self-funding via "
                "carbon credits, like Zefiro's ACR959 (one well ≈ 92,956 t CO₂e). "
                "Requires measured pre-plug flux + additionality."
            ),
            "timeline": "Quarters (measure → plug → verify → issue credits)",
            "actor": "carbon_developer",
            "confidence": "high" if carbon_tier == "self_funding" else "medium",
            "priority": 0,
        })

    # 4. Charity / adopt-a-well — right profile only (near people / methane-first).
    if near_people:
        out.append({
            "key": "charity",
            "label": "Charity adopt-a-well (Well Done Foundation / Orphan Well Cooperative)",
            "eligible": True,
            "rationale": "Methane-first, high-exposure site fits adopt-a-well selection.",
            "timeline": "Months (sponsor-dependent)",
            "actor": "charity",
            "confidence": "medium",
            "priority": 2,
        })

    # 5. Landowner-funded — only when a surface owner is actually named (agentic).
    if has_surface_owner:
        out.append({
            "key": "landowner",
            "label": "Landowner-funded plugging",
            "eligible": True,
            "rationale": "A named surface owner can plug for access/liability reasons.",
            "timeline": "Variable",
            "actor": "surface_owner",
            "confidence": "low",
            "priority": 3,
        })

    out.sort(key=lambda p: (p["priority"], {"high": 0, "medium": 1, "low": 2}[p["confidence"]]))
    return out


def pathways_for_record(rec: dict) -> list[dict]:
    """Convenience: pull the inputs off a scored detail record."""
    e = rec.get("enrichment") or {}
    cb = rec.get("carbon") or {}
    near = bool((e.get("schools_within_1mi") or 0) > 0 or (e.get("population_1mi") or 0) >= 1000)
    return pathways_for(
        state_abbr=rec.get("state_abbr"),
        cejst_disadvantaged=e.get("cejst_disadvantaged"),
        carbon_viable=bool(cb.get("carbon_viable")),
        carbon_tier=cb.get("tier"),
        near_people=near,
        has_surface_owner=bool((rec.get("case") or {}).get("surface_owner")),
    )


if __name__ == "__main__":
    import json
    print(json.dumps(pathways_for(state_abbr="OH", cejst_disadvantaged=True,
                                  carbon_viable=False, near_people=True), indent=2))
