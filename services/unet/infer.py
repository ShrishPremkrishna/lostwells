"""Extend LBNL's CATALOG U-Net to find Undocumented Orphaned Wells (UOWs).

Documented, runnable inference pipeline (spec §1.7). It is intentionally NOT run
in the Lost Wells sandbox (no GPU, and we serve the LBNL pre-computed candidates
instead) — run it on a GPU host with the model + data from ``README.md``.

Method (Ciulla et al. 2024, DOI 10.1021/acs.est.4c04413):
  1. Read a georeferenced HTMC GeoTIFF (rasterio reads the embedded CRS/datum —
     HTMC maps are often NAD27; do NOT assume WGS84).
  2. Tile into 256x256 patches; run the U-Net; threshold the segmentation mask.
  3. Take the centroid of each detected well-symbol blob; convert pixel (row,col)
     -> map CRS via the affine transform; reproject to EPSG:4326.
  4. Dedup against documented wells (USGS DOW + state DBs): a detection >100 m
     from any documented well is a candidate UOW.

Validate on a known LBNL county (Kern, CA) FIRST and confirm you reproduce their
published detections before trusting new ground (the model was trained on the
1947-1992 1:24,000 series and degrades off that symbology).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

PATCH = 256
DEFAULT_THRESHOLD = 0.5
METRIC_CRS = "EPSG:5070"  # CONUS Albers (meters)
UOW_RADIUS_M = 100.0


def load_model(model_path: str):
    import tensorflow as tf
    # compile=False: we only need inference (matches the LBNL release).
    return tf.keras.models.load_model(model_path, compile=False)


def iter_patches(arr: np.ndarray, size: int = PATCH):
    """Yield (row0, col0, patch) over a HxWxC image, zero-padding the edges."""
    h, w = arr.shape[:2]
    for r0 in range(0, h, size):
        for c0 in range(0, w, size):
            patch = arr[r0:r0 + size, c0:c0 + size]
            ph, pw = patch.shape[:2]
            if (ph, pw) != (size, size):
                pad = np.zeros((size, size, arr.shape[2]), dtype=arr.dtype)
                pad[:ph, :pw] = patch
                patch = pad
            yield r0, c0, patch


def detect_in_geotiff(model, tif_path: str, threshold: float = DEFAULT_THRESHOLD):
    """Run the model over one GeoTIFF; return detected well centroids as lon/lat."""
    import rasterio
    from rasterio.transform import xy
    from scipy import ndimage

    with rasterio.open(tif_path) as src:
        img = np.dstack([src.read(b) for b in range(1, min(src.count, 3) + 1)]).astype("float32")
        img /= 255.0
        transform, src_crs = src.transform, src.crs

    detections_rc: list[tuple[float, float]] = []
    for r0, c0, patch in iter_patches(img):
        prob = model.predict(patch[None, ...], verbose=0)[0]
        mask = (prob[..., 0] if prob.ndim == 3 else prob) > threshold
        if not mask.any():
            continue
        labels, n = ndimage.label(mask)
        for cy, cx in ndimage.center_of_mass(mask, labels, range(1, n + 1)):
            detections_rc.append((r0 + cy, c0 + cx))

    # pixel (row,col) -> map CRS -> EPSG:4326 lon/lat
    from pyproj import Transformer
    to_wgs84 = Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)
    lonlat = []
    for row, col in detections_rc:
        x, y = xy(transform, row, col)
        lon, lat = to_wgs84.transform(x, y)
        lonlat.append((lon, lat))
    return lonlat


def filter_uows(detections_lonlat, documented_geojson: str, radius_m: float = UOW_RADIUS_M):
    """Keep detections >radius_m from any documented well (the LBNL UOW rule)."""
    import geopandas as gpd
    from shapely.geometry import Point

    det = gpd.GeoDataFrame(
        geometry=[Point(lon, lat) for lon, lat in detections_lonlat], crs="EPSG:4326"
    ).to_crs(METRIC_CRS)
    documented = gpd.read_file(documented_geojson).to_crs(METRIC_CRS)
    near = gpd.sjoin_nearest(det, documented[["geometry"]], how="left", distance_col="dist_m")
    near = near[~near.index.duplicated(keep="first")]
    uows = det[near["dist_m"] > radius_m].to_crs("EPSG:4326")
    return [(geom.x, geom.y) for geom in uows.geometry]


def main() -> None:
    ap = argparse.ArgumentParser(description="LBNL U-Net UOW detection (documented pipeline)")
    ap.add_argument("--model", required=True, help="path to unet_model.h5")
    ap.add_argument("--geotiff", required=True, help="georeferenced HTMC quad GeoTIFF")
    ap.add_argument("--documented", required=True, help="documented wells GeoJSON for dedup")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    ap.add_argument("--out", default="detections_uows.geojson")
    args = ap.parse_args()

    model = load_model(args.model)
    detections = detect_in_geotiff(model, args.geotiff, args.threshold)
    print(f"[unet] {len(detections)} symbol detections on {Path(args.geotiff).name}")
    uows = filter_uows(detections, args.documented)
    print(f"[unet] {len(uows)} are candidate UOWs (>{UOW_RADIUS_M:.0f} m from documented wells)")

    import json
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
         "properties": {"source": "u-net", "quad": Path(args.geotiff).stem}}
        for lon, lat in uows
    ]}
    Path(args.out).write_text(json.dumps(fc))
    print(f"[unet] wrote {args.out}")


if __name__ == "__main__":
    main()
