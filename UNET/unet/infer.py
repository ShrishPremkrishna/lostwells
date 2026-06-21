#!/usr/bin/env python3
"""Run LBNL's pretrained CATALOG U-Net on a topo quad to find candidate UOWs.

This is a faithful re-implementation of LBNL's own `predict.ipynb`
(`find_UOWs_in_topomap`), verified against their released code. It reproduces
their method EXACTLY — the earlier `services/unet/infer.py` in this repo was a
sketch that got several things wrong (it normalized /255 and tiled naively); this
is the correct pipeline. Differences that matter:

  * Model is a **segmentation_models U-Net, backbone resnet34**, loaded with
    `keras.models.load_model(..., compile=False)` AFTER importing
    segmentation_models. Input is preprocessed with **`sm.get_preprocessing(
    'resnet34')`** (ImageNet/caffe-style) — NOT /255.
  * Tiling is 256x256 with a **25-pixel overlap** (not disjoint tiles).
  * Detected blobs are aggregated with `cv2.connectedComponentsWithStats` and
    filtered to **area >= 45 px**.
  * The map **collar/margin is cropped** using the FGDC XML bbox before tiling,
    so legend/neatline text doesn't produce false detections.
  * Pixel<->coord uses the GeoTIFF's GDAL GeoTransform + an osr transform to
    WGS84 (HTMC maps are often NAD27 — the embedded CRS is honored, never
    assumed WGS84).
  * A detection is a candidate **UOW** if it is **> 100 m (haversine)** from any
    documented well in the quad.

Run on a host with the LBNL stack (see ../README.md): TF 2.8 + segmentation-
models 1.0.1 + GDAL + opencv. The pretrained `unet_model.h5` comes from EDX
(see scripts/get_model.py).

Usage:
    python infer.py \
        --tif        CA_OilCenter_293661_1954_24000_geo.tif \
        --xml        CA_OilCenter_293661_1954_24000_geo.xml \
        --model      unet_model.h5 \
        --documented documented_wells.geojson \
        --out-dir    ../outputs

`--documented` accepts a GeoJSON of points (from scripts/download_wells.py or
dow_to_geojson.py) OR a CSV with Latitude/Longitude columns (LBNL's CalGEM form).
The map date for temporal context is parsed from the filename `..._YYYY_24000_...`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

# segmentation_models selects its framework AT IMPORT TIME (default 'keras').
# Force tf.keras BEFORE importing it, or loading the resnet34 .h5 fails.
os.environ.setdefault("SM_FRAMEWORK", "tf.keras")

SIZE = 256            # tile size (LBNL)
OVERLAP = 25          # tile overlap in px (LBNL)
PROB_THRESHOLD = 0.5  # sigmoid threshold (LBNL)
MIN_AREA = 45         # min connected-component area in px (LBNL "mask area")
UOW_KM = 0.1          # 100 m dedup radius (LBNL is_UOW = min_dist > 0.1 km)
BACKBONE = "resnet34"


# --- georeferencing helpers (ported verbatim from predict.ipynb) --------------
def haversine_km(s_lat, s_lng, e_lat, e_lng):
    R = 6373.0
    s_lat = s_lat * np.pi / 180.0
    s_lng = np.deg2rad(s_lng)
    e_lat = np.deg2rad(e_lat)
    e_lng = np.deg2rad(e_lng)
    d = (np.sin((e_lat - s_lat) / 2) ** 2
         + np.cos(s_lat) * np.cos(e_lat) * np.sin((e_lng - s_lng) / 2) ** 2)
    return 2 * R * np.arcsin(np.sqrt(d))


def get_coordinate_transforms(ds):
    from osgeo import osr
    old_cs = osr.SpatialReference()
    old_cs.ImportFromWkt(ds.GetProjectionRef())
    wgs84_wkt = """
    GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,
    AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,
    AUTHORITY["EPSG","8901"]],UNIT["degree",0.01745329251994328,
    AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]"""
    new_cs = osr.SpatialReference()
    new_cs.ImportFromWkt(wgs84_wkt)
    return (osr.CoordinateTransformation(old_cs, new_cs),
            osr.CoordinateTransformation(new_cs, old_cs))


def pixel2coord(pixels, ds, reverse=False):
    """pixel (x,y) -> map coord (forward); or map coord -> pixel (reverse)."""
    xoff, a, b, yoff, d, e = ds.GetGeoTransform()
    out = []
    if not reverse:
        for xp, yp in pixels:
            out.append((a * xp + b * yp + xoff, d * xp + e * yp + yoff))
    else:
        D = a * e - b * d
        for xp, yp in pixels:
            x = (1.0 / D) * (e * (xp - xoff) - b * (yp - yoff))
            y = (1.0 / D) * (-d * (xp - xoff) + a * (yp - yoff))
            out.append((int(np.round(y)), int(np.round(x))))
    return out


def coord2latlon(coords, transform):
    out = []
    for x, y in coords:
        lat, lon, _ = transform.TransformPoint(x, y)
        out.append((lat, lon))
    return out


def get_bbox_from_xml(xml_path: str):
    """Read the neatline bbox from the FGDC metadata sidecar."""
    tree = ET.parse(xml_path)

    def one(tag):
        els = tree.findall(f".//{tag}")
        return float(els[0].text) if els else None

    return one("westbc"), one("eastbc"), one("northbc"), one("southbc")


# --- documented wells ---------------------------------------------------------
def load_documented(path: str):
    """Return arrays of (lat, lon) for documented wells. CSV or GeoJSON."""
    p = Path(path)
    lats, lons = [], []
    if p.suffix.lower() in (".geojson", ".json"):
        fc = json.loads(p.read_text())
        for f in fc.get("features", []):
            g = f.get("geometry") or {}
            if g.get("type") == "Point":
                lon, lat = g["coordinates"][:2]
                lats.append(float(lat))
                lons.append(float(lon))
    else:  # CSV (LBNL CalGEM form: Latitude/Longitude columns)
        import pandas as pd
        df = pd.read_csv(path, encoding="utf-8", encoding_errors="replace")
        latcol = next(c for c in df.columns if c.lower() in ("latitude", "lat"))
        loncol = next(c for c in df.columns if c.lower() in ("longitude", "lon", "long"))
        lats = df[latcol].astype(float).tolist()
        lons = df[loncol].astype(float).tolist()
    return np.array(lats), np.array(lons)


# --- model --------------------------------------------------------------------
def load_unet(model_path: str):
    import segmentation_models as sm
    sm.set_framework("tf.keras")
    from tensorflow import keras
    model = keras.models.load_model(model_path, compile=False)
    preprocess = sm.get_preprocessing(BACKBONE)
    return model, preprocess


# --- core detection (ported from find_UOWs_in_topomap) ------------------------
def detect_quad(tif_path: str, bbox, model, preprocess,
                doc_lat: np.ndarray, doc_lon: np.ndarray,
                batch_size: int = 16):
    """bbox = (west, east, north, south) in lon/lat, or None to skip collar crop."""
    import cv2
    from osgeo import gdal

    ds = gdal.Open(tif_path)
    transform, transform_inv = get_coordinate_transforms(ds)
    image_full = cv2.cvtColor(cv2.imread(tif_path), cv2.COLOR_BGR2RGB)

    if bbox is not None:
        westbc, eastbc, northbc, southbc = bbox
        # Crop the collar: map the 4 neatline corners (lat/lon) -> pixels.
        collar_coords = [(northbc, westbc), (southbc, westbc),
                         (northbc, eastbc), (southbc, eastbc)]
        cp = pixel2coord(coord2latlon(collar_coords, transform_inv), ds, reverse=True)
        sl = [max(cp[0][0], cp[2][0]), min(cp[1][0], cp[3][0]),
              max(cp[0][1], cp[1][1]), min(cp[2][1], cp[3][1])]  # r0,r1,c0,c1
    else:  # no bbox -> process the whole raster (collar may add false positives)
        print("[infer] WARNING: no bbox (XML/--bbox) -> NOT cropping the map collar; "
              "expect extra false detections in the margin/legend.")
        sl = [0, image_full.shape[0], 0, image_full.shape[1]]
        westbc = eastbc = northbc = southbc = None
    image = image_full[sl[0]:sl[1], sl[2]:sl[3], :]

    # Documented wells inside this quad (small buffer), for dedup. If no bbox was
    # given, derive the raster's lat/lon extent from its corner pixels.
    if westbc is None:
        h, w = image_full.shape[:2]
        corners = coord2latlon(pixel2coord([(0, 0), (w, 0), (0, h), (w, h)], ds),
                               transform)
        clat = [c[0] for c in corners]
        clon = [c[1] for c in corners]
        westbc, eastbc, northbc, southbc = min(clon), max(clon), max(clat), min(clat)
    in_map = ((doc_lat >= southbc - 0.002) & (doc_lat <= northbc + 0.002)
              & (doc_lon >= westbc - 0.002) & (doc_lon <= eastbc + 0.002))
    wells_lat, wells_lon = doc_lat[in_map], doc_lon[in_map]

    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    # Tile 256x256 with 25px overlap; pad short edges with white (255). Predict
    # incrementally instead of materializing every float32 tile for a full quad.
    # A typical quad can otherwise require >1 GB of transient RAM in Colab.
    tile_batch, offset_batch = [], []
    mask = np.zeros(image.shape[:2], dtype=np.uint8)

    def predict_batch():
        if not tile_batch:
            return
        pred = model.predict(preprocess(np.asarray(tile_batch)), verbose=0)
        for k, (oi, oj) in enumerate(offset_batch):
            xs, ys = (pred[k][:, :, 0] > PROB_THRESHOLD).nonzero()
            xs, ys = xs + oi, ys + oj
            ok = (xs < mask.shape[0]) & (ys < mask.shape[1])
            mask[xs[ok], ys[ok]] = 1
        tile_batch.clear()
        offset_batch.clear()

    for i in range(0, image.shape[0] + OVERLAP, SIZE):
        ii = i - OVERLAP if i != 0 else 0
        for j in range(0, image.shape[1] + OVERLAP, SIZE):
            jj = j - OVERLAP if j != 0 else 0
            inset = image[ii:ii + SIZE, jj:jj + SIZE, :]
            if inset.shape[0] < SIZE:
                inset = np.concatenate(
                    [inset, 255 * np.ones((SIZE - inset.shape[0], inset.shape[1], 3),
                                          dtype=np.uint8)], axis=0)
            if inset.shape[1] < SIZE:
                inset = np.concatenate(
                    [inset, 255 * np.ones((inset.shape[0], SIZE - inset.shape[1], 3),
                                          dtype=np.uint8)], axis=1)
            tile_batch.append(inset)
            offset_batch.append((ii, jj))
            if len(tile_batch) >= batch_size:
                predict_batch()
    predict_batch()

    n, _, stats, centroids = cv2.connectedComponentsWithStats(mask, 4, cv2.CV_32S)
    detected = []
    for blob in range(1, n):
        if stats[blob, cv2.CC_STAT_AREA] >= MIN_AREA:
            cy, cx = centroids[blob]
            detected.append([int(round(cx + sl[0])), int(round(cy + sl[2]))])  # +collar offset
    if not detected:
        return []
    detected = np.array(detected)

    # Detected pixel -> lat/lon (note row/col swap, as in predict.ipynb).
    det_latlon = coord2latlon(pixel2coord(detected[:, ::-1], ds, reverse=False), transform)

    # UOW test: > 100 m from every documented well in the quad.
    out = []
    for (lat, lon) in det_latlon:
        if len(wells_lat) == 0:
            mind, is_uow = None, True
        else:
            mind = float(np.min(haversine_km(lat, lon, wells_lat, wells_lon)))
            is_uow = mind > UOW_KM
        if is_uow:
            out.append({"lat": lat, "lon": lon,
                        "dist_to_documented_m": None if mind is None else int(round(1000 * mind))})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tif", required=True, help="georeferenced HTMC GeoTIFF")
    ap.add_argument("--xml", default=None, help="FGDC metadata sidecar (.xml); "
                    "if absent, --bbox is used, else the collar is not cropped")
    ap.add_argument("--bbox", nargs=4, type=float, default=None,
                    metavar=("WEST", "EAST", "NORTH", "SOUTH"),
                    help="neatline bbox in lon/lat (from the download manifest)")
    ap.add_argument("--model", required=True, help="path to unet_model.h5")
    ap.add_argument("--documented", required=True,
                    help="documented wells GeoJSON or CSV (for dedup)")
    ap.add_argument("--out-dir", default="../outputs")
    ap.add_argument("--batch-size", type=int, default=16,
                    help="tiles per prediction batch (default: 16; lower if GPU RAM is tight)")
    args = ap.parse_args()

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Resolve the neatline bbox: explicit --bbox wins, else parse the XML, else None.
    bbox = None
    if args.bbox:
        bbox = tuple(args.bbox)
    elif args.xml and Path(args.xml).exists():
        try:
            bbox = get_bbox_from_xml(args.xml)
        except Exception as e:  # noqa: BLE001
            print(f"[infer] could not parse bbox from {args.xml} ({e}); continuing")

    model, preprocess = load_unet(args.model)
    doc_lat, doc_lon = load_documented(args.documented)
    print(f"[infer] {len(doc_lat)} documented wells loaded for dedup")

    year_m = re.search(r"_(\d{4})_\d+_geo", Path(args.tif).name)
    quad_year = year_m.group(1) if year_m else None

    uows = detect_quad(args.tif, bbox, model, preprocess, doc_lat, doc_lon,
                       batch_size=args.batch_size)
    print(f"[infer] {len(uows)} candidate UOWs (>100 m from documented) "
          f"on {Path(args.tif).name}")

    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": [u["lon"], u["lat"]]},
         "properties": {"source": "unet_catalog", "quad": Path(args.tif).stem,
                        "quad_year": quad_year,
                        "dist_to_documented_m": u["dist_to_documented_m"]}}
        for u in uows]}
    out = out_dir / (Path(args.tif).stem + "_UOWs.geojson")
    out.write_text(json.dumps(fc))
    print(f"[infer] wrote {out}")


if __name__ == "__main__":
    main()
