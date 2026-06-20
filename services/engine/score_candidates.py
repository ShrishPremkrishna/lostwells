"""Score candidate UOWs: methane + plug cost + carbon + composite ranking.

Reads  data/processed/candidates.base.json
       data/processed/enrichment.json     (optional; written by services/ingest/enrich.py)
Writes data/processed/candidates.scored.json   (ranked, full per-well economics)

Run after enrichment for differentiated human-exposure/equity scores; runnable
beforehand too (those metrics simply read as missing and are renormalized out).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from methane import estimate_methane            # noqa: E402
from plugcost import estimate_plug_cost          # noqa: E402
from carbon import carbon_kicker                 # noqa: E402
import scoring                                   # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"

# Modest state cost indices (default 1.0). Raimi notes wide state variation;
# kept conservative/neutral to avoid false precision.
STATE_COST_INDEX = {"CA": 1.25, "AK": 1.4}


def build_record(base: dict, enrich: dict | None) -> dict:
    methane = estimate_methane(plugged=bool(base.get("is_plugged")))
    plug = estimate_plug_cost(
        type_norm=base.get("type_norm", "unknown"),
        depth_ft=base.get("depth_ft"),
        state_cost_index=STATE_COST_INDEX.get(base.get("state_abbr"), 1.0),
    )
    carbon = carbon_kicker(methane.t_co2e_gwp100_point, plug.point_usd)

    e = enrich or {}
    rec = dict(base)
    rec["methane"] = methane.to_dict()
    rec["plug_cost"] = plug.to_dict()
    rec["carbon"] = carbon.to_dict()
    rec["enrichment"] = e
    rec["metrics"] = {
        "population": e.get("population"),
        "schools": e.get("schools_within_1mi"),
        "hospitals": e.get("hospitals_within_5mi"),
        "drinking_water": e.get("drinking_water_score"),
        "svi": e.get("svi"),
        "ej": e.get("ej"),
        "methane": methane.t_co2e_gwp100_point,
        "plug_cost": plug.point_usd,
        "program_match": scoring.program_match_score(base.get("state_abbr")),
    }
    return rec


def _load(name: str):
    p = PROC / name
    return json.loads(p.read_text()) if p.exists() else None


def main() -> None:
    cand_base = json.loads((PROC / "candidates.base.json").read_text())
    cand_enrich = _load("enrichment.json") or {}
    if cand_enrich:
        print(f"[score] using enrichment for {len(cand_enrich)} candidates")
    else:
        print("[score] no enrichment.json yet — exposure/equity metrics renormalized out")

    hero_base = _load("heroes.base.json") or []
    hero_enrich = _load("heroes.enrichment.json") or {}
    if hero_base:
        print(f"[score] folding in {len(hero_base)} hero wells")

    cand = [build_record(b, cand_enrich.get(b["well_id"])) for b in cand_base]
    heroes = [build_record(b, hero_enrich.get(b["well_id"])) for b in hero_base]

    # Score candidates + heroes together so percentiles share one distribution.
    combined = scoring.score_set(cand + heroes)
    combined.sort(key=lambda r: r["score"]["composite"], reverse=True)
    for i, r in enumerate(combined, 1):
        r["global_rank"] = i

    candidates = [r for r in combined if r.get("layer") != "hero"]
    for i, r in enumerate(candidates, 1):
        r["rank"] = i
    out = PROC / "candidates.scored.json"
    out.write_text(json.dumps(candidates, separators=(",", ":"), default=str))
    comps = [r["score"]["composite"] for r in candidates]
    print(f"[score] {len(candidates)} candidates scored -> {out.relative_to(ROOT)}")
    print(f"[score] composite min/median/max = "
          f"{min(comps):.1f} / {comps[len(comps)//2]:.1f} / {max(comps):.1f}")
    print("[score] top 3:")
    for r in candidates[:3]:
        print(f"    #{r['rank']:>3}  {r['score']['composite']:>5.1f}  "
              f"{r['state_abbr']}/{r['county_group']}  {r['well_id']}")

    hero_records = [r for r in combined if r.get("layer") == "hero"]
    if hero_records:
        for r in hero_records:
            r["rank"] = r["global_rank"]
        hp = PROC / "heroes.json"
        hp.write_text(json.dumps(hero_records, separators=(",", ":"), default=str))
        print(f"[score] {len(hero_records)} heroes scored -> {hp.relative_to(ROOT)}")
        for r in hero_records:
            print(f"    ★ {r['score']['composite']:>5.1f} (global #{r['global_rank']})  "
                  f"{r['hero']['title']}")


if __name__ == "__main__":
    main()
