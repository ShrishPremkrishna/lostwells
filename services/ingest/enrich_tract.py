"""Tract-keyed enrichment for the score-moving §2A metrics.

Complements ``enrich.py`` (which keeps the per-point SVI + schools lookups).
The expensive layers here are *downloaded once* and joined locally, so the full
consolidated universe enriches in well under an hour (downloads dominate, not
per-well API calls). Two caches:

  - ``data/cache/enrich_tract.sqlite`` keyed by **tract GEOID** for tract metrics
    (population_1mi, EJ via CEJST/EJI).
  - a point cache (rounded lat/lon) for proximity metrics (drinking water,
    hospitals) — these depend on exact location, not just the tract.

New / upgraded metrics (each emitted whether or not the well lands in a polygon,
so "outside any service area" is an explicit signal, not missing data):

  - ``drinking_water_score`` — EPA Community Water System service-area PIP
    (in-CWS + population-served scaling; rural-outside = explicit no-service).
  - ``hospitals_within_5mi`` (+ ``nearest_hospital_m``) — local nearest-feature
    over a downloaded hospitals point layer.
  - ``population_1mi`` — block-group areal interpolation: 1-mi buffer × BG
    polygons area-weighted by ACS block-group population.
  - ``cejst_disadvantaged`` (Justice40 boolean) + ``eji_rank`` (CDC EJI),
    the real EJ signal replacing the SVI-derived proxy.

Heavy/optional downloads (NHD, wetlands, EJScreen) are intentionally NOT here.

CLI:
    python services/ingest/enrich_tract.py --input lost_wells.json \\
        --states OH,WV,PA,NY,KY [--with-downloads]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
import requests
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tracts as T  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw" / "enrich"
CACHE_DB = ROOT / "data" / "cache" / "enrich_tract.sqlite"
METRIC_CRS = "EPSG:5070"  # CONUS Albers (meters)

# --- source URLs (light budget) ------------------------------------------
PWS_URL = ("https://www.epa.gov/sites/default/files/2021-06/"
           "pws_boundaries_latest.zip")  # ~570 MB CWS service areas
HOSPITALS_URL = ("https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/"
                 "services/Hospitals_1/FeatureServer/0/query")  # HIFLD points
CEJST_CSV_URL = ("https://static-data-screeningtool.geoplatform.gov/"
                 "data-versions/2.0/data/score/downloadable/2.0-communities.csv")
EJI_URL = ("https://onemap.cdc.gov/OneMapServices/rest/services/EJI/"
           "CDC_ATSDR_EJI_2024/FeatureServer/0/query")

MILE_M = 1609.34
HOSP_RADIUS_M = 5 * MILE_M

ACS_BASE = "https://api.census.gov/data/2022/acs/acs5"
ACS_KEY = os.environ.get("CENSUS_API_KEY", "")


# --- caches ---------------------------------------------------------------
def _open_cache() -> sqlite3.Connection:
    CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(CACHE_DB)
    con.execute("CREATE TABLE IF NOT EXISTS tract (geoid TEXT PRIMARY KEY, json TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS point (key TEXT PRIMARY KEY, json TEXT)")
    return con


def _pkey(lat: float, lon: float) -> str:
    return f"{round(lat, 4)},{round(lon, 4)}"


# --- downloads (gated) ----------------------------------------------------
def _download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[skip] {dest.relative_to(ROOT)} ({dest.stat().st_size/1e6:.1f} MB)")
        return dest
    print(f"[get ] {dest.relative_to(ROOT)}")
    with requests.get(url, stream=True, timeout=900) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        with open(dest, "wb") as f, tqdm(total=total, unit="B", unit_scale=True) as bar:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)
                bar.update(len(chunk))
    return dest


# --- drinking-water service areas (PWS) ----------------------------------
def load_pws(with_downloads: bool) -> Optional[gpd.GeoDataFrame]:
    dest = RAW / "pws_boundaries_latest.zip"
    if not dest.exists():
        if not with_downloads:
            print("[pws] not cached; pass --with-downloads to fetch (570MB)")
            return None
        _download(PWS_URL, dest)
    try:
        g = gpd.read_file(f"zip://{dest}")
    except Exception as e:  # noqa: BLE001
        print(f"[pws] read failed: {e}")
        return None
    if str(g.crs).upper() != "EPSG:4326":
        g = g.to_crs("EPSG:4326")
    return g


def _pws_pop_col(g: gpd.GeoDataFrame) -> Optional[str]:
    for c in ("Population_Served_Count", "POP_SERVED", "population_served_count",
              "PopServed", "POPULATION"):
        if c in g.columns:
            return c
    return None


def drinking_water_scores(wells: gpd.GeoDataFrame, pws: gpd.GeoDataFrame) -> dict:
    """well_id -> drinking_water_score in 0-1 (in-CWS + pop-served scaled).

    Rural wells outside any CWS polygon score 0.0 — an explicit "no community
    water service" signal rather than missing data.
    """
    pop_col = _pws_pop_col(pws)
    cols = ["geometry"] + ([pop_col] if pop_col else [])
    joined = gpd.sjoin(wells[["well_id", "geometry"]], pws[cols],
                       how="left", predicate="within")
    joined = joined[~joined.index.duplicated(keep="first")]
    out: dict = {}
    if pop_col:
        served = pd.to_numeric(joined[pop_col], errors="coerce")
        # log-scale population served into 0..1 (cap ~1M served).
        import math
        for wid, ps in zip(joined["well_id"], served):
            if ps is None or pd.isna(ps) or ps <= 0:
                out[wid] = 0.0
            else:
                out[wid] = round(min(1.0, math.log10(ps + 1) / 6.0), 4)
    else:
        in_cws = joined["index_right"].notna()
        for wid, hit in zip(joined["well_id"], in_cws):
            out[wid] = 1.0 if bool(hit) else 0.0
    return out


# --- hospitals (point nearest) -------------------------------------------
def load_hospitals(with_downloads: bool, bbox: Optional[tuple] = None
                   ) -> Optional[gpd.GeoDataFrame]:
    """Fetch hospital points (HIFLD ArcGIS), cached to a local GeoJSON."""
    dest = RAW / "hospitals.geojson"
    if dest.exists() and dest.stat().st_size > 0:
        return gpd.read_file(dest)
    if not with_downloads:
        print("[hospitals] not cached; pass --with-downloads to fetch")
        return None
    params = {
        "where": "1=1", "outFields": "NAME,STATE,TYPE", "outSR": "4326",
        "returnGeometry": "true", "f": "geojson", "resultRecordCount": 4000,
    }
    if bbox:
        params.update({
            "geometry": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
            "geometryType": "esriGeometryEnvelope", "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
        })
    feats = []
    offset = 0
    sess = requests.Session()
    while True:
        params["resultOffset"] = offset
        r = sess.get(HOSPITALS_URL, params=params, timeout=120)
        r.raise_for_status()
        payload = r.json()
        page = payload.get("features", [])
        feats.extend(page)
        if len(page) < params["resultRecordCount"]:
            break
        offset += len(page)
    if not feats:
        return None
    g = gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326")
    dest.parent.mkdir(parents=True, exist_ok=True)
    g.to_file(dest, driver="GeoJSON")
    return g


def hospital_proximity(wells: gpd.GeoDataFrame, hosp: gpd.GeoDataFrame) -> dict:
    """well_id -> {hospitals_within_5mi, nearest_hospital_m}."""
    w_m = wells[["well_id", "geometry"]].to_crs(METRIC_CRS)
    h_m = hosp[["geometry"]].to_crs(METRIC_CRS)
    # nearest distance
    near = gpd.sjoin_nearest(w_m, h_m, how="left", distance_col="d")
    near = near[~near.index.duplicated(keep="first")]
    # count within 5 mi via buffer join
    buf = w_m.copy()
    buf["geometry"] = buf.geometry.buffer(HOSP_RADIUS_M)
    cnt = gpd.sjoin(buf, h_m, how="left", predicate="intersects")
    counts = cnt.groupby("well_id").size()  # at least 1 row per well (left join)
    has = cnt.dropna(subset=["index_right"]).groupby("well_id").size()
    out = {}
    for wid, d in zip(near["well_id"], near["d"]):
        n = int(has.get(wid, 0))
        out[wid] = {
            "hospitals_within_5mi": n,
            "nearest_hospital_m": round(float(d), 1) if d is not None and not pd.isna(d) else None,
        }
    return out


# --- true 1-mile population via BG areal interpolation -------------------
def _acs_bg_population(states: list[str]) -> dict:
    """12-digit BG GEOID -> ACS5 2022 total population (B01003_001E)."""
    if not ACS_KEY:
        print("[acs] CENSUS_API_KEY not set; population_1mi will be skipped")
        return {}
    out: dict = {}
    sess = requests.Session()
    for st in states:
        fips = T.STATE_FIPS.get(st.upper())
        if not fips:
            continue
        params = {
            "get": "B01003_001E", "for": "block group:*",
            "in": f"state:{fips} county:*", "key": ACS_KEY,
        }
        try:
            r = sess.get(ACS_BASE, params=params, timeout=120)
            r.raise_for_status()
            rows = r.json()
        except Exception as e:  # noqa: BLE001
            print(f"[acs] {st} failed: {e}")
            continue
        header = rows[0]
        for row in rows[1:]:
            rec = dict(zip(header, row))
            geoid = rec["state"] + rec["county"] + rec["tract"] + rec["block group"]
            try:
                out[geoid] = float(rec["B01003_001E"])
            except (TypeError, ValueError):
                out[geoid] = 0.0
    print(f"[acs] loaded population for {len(out):,} block groups")
    return out


def population_1mi(wells: gpd.GeoDataFrame, states: list[str]) -> dict:
    """well_id -> areal-interpolated population within a 1-mile buffer."""
    bg_pop = _acs_bg_population(states)
    if not bg_pop:
        return {}
    bg = T.load_polygons(states, kind="bg")
    if bg.empty:
        return {}
    bg = bg.to_crs(METRIC_CRS)
    bg["pop"] = bg["GEOID"].map(bg_pop).fillna(0.0)
    bg["bg_area"] = bg.geometry.area
    bg = bg[bg["bg_area"] > 0]

    w_m = wells[["well_id", "geometry"]].to_crs(METRIC_CRS).copy()
    w_m["geometry"] = w_m.geometry.buffer(MILE_M)

    inter = gpd.overlay(w_m, bg[["GEOID", "pop", "bg_area", "geometry"]],
                        how="intersection", keep_geom_type=True)
    inter["frac"] = inter.geometry.area / inter["bg_area"]
    inter["pop_share"] = inter["pop"] * inter["frac"]
    agg = inter.groupby("well_id")["pop_share"].sum()
    return {wid: int(round(v)) for wid, v in agg.items()}


# --- EJ via CEJST + EJI ---------------------------------------------------
def load_cejst(with_downloads: bool) -> dict:
    """tract GEOID (11) -> cejst_disadvantaged boolean (Justice40)."""
    dest = RAW / "cejst_communities.csv"
    if not dest.exists():
        if not with_downloads:
            print("[cejst] not cached; pass --with-downloads to fetch")
            return {}
        _download(CEJST_CSV_URL, dest)
    try:
        df = pd.read_csv(dest, dtype={"Census tract 2010 ID": str}, low_memory=False)
    except Exception as e:  # noqa: BLE001
        print(f"[cejst] read failed: {e}")
        return {}
    geo_col = next((c for c in df.columns if "tract" in c.lower() and "id" in c.lower()), None)
    flag_col = next((c for c in df.columns
                     if "disadvantaged" in c.lower() and "final" in c.lower()), None)
    if flag_col is None:
        flag_col = next((c for c in df.columns if "disadvantaged" in c.lower()), None)
    if geo_col is None or flag_col is None:
        print("[cejst] expected columns not found")
        return {}
    out = {}
    for geoid, flag in zip(df[geo_col], df[flag_col]):
        if pd.isna(geoid):
            continue
        out[str(geoid).zfill(11)] = bool(flag) if not pd.isna(flag) else False
    print(f"[cejst] loaded {len(out):,} tracts ({sum(out.values()):,} disadvantaged)")
    return out


def load_eji(states: list[str], with_downloads: bool) -> dict:
    """tract GEOID (11) -> eji_rank (0-1, CDC EJI overall rank)."""
    if not with_downloads:
        print("[eji] pass --with-downloads to fetch")
        return {}
    sess = requests.Session()
    out: dict = {}
    for st in states:
        params = {
            "where": f"StateAbbr='{st}'",
            "outFields": "GEOID,RPL_EJI", "returnGeometry": "false",
            "f": "json", "resultRecordCount": 5000,
        }
        offset = 0
        while True:
            params["resultOffset"] = offset
            try:
                r = sess.get(EJI_URL, params=params, timeout=120)
                r.raise_for_status()
                feats = r.json().get("features", [])
            except Exception as e:  # noqa: BLE001
                print(f"[eji] {st} failed: {e}")
                break
            for ft in feats:
                a = ft.get("attributes", {})
                g = a.get("GEOID")
                v = a.get("RPL_EJI")
                if g is not None and v not in (None, -999):
                    out[str(g).zfill(11)] = round(float(v), 4)
            if len(feats) < params["resultRecordCount"]:
                break
            offset += len(feats)
    print(f"[eji] loaded {len(out):,} tract EJI ranks")
    return out


# --- driver ---------------------------------------------------------------
def run(input_file: str = "lost_wells.json", states: Optional[list[str]] = None,
        with_downloads: bool = False, output_file: str = "enrichment.json",
        limit: int | None = None) -> None:
    records = json.loads((PROC / input_file).read_text())
    if isinstance(records, dict):  # columnar guard — expect array-of-objects
        raise SystemExit(f"{input_file} is not an array of well records")
    if limit:
        records = records[:limit]
    df = pd.DataFrame(records)
    states = states or T._states_in(df) or ["OH", "WV", "PA", "NY", "KY"]
    print(f"[enrich_tract] {len(df):,} wells | states={','.join(states)}")

    # Resolve tract GEOID for dedup + tract-keyed metrics.
    df = T.resolve_tracts(df, states, kind="tract")
    wells = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326"
    )

    con = _open_cache()
    point_cache = {k: json.loads(v) for k, v in con.execute("SELECT key,json FROM point")}
    tract_cache = {g: json.loads(v) for g, v in con.execute("SELECT geoid,json FROM tract")}

    # --- proximity metrics (point-keyed) ---------------------------------
    dw_scores: dict = {}
    hosp: dict = {}
    pws = load_pws(with_downloads)
    if pws is not None:
        dw_scores = drinking_water_scores(wells, pws)
    bbox = (float(df["lon"].min()), float(df["lat"].min()),
            float(df["lon"].max()), float(df["lat"].max()))
    hospitals = load_hospitals(with_downloads, bbox=bbox)
    if hospitals is not None and not hospitals.empty:
        hosp = hospital_proximity(wells, hospitals)

    # --- 1-mile population (BG areal interpolation) ----------------------
    pop1mi = population_1mi(wells, states)

    # --- EJ (tract-keyed) ------------------------------------------------
    cejst = load_cejst(with_downloads)
    eji = load_eji(states, with_downloads)

    # --- merge into per-well enrichment (preserve existing enrichment.json) -
    existing_path = PROC / output_file
    enrichment: dict = {}
    if existing_path.exists():
        try:
            enrichment = json.loads(existing_path.read_text())
        except Exception:  # noqa: BLE001
            enrichment = {}

    n_dw = n_hosp = n_pop = n_ej = 0
    new_tract_rows: dict = {}
    new_point_rows: dict = {}
    for rec in records:
        wid = rec["well_id"]
        cur = dict(enrichment.get(wid, {}))
        geoid = df.loc[df["well_id"] == wid, "tract_geoid"]
        geoid = geoid.iloc[0] if len(geoid) else None

        if wid in dw_scores:
            cur["drinking_water_score"] = dw_scores[wid]; n_dw += 1
        if wid in hosp:
            cur.update(hosp[wid]); n_hosp += 1
        if wid in pop1mi:
            cur["population_1mi"] = pop1mi[wid]; n_pop += 1
        if geoid:
            if geoid in cejst:
                cur["cejst_disadvantaged"] = cejst[geoid]
            if geoid in eji:
                cur["eji_rank"] = eji[geoid]; n_ej += 1
            cur["tract_geoid"] = geoid
            tr = {k: cur[k] for k in ("cejst_disadvantaged", "eji_rank")
                  if k in cur}
            if tr:
                new_tract_rows[geoid] = tr
        pk = _pkey(rec["lat"], rec["lon"])
        pr = {k: cur[k] for k in ("drinking_water_score", "hospitals_within_5mi",
                                  "nearest_hospital_m", "population_1mi") if k in cur}
        if pr:
            new_point_rows[pk] = pr
        enrichment[wid] = cur

    if new_tract_rows:
        with con:
            con.executemany("INSERT OR REPLACE INTO tract VALUES (?,?)",
                            [(g, json.dumps(v)) for g, v in new_tract_rows.items()])
    if new_point_rows:
        with con:
            con.executemany("INSERT OR REPLACE INTO point VALUES (?,?)",
                            [(k, json.dumps(v)) for k, v in new_point_rows.items()])
    con.close()

    existing_path.write_text(json.dumps(enrichment, separators=(",", ":")))
    n = len(records)
    print(f"[enrich_tract] wrote {existing_path.relative_to(ROOT)}")
    print(f"  drinking_water {n_dw}/{n} | hospitals {n_hosp}/{n} | "
          f"population_1mi {n_pop}/{n} | eji {n_ej}/{n}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="lost_wells.json")
    p.add_argument("--output", default="enrichment.json")
    p.add_argument("--states", default="")
    p.add_argument("--with-downloads", action="store_true",
                   help="fetch the heavy light-budget layers (PWS 570MB, etc.)")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()
    states = [s.strip().upper() for s in args.states.split(",") if s.strip()] or None
    run(args.input, states, args.with_downloads, args.output, args.limit)


if __name__ == "__main__":
    main()
