"""Score candidate UOWs: methane + plug cost + carbon + composite ranking.

Reads  data/processed/candidates.base.json
       data/processed/enrichment.json     (optional; written by services/ingest/enrich.py)
Writes data/processed/candidates.scored.json   (ranked, full per-well economics)

Run after enrichment for differentiated human-exposure/equity scores; runnable
beforehand too (those metrics simply read as missing and are renormalized out).
"""
from __future__ import annotations

import json
import math
import os
import shutil
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


def build_record(base: dict, enrich: dict | None, se: dict | None = None) -> dict:
    # Status honesty (§2B): undocumented candidates have genuinely unknown
    # status, so treat status as None to fire the unplugged/plugged blend + the
    # "undifferentiated" badge. This does NOT mutate base["is_plugged"], so
    # plug_cost (which keys off the raw flag) is untouched.
    status_norm = base.get("status_norm")
    plugged = (None if status_norm in (None, "undocumented", "unknown")
               else bool(base.get("is_plugged")))

    se_rec = se or {}
    methane = estimate_methane(
        plugged=plugged,
        state_abbr=base.get("state_abbr"),
        well_type=base.get("type_norm"),
        super_emitter=se_rec.get("super_emitter"),
        super_emitter_dist_m=se_rec.get("super_emitter_dist_m"),
        super_emitter_rate_kg_hr=se_rec.get("super_emitter_rate_kg_hr"),
    )
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
        # Prefer the true 1-mile areal-interpolated population (§2A) over the
        # tract-pop proxy; fall back to the proxy where the new layer is absent.
        "population": e.get("population_1mi") if e.get("population_1mi") is not None
                      else e.get("population"),
        "schools": e.get("schools_within_1mi"),
        "hospitals": e.get("hospitals_within_5mi"),
        "drinking_water": e.get("drinking_water_score"),
        "svi": e.get("svi"),
        # Real EJ signal from EJI/CEJST when present (§2A); else the SVI-derived proxy.
        "ej": e.get("eji_rank") if e.get("eji_rank") is not None else e.get("ej"),
        # Scored scalar (§2B): a super-emitter-flagged well uses our own modeled
        # right-tail anchor (not an invented measurement); else the point.
        "methane": (methane.t_co2e_gwp100_high if methane.super_emitter
                    else methane.t_co2e_gwp100_point),
        "plug_cost": plug.point_usd,
        "program_match": scoring.program_match_score(base.get("state_abbr")),
    }
    return rec


def _load(name: str):
    p = PROC / name
    return json.loads(p.read_text()) if p.exists() else None


# Lite fields the map/list/hover/search/sort/swarm components read. Everything
# else (full score, methane, plug_cost, carbon, full enrichment, provenance) is
# lazy-loaded per shard only when a well's DossierPanel opens.
_SLIM_ENRICH_KEYS = (
    "population", "schools_within_1mi", "nearest_school_m", "nearest_school", "county",
)
SHARD_SIZE = 1000


def _slim_record(r: dict) -> dict:
    e = r.get("enrichment") or {}
    out = {
        "well_id": r["well_id"],
        "rank": r["rank"],
        # 5 decimals ≈ 1.1 m precision — plenty for the map, and trims the payload.
        "lat": round(r["lat"], 5),
        "lon": round(r["lon"], 5),
        "name": r.get("name"),
        "quad_name": r.get("quad_name"),
        "county_group": r.get("county_group"),
        "state": r.get("state"),
        "score": {"composite": r["score"]["composite"]},
    }
    # Omit null enrichment fields (and the dict entirely when empty). Most records
    # have no nearby population/schools, so dropping their repeated null keys trims
    # ~4 MB. All web reads are null-safe (`e.population ?? …`), so absent == null.
    enr = {k: e[k] for k in _SLIM_ENRICH_KEYS if e.get(k) is not None}
    if enr:
        out["enrichment"] = enr
    if r.get("hero"):
        h = r["hero"]
        out["hero"] = {
            "title": h.get("title"),
            "place": h.get("place"),
            "confirmed": h.get("confirmed"),
        }
    return out


def _nan_to_none(o):
    """Recursively replace float NaN/Infinity with None so the output is valid
    JSON (the browser's JSON.parse rejects bare NaN, unlike Python's loader)."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _nan_to_none(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_nan_to_none(v) for v in o]
    return o


def _dump_json(obj) -> str:
    # allow_nan=False makes any residual non-finite float a hard error rather
    # than silently emitting browser-invalid `NaN`/`Infinity`.
    return json.dumps(_nan_to_none(obj), separators=(",", ":"),
                      default=str, allow_nan=False)


def write_web_payloads(candidates: list[dict]) -> None:
    """Emit the slim base payload + rank-bucketed detail shards for the web app."""
    web = PROC / "candidates.web.json"
    slim = [_slim_record(r) for r in candidates]
    web.write_text(_dump_json(slim))
    print(f"[score] slim payload {len(slim)} -> {web.relative_to(ROOT)} "
          f"({web.stat().st_size / 1e6:.1f} MB)")

    # Clear stale shards so a smaller run never leaves orphans behind.
    detail_dir = PROC / "detail"
    if detail_dir.exists():
        shutil.rmtree(detail_dir)
    detail_dir.mkdir(parents=True)

    # Shards (and the web byId map) are keyed by well_id, so any duplicate ids in
    # the upstream data collapse to one entry. Surface that rather than silently
    # corrupting shards; the assertion is against unique ids, which is what the
    # keyed shards can actually address.
    unique_ids = {r["well_id"] for r in candidates}
    n_dupe = len(candidates) - len(unique_ids)
    if n_dupe:
        print(f"[score] WARNING: {n_dupe} duplicate well_id(s) in candidates "
              f"(upstream dedup issue) — they share a shard entry")

    shards: dict[int, dict] = {}
    for r in candidates:
        shards.setdefault((r["rank"] - 1) // SHARD_SIZE, {})[r["well_id"]] = r

    max_bytes = 0
    total = 0
    for nn, recs in sorted(shards.items()):
        p = detail_dir / f"{nn:02d}.json"
        p.write_text(_dump_json(recs))
        max_bytes = max(max_bytes, p.stat().st_size)
        total += len(recs)
    assert total == len(unique_ids), f"shard total {total} != unique ids {len(unique_ids)}"
    print(f"[score] detail shards: {len(shards)} files in {detail_dir.relative_to(ROOT)} "
          f"(max {max_bytes / 1e6:.1f} MB, sum lens {total} == {len(unique_ids)} unique ids ✓)")


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

    # §2B EPA super-emitter sidecars (well_id -> flags); absent -> no flags.
    cand_se = _load("super_emitter.json") or {}
    hero_se = _load("heroes.super_emitter.json") or {}
    n_se = sum(1 for v in cand_se.values() if v.get("super_emitter"))
    if cand_se or hero_se:
        print(f"[score] super-emitter flags: {n_se} candidates, "
              f"{sum(1 for v in hero_se.values() if v.get('super_emitter'))} heroes")

    cand = [build_record(b, cand_enrich.get(b["well_id"]), cand_se.get(b["well_id"]))
            for b in cand_base]
    heroes = [build_record(b, hero_enrich.get(b["well_id"]), hero_se.get(b["well_id"]))
              for b in hero_base]

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

    write_web_payloads(candidates)

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
