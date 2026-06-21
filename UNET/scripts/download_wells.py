#!/usr/bin/env python3
"""Download documented oil/gas wells for the Appalachian states.

Two uses in this project:
  1. **Dedup (inference path, required):** a U-Net symbol detection that is
     >100 m from *any* documented well is a candidate Undocumented Orphaned Well
     (UOW). We need the documented-well universe to make that call. State
     registries (ALL wells, not just orphaned) are better for dedup than the USGS
     DOW (orphaned-only) because a detection next to a documented *active* well is
     not a discovery.
  2. **Labels (fine-tune path, optional):** wells whose drill/permit date is on or
     before a quad's publication year are positives for that quad's training mask
     (see ``make_labels.py``). We pull every field (``outFields=*``) so the
     date/status/type columns are available downstream.

Sources (all FREE, no key; endpoints reachability-probed 2026-06-20). Each state's
master layer carries API#, lat/lon, type, status, operator; depth where noted.
Output: one GeoJSON FeatureCollection per state in ``--out`` (EPSG:4326).
Bulk shapefiles are converted automatically so every output can be passed to
``infer.py`` and ``run_batch.py`` without a manual format-conversion step.

Usage:
    python download_wells.py --states OH WV KY --out ../data/wells
    python download_wells.py --states OH --limit 5000 --out ../data/wells   # test
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import zipfile
from pathlib import Path

import requests

# --- per-state source registry -------------------------------------------------
# kind="arcgis": paginated ArcGIS REST /query (f=geojson). kind="shapefile_zip":
# a bulk shapefile we save as-is (read later with geopandas in make_labels.py).
# Notes capture the verified date/status/depth fields for the fine-tune step.
SOURCES: dict[str, dict] = {
    "OH": {
        "kind": "arcgis",
        # ODNR DOGRM statewide (RBDMS-sourced), ~242,145 wells.
        "url": "https://services5.arcgis.com/ajRlmtxbNBjZggOT/arcgis/rest/services/Oil_And_Gas_Wells/FeatureServer/3/query",
        "page": 2000,
        "notes": "fields: API_NO, LAT83/LONG83, WELL_TYP, WELL_STATUS_DESCRIPTION, "
                 "OPERATOR, TOTAL_DEPTH; date fields incl. permit/spud/completion.",
    },
    "WV": {
        "kind": "arcgis",
        # WVDEP TAGIS 'All DEP Wells' (layer 7), ~153,842 wells.
        "url": "https://tagis.dep.wv.gov/arcgis/rest/services/WVDEP_enterprise/oil_gas/MapServer/7/query",
        "page": 1000,
        "notes": "fields: api, WellX/WellY, WellType, WellStatus, RespParty, WellDepth.",
    },
    "KY": {
        "kind": "shapefile_zip",
        # Kentucky Geological Survey statewide shapefile, ~162,132 wells (weekly).
        "url": "https://kgs.uky.edu/ogdata/kyog_dd.zip",
        "notes": "shapefile; read with geopandas. Status field present; verify "
                 "date column via kyog_info.txt.",
    },
    # PA and NY use different mechanisms; configured but verify before relying on
    # them for labels (PA via PASDA bulk; NY via Socrata). For DEDUP the USGS DOW
    # (already in data/processed/wells.documented.json) plus OH/WV/KY is a strong
    # Appalachian baseline.
    "PA": {
        "kind": "shapefile_zip",
        # PASDA 1088 'Oil & Gas Locations' (live registry incl. orphan/abandoned).
        # Filename is date-versioned; if this 404s, open the DataSummary page
        # https://www.pasda.psu.edu/uci/DataSummary.aspx?dataset=1088 for the
        # current link. OPERATOR present; PA layers lack a depth attribute.
        "url": "https://www.pasda.psu.edu/download/dep/OilGasLocations_ConventionalUnconventional2026_06.zip",
        "notes": "PASDA bulk shapefile; date-versioned filename may drift monthly.",
    },
    "NY": {
        "kind": "socrata",
        # data.ny.gov 'Oil, Gas & Other Regulated Wells: Beginning 1860' (szye-wmt3).
        "url": "https://data.ny.gov/resource/szye-wmt3.geojson",
        "page": 50000,
        "notes": "Socrata SODA; full depth suite + surface lat/long; $limit/$offset.",
    },
}

APPALACHIA_DEFAULT = ["OH", "WV", "KY", "PA"]


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "lost-wells-unet/1.0 (research; documented-wells fetch)"
    return s


# --- ArcGIS REST paginator -----------------------------------------------------
def fetch_arcgis(url: str, page: int, sess: requests.Session,
                 limit: int | None = None) -> list[dict]:
    """Page an ArcGIS FeatureServer/MapServer /query as GeoJSON features."""
    feats: list[dict] = []
    offset = 0
    while True:
        params = {
            "where": "1=1", "outFields": "*", "f": "geojson",
            "outSR": "4326", "resultOffset": offset, "resultRecordCount": page,
            "returnGeometry": "true",
        }
        for attempt in range(4):
            try:
                r = sess.get(url, params=params, timeout=120)
                r.raise_for_status()
                data = r.json()
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        batch = data.get("features", [])
        if not batch:
            break
        feats.extend(batch)
        print(f"    fetched {len(feats)} ...", end="\r", flush=True)
        if limit and len(feats) >= limit:
            feats = feats[:limit]
            break
        if len(batch) < page:  # last page
            break
        offset += page
    print()
    return feats


def fetch_socrata(url: str, page: int, sess: requests.Session,
                  limit: int | None = None) -> list[dict]:
    """Page a Socrata .geojson endpoint via $limit/$offset."""
    feats: list[dict] = []
    offset = 0
    while True:
        params = {"$limit": page, "$offset": offset}
        r = sess.get(url, params=params, timeout=120)
        r.raise_for_status()
        batch = r.json().get("features", [])
        if not batch:
            break
        feats.extend(batch)
        print(f"    fetched {len(feats)} ...", end="\r", flush=True)
        if limit and len(feats) >= limit:
            feats = feats[:limit]
            break
        if len(batch) < page:
            break
        offset += page
    print()
    return feats


def save_geojson(feats: list[dict], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fc = {"type": "FeatureCollection", "features": feats}
    dest.write_text(json.dumps(fc, separators=(",", ":")))
    print(f"[wells] wrote {len(feats)} features -> {dest}")


def fetch_shapefile_zip(url: str, out_dir: Path, state: str,
                        sess: requests.Session) -> Path | None:
    """Download a bulk shapefile ZIP and convert its points to EPSG:4326 GeoJSON."""
    dest_dir = out_dir / f"{state}_shapefile"
    geojson = out_dir / f"{state}.geojson"
    if geojson.exists() and geojson.stat().st_size > 0:
        print(f"[wells] {state}: skip (exists) -> {geojson}")
        return geojson
    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"[wells] {state}: downloading shapefile {url}")
    try:
        r = sess.get(url, timeout=600)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        print(f"[wells]   ERROR {state}: {e}\n"
              f"[wells]   (filename may be date-versioned or host down — see SOURCES notes)")
        return None
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        zf.extractall(dest_dir)
    shp = next((p for p in dest_dir.rglob("*.shp")), None)
    print(f"[wells] {state}: extracted -> {dest_dir}"
          + (f" (shapefile: {shp.name})" if shp else " (no .shp found — inspect)"))
    if shp is None:
        return None

    import geopandas as gpd
    gdf = gpd.read_file(shp)
    if gdf.crs is None:
        raise RuntimeError(f"{shp} has no CRS; refusing to guess coordinates")
    gdf = gdf[gdf.geometry.notna() & (gdf.geometry.geom_type == "Point")].copy()
    gdf = gdf.to_crs("EPSG:4326")
    gdf.to_file(geojson, driver="GeoJSON")
    print(f"[wells] {state}: converted {len(gdf)} point wells -> {geojson}")
    return geojson


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--states", nargs="+", default=APPALACHIA_DEFAULT,
                    help=f"state codes (default: {APPALACHIA_DEFAULT}); "
                         f"available: {sorted(SOURCES)}")
    ap.add_argument("--out", default="../data/wells", help="output dir")
    ap.add_argument("--limit", type=int, default=None, help="cap features (test)")
    args = ap.parse_args()

    out_dir = Path(args.out).resolve()
    sess = _session()

    for st in (s.upper() for s in args.states):
        src = SOURCES.get(st)
        if not src:
            print(f"[wells] no source configured for {st}; skipping "
                  f"(available: {sorted(SOURCES)})")
            continue
        print(f"[wells] === {st} ({src['kind']}) ===  {src.get('notes','')}")
        try:
            if src["kind"] == "arcgis":
                feats = fetch_arcgis(src["url"], src["page"], sess, args.limit)
                save_geojson(feats, out_dir / f"{st}.geojson")
            elif src["kind"] == "socrata":
                feats = fetch_socrata(src["url"], src["page"], sess, args.limit)
                save_geojson(feats, out_dir / f"{st}.geojson")
            elif src["kind"] == "shapefile_zip":
                fetch_shapefile_zip(src["url"], out_dir, st, sess)
            else:
                print(f"[wells] unknown kind {src['kind']} for {st}")
        except Exception as e:  # noqa: BLE001
            print(f"[wells] ERROR {st}: {e}")

    print(f"[wells] done -> {out_dir}")
    print("[wells] For dedup you can ALSO reuse data/processed/wells.documented.json "
          "(USGS DOW, 27 states) — convert to GeoJSON with scripts/dow_to_geojson.py.")


if __name__ == "__main__":
    main()
