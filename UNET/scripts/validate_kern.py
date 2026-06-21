#!/usr/bin/env python3
"""Validate the pipeline on Kern County, CA before trusting new ground.

Runs the pretrained model over Kern HTMC quads and checks that our candidate UOWs
reproduce LBNL's published `Kern_CA_UOWs.csv` (304 candidates). This is the
go/no-go gate from the handoff: if you can't reproduce Kern within a small
tolerance, fix the setup before running Appalachia.

Steps it performs:
  1. For each `*_geo.tif` in --quads (with a sibling `*_geo.xml` or manifest bbox),
     run the detector with the CalGEM documented-wells CSV.
  2. Aggregate candidate UOWs.
  3. Match each published Kern UOW to the nearest of ours; report how many match
     within --tol-m (default 60 m; LBNL detections are blob centroids, so exact
     equality isn't expected — tens of meters is a good reproduction).

Usage:
    python validate_kern.py \
        --quads ../data/maps/California \
        --model ../data/lbnl/unet_model.h5 \
        --documented ../data/lbnl/CalGEM_AllWells_20231128.csv \
        --published ../../data/raw/lbnl/found_potential_UOWs/Kern_CA_UOWs.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unet"))
from infer import (detect_quad, get_bbox_from_xml, haversine_km,  # noqa: E402
                   load_documented, load_unet)


def load_published(path: str) -> list[tuple[float, float]]:
    pts = []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            coord = row.get("Coordinates") or ""
            if "," in coord:
                lat, lon = coord.split(",")[:2]
                pts.append((float(lat), float(lon)))
    return pts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quads", required=True, help="dir of *_geo.tif (+ *_geo.xml)")
    ap.add_argument("--model", required=True)
    ap.add_argument("--documented", required=True, help="CalGEM CSV")
    ap.add_argument("--published", required=True, help="Kern_CA_UOWs.csv")
    ap.add_argument("--tol-m", type=float, default=60.0)
    ap.add_argument("--batch-size", type=int, default=16)
    args = ap.parse_args()

    model, preprocess = load_unet(args.model)
    doc_lat, doc_lon = load_documented(args.documented)

    ours: list[tuple[float, float]] = []
    covered_bboxes = []
    tifs = sorted(Path(args.quads).glob("*_geo.tif"))
    if not tifs:
        sys.exit(f"[kern] no *_geo.tif in {args.quads}")
    for tif in tifs:
        xml = tif.with_suffix(".xml")
        bbox = get_bbox_from_xml(str(xml)) if xml.exists() else None
        if bbox and all(v is not None for v in bbox):
            covered_bboxes.append(bbox)
        uows = detect_quad(str(tif), bbox, model, preprocess, doc_lat, doc_lon,
                           batch_size=args.batch_size)
        ours.extend((u["lat"], u["lon"]) for u in uows)
        print(f"[kern] {tif.name}: {len(uows)} candidate UOWs")

    pub = load_published(args.published)
    if covered_bboxes:
        pub = [(lat, lon) for lat, lon in pub if any(
            west <= lon <= east and south <= lat <= north
            for west, east, north, south in covered_bboxes)]
        print(f"[kern] scoring only the {len(pub)} published points covered by "
              f"the {len(covered_bboxes)} processed map bbox(es)")
    print(f"\n[kern] ours={len(ours)}  published={len(pub)}")
    if not pub:
        sys.exit("[kern] FAIL: no published validation points fall inside processed maps")
    if not ours:
        sys.exit("[kern] FAIL: no detections — check the env (model load/preprocess).")

    olat = np.array([p[0] for p in ours])
    olon = np.array([p[1] for p in ours])
    matched = 0
    for plat, plon in pub:
        d_km = haversine_km(plat, plon, olat, olon)
        if float(np.min(d_km)) * 1000.0 <= args.tol_m:
            matched += 1
    rate = matched / len(pub) if pub else 0.0
    print(f"[kern] {matched}/{len(pub)} published UOWs reproduced within "
          f"{args.tol_m:.0f} m  ({rate:.0%})")
    if rate >= 0.7:
        print("[kern] PASS — reproduction looks good; proceed to new ground.")
    else:
        print("[kern] LOW match rate — check resolution/preprocess/threshold before "
              "trusting Appalachia (see README §Validation).")


if __name__ == "__main__":
    main()
