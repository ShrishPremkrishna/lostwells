#!/usr/bin/env python3
"""Generate (image, mask) training tiles for FINE-TUNING (optional fallback).

IMPORTANT — read before using. LBNL did NOT generate labels this way. Per the
paper (Ciulla et al. 2024, PMC11656717) they **manually annotated** 11,046 well
symbols in Labelme (~40 h) and stamped r=4px discs (area≈49px) at each clicked
center. This script instead AUTO-LABELS from a documented-well database, which is
a pragmatic approximation with two real limitations you must accept:
  * The very UOWs you want to find are, by definition, NOT in the database, so
    they appear on the map but get NO label (trained as background) — this caps
    achievable recall.
  * Wells drilled AFTER the map's date are in the DB but not on the map; we
    exclude them with a temporal filter (well date <= map year), but the filter
    is only as good as the DB's date column.
So: inference with the pretrained model (infer.py) is the recommended path;
fine-tune only if Appalachian accuracy is poor, ideally with some manual
Labelme annotation. This script gives a runnable starting point.

Method (matches the released checkpoint's scale):
  * Reproject each documented well's lon/lat -> the GeoTIFF CRS -> pixel (the
    inverse-affine path from predict.ipynb; honors NAD27, whose ~20-40 m eastern-US
    datum shift exceeds the disc radius, so reprojection is mandatory).
  * Stamp a solid disc, radius --disk-radius (default 4 px), into the mask.
    HTMC 1:24k GeoTIFFs are ~2 m/px natively, matching the paper's training scale,
    so r=4px ≈ the paper's disc. (If a quad is much finer than ~2 m/px, raise the
    radius or downsample.)
  * Crop the collar, tile 256x256 with 25px overlap (as in inference), keep all
    tiles containing >=1 labeled pixel plus a sampled fraction of empty tiles
    (--neg-ratio) to control the severe class imbalance.

Usage:
    python make_labels.py \
        --maps ../data/maps/Ohio \
        --wells ../data/wells/OH.geojson --date-field COMPLETIONDATE \
        --out ../data/patches/OH
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unet"))
from infer import (coord2latlon, get_bbox_from_xml, get_coordinate_transforms,  # noqa: E402
                   load_documented, pixel2coord)

SIZE, OVERLAP = 256, 25


def _well_year(props: dict, field: str | None) -> int | None:
    if not field:
        return None
    v = props.get(field)
    if v is None:
        return None
    m = re.search(r"(18|19|20)\d{2}", str(v))
    return int(m.group(0)) if m else None


def load_wells_with_dates(path: str, date_field: str | None):
    """Return (lats, lons, years). Years are None where unparseable."""
    import json
    fc = json.loads(Path(path).read_text())
    lats, lons, years = [], [], []
    for f in fc.get("features", []):
        g = f.get("geometry") or {}
        if g.get("type") != "Point":
            continue
        lon, lat = g["coordinates"][:2]
        lats.append(float(lat))
        lons.append(float(lon))
        years.append(_well_year(f.get("properties", {}), date_field))
    return np.array(lats), np.array(lons), np.array([y or 0 for y in years])


def stamp_discs(mask, pixels, radius):
    import cv2
    for (px, py) in pixels:
        cv2.circle(mask, (int(px), int(py)), int(radius), 1, -1)
    return mask


def process_quad(tif, xml, wlat, wlon, wyear, map_year, radius, neg_ratio, out_dir):
    import cv2
    from osgeo import gdal

    ds = gdal.Open(str(tif))
    transform, transform_inv = get_coordinate_transforms(ds)
    img_full = cv2.cvtColor(cv2.imread(str(tif)), cv2.COLOR_BGR2RGB)

    bbox = get_bbox_from_xml(str(xml)) if xml and Path(xml).exists() else None
    if bbox is not None:
        west, east, north, south = bbox
        cc = [(north, west), (south, west), (north, east), (south, east)]
        cp = pixel2coord(coord2latlon(cc, transform_inv), ds, reverse=True)
        sl = [max(cp[0][0], cp[2][0]), min(cp[1][0], cp[3][0]),
              max(cp[0][1], cp[1][1]), min(cp[2][1], cp[3][1])]
    else:
        sl = [0, img_full.shape[0], 0, img_full.shape[1]]
        west = east = north = south = None
    image = img_full[sl[0]:sl[1], sl[2]:sl[3], :]

    # temporal + spatial filter of documented wells for THIS quad
    keep = wyear <= map_year if map_year else np.ones(len(wlat), bool)
    if west is not None:
        keep &= ((wlat >= south - 0.002) & (wlat <= north + 0.002)
                 & (wlon >= west - 0.002) & (wlon <= east + 0.002))
    qlat, qlon = wlat[keep], wlon[keep]

    mask = np.zeros(image.shape[:2], dtype=np.uint8)
    if len(qlat):
        px = np.array(pixel2coord(coord2latlon(list(zip(qlat, qlon)), transform_inv),
                                  ds, reverse=True))
        # px rows are (row,col); subtract collar offset; stamp as (x=col, y=row)
        pts = [(c - sl[2], r - sl[0]) for (r, c) in px]
        pts = [(x, y) for (x, y) in pts if 0 <= x < image.shape[1] and 0 <= y < image.shape[0]]
        stamp_discs(mask, pts, radius)

    out_dir.mkdir(parents=True, exist_ok=True)
    n_pos = n_neg = 0
    rng = np.random.default_rng(0)
    for i in range(0, image.shape[0] + OVERLAP, SIZE):
        ii = i - OVERLAP if i else 0
        for j in range(0, image.shape[1] + OVERLAP, SIZE):
            jj = j - OVERLAP if j else 0
            im = image[ii:ii + SIZE, jj:jj + SIZE]
            mk = mask[ii:ii + SIZE, jj:jj + SIZE]
            if im.shape[:2] != (SIZE, SIZE):
                im = np.pad(im, ((0, SIZE - im.shape[0]), (0, SIZE - im.shape[1]), (0, 0)),
                            constant_values=255)
                mk = np.pad(mk, ((0, SIZE - mk.shape[0]), (0, SIZE - mk.shape[1])))
            has_well = mk.any()
            if not has_well and rng.random() > neg_ratio:
                continue
            stem = f"{tif.stem}_{ii}_{jj}"
            np.savez_compressed(out_dir / f"{stem}.npz", image=im, mask=mk,
                                quad=tif.stem)
            n_pos += int(has_well)
            n_neg += int(not has_well)
    print(f"[labels] {tif.name}: {n_pos} positive + {n_neg} negative tiles "
          f"({len(qlat)} wells <= {map_year})")
    return n_pos, n_neg


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--maps", required=True, help="dir of *_geo.tif (+ *_geo.xml)")
    ap.add_argument("--wells", required=True, help="documented-wells GeoJSON")
    ap.add_argument("--date-field", default=None,
                    help="property holding the well's drill/permit/completion date "
                         "(e.g. OH=COMPLETIONDATE/PERMITDATE; verify per state)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--disk-radius", type=int, default=4)
    ap.add_argument("--neg-ratio", type=float, default=0.1,
                    help="fraction of empty tiles to keep (default 0.1)")
    args = ap.parse_args()

    wlat, wlon, wyear = load_wells_with_dates(args.wells, args.date_field)
    print(f"[labels] {len(wlat)} documented wells "
          + (f"with dates ({(wyear>0).sum()} parsed)" if args.date_field else "(no date filter)"))

    out = Path(args.out).resolve()
    tot_p = tot_n = 0
    for tif in sorted(Path(args.maps).glob("*_geo.tif")):
        ym = re.search(r"_(\d{4})_\d+_geo", tif.name)
        map_year = int(ym.group(1)) if ym else 0
        xml = tif.with_suffix(".xml")
        p, n = process_quad(tif, xml, wlat, wlon, wyear, map_year,
                            args.disk_radius, args.neg_ratio, out)
        tot_p += p
        tot_n += n
    print(f"[labels] TOTAL {tot_p} positive + {tot_n} negative tiles -> {out}")


if __name__ == "__main__":
    main()
