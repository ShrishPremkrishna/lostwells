#!/usr/bin/env python3
"""Merge nearby detections without discarding their original provenance."""
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
        # A longitude degree is shorter than a latitude degree away from the
        # equator. Search enough longitude cells to cover radius_m at this lat.
        lon_cells = max(1, math.ceil(1 / max(abs(math.cos(math.radians(lat))), 0.1)))
        for dx in range(-lon_cells, lon_cells + 1):
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
        source_records = []
        for feature in items:
            provenance = feature.get("_merge_provenance", {})
            original_feature = {k: v for k, v in feature.items()
                                if k != "_merge_provenance"}
            source_records.append({
                "input_file": provenance.get("input_file"),
                "collection_metadata": provenance.get("collection_metadata"),
                "feature": original_feature,
            })
        output.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                       "properties": {"source": "unet_catalog",
                                      "detection_count": len(items),
                                      "scan_ids": sorted({p.get("scan_id") for p in props
                                                          if p.get("scan_id")}),
                                      "states": sorted({p.get("state") for p in props if p.get("state")}),
                                      "quads": sorted({p.get("quad") for p in props if p.get("quad")}),
                                      "years": sorted({p.get("quad_year") for p in props if p.get("quad_year")}),
                                      "documented_distances_m": distances,
                                      "min_dist_to_documented_m": min(distances) if distances else None,
                                      "max_dist_to_documented_m": max(distances) if distances else None,
                                      "source_coordinates": [f["geometry"]["coordinates"]
                                                             for f in items],
                                      "source_files": sorted({
                                          f.get("_merge_provenance", {}).get("input_file")
                                          for f in items
                                          if f.get("_merge_provenance", {}).get("input_file")}),
                                      # Complete, unmodified source features plus
                                      # their input-file/collection provenance.
                                      "source_records": source_records}})
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
        collection = json.loads(path.read_text())
        collection_metadata = {k: v for k, v in collection.items() if k != "features"}
        for feature in collection.get("features", []):
            feature["_merge_provenance"] = {
                "input_file": str(path),
                "collection_metadata": collection_metadata,
            }
            features.append(feature)
    merged = merge(features, args.radius_m)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    tmp.write_text(json.dumps({"type": "FeatureCollection", "features": merged},
                              separators=(",", ":")))
    tmp.replace(out)
    print(f"[merge] {len(features)} detections from {len(files)} files -> {len(merged)} locations -> {out}")


if __name__ == "__main__":
    main()
