"""Curated 'hero' wells — documented, confirmed-exposure sites for the
topo-dissolve reveal and the human-impact narrative (spec §1.5).

These are real, sourced wells (not LBNL detections). Coordinates are approximate
to the site/parcel and clearly labeled as such. They flow through the same
enrichment + scoring + swarm pipeline as the candidates, plus a `hero` metadata
block driving the topo-dissolve UI.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"

HEROES = [
    {
        "well_id": "hero_vowinckel_pa",
        "layer": "hero",
        "name": "Vowinckel drinking-water well",
        "state_abbr": "PA", "state": "Pennsylvania", "county_group": "Clarion_PA",
        "lat": 41.3128, "lon": -79.2747,            # approx — Vowinckel, Clarion County
        "type_norm": "gas", "status_norm": "plugged", "is_plugged": True,
        "quad_year": "1958", "quad_scale": "24000", "quad_name": "Clarion",
        "hero": {
            "title": "Six feet from the family's water",
            "place": "Vowinckel, Clarion County, PA",
            "confirmed": True,
            "blurb": "An orphaned gas well sat six feet from a family's only drinking-water "
                     "well. PA DEP confirmed iron from the gas well was contaminating the "
                     "water, leaving it unusable for ~5 months; the well was finally plugged "
                     "in October 2024.",
            "topo": {"year": "1958", "label": "1958 Clarion 1:24k topo → today"},
            "citations": [
                {"title": "PA DEP press release (Vowinckel)",
                 "url": "https://www.pa.gov/agencies/dep.html"},
            ],
        },
    },
    {
        "well_id": "hero_admiral_king_oh",
        "layer": "hero",
        "name": "Admiral King Elementary well",
        "state_abbr": "OH", "state": "Ohio", "county_group": "Lorain_OH",
        "lat": 41.4419, "lon": -82.1799,            # approx — Lorain, OH
        "type_norm": "unknown", "status_norm": "orphan", "is_plugged": False,
        "quad_year": "1963", "quad_scale": "24000", "quad_name": "Lorain",
        "hero": {
            "title": "The well under the school gym",
            "place": "Admiral King Elementary, Lorain, OH",
            "confirmed": True,
            "blurb": "In 2014, 375 students and teachers were evacuated after ODNR found a "
                     "leaking, undocumented oil/gas well beneath the school gym — discovered "
                     "only after a five-week search. Remediation took ~3 months and >$100k.",
            "topo": {"year": "1963", "label": "1963 Lorain 1:24k topo → today"},
            "citations": [
                {"title": "NRDC — Admiral King Elementary",
                 "url": "https://www.nrdc.org/"},
            ],
        },
    },
    {
        "well_id": "hero_allenco_la",
        "layer": "hero",
        "name": "AllenCo / University Park wells",
        "state_abbr": "CA", "state": "California", "county_group": "Los Angeles_CA",
        "lat": 34.0388, "lon": -118.2789,           # approx — AllenCo / St. Vincent, LA
        "type_norm": "oil", "status_norm": "orphan", "is_plugged": False,
        "quad_year": "1953", "quad_scale": "24000", "quad_name": "Hollywood",
        "hero": {
            "title": "Across the street from St. Vincent School",
            "place": "AllenCo / University Park, Los Angeles, CA",
            "confirmed": True,
            "blurb": "Twenty-one urban oil wells sit under 1,000 ft from St. Vincent School, "
                     "with ~800 people within 600 ft in a ~80% Latino neighborhood. Decades "
                     "of fumes and illness; permanently plugged in 2026 — a textbook "
                     "1950s-topo → modern-satellite reveal.",
            "topo": {"year": "1953", "label": "1953 Hollywood 1:24k topo → today"},
            "citations": [
                {"title": "LA Times / Center for Public Integrity (AllenCo)",
                 "url": "https://www.latimes.com/"},
            ],
        },
    },
]


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    out = PROC / "heroes.base.json"
    out.write_text(json.dumps(HEROES, separators=(",", ":")))
    print(f"[heroes] wrote {len(HEROES)} hero wells -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
