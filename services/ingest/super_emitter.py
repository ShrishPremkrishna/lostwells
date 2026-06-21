"""EPA Methane Super-Emitter spatial cross-reference (§2B).

The only per-well methane signal available for attribute-less undocumented
candidates is proximity to a measured EPA Super-Emitter Program event. This
module loads super-emitter events, joins them to wells (nearest within a radius)
and writes a ``well_id``-keyed sidecar consumed by ``score_candidates.py``.

Source (3-tier — handles ECHO access uncertainty):
  The ECHO Methane Super Emitter Data Explorer is an interactive map; a CSV
  export is manual and the programmatic web-service was only "planned mid-2025"
  (the program itself is in deregulatory delay). We therefore degrade gracefully:
    1. Try a backing ECHO REST / ArcGIS FeatureServer JSON endpoint (paged like
       ``enrich_tract.load_hospitals``).
    2. Fallback to a manual CSV at ``data/raw/super_emitter/events.csv`` with
       aliased columns (lat/latitude, lon/longitude, emission_rate/rate_kg_hr,
       operator, event_date).
    3. Absent -> return ``None``; flags stay null everywhere (never crashes).

Conventions mirror ``enrich_tract.py`` (geopandas, EPSG:5070, sjoin_nearest,
``--with-downloads`` gating, well_id-keyed JSON sidecar).

CLI:
    python services/ingest/super_emitter.py --input candidates.base.json \\
        [--output super_emitter.json] [--with-downloads]
    python services/ingest/super_emitter.py --input heroes.base.json \\
        --output heroes.super_emitter.json [--with-downloads]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw" / "super_emitter"
METRIC_CRS = "EPSG:5070"  # CONUS Albers (meters)

# Candidate backing endpoint for the ECHO super-emitter explorer. The explorer
# is an interactive map; if/when a stable FeatureServer is published the layer
# URL goes here. Discover at impl via the explorer's network calls. Any failure
# degrades to the manual CSV / None, so a wrong/absent URL never crashes.
ECHO_SUPER_EMITTER_FS = os.environ.get(
    "ECHO_SUPER_EMITTER_FS",
    "https://echo.epa.gov/system/rest/services/methane_super_emitter/"
    "FeatureServer/0/query",
)

MIN_RATE_KG_HR = 100.0  # super-emitter program floor
DEFAULT_RADIUS_M = 2000.0

# Column aliases for the manual-CSV fallback.
_LAT_ALIASES = ("lat", "latitude", "y")
_LON_ALIASES = ("lon", "longitude", "lng", "x")
_RATE_ALIASES = ("emission_rate", "rate_kg_hr", "emission_rate_kg_hr",
                 "rate", "ch4_kg_hr", "kg_hr")
_OPERATOR_ALIASES = ("operator", "company", "owner", "facility")
_DATE_ALIASES = ("event_date", "date", "detection_date", "observed")


def _first_alias(cols, aliases) -> Optional[str]:
    lower = {c.lower(): c for c in cols}
    for a in aliases:
        if a in lower:
            return lower[a]
    return None


def _normalize_frame(df: pd.DataFrame) -> Optional[gpd.GeoDataFrame]:
    """Normalize an arbitrary events frame to the canonical schema (4326)."""
    lat_c = _first_alias(df.columns, _LAT_ALIASES)
    lon_c = _first_alias(df.columns, _LON_ALIASES)
    if not lat_c or not lon_c:
        print("[super_emitter] events missing lat/lon columns; skipping")
        return None
    rate_c = _first_alias(df.columns, _RATE_ALIASES)
    op_c = _first_alias(df.columns, _OPERATOR_ALIASES)
    date_c = _first_alias(df.columns, _DATE_ALIASES)

    out = pd.DataFrame()
    out["lat"] = pd.to_numeric(df[lat_c], errors="coerce")
    out["lon"] = pd.to_numeric(df[lon_c], errors="coerce")
    out["emission_rate_kg_hr"] = (pd.to_numeric(df[rate_c], errors="coerce")
                                  if rate_c else pd.NA)
    out["operator"] = df[op_c].astype(str) if op_c else None
    out["event_date"] = df[date_c].astype(str) if date_c else None
    out = out.dropna(subset=["lat", "lon"])
    if out.empty:
        return None
    g = gpd.GeoDataFrame(
        out, geometry=gpd.points_from_xy(out["lon"], out["lat"]),
        crs="EPSG:4326",
    )
    # Filter to true super-emitters (>= 100 kg/hr) when a rate is present; keep
    # rateless rows (some exports omit the magnitude) rather than drop signal.
    rate = pd.to_numeric(g["emission_rate_kg_hr"], errors="coerce")
    g = g[rate.isna() | (rate >= MIN_RATE_KG_HR)]
    return g if not g.empty else None


def _load_fs(with_downloads: bool, bbox: Optional[tuple] = None
             ) -> Optional[gpd.GeoDataFrame]:
    """Tier 1: paged ArcGIS/REST FeatureServer JSON (best-effort)."""
    dest = RAW / "super_emitter_fs.geojson"
    if dest.exists() and dest.stat().st_size > 0:
        return _normalize_frame(pd.DataFrame(gpd.read_file(dest).assign(
            lon=lambda d: d.geometry.x, lat=lambda d: d.geometry.y)))
    if not with_downloads:
        return None
    params = {
        "where": "1=1", "outFields": "*", "outSR": "4326",
        "returnGeometry": "true", "f": "geojson", "resultRecordCount": 2000,
    }
    if bbox:
        params.update({
            "geometry": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
            "geometryType": "esriGeometryEnvelope", "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
        })
    feats: list = []
    offset = 0
    sess = requests.Session()
    try:
        while True:
            params["resultOffset"] = offset
            r = sess.get(ECHO_SUPER_EMITTER_FS, params=params, timeout=120)
            r.raise_for_status()
            page = r.json().get("features", [])
            feats.extend(page)
            if len(page) < params["resultRecordCount"]:
                break
            offset += len(page)
    except Exception as e:  # noqa: BLE001 — degrade, don't crash the pipeline
        print(f"[super_emitter] FeatureServer fetch failed ({e}); trying CSV")
        return None
    if not feats:
        return None
    g = gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326")
    df = pd.DataFrame(g.drop(columns="geometry"))
    df["lon"] = g.geometry.x
    df["lat"] = g.geometry.y
    norm = _normalize_frame(df)
    if norm is not None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        norm.to_file(dest, driver="GeoJSON")
    return norm


def _load_csv() -> Optional[gpd.GeoDataFrame]:
    """Tier 2: manual CSV export at data/raw/super_emitter/events.csv."""
    dest = RAW / "events.csv"
    if not dest.exists():
        return None
    try:
        df = pd.read_csv(dest, low_memory=False)
    except Exception as e:  # noqa: BLE001
        print(f"[super_emitter] CSV read failed: {e}")
        return None
    return _normalize_frame(df)


def load_events(with_downloads: bool = False, bbox: Optional[tuple] = None
                ) -> Optional[gpd.GeoDataFrame]:
    """Load super-emitter events (FeatureServer -> manual CSV -> None)."""
    g = _load_fs(with_downloads, bbox=bbox)
    if g is not None and not g.empty:
        print(f"[super_emitter] loaded {len(g):,} events (FeatureServer)")
        return g
    g = _load_csv()
    if g is not None and not g.empty:
        print(f"[super_emitter] loaded {len(g):,} events (manual CSV)")
        return g
    print("[super_emitter] no events available; flags stay null")
    return None


def match_wells(wells_m: gpd.GeoDataFrame, events_m: gpd.GeoDataFrame,
                radius_m: float = DEFAULT_RADIUS_M) -> dict:
    """well_id -> {super_emitter, super_emitter_dist_m, ..rate.., operator}.

    Nearest event within ``radius_m`` flags the well True; nearer-but-outside or
    no event leaves it False/None.
    """
    cols = ["geometry"]
    for c in ("emission_rate_kg_hr", "operator"):
        if c in events_m.columns:
            cols.append(c)
    near = gpd.sjoin_nearest(
        wells_m[["well_id", "geometry"]], events_m[cols],
        how="left", distance_col="d",
    )
    near = near[~near.index.duplicated(keep="first")]
    out: dict = {}
    for _, row in near.iterrows():
        wid = row["well_id"]
        d = row.get("d")
        within = d is not None and not pd.isna(d) and d <= radius_m
        rate = row.get("emission_rate_kg_hr")
        op = row.get("operator")
        out[wid] = {
            "super_emitter": bool(within),
            "super_emitter_dist_m": (round(float(d), 1)
                                     if d is not None and not pd.isna(d) else None),
            "super_emitter_rate_kg_hr": (round(float(rate), 1)
                                         if rate is not None and not pd.isna(rate)
                                         else None),
            "operator": (str(op) if op is not None and not pd.isna(op) else None),
        }
    return out


def run(input_file: str = "candidates.base.json",
        output_file: str = "super_emitter.json",
        with_downloads: bool = False, radius_m: float = DEFAULT_RADIUS_M
        ) -> None:
    records = json.loads((PROC / input_file).read_text())
    if isinstance(records, dict):
        raise SystemExit(f"{input_file} is not an array of well records")
    df = pd.DataFrame(records)
    if df.empty:
        print(f"[super_emitter] {input_file} is empty; nothing to match")
        (PROC / output_file).write_text(json.dumps({}))
        return
    print(f"[super_emitter] {len(df):,} wells <- {input_file}")

    bbox = (float(df["lon"].min()), float(df["lat"].min()),
            float(df["lon"].max()), float(df["lat"].max()))
    events = load_events(with_downloads, bbox=bbox)

    sidecar: dict = {}
    if events is not None and not events.empty:
        wells = gpd.GeoDataFrame(
            df[["well_id"]],
            geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326",
        ).to_crs(METRIC_CRS)
        events_m = events.to_crs(METRIC_CRS)
        sidecar = match_wells(wells, events_m, radius_m=radius_m)

    n_flag = sum(1 for v in sidecar.values() if v.get("super_emitter"))
    out = PROC / output_file
    out.write_text(json.dumps(sidecar, separators=(",", ":")))
    print(f"[super_emitter] wrote {out.relative_to(ROOT)} | "
          f"{n_flag}/{len(df)} wells flagged within {radius_m:.0f} m")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="candidates.base.json")
    p.add_argument("--output", default="super_emitter.json")
    p.add_argument("--radius-m", type=float, default=DEFAULT_RADIUS_M)
    p.add_argument("--with-downloads", action="store_true",
                   help="fetch super-emitter events from the ECHO FeatureServer")
    args = p.parse_args()
    run(args.input, args.output, args.with_downloads, args.radius_m)


if __name__ == "__main__":
    main()
