"""Per-well enrichment via free, no-key federal ArcGIS endpoints.

Materializes the human-exposure + equity metrics that drive the composite
score, then caches every response to SQLite so the app/demo never refetches
(the "ingest once, serve from cache" architecture).

Sources (verified live):
  - CDC/ATSDR SVI 2022 tract layer (onemap.cdc.gov) -> population, daytime pop,
    overall vulnerability (RPL_THEMES), poverty %, minority % .  An EJ
    "demographic index" proxy is derived as mean(poverty%, minority%), mirroring
    EPA EJScreen's construction (the federal EJScreen was removed Feb 2025).
  - NCES Public School Locations (ArcGIS Online) -> count + nearest public
    school within 1 mile.

Hospitals and drinking-water service-area joins are intentionally omitted here
(their endpoints are flaky/heavy); the scorer renormalizes those weights out
uniformly, which is honest and keeps ingestion fast and reliable.
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
CACHE_DB = ROOT / "data" / "cache" / "enrich.sqlite"

SVI_URL = ("https://onemap.cdc.gov/OneMapServices/rest/services/SVI/"
           "CDC_ATSDR_Social_Vulnerability_Index_2022_USA/FeatureServer/2/query")
SVI_FIELDS = "E_TOTPOP,E_DAYPOP,RPL_THEMES,EP_POV150,EP_MINRTY,RPL_THEME1,RPL_THEME3,COUNTY,STATE,FIPS"
SCHOOLS_URL = ("https://services1.arcgis.com/Ua5sjt3LWTPigjyD/arcgis/rest/services/"
               "Public_School_Locations_Current/FeatureServer/0/query")
SCHOOL_RADIUS_M = 1609  # 1 mile

_local = threading.local()


def _session() -> requests.Session:
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
        _local.s.headers["User-Agent"] = "lost-wells/1.0 (research)"
    return _local.s


def _get(url: str, params: dict, tries: int = 3) -> dict:
    last = None
    for i in range(tries):
        try:
            r = _session().get(url, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"GET failed after {tries}: {last}")


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def svi_lookup(lat: float, lon: float) -> dict:
    d = _get(SVI_URL, {
        "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint",
        "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
        "outFields": SVI_FIELDS, "returnGeometry": "false", "f": "json",
    })
    feats = d.get("features", [])
    if not feats:
        return {}
    a = feats[0]["attributes"]
    pov, minr = a.get("EP_POV150"), a.get("EP_MINRTY")
    ej = None
    if pov is not None and minr is not None:
        ej = round(max(0.0, min(1.0, (pov + minr) / 200.0)), 4)
    pop = a.get("E_TOTPOP")
    return {
        "population": int(pop) if pop not in (None, -999) else None,
        "daytime_population": int(a["E_DAYPOP"]) if a.get("E_DAYPOP") not in (None, -999) else None,
        "svi": a.get("RPL_THEMES") if a.get("RPL_THEMES") not in (None, -999) else None,
        "poverty_pct": pov if pov != -999 else None,
        "minority_pct": minr if minr != -999 else None,
        "ej": ej,
        "svi_socioeconomic": a.get("RPL_THEME1") if a.get("RPL_THEME1") not in (None, -999) else None,
        "svi_minority": a.get("RPL_THEME3") if a.get("RPL_THEME3") not in (None, -999) else None,
        "county": a.get("COUNTY"), "tract_fips": a.get("FIPS"),
    }


def schools_within(lat: float, lon: float, radius_m: int = SCHOOL_RADIUS_M) -> dict:
    d = _get(SCHOOLS_URL, {
        "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint",
        "distance": radius_m, "units": "esriSRUnit_Meter", "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "NAME,CITY,STATE", "returnGeometry": "true",
        "outSR": "4326", "f": "json",
    })
    feats = d.get("features", [])
    nearest, nearest_m, names = None, None, []
    for f in feats:
        a = f["attributes"]
        names.append(a.get("NAME"))
        g = f.get("geometry") or {}
        if "x" in g and "y" in g:
            dist = _haversine_m(lat, lon, g["y"], g["x"])
            if nearest_m is None or dist < nearest_m:
                nearest_m, nearest = dist, a.get("NAME")
    return {
        "schools_within_1mi": len(feats),
        "nearest_school": nearest,
        "nearest_school_m": round(nearest_m, 1) if nearest_m is not None else None,
        "school_names": names[:8],
    }


def enrich_point(lat: float, lon: float) -> dict:
    out = {"hospitals_within_5mi": None, "drinking_water_score": None}
    try:
        out.update(svi_lookup(lat, lon))
    except Exception as e:  # noqa: BLE001
        out["svi_error"] = str(e)
    try:
        out.update(schools_within(lat, lon))
    except Exception as e:  # noqa: BLE001
        out["schools_error"] = str(e)
    return out


# --- cache ---------------------------------------------------------------
def _open_cache() -> sqlite3.Connection:
    CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(CACHE_DB)
    con.execute("CREATE TABLE IF NOT EXISTS enrich (key TEXT PRIMARY KEY, json TEXT)")
    return con


def _key(lat: float, lon: float) -> str:
    return f"{round(lat, 4)},{round(lon, 4)}"


def run(input_file: str = "candidates.base.json", limit: int | None = None,
        workers: int = 8, output_file: str = "enrichment.json") -> None:
    records = json.loads((PROC / input_file).read_text())
    if limit:
        records = records[:limit]
    con = _open_cache()
    cached = {k: json.loads(v) for k, v in con.execute("SELECT key,json FROM enrich")}
    print(f"[enrich] {len(records)} wells | {len(cached)} already cached")

    todo = [(r["well_id"], r["lat"], r["lon"]) for r in records
            if _key(r["lat"], r["lon"]) not in cached]
    new_rows = {}
    if todo:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(enrich_point, lat, lon): (wid, lat, lon)
                    for wid, lat, lon in todo}
            for fut in tqdm(as_completed(futs), total=len(futs), desc="enrich"):
                wid, lat, lon = futs[fut]
                try:
                    new_rows[_key(lat, lon)] = fut.result()
                except Exception as e:  # noqa: BLE001
                    new_rows[_key(lat, lon)] = {"error": str(e)}
        with con:
            con.executemany("INSERT OR REPLACE INTO enrich VALUES (?,?)",
                            [(k, json.dumps(v)) for k, v in new_rows.items()])
        cached.update(new_rows)

    enrichment = {r["well_id"]: cached.get(_key(r["lat"], r["lon"]), {}) for r in records}
    out = PROC / output_file
    out.write_text(json.dumps(enrichment, separators=(",", ":")))

    with_pop = sum(1 for v in enrichment.values() if v.get("population"))
    with_school = sum(1 for v in enrichment.values() if v.get("schools_within_1mi"))
    print(f"[enrich] wrote {out.relative_to(ROOT)}  "
          f"({with_pop}/{len(records)} w/ population, {with_school} w/ >=1 school in 1mi)")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="candidates.base.json")
    p.add_argument("--output", default="enrichment.json")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args()
    run(args.input, args.limit, args.workers, args.output)
