"""Curated 'hero' wells — documented, confirmed-exposure sites for the
topo-dissolve reveal and the human-impact narrative (spec §1.5).

These are real, sourced wells (not LBNL detections). Each coordinate carries
explicit provenance via `coord_source` (where the lat/lon came from) and
`coord_precision` ("building" | "parcel" | "community") so varying confidence is
honest: building/parcel coords are geocoded from authoritative records, while
community-level coords (e.g. Vowinckel, whose residential bore is not public) are
centroids labeled as approximate. They flow through the same enrichment + scoring
+ swarm pipeline as the candidates, plus a `hero` metadata block driving the
topo-dissolve UI.
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
        "lat": 41.411452, "lon": -79.228653,        # Vowinckel community centroid (bore not public)
        "coord_source": "Vowinckel community centroid (OpenStreetMap/Nominatim); "
                        "DEP release gives locality only, residential bore not public",
        "coord_precision": "community",
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
            "topo": {"year": "1958",
                     "label": "USGS historical topo · Clarion quad (1958 ed.) → today"},
            "citations": [
                {"title": "PA DEP: Shapiro Admin. plugs orphan well that contaminated family's water (Oct 25 2024)",
                 "url": "https://www.pa.gov/agencies/dep/newsroom/shapiro-administration-plugs-orphan-well-that-contaminated-famil"},
                {"title": "exploreClarion: State DEP plugs orphan gas well (Vowinckel family)",
                 "url": "http://www.exploreclarion.com/local/2024/10/24/state-dep-plugs-orphan-gas-well-that-contaminated-vowinckel-familys-drinking-water-829920/"},
            ],
        },
    },
    {
        "well_id": "hero_admiral_king_oh",
        "layer": "hero",
        "name": "Admiral King Elementary well",
        "state_abbr": "OH", "state": "Ohio", "county_group": "Lorain_OH",
        "lat": 41.462477, "lon": -82.179203,        # 720 Washington Ave, Lorain OH (school footprint)
        "coord_source": "US Census geocoder on NCES CCD school address "
                        "(Admiral King Elementary, NCES ID 390442601193; 720 Washington Ave, Lorain OH 44052)",
        "coord_precision": "building",
        "type_norm": "unknown", "status_norm": "orphan", "is_plugged": False,
        "quad_year": "1963", "quad_scale": "24000", "quad_name": "Lorain",
        "hero": {
            "title": "The well under the school gym",
            "place": "Admiral King Elementary, Lorain, OH",
            "confirmed": True,
            "blurb": "In 2014, 375 students and teachers were evacuated after ODNR found a "
                     "leaking, undocumented oil/gas well beneath the school gym — discovered "
                     "only after a five-week search. Remediation took ~3 months and >$100k.",
            "topo": {"year": "1963",
                     "label": "USGS historical topo · Lorain quad (1963 ed.) → today"},
            "citations": [
                {"title": "WKYC: Source of Lorain school gas leak found (uncapped well under the gym)",
                 "url": "https://www.wkyc.com/article/news/local/lorain-county/after-a-month-source-of-lorain-school-gas-leak-found/95-242077711"},
                {"title": "Fox 8: First look inside school closed 3 months over strange smell",
                 "url": "https://fox8.com/2014/12/30/first-look-inside-school-that-closed-for-3-months-due-to-strange-smell"},
            ],
        },
    },
    {
        "well_id": "hero_allenco_la",
        "layer": "hero",
        "name": "AllenCo / University Park wells",
        "state_abbr": "CA", "state": "California", "county_group": "Los Angeles_CA",
        "lat": 34.032662, "lon": -118.278445,       # 814 W 23rd St — AllenCo St. James Drill Site
        "coord_source": "US Census geocoder on 814 W 23rd St, Los Angeles CA 90007 "
                        "(AllenCo 'St. James Drill Site', 21 wells)",
        "coord_precision": "parcel",
        "type_norm": "oil", "status_norm": "orphan", "is_plugged": False,
        "quad_year": "1953", "quad_scale": "24000", "quad_name": "Hollywood",
        "hero": {
            "title": "Across the street from St. Vincent School",
            "place": "AllenCo / University Park, Los Angeles, CA",
            "confirmed": True,
            "blurb": "Twenty-one urban oil wells sit under 1,000 ft from St. Vincent School, "
                     "with ~800 people within 600 ft in a ~80% Latino neighborhood. Decades "
                     "of fumes and illness; ordered permanently closed by CA's Dept. of "
                     "Conservation; well-abandonment underway (2025) — a textbook "
                     "1950s-topo → modern-satellite reveal.",
            "topo": {"year": "1953",
                     "label": "USGS historical topo · Hollywood quad (1953 ed.) → today"},
            "citations": [
                {"title": "US EPA: AllenCo oil-facility Clean Air Act violations (Jan 15 2014)",
                 "url": "https://www.epa.gov/archive/epapages/newsroom_archive/newsreleases/aed2e1e5c55d665f85257c610068b51b.html"},
                {"title": "US EPA: AllenCo to pay $99k penalty for violations (Jul 30 2014)",
                 "url": "https://www.epa.gov/archive/epapages/newsroom_archive/newsreleases/29a72b267d4b4f1285257d25006a2fc1.html"},
                {"title": "National Catholic Reporter: LA archdiocese & the fight to close toxic oil wells",
                 "url": "https://www.ncronline.org/news/landlord-la-archdiocese-little-help-neighborhoods-long-fight-close-toxic-oil-wells-good"},
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
