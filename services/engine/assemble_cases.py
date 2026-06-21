"""Assemble per-well case files (§3.7) → data/processed/case_files.json.

Merges, for the top-N Appalachia wells: the evidence (score + exposure), the
funding **pathways** (pathways.py), the **actor map** (actors.py), and — when
ANTHROPIC_API_KEY is set — a short sourced **story** (story.py). Deterministic
parts always run; the story degrades to null offline. Keyed by well_id.

Run as a file:  python services/engine/assemble_cases.py [--total 150]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import actors as A          # noqa: E402
import pathways as P        # noqa: E402
import story as STORY       # noqa: E402

sys.path.insert(0, str(ROOT / "services" / "swarm" / "web"))
import parcel as PARCEL     # noqa: E402 — free ArcGIS surface-owner lookup (WV/…)

sys.path.insert(0, str(ROOT / "services"))
from dotenv_min import load_root_env  # noqa: E402
load_root_env()  # ANTHROPIC_API_KEY from <repo-root>/.env enables story.py

APPALACHIA = {"Ohio", "Pennsylvania", "West Virginia", "Kentucky"}
SHARD_SIZE = 1000

_shard_cache: dict[int, dict] = {}


def _shard(rank: int) -> dict:
    n = (rank - 1) // SHARD_SIZE
    if n not in _shard_cache:
        path = PROC / "detail" / f"{n:02d}.json"
        _shard_cache[n] = json.loads(path.read_text()) if path.exists() else {}
    return _shard_cache[n]


def _detail(well_id: str, rank: int) -> dict | None:
    return _shard(rank).get(well_id)


def _evidence(rec: dict) -> dict:
    e = rec.get("enrichment") or {}
    s = rec.get("score") or {}
    cb = rec.get("carbon") or {}
    return {
        "composite": s.get("composite"),
        "population_1mi": e.get("population_1mi") or e.get("population"),
        "schools_within_1mi": e.get("schools_within_1mi"),
        "drinking_water_score": e.get("drinking_water_score"),
        "svi": e.get("svi"),
        "ej": e.get("eji_rank") if e.get("eji_rank") is not None else e.get("ej"),
        "cejst_disadvantaged": e.get("cejst_disadvantaged"),
        "carbon_tier": cb.get("tier"),
        "carbon_viable": cb.get("carbon_viable"),
        "quad": f"{rec.get('quad_year')} {rec.get('quad_name')}",
        "nearest_doc_well_m": rec.get("nearest_doc_well_m"),
    }


_ABBR = {"Ohio": "OH", "Pennsylvania": "PA", "West Virginia": "WV", "Kentucky": "KY"}


def _hero_ids() -> set[str]:
    p = PROC / "heroes.json"
    try:
        return {h["well_id"] for h in json.loads(p.read_text())} if p.exists() else set()
    except Exception:  # noqa: BLE001
        return set()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--total", type=int, default=150, help="top-N Appalachia wells to case")
    ap.add_argument("--stories", type=int, default=40, help="Claude briefs for top-N (+heroes)")
    ap.add_argument("--force-stories", action="store_true", help="regenerate briefs even if cached")
    args = ap.parse_args()

    web = json.loads((PROC / "candidates.web.json").read_text())
    app = sorted((c for c in web if c.get("state") in APPALACHIA), key=lambda c: c["rank"])
    cohort = app[: args.total]
    # Always include the hero wells even if they rank outside the top-N.
    in_cohort = {c["well_id"] for c in cohort}
    heroes = _hero_ids()
    cohort += [c for c in app if c["well_id"] in heroes and c["well_id"] not in in_cohort]

    have_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    ep = PROC / "case_files.json"
    existing = {}
    if ep.exists():
        try:
            existing = json.loads(ep.read_text())
        except Exception:  # noqa: BLE001
            existing = {}

    print(f"[cases] casing {len(cohort)} Appalachia wells (briefs: "
          f"{'top ' + str(args.stories) + '+heroes' if have_key else 'off — no ANTHROPIC_API_KEY'})")

    # 1) deterministic case for every well (geocoder/parcel are SQLite-cached, so fast)
    cases: dict[str, dict] = {}
    recs: dict[str, dict] = {}
    for i, c in enumerate(cohort):
        rec = _detail(c["well_id"], c["rank"]) or c
        recs[c["well_id"]] = rec
        st = rec.get("state_abbr") or _ABBR.get(c.get("state"))
        actor_map = A.actors_for(c["lat"], c["lon"], st)
        actor_map["surface_owner"] = PARCEL.owner_at(c["lat"], c["lon"], st) if st else None
        e = rec.get("enrichment") or {}
        cb = rec.get("carbon") or {}
        near = bool((e.get("schools_within_1mi") or 0) > 0 or (e.get("population_1mi") or 0) >= 1000)
        paths = P.pathways_for(
            state_abbr=st,
            cejst_disadvantaged=e.get("cejst_disadvantaged"),
            carbon_viable=bool(cb.get("carbon_viable")),
            carbon_tier=cb.get("tier"),
            near_people=near,
            has_surface_owner=bool(actor_map["surface_owner"]),
        )
        cases[c["well_id"]] = {
            "well_id": c["well_id"], "rank": c["rank"], "name": c.get("name"),
            "state": c.get("state"),
            "county": (rec.get("enrichment") or {}).get("county") or c.get("county_group"),
            "evidence": _evidence(rec), "pathways": paths, "actors": actor_map,
            "story": (existing.get(c["well_id"]) or {}).get("story"),  # reuse cached brief
        }
        if (i + 1) % 50 == 0:
            print(f"[cases]   deterministic {i + 1}/{len(cohort)}")

    # 2) Claude advocacy briefs for the story cohort (heroes + top-N), parallel + idempotent
    if have_key and args.stories > 0:
        order = list(_hero_ids() & set(cases)) + [c["well_id"] for c in cohort[: args.stories]]
        seen: set[str] = set()
        story_ids = [w for w in order if not (w in seen or seen.add(w))]
        todo = [w for w in story_ids if args.force_stories or not (cases[w].get("story") or {}).get("text")]
        print(f"[cases] briefs: {len(story_ids)} in cohort, {len(todo)} to generate (parallel)")

        def gen(w: str):
            cs = cases[w]
            top = cs["pathways"][0] if cs["pathways"] else None
            return w, STORY.generate_story(recs[w], top, cs["actors"])

        with ThreadPoolExecutor(max_workers=6) as ex:
            for w, story in ex.map(gen, todo):
                if story:
                    cases[w]["story"] = story

    ep.write_text(json.dumps(cases, separators=(",", ":"), default=str))
    n_story = sum(1 for v in cases.values() if (v.get("story") or {}).get("text"))
    n_owner = sum(1 for v in cases.values() if (v["actors"].get("surface_owner") or {}).get("owner"))
    print(f"[cases] wrote {len(cases)} -> {ep.relative_to(ROOT)} "
          f"(briefs {n_story}, named owners {n_owner})")


if __name__ == "__main__":
    main()
