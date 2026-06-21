"""Config-driven state oil-&-gas registry ingester (§1.3).

State agencies publish the depth / type / status / operator that the federal
USGS DOW omits, plus orphan/abandoned wells the DOW never captured. This module
pulls those registries once, normalizes them into a single canonical schema, and
writes one GeoJSON intermediate per state for ``build_datastore.consolidate()``.

Design: one declarative ``REGISTRIES`` dict (per-state ``{mode, url, where,
fieldmap, ...}``) feeds two generic fetch paths:

  - ``fetch_rest``  : paginated ArcGIS ``/query`` (resultOffset/resultRecordCount)
  - ``fetch_bulk``  : streamed CSV / zipped shapefile read via geopandas

Raw pulls are cached to ``data/cache/registries.sqlite`` (one table per state)
so re-runs are instant. We filter on orphan/abandoned/idle/plugged status at the
source ``where`` to keep scale down and stay on-mission (active wells excluded).

Appalachia first (OH, WV, PA, NY, KY); the structure generalizes to the rest.

CLI:
    python services/ingest/state_registries.py --states OH,WV,PA,NY,KY
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
import requests
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import normalize as N  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "state_registries"
CACHE_DB = ROOT / "data" / "cache" / "registries.sqlite"

# Canonical normalized columns every state resolves to.
CANONICAL = ["api", "lat", "lon", "type", "status", "operator", "depth"]

# ---------------------------------------------------------------------------
# Per-state registry configuration.
#
# fieldmap maps SOURCE column name -> canonical key in CANONICAL.  For REST
# pulls the source columns are the ArcGIS attribute names; for bulk pulls they
# are the CSV/shapefile column names.  ``lat``/``lon`` are taken from geometry
# when absent from attributes (see ``_attach_lonlat``).
#
# ``where`` filters to orphan/abandoned/idle/plugged at the source so we never
# pull the full active-well universe.
# ---------------------------------------------------------------------------
REGISTRIES: dict[str, dict] = {
    "OH": {
        "mode": "rest",
        "url": ("https://gis.ohiodnr.gov/arcgis_site2/rest/services/"
                "OIL_GAS/Oil_And_Gas_Wells/FeatureServer/3/query"),
        # OH WELL_STATUS_DESCRIPTION vocab incl. Orphan/Plugged/Idle/Abandoned.
        "where": ("WELL_STATUS_DESCRIPTION IN "
                  "('Orphan','Plugged','Idle and Orphan','Abandoned',"
                  "'Idle','Temporarily Abandoned')"),
        "fieldmap": {
            "API_WELLNO": "api",
            "TOTAL_DEPTH": "depth",
            "WELL_STATUS_DESCRIPTION": "status",
            "WELL_TYPE": "type",
            "COMPANY_NAME": "operator",
        },
        # Bulk CSV fallback (ArcGIS Hub item) if the REST host throttles.
        "bulk_fallback": ("https://opendata.arcgis.com/api/v3/datasets/"
                          "e03ec46046af49c49d879ab9be07f980_3/downloads/data"
                          "?format=csv&spatialRefId=4326"),
    },
    "WV": {
        "mode": "rest",
        "url": ("https://tagis.dep.wv.gov/arcgis/rest/services/"
                "oil_gas/MapServer/7/query"),
        # WV layer 7 = wells; layer 4 = plugged wells (folded in via status).
        "where": "1=1",
        "fieldmap": {
            "API": "api",
            "WellDepth": "depth",
            "Status": "status",
            "WellType": "type",
            "Operator": "operator",
        },
    },
    "PA": {
        "mode": "rest",
        # PASDA item 1088: PA DEP oil & gas locations. Operator present, no depth.
        "url": ("https://mapservices.pasda.psu.edu/server/rest/services/"
                "pasda/DEP/MapServer/0/query"),
        "where": ("WELL_STATU IN ('Orphan','Abandoned','Plugged OG Well',"
                  "'DEP Plugged','Regulatory Inactive Status')"),
        "fieldmap": {
            "API": "api",
            "WELL_STATU": "status",
            "WELL_TYPE": "type",
            "OPERATOR": "operator",
            # no depth in PASDA 1088
        },
    },
    "NY": {
        "mode": "bulk",
        # NY DEC oil/gas wells, Socrata bulk JSON (full depth suite).
        "url": "https://data.ny.gov/resource/szye-wmt3.json?$limit=500000",
        "format": "json",
        "fieldmap": {
            "api_well_number": "api",
            "true_vertical_depth": "depth",
            "well_status": "status",
            "well_type": "type",
            "company_name": "operator",
            "surface_latitude": "lat",
            "surface_longitude": "lon",
        },
    },
    "KY": {
        "mode": "bulk",
        # KGS directional/deviated well data — zipped shapefile.
        "url": "https://kgs.uky.edu/ogdata/kyog_dd.zip",
        "format": "shp",
        # NAD27 caveat: KGS shapefiles are often NAD27; reproject on load.
        "src_crs": "EPSG:4267",
        "fieldmap": {
            "API_NUMBER": "api",
            "TOTAL_DEPT": "depth",
            "STATUS": "status",
            "WELL_TYPE": "type",
            "OPERATOR": "operator",
        },
    },
}

PAGE = 2000  # ArcGIS records-per-page


# --- HTTP session ---------------------------------------------------------
def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "lost-wells/1.0 (research)"
    return s


# --- REST: generic paginated ArcGIS /query --------------------------------
def fetch_rest(cfg: dict) -> pd.DataFrame:
    """Page an ArcGIS FeatureServer/MapServer ``/query`` until exhausted.

    Requests ``f=geojson`` first (clean lon/lat from geometry); falls back to
    ``f=json`` + ``features[].attributes`` + ``geometry.{x,y}`` when the host
    does not speak GeoJSON.
    """
    sess = _session()
    out_fields = ",".join(cfg["fieldmap"].keys())
    rows: list[dict] = []
    offset = 0
    pbar = tqdm(desc=f"  REST {cfg['url'].split('/services/')[-1][:24]}", unit="rec")
    while True:
        params = {
            "where": cfg.get("where", "1=1"),
            "outFields": out_fields,
            "returnGeometry": "true",
            "outSR": "4326",
            "resultOffset": offset,
            "resultRecordCount": PAGE,
            "f": "geojson",
        }
        try:
            r = sess.get(cfg["url"], params=params, timeout=120)
            r.raise_for_status()
            payload = r.json()
        except Exception:  # noqa: BLE001 — retry as esri json
            payload = None

        feats = (payload or {}).get("features") if payload else None
        is_geojson = bool(feats) and "properties" in (feats[0] if feats else {})

        if not feats:
            # Retry this page as esri json (some hosts ignore f=geojson).
            params["f"] = "json"
            r = sess.get(cfg["url"], params=params, timeout=120)
            r.raise_for_status()
            payload = r.json()
            feats = payload.get("features", [])
            is_geojson = False
            if not feats:
                break

        for ft in feats:
            if is_geojson:
                props = dict(ft.get("properties") or {})
                geom = ft.get("geometry") or {}
                coords = geom.get("coordinates") or [None, None]
                props["__lon"], props["__lat"] = coords[0], coords[1]
            else:
                props = dict(ft.get("attributes") or {})
                g = ft.get("geometry") or {}
                props["__lon"], props["__lat"] = g.get("x"), g.get("y")
            rows.append(props)

        got = len(feats)
        pbar.update(got)
        offset += got
        if got < PAGE:
            break
    pbar.close()
    return pd.DataFrame(rows)


# --- bulk: stream-download CSV / JSON / zipped shapefile ------------------
def _download(url: str) -> bytes:
    sess = _session()
    with sess.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        buf = io.BytesIO()
        with tqdm(total=total, unit="B", unit_scale=True, desc="  download") as bar:
            for chunk in r.iter_content(chunk_size=1 << 16):
                buf.write(chunk)
                bar.update(len(chunk))
        return buf.getvalue()


def fetch_bulk(cfg: dict) -> pd.DataFrame:
    """Download + read a bulk source (CSV / Socrata JSON / zipped shapefile).

    Reprojects geometry to EPSG:4326, honoring a per-state ``src_crs`` for the
    NAD27 datum sometimes used by KGS/older shapefiles.
    """
    fmt = cfg.get("format", "csv")
    raw = _download(cfg["url"])

    if fmt == "json":
        df = pd.DataFrame(json.loads(raw.decode("utf-8")))
        return df

    if fmt == "csv":
        df = pd.read_csv(io.BytesIO(raw), low_memory=False)
        return df

    if fmt == "shp":
        with tempfile.TemporaryDirectory() as td:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                zf.extractall(td)
            shp = next(Path(td).rglob("*.shp"))
            gdf = gpd.read_file(shp)
        src = cfg.get("src_crs")
        if src and (gdf.crs is None):
            gdf = gdf.set_crs(src, allow_override=True)
        if gdf.crs is not None and str(gdf.crs).upper() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        df = pd.DataFrame(gdf.drop(columns="geometry"))
        df["__lon"] = gdf.geometry.x.values
        df["__lat"] = gdf.geometry.y.values
        return df

    raise ValueError(f"unknown bulk format: {fmt}")


# --- raw cache (one table per state) -------------------------------------
def _open_cache() -> sqlite3.Connection:
    CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(CACHE_DB)


def _cache_table(st: str) -> str:
    return f"raw_{st.lower()}"


def _cache_load(con: sqlite3.Connection, st: str) -> Optional[pd.DataFrame]:
    tbl = _cache_table(st)
    have = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
    ).fetchone()
    if not have:
        return None
    return pd.read_sql(f"SELECT * FROM {tbl}", con)


def _cache_store(con: sqlite3.Connection, st: str, df: pd.DataFrame) -> None:
    df.to_sql(_cache_table(st), con, if_exists="replace", index=False)


# --- normalization -------------------------------------------------------
def _attach_lonlat(cfg: dict, df: pd.DataFrame) -> pd.DataFrame:
    """Resolve lon/lat from fieldmap columns or the geometry helpers."""
    fm = cfg["fieldmap"]
    # explicit lat/lon columns in the fieldmap take precedence
    lat_col = next((src for src, dst in fm.items() if dst == "lat"), None)
    lon_col = next((src for src, dst in fm.items() if dst == "lon"), None)
    if lat_col and lon_col and lat_col in df and lon_col in df:
        df["lat"] = pd.to_numeric(df[lat_col], errors="coerce")
        df["lon"] = pd.to_numeric(df[lon_col], errors="coerce")
    else:
        df["lat"] = pd.to_numeric(df.get("__lat"), errors="coerce")
        df["lon"] = pd.to_numeric(df.get("__lon"), errors="coerce")
    return df


def normalize_state(cfg: dict, raw_df: pd.DataFrame) -> pd.DataFrame:
    """Apply ``fieldmap`` + the normalize helpers -> canonical records."""
    fm = cfg["fieldmap"]
    df = raw_df.copy()
    df = _attach_lonlat(cfg, df)

    def col(dst: str):
        src = next((s for s, d in fm.items() if d == dst), None)
        return df[src] if (src and src in df) else pd.Series([None] * len(df))

    out = pd.DataFrame({
        "api": col("api").map(N.normalize_api),
        "lat": df["lat"],
        "lon": df["lon"],
        "type": col("type").map(N.classify_type),
        "status": col("status").map(N.classify_status),
        "operator": col("operator").map(N.normalize_operator),
        "depth": col("depth").map(N.normalize_depth),
    })
    out = out.dropna(subset=["lat", "lon"])
    # Keep only on-mission statuses (active wells excluded). Bulk sources that
    # could not be filtered at the source get filtered here.
    keep = {N.STATUS_ORPHAN, N.STATUS_ABANDONED, N.STATUS_PLUGGED, N.STATUS_IDLE}
    out = out[out["status"].isin(keep)]
    return out.reset_index(drop=True)


# --- per-state driver ----------------------------------------------------
def pull_state(st: str, con: sqlite3.Connection, refresh: bool = False) -> pd.DataFrame:
    cfg = REGISTRIES[st]
    raw = None if refresh else _cache_load(con, st)
    if raw is None:
        print(f"[{st}] fetching ({cfg['mode']}) ...")
        try:
            raw = fetch_rest(cfg) if cfg["mode"] == "rest" else fetch_bulk(cfg)
        except Exception as e:  # noqa: BLE001
            fb = cfg.get("bulk_fallback")
            if cfg["mode"] == "rest" and fb:
                print(f"[{st}] REST failed ({e}); trying bulk fallback ...")
                raw = fetch_bulk({**cfg, "mode": "bulk", "url": fb, "format": "csv"})
            else:
                raise
        _cache_store(con, st, raw)
        print(f"[{st}] cached {len(raw):,} raw rows")
    else:
        print(f"[{st}] {len(raw):,} raw rows from cache")

    norm = normalize_state(cfg, raw)
    print(f"[{st}] normalized -> {len(norm):,} on-mission wells "
          f"(depth={int(norm['depth'].notna().sum()):,}, "
          f"operator={int(norm['operator'].notna().sum()):,})")
    return norm


def write_state(st: str, norm: pd.DataFrame) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    gdf = gpd.GeoDataFrame(
        norm, geometry=gpd.points_from_xy(norm["lon"], norm["lat"]), crs="EPSG:4326"
    )
    path = RAW / f"{st}.geojson"
    gdf.to_file(path, driver="GeoJSON")
    print(f"[write] {path.relative_to(ROOT)}  ({len(gdf):,} wells)")
    return path


def run(states: list[str], refresh: bool = False) -> None:
    con = _open_cache()
    try:
        for st in states:
            if st not in REGISTRIES:
                print(f"[skip] no registry config for {st}")
                continue
            norm = pull_state(st, con, refresh=refresh)
            write_state(st, norm)
    finally:
        con.close()
    print("\n[done] state registries ->", RAW.relative_to(ROOT))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--states", default="OH,WV,PA,NY,KY",
                   help="comma-separated state abbreviations")
    p.add_argument("--refresh", action="store_true",
                   help="ignore the SQLite raw cache and re-pull")
    args = p.parse_args()
    states = [s.strip().upper() for s in args.states.split(",") if s.strip()]
    run(states, refresh=args.refresh)


if __name__ == "__main__":
    main()
