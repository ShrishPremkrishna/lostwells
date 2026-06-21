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

# --- source URLs (HANDOFF §2A verified-live, light budget) ---------------
# Drinking water: EPA CWS service-area boundaries. GitHub raw zip is primary
# (~570 MB); anon ArcGIS FeatureServer is the fallback (44,615 CWS).
PWS_URL = ("https://github.com/USEPA/ORD_SAB_Model/raw/refs/heads/main/"
           "Version_History/PWS_Boundaries_Latest.zip")
PWS_FALLBACK_FS = ("https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/"
                   "services/Water_System_Boundaries/FeatureServer/0/query")
# USGS National Map "structures" layer 14 = Hospitals/Medical Centers — the
# authoritative national, weekly-updated source. (The HIFLD ArcGIS mirrors are
# dead/partial: the old geoplatform layer 404s, one mirror is Canada-only, the
# NASA NCCS archive times out — so we use USGS, which PROGRESS §2.2 flagged the
# 5% hospitals gap on.)
HOSPITALS_URL = ("https://carto.nationalmap.gov/arcgis/rest/services/"
                 "structures/MapServer/14/query")  # field: name; pts EPSG:4326
# CEJST / Justice40 — PEDP CloudFront mirror (federal *.geoplatform.gov is
# DNS-DEAD after the 2025 takedown).
CEJST_CSV_URL = ("https://dblew8dgr6ajz.cloudfront.net/data-versions/2.0/"
                 "data/score/downloadable/2.0-communities.csv")
# CDC/ATSDR EJI — still official & live; the most reliable EJ source now.
# Base is lowercase /onemapservices/ and the Hosted 2022 service.
EJI_URL = ("https://onemap.cdc.gov/onemapservices/rest/services/Hosted/"
           "Environmental_Justice_Index_2022_Hosted/FeatureServer/0/query")
# CDC/ATSDR SVI 2022 tract layer (same source enrich.py uses per-point). Here it
# is bulk-pulled per state and joined locally by tract GEOID so the score-moving
# vulnerability/equity fields reach the full universe, not just sampled points.
SVI_URL = ("https://onemap.cdc.gov/OneMapServices/rest/services/SVI/"
           "CDC_ATSDR_Social_Vulnerability_Index_2022_USA/FeatureServer/2/query")
SVI_FIELDS = ("E_TOTPOP,E_DAYPOP,RPL_THEMES,EP_POV150,EP_MINRTY,"
              "RPL_THEME1,RPL_THEME3,COUNTY,ST_ABBR,FIPS")
# NCES Public School Locations (same layer as enrich.py); bulk-pulled once and
# joined locally for schools_within_1mi + nearest_school over the full universe.
SCHOOLS_URL = ("https://services1.arcgis.com/Ua5sjt3LWTPigjyD/arcgis/rest/services/"
               "Public_School_Locations_Current/FeatureServer/0/query")

MILE_M = 1609.34
HOSP_RADIUS_M = 5 * MILE_M
SCHOOL_RADIUS_M = MILE_M

