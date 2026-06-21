"""Build heroes.json from DISCOVERED wells (§3.14 / S5.1).

Heroes are now drawn from the wells we actually found (not confirmed/already-
plugged sites). Each is a real top-ranked Appalachia detection, picked to showcase
a DIFFERENT plugging pathway, and carries `hero` metadata for the topo-dissolve +
the demo narrative. We don't re-enrich/re-score — we copy the well's already-scored
detail record and attach the hero block, so there's a single source of truth.

Run as a file:  python services/ingest/build_heroes.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
WEB = ROOT / "apps" / "web" / "public" / "data"
SHARD_SIZE = 1000

# (well_id, hero metadata). Pathway = the demo "ending"; confirmed=False because
# these are high-confidence candidates, not confirmed wells (honesty).
HEROES = [
    {
        "well_id": "unet_PA_Pittsburg-West_1951_24000_geo_15",  # rank #52
        "title": "Under the most crowded square mile we found",
        "place": "Pittsburgh (West End), Allegheny County, PA",
        "pathway": "Federal BIL / Justice40",
        "blurb": (
            "From the 1951 Pittsburg West quad and in no modern database — ~16,900 "
            "people within a mile, six schools, in a Justice40 community. The clearest "
            "case for the $4.7B federal orphan-well fund."
        ),
    },
    {
        "well_id": "unet_OH_Cincinnati-West_1961_24000_geo_12",  # rank #495
        "title": "A lost well under Cincinnati's West Side",
        "place": "Cincinnati (West Side), Hamilton County, OH",
        "pathway": "Charity adopt-a-well (Well Done Foundation)",
        "blurb": (
            "On the 1961 Cincinnati West quad, ~8 km from any documented well — about "
            "6,100 people and a school within a mile. A methane-first adopt-a-well "
            "sponsor could take this on while the state queue catches up."
        ),
    },
    {
        "well_id": "unet_WV_Radnor_1962_24000_geo_28",  # rank #15060
        "title": "The well nobody was looking for",
        "place": "Radnor, Wayne County, WV",
        "pathway": "Landowner + state program",
        "blurb": (
            "From the 1962 Radnor quad in rural Wayne County — ~3.7 mi from any "
            "documented well, the purest 'lost' discovery in this set. It sits on a "
            "named family's 49-acre surface tract in a disadvantaged community: a clean "
            "candidate to plug via the surface owner and West Virginia's program."
        ),
    },
]


def _rank_index() -> dict[str, int]:
    web = json.loads((PROC / "candidates.web.json").read_text())
    return {c["well_id"]: c["rank"] for c in web}


def _detail(well_id: str, rank: int) -> dict | None:
    n = (rank - 1) // SHARD_SIZE
    path = PROC / "detail" / f"{n:02d}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text()).get(well_id)


def main() -> None:
    ranks = _rank_index()
    out = []
    for h in HEROES:
        wid = h["well_id"]
        rank = ranks.get(wid)
        if rank is None:
            print(f"[heroes] WARNING: {wid} not in candidates.web.json — skipped")
            continue
        rec = _detail(wid, rank)
        if not rec:
            print(f"[heroes] WARNING: no detail record for {wid} — skipped")
            continue
        rec = dict(rec)
        rec["layer"] = "hero"
        rec["hero"] = {
            "title": h["title"],
            "place": h["place"],
            "pathway": h["pathway"],
            "blurb": h["blurb"],
            "confirmed": False,  # discovered candidate, not a confirmed well
            "topo": {
                "year": rec.get("quad_year"),
                "label": f"USGS historical topo · {rec.get('quad_name')} quad "
                         f"({rec.get('quad_year')} ed.) → today",
            },
        }
        out.append(rec)
        print(f"[heroes] {wid}  rank #{rank}  → {h['pathway']}")

    for d in (PROC, WEB):
        (d / "heroes.json").write_text(json.dumps(out, separators=(",", ":"), default=str))
    print(f"[heroes] wrote {len(out)} heroes → data/processed/heroes.json (+ public)")


if __name__ == "__main__":
    main()
