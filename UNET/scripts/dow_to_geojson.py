#!/usr/bin/env python3
"""Convert the committed USGS DOW datastore to GeoJSON points for UOW dedup.

``data/processed/wells.documented.json`` is stored columnar (count + legends +
parallel lon/lat/idx arrays, ~703 KB gzip for 117,672 wells). The inference dedup
step (``infer.py --documented``) wants a GeoJSON FeatureCollection. This is a
zero-dependency converter (stdlib only).

Usage:
    python dow_to_geojson.py \
        --in ../../data/processed/wells.documented.json \
        --out ../data/wells/dow_documented.geojson
    # filter to a few states (names from state_legend):
    python dow_to_geojson.py --states Pennsylvania Ohio "West Virginia" Kentucky
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IN = ROOT / "data" / "processed" / "wells.documented.json"


def convert(src: Path, dest: Path, states: list[str] | None) -> None:
    d = json.loads(src.read_text())
    leg = d["state_legend"]
    want = set(states) if states else None
    feats = []
    for i in range(d["count"]):
        if want is not None and leg[d["state_idx"][i]] not in want:
            continue
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [d["lon"][i], d["lat"][i]]},
            "properties": {"state": leg[d["state_idx"][i]], "source": "usgs_dow"},
        })
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(
        {"type": "FeatureCollection", "features": feats}, separators=(",", ":")))
    print(f"[dow] wrote {len(feats)} documented wells -> {dest}"
          + (f" (states={sorted(want)})" if want else " (all 27 states)"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="src", default=str(DEFAULT_IN))
    ap.add_argument("--out", default="../data/wells/dow_documented.geojson")
    ap.add_argument("--states", nargs="*", default=None,
                    help="optional state-name filter (e.g. Pennsylvania Ohio)")
    args = ap.parse_args()
    convert(Path(args.src), Path(args.out).resolve(), args.states)


if __name__ == "__main__":
    main()