ACS_BASE = "https://api.census.gov/data/2023/acs/acs5"
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
def _load_pws_fallback(with_downloads: bool, bbox: Optional[tuple] = None
                       ) -> Optional[gpd.GeoDataFrame]:
    """Anon ArcGIS FeatureServer fallback (44,615 CWS) when the zip is absent."""
    dest = RAW / "pws_boundaries_fs.geojson"
    if dest.exists() and dest.stat().st_size > 0:
        return gpd.read_file(dest)
    if not with_downloads:
        return None
    params = {
        "where": "1=1", "outFields": "PWSID,PWS_Name,Population_Served_Count",
        "outSR": "4326", "returnGeometry": "true", "f": "geojson",
        "resultRecordCount": 2000,
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
    while True:
        params["resultOffset"] = offset
        try:
            r = sess.get(PWS_FALLBACK_FS, params=params, timeout=180)
            r.raise_for_status()
            page = r.json().get("features", [])
        except Exception as e:  # noqa: BLE001
            print(f"[pws] FeatureServer fallback failed: {e}")
            break
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


def load_pws(with_downloads: bool, bbox: Optional[tuple] = None
             ) -> Optional[gpd.GeoDataFrame]:
    dest = RAW / "pws_boundaries_latest.zip"
    if not dest.exists():
        if not with_downloads:
            print("[pws] not cached; pass --with-downloads to fetch (570MB)")
            return _load_pws_fallback(with_downloads, bbox)
        try:
            _download(PWS_URL, dest)
        except Exception as e:  # noqa: BLE001
            print(f"[pws] GitHub zip failed ({e}); trying FeatureServer fallback")
            return _load_pws_fallback(with_downloads, bbox)
    try:
        g = gpd.read_file(f"zip://{dest}")
    except Exception as e:  # noqa: BLE001
        print(f"[pws] read failed: {e}; trying FeatureServer fallback")
        return _load_pws_fallback(with_downloads, bbox)
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
    """Fetch hospital points (USGS National Map), cached to a local GeoJSON.

    Hospitals are only 5% of the score and the public layers are historically
    flaky, so any fetch error degrades gracefully to ``None`` (the metric
    renormalizes out) rather than crashing the whole enrichment.
    """
    dest = RAW / "hospitals.geojson"
    if dest.exists() and dest.stat().st_size > 0:
        return gpd.read_file(dest)
    if not with_downloads:
        print("[hospitals] not cached; pass --with-downloads to fetch")
        return None
    PAGE = 2000  # = layer 14 maxRecordCount
    params = {
        "where": "1=1", "outFields": "*", "outSR": "4326",
        "returnGeometry": "true", "f": "geojson", "resultRecordCount": PAGE,
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
            r = sess.get(HOSPITALS_URL, params=params, timeout=120)
            r.raise_for_status()
            page = r.json().get("features", [])
            feats.extend(page)
            if len(page) < PAGE:
                break
            offset += len(page)
    except Exception as e:  # noqa: BLE001 — degrade, don't crash the pipeline
        print(f"[hospitals] fetch failed ({e}); skipping (metric renormalizes out)")
        return None
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


# --- schools (point nearest + 1-mile count) ------------------------------
def load_schools(with_downloads: bool, bbox: Optional[tuple] = None
                 ) -> Optional[gpd.GeoDataFrame]:
    """Fetch public-school points (NCES), cached to a local GeoJSON.

    Mirrors ``load_hospitals``: any fetch error degrades gracefully to ``None``
    (the schools metric renormalizes out) rather than crashing enrichment.
    """
    dest = RAW / "schools.geojson"
    if dest.exists() and dest.stat().st_size > 0:
        return gpd.read_file(dest)
    if not with_downloads:
        print("[schools] not cached; pass --with-downloads to fetch")
        return None
    PAGE = 2000
    params = {
        "where": "1=1", "outFields": "NAME,CITY,STATE", "outSR": "4326",
        "returnGeometry": "true", "f": "geojson", "resultRecordCount": PAGE,
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
            r = sess.get(SCHOOLS_URL, params=params, timeout=120)
            r.raise_for_status()
            page = r.json().get("features", [])
            feats.extend(page)
            if len(page) < PAGE:
                break
            offset += len(page)
    except Exception as e:  # noqa: BLE001 — degrade, don't crash the pipeline
        print(f"[schools] fetch failed ({e}); skipping (metric renormalizes out)")
        return None
    if not feats:
        return None
    g = gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326")
    dest.parent.mkdir(parents=True, exist_ok=True)
    g.to_file(dest, driver="GeoJSON")
    return g


def school_proximity(wells: gpd.GeoDataFrame, schools: gpd.GeoDataFrame) -> dict:
    """well_id -> {schools_within_1mi, nearest_school, nearest_school_m,
    school_names}. Mirrors ``hospital_proximity`` (metric CRS, sjoin_nearest +
    1-mile buffer count)."""
    name_col = "NAME" if "NAME" in schools.columns else None
    w_m = wells[["well_id", "geometry"]].to_crs(METRIC_CRS)
    s_cols = ["geometry"] + ([name_col] if name_col else [])
    s_m = schools[s_cols].to_crs(METRIC_CRS)

    # nearest school (distance + name)
    near = gpd.sjoin_nearest(w_m, s_m, how="left", distance_col="d")
    near = near[~near.index.duplicated(keep="first")]
    nearest_name = (dict(zip(near["well_id"], near[name_col]))
                    if name_col else {})

    # count + names within 1 mile via buffer join
    buf = w_m.copy()
    buf["geometry"] = buf.geometry.buffer(SCHOOL_RADIUS_M)
    cnt = gpd.sjoin(buf, s_m, how="left", predicate="intersects")
    hit = cnt.dropna(subset=["index_right"])
    counts = hit.groupby("well_id").size()
    names_by_well: dict = {}
    if name_col:
        for wid, nm in zip(hit["well_id"], hit[name_col]):
            if nm is not None and not pd.isna(nm):
                names_by_well.setdefault(wid, []).append(nm)

    out: dict = {}
    for wid, d in zip(near["well_id"], near["d"]):
        nm = nearest_name.get(wid)
        out[wid] = {
            "schools_within_1mi": int(counts.get(wid, 0)),
            "nearest_school": nm if nm is not None and not pd.isna(nm) else None,
            "nearest_school_m": round(float(d), 1) if d is not None and not pd.isna(d) else None,
            "school_names": names_by_well.get(wid, [])[:8],
        }
    return out


# --- true 1-mile population via BG areal interpolation -------------------
def _acs_bg_population(states: list[str]) -> dict:
    """12-digit BG GEOID -> ACS5 2023 total population (B01003_001E)."""
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
    PAGE = 2000  # = EJI layer maxRecordCount (lowercase, PostgreSQL-backed)
    for st in states:
        params = {
            "where": f"stateabbr='{st}'",
            "outFields": "geoid,rpl_eji", "returnGeometry": "false",
            "f": "json", "resultRecordCount": PAGE,
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
                g = a.get("geoid")
                v = a.get("rpl_eji")
                if g is not None and v not in (None, -999):
                    out[str(g).zfill(11)] = round(float(v), 4)
            if len(feats) < PAGE:
                break
            offset += len(feats)
    print(f"[eji] loaded {len(out):,} tract EJI ranks")
    return out


def _parse_svi_attrs(a: dict) -> dict:
    """SVI feature attributes -> per-tract enrichment dict (mirrors
    ``enrich.svi_lookup``: filter -999, derive the EJ proxy, map themes)."""
    pov, minr = a.get("EP_POV150"), a.get("EP_MINRTY")
    ej = None
    if pov not in (None, -999) and minr not in (None, -999):
        ej = round(max(0.0, min(1.0, (pov + minr) / 200.0)), 4)
    pop = a.get("E_TOTPOP")
    day = a.get("E_DAYPOP")
    return {
        "population": int(pop) if pop not in (None, -999) else None,
        "daytime_population": int(day) if day not in (None, -999) else None,
        "svi": a.get("RPL_THEMES") if a.get("RPL_THEMES") not in (None, -999) else None,
        "poverty_pct": pov if pov not in (None, -999) else None,
        "minority_pct": minr if minr not in (None, -999) else None,
        "ej": ej,
        "svi_socioeconomic": a.get("RPL_THEME1") if a.get("RPL_THEME1") not in (None, -999) else None,
        "svi_minority": a.get("RPL_THEME3") if a.get("RPL_THEME3") not in (None, -999) else None,
        "county": a.get("COUNTY"),
    }


def load_svi(states: list[str], with_downloads: bool) -> dict:
    """tract GEOID (11) -> SVI/equity fields, bulk-pulled per state and keyed
    by FIPS (mirrors ``load_eji``; parses like ``enrich.svi_lookup``).

    Probes one state to confirm the ``ST_ABBR`` where-clause is supported,
    falling back to ``FIPS LIKE '<fips>%'`` if the field is absent.
    """
    if not with_downloads:
        print("[svi] pass --with-downloads to fetch")
        return {}
    sess = requests.Session()
    out: dict = {}
    PAGE = 2000  # SVI layer maxRecordCount

    def _where(st: str) -> str:
        return f"ST_ABBR='{st}'"

    # Probe the first state: if ST_ABBR is unsupported, fall back to FIPS LIKE.
    use_fips_like = False
    if states:
        st0 = states[0]
        try:
            r = sess.get(SVI_URL, params={
                "where": _where(st0), "outFields": SVI_FIELDS,
                "returnGeometry": "false", "f": "json", "resultRecordCount": 1,
            }, timeout=120)
            r.raise_for_status()
            body = r.json()
            if body.get("error") or "features" not in body:
                use_fips_like = True
        except Exception as e:  # noqa: BLE001
            print(f"[svi] ST_ABBR probe failed ({e}); using FIPS LIKE fallback")
            use_fips_like = True
        if use_fips_like:
            print("[svi] ST_ABBR unsupported; using FIPS LIKE where-clause")

    for st in states:
        if use_fips_like:
            fips = T.STATE_FIPS.get(st.upper())
            if not fips:
                continue
            where = f"FIPS LIKE '{fips}%'"
        else:
            where = _where(st)
        params = {
            "where": where, "outFields": SVI_FIELDS,
            "returnGeometry": "false", "f": "json", "resultRecordCount": PAGE,
        }
        offset = 0
        while True:
            params["resultOffset"] = offset
            try:
                r = sess.get(SVI_URL, params=params, timeout=120)
                r.raise_for_status()
                feats = r.json().get("features", [])
            except Exception as e:  # noqa: BLE001
                print(f"[svi] {st} failed: {e}")
                break
            for ft in feats:
                a = ft.get("attributes", {})
                g = a.get("FIPS")
                if g is None:
                    continue
                out[str(g).zfill(11)] = _parse_svi_attrs(a)
            if len(feats) < PAGE:
                break
            offset += len(feats)
    print(f"[svi] loaded {len(out):,} tract SVI records")
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
    bbox = (float(df["lon"].min()), float(df["lat"].min()),
            float(df["lon"].max()), float(df["lat"].max()))
    pws = load_pws(with_downloads, bbox=bbox)
    if pws is not None:
        dw_scores = drinking_water_scores(wells, pws)
    hospitals = load_hospitals(with_downloads, bbox=bbox)
    if hospitals is not None and not hospitals.empty:
        hosp = hospital_proximity(wells, hospitals)
    sch: dict = {}
    schools = load_schools(with_downloads, bbox=bbox)
    if schools is not None and not schools.empty:
        sch = school_proximity(wells, schools)

    # --- 1-mile population (BG areal interpolation) ----------------------
    pop1mi = population_1mi(wells, states)

    # --- EJ + SVI (tract-keyed) ------------------------------------------
    cejst = load_cejst(with_downloads)
    eji = load_eji(states, with_downloads)
    svi = load_svi(states, with_downloads)

    # --- merge into per-well enrichment (preserve existing enrichment.json) -
    existing_path = PROC / output_file
    enrichment: dict = {}
    if existing_path.exists():
        try:
            enrichment = json.loads(existing_path.read_text())
        except Exception:  # noqa: BLE001
            enrichment = {}

    SVI_KEYS = ("svi", "svi_socioeconomic", "svi_minority", "poverty_pct",
                "minority_pct", "ej", "population", "daytime_population", "county")
    n_dw = n_hosp = n_pop = n_ej = n_sch = n_svi = 0
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
        if wid in sch:
            cur.update(sch[wid]); n_sch += 1
        if wid in pop1mi:
            cur["population_1mi"] = pop1mi[wid]; n_pop += 1
        if geoid:
            if geoid in cejst:
                cur["cejst_disadvantaged"] = cejst[geoid]
            if geoid in eji:
                cur["eji_rank"] = eji[geoid]; n_ej += 1
            if geoid in svi:
                # Fill-missing-first: the per-point SVI from enrich.py is the
                # same tract value, so only backfill fields not already set.
                for k, v in svi[geoid].items():
                    if v is not None and cur.get(k) is None:
                        cur[k] = v
                if cur.get("svi") is not None:
                    n_svi += 1
            cur["tract_geoid"] = geoid
            tr = {k: cur[k] for k in ("cejst_disadvantaged", "eji_rank", *SVI_KEYS)
                  if k in cur}
            if tr:
                new_tract_rows[geoid] = tr
        pk = _pkey(rec["lat"], rec["lon"])
        pr = {k: cur[k] for k in ("drinking_water_score", "hospitals_within_5mi",
                                  "nearest_hospital_m", "population_1mi",
                                  "schools_within_1mi", "nearest_school",
                                  "nearest_school_m", "school_names") if k in cur}
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
    print(f"  svi {n_svi}/{n} | schools {n_sch}/{n}")


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
