#!/usr/bin/env python3
"""Merge per-map GeoJSON outputs and collapse nearby duplicate detections."""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def distance_m(a, b):
    lat1, lon1 = map(math.radians, (a[1], a[0]))
    lat2, lon2 = map(math.radians, (b[1], b[0]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(h))


def merge(features, radius_m):
    # Greedy spatial hashing is sufficient here: duplicates arise at overlapping
    # map edges/editions and are normally only a few metres apart.
    cell = radius_m / 111_000
    buckets, clusters = defaultdict(list), []
    for feature in features:
        lon, lat = feature["geometry"]["coordinates"][:2]
        key = (math.floor(lon / cell), math.floor(lat / cell))
        match = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for ci in buckets[(key[0] + dx, key[1] + dy)]:
                    if distance_m((lon, lat), clusters[ci]["center"]) <= radius_m:
                        match = ci
                        break
                if match is not None:
                    break
            if match is not None:
                break
        if match is None:
            match = len(clusters)
            clusters.append({"center": (lon, lat), "items": []})
            buckets[key].append(match)
        cluster = clusters[match]
        cluster["items"].append(feature)
        coords = [f["geometry"]["coordinates"] for f in cluster["items"]]
        cluster["center"] = (sum(c[0] for c in coords) / len(coords),
                             sum(c[1] for c in coords) / len(coords))

    output = []
    for cluster in clusters:
        items, (lon, lat) = cluster["items"], cluster["center"]
        props = [f.get("properties", {}) for f in items]
        distances = [p.get("dist_to_documented_m") for p in props
                     if p.get("dist_to_documented_m") is not None]
        output.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                       "properties": {"source": "unet_catalog",
                                      "detection_count": len(items),
                                      "states": sorted({p.get("state") for p in props if p.get("state")}),
                                      "quads": sorted({p.get("quad") for p in props if p.get("quad")}),
                                      "years": sorted({p.get("quad_year") for p in props if p.get("quad_year")}),
                                      "min_dist_to_documented_m": min(distances) if distances else None}})
    return output


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inputs", nargs="+", required=True, help="files, directories, or glob patterns")
    ap.add_argument("--out", required=True)
    ap.add_argument("--radius-m", type=float, default=60)
    args = ap.parse_args()
    files = []
    for value in args.inputs:
        path = Path(value)
        files.extend(sorted(path.rglob("*_UOWs.geojson")) if path.is_dir() else [path])
    features = []
    for path in files:
        features.extend(json.loads(path.read_text()).get("features", []))
    merged = merge(features, args.radius_m)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"type": "FeatureCollection", "features": merged}, separators=(",", ":")))
    print(f"[merge] {len(features)} detections from {len(files)} files -> {len(merged)} locations -> {out}")


if __name__ == "__main__":
    main()
