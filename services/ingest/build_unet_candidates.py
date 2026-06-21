"""Ingest the U-Net Appalachia detections into the candidate datastore.

A standalone stage run **after** ``build_datastore.py``. It converts the U-Net
detection GeoJSON (``full_data_core_appala.geojson`` — 36,919 PA/KY/WV/OH wells)
into the existing 17-field ``candidates.base.json`` schema and **merges** it onto
the LBNL CA/OK candidates already written by ``build_datastore.py`` (~38.2k total).

Idempotent: always rebuilds the U-Net portion fresh and strips any prior
``unet_*`` rows before merging, so the LBNL stage remains the sole writer of its
own rows.

Provenance lives in the **nested** ``source_records[0].feature.properties``
(the top-level aggregation props are an empty known upstream bug). 36,792 features
have one ``source_records`` entry; 127 have two -> we take the primary (first).

Field synthesis notes:
  - ``quad_scale`` is recovered via a ``(quad, year, primary_state) -> map_scale``
    join against the USGS HTMC inventory (no ``scan_id`` exists): 99.9%
    exact-unique; ambiguous -> 24000 tie-break; missing -> 24000 default.
  - ``county_group`` via an offline national-county point-in-polygon; rural points
    outside any county polygon fall back to ``Unknown_{state_abbr}`` (counted, not
    dropped).
  - ``nearest_doc_well_m`` is recomputed nationally vs the documented universe
    (EPSG:5070 ``sjoin_nearest``) rather than trusting the source distance (2.8%
    are null and the U-Net reference set may differ).
"""
from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import normalize as N  # noqa: E402
import build_datastore as B  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
METRIC_CRS = B.METRIC_CRS  # EPSG:5070 CONUS Albers Equal Area (meters)

UNET_GEOJSON = ROOT / "full_data_core_appala.geojson"

HTMC_DIR = RAW / "htmc"
HTMC_CSV = HTMC_DIR / "historicaltopo.csv"
HTMC_URL = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Maps/Metadata/historicaltopo.zip"

TIGER_DIR = RAW / "tiger"
COUNTY_YEARS = ("2025", "2024")
COUNTY_URL = "https://www2.census.gov/geo/tiger/TIGER{yr}/COUNTY/tl_{yr}_us_county.zip"

DEFAULT_SCALE = 24000


# --------------------------------------------------------------------------- #
# 1. Read the U-Net GeoJSON                                                    #
# --------------------------------------------------------------------------- #
def read_unet_features() -> pd.DataFrame:
    """Pull lon/lat + nested (state, quad, year) provenance per detection."""
    print(f"[unet] reading {UNET_GEOJSON.name} ...")
    gj = json.loads(UNET_GEOJSON.read_text())
    feats = gj["features"]
    rows = []
    for f in feats:
        lon, lat = f["geometry"]["coordinates"][:2]
        srecs = f["properties"].get("source_records") or []
        if not srecs:
            continue
        # Primary (first) record carries the provenance we trust.
        props = srecs[0]["feature"]["properties"]
        states = props.get("states") or []
        quads = props.get("quads") or []
        years = props.get("years") or []
        if not (states and quads and years):
            continue
        rows.append({
            "lon": float(lon),
            "lat": float(lat),
            "state": str(states[0]).strip(),
            "quad": str(quads[0]).strip(),
            "year": str(years[0]).strip(),
        })
    df = pd.DataFrame(rows)
    print(f"[unet] {len(df):,} detections with nested provenance "
          f"(of {len(feats):,} features)")
    return df


# --------------------------------------------------------------------------- #
# 2. Scale lookup via the USGS HTMC inventory                                  #
# --------------------------------------------------------------------------- #
def _ensure_htmc() -> None:
    """Download + cache the HTMC inventory CSV once. Idempotent."""
    if HTMC_CSV.exists() and HTMC_CSV.stat().st_size > 0:
        print(f"[skip] {HTMC_CSV.relative_to(ROOT)} "
              f"({HTMC_CSV.stat().st_size/1e6:.0f} MB)")
        return
    HTMC_DIR.mkdir(parents=True, exist_ok=True)
    zpath = HTMC_DIR / "historicaltopo.zip"
    print(f"[get ] {HTMC_URL}")
    with requests.get(HTMC_URL, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(zpath, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)
    with zipfile.ZipFile(zpath) as z:
        z.extract("historicaltopo.csv", HTMC_DIR)
    zpath.unlink(missing_ok=True)
    print(f"[get ] -> {HTMC_CSV.relative_to(ROOT)}")


def build_scale_lookup() -> dict[tuple[str, str, str], tuple[int, bool]]:
    """``(quad_lower, year, primary_state) -> (map_scale, ambiguous)``.

    Ambiguous keys (>1 distinct scale) collapse to 24000 when present (always,
    for our corpus) else the smallest, and are flagged. Missing keys default to
    24000 at lookup.
    """
    _ensure_htmc()
    inv = pd.read_csv(
        HTMC_CSV, low_memory=False,
        usecols=["map_name", "primary_state", "date_on_map", "map_scale"],
    ).dropna(subset=["map_name", "primary_state", "date_on_map", "map_scale"])
    inv["k_quad"] = inv["map_name"].astype(str).str.lower().str.strip()
    inv["k_year"] = inv["date_on_map"].astype(int).astype(str)
    inv["k_state"] = inv["primary_state"].astype(str).str.strip()
    inv["scale"] = inv["map_scale"].astype(int)

    lookup: dict[tuple[str, str, str], tuple[int, bool]] = {}
    grouped = inv.groupby(["k_quad", "k_year", "k_state"])["scale"]
    for key, scales in grouped:
        uniq = sorted(set(scales))
        if len(uniq) == 1:
            lookup[key] = (uniq[0], False)
        elif DEFAULT_SCALE in uniq:
            lookup[key] = (DEFAULT_SCALE, True)
        else:
            lookup[key] = (uniq[0], True)
    print(f"[scale] inventory keys: {len(lookup):,}")
    return lookup


def attach_scale(df: pd.DataFrame, lookup: dict) -> pd.DataFrame:
    """Resolve ``quad_scale`` per row; report exact/ambiguous/default coverage."""
    df = df.copy()
    scales, exact, ambiguous, default = [], 0, 0, 0
    for _, r in df.iterrows():
        key = (r["quad"].lower(), str(r["year"]), r["state"])
        hit = lookup.get(key)
        if hit is None:
            scales.append(DEFAULT_SCALE)
            default += 1
        else:
            scale, amb = hit
            scales.append(scale)
            if amb:
                ambiguous += 1
            else:
                exact += 1
    df["scale"] = scales
    df.attrs["scale_exact"] = exact
    df.attrs["scale_ambiguous"] = ambiguous
    df.attrs["scale_default"] = default
    return df


# --------------------------------------------------------------------------- #
# 3. County point-in-polygon (offline national TIGER county file)             #
# --------------------------------------------------------------------------- #
def _ensure_county_zip() -> Path | None:
    """Download + cache the national TIGER county zip (2025 -> 2024). Idempotent."""
    TIGER_DIR.mkdir(parents=True, exist_ok=True)
    for yr in COUNTY_YEARS:
        dest = TIGER_DIR / f"tl_{yr}_us_county.zip"
        if dest.exists() and dest.stat().st_size > 0:
            print(f"[skip] {dest.relative_to(ROOT)} "
                  f"({dest.stat().st_size/1e6:.0f} MB)")
            return dest
    for yr in COUNTY_YEARS:
        dest = TIGER_DIR / f"tl_{yr}_us_county.zip"
        url = COUNTY_URL.format(yr=yr)
        print(f"[get ] {url}")
        try:
            with requests.get(url, stream=True, timeout=600) as r:
                if r.status_code != 200:
                    continue
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 16):
                        f.write(chunk)
            return dest
        except Exception as e:  # noqa: BLE001 — try the next year
            print(f"[county] {yr} failed: {e}")
            continue
    return None


def attach_county_group(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """``county_group = f"{NAME}_{state_abbr}"`` via ``within`` PIP (EPSG:4326).

    Points with no county hit fall back to ``Unknown_{state_abbr}``.
    """
    zpath = _ensure_county_zip()
    gdf = gdf.copy()
    if zpath is None:
        print("[county] no TIGER county file; all -> Unknown_*")
        gdf["county_group"] = "Unknown_" + gdf["state_abbr"]
        gdf.attrs["county_fallback"] = int(len(gdf))
        return gdf
    counties = gpd.read_file(f"zip://{zpath}")[["NAME", "geometry"]]
    if str(counties.crs).upper() != "EPSG:4326":
        counties = counties.to_crs("EPSG:4326")
    joined = gpd.sjoin(gdf, counties, how="left", predicate="within")
    joined = joined[~joined.index.duplicated(keep="first")]
    names = joined["NAME"].values
    out = []
    fallback = 0
    for name, abbr in zip(names, gdf["state_abbr"].values):
        if isinstance(name, str) and name:
            out.append(f"{name}_{abbr}")
        else:
            out.append(f"Unknown_{abbr}")
            fallback += 1
    gdf["county_group"] = out
    gdf.attrs["county_fallback"] = fallback
    print(f"[county] resolved {len(gdf)-fallback:,}/{len(gdf):,} "
          f"(fallback Unknown_* = {fallback:,})")
    return gdf


# --------------------------------------------------------------------------- #
# 4. Nearest documented well                                                   #
# --------------------------------------------------------------------------- #
def load_documented() -> gpd.GeoDataFrame:
    """Authoritative documented universe for the nearest-well distance.

    Prefer ``build_documented()`` (raw DOW csv); fall back to the materialized
    ``wells.documented.json`` columnar backbone when the raw csv is absent.
    """
    dow_csv = RAW / "dow" / "US_orphaned_wells.csv"
    if dow_csv.exists():
        return B.build_documented()
    doc_json = PROC / "wells.documented.json"
    print(f"[documented] raw DOW csv absent; using {doc_json.name} "
          "(materialized documented universe)")
    d = json.loads(doc_json.read_text())
    df = pd.DataFrame({"lon": d["lon"], "lat": d["lat"]})
    df["well_id"] = [f"doc_{i}" for i in range(len(df))]
    df["name"] = None
    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326"
    )
    print(f"[documented] {len(gdf):,} documented wells")
    return gdf


# --------------------------------------------------------------------------- #
# 5. Field synthesis                                                           #
# --------------------------------------------------------------------------- #
def _slug(quad: str) -> str:
    return "-".join(str(quad).split())


def synthesize(df: pd.DataFrame) -> pd.DataFrame:
    """Build the 17-field candidate columns from the resolved provenance."""
    df = df.copy()
    df["state_abbr"] = df["state"].map(N.STATE_ABBR)
    df["quad_name"] = df["quad"]
    df["quad_year"] = df["year"].astype(str)
    df["quad_scale"] = df["scale"].astype(str)
    df["quad_id"] = None
    df["quad_slug"] = df["quad"].map(_slug)
    # Running sequence over the full well_id namespace (state, slug, year, scale)
    # so distinct raw quad spellings that slug-collapse (e.g. double spaces)
    # still receive unique ids.
    df["seq"] = df.groupby(
        ["state_abbr", "quad_slug", "quad_year", "quad_scale"]).cumcount()
    df["detection_index"] = df["seq"].astype(int)
    df["layer"] = "candidate"
    df["type_norm"] = N.TYPE_UNKNOWN
    df["status_norm"] = N.STATUS_UNDOCUMENTED
    df["is_plugged"] = False
    df["source"] = "unet_2026"  # our Appalachia U-Net detections (provenance)
    df["well_id"] = [
        f"unet_{ab}_{slug}_{y}_{sc}_geo_{s}"
        for ab, slug, y, sc, s in zip(
            df["state_abbr"], df["quad_slug"], df["quad_year"],
            df["quad_scale"], df["seq"])
    ]
    df["name"] = [
        f"Undocumented well \u00b7 {q} quad ({y})"
        for q, y in zip(df["quad"], df["year"])
    ]
    return df


# --------------------------------------------------------------------------- #
# 6. Merge + write                                                             #
# --------------------------------------------------------------------------- #
KEEP = [
    "well_id", "layer", "name", "county_group", "state_abbr", "state",
    "quad_name", "quad_id", "quad_year", "quad_scale", "detection_index",
    "type_norm", "status_norm", "is_plugged", "lat", "lon", "nearest_doc_well_m",
    "source",  # "unet_2026" provenance tag
]


def _project(gdf: gpd.GeoDataFrame) -> list[dict]:
    """17-field projection with round6 coords + bool is_plugged (mirrors write_candidates)."""
    records = []
    for _, r in gdf.iterrows():
        rec = {k: (None if (k in r and pd.isna(r[k])) else r[k]) for k in KEEP}
        rec["lat"] = B.round6(rec["lat"])
        rec["lon"] = B.round6(rec["lon"])
        rec["is_plugged"] = bool(rec["is_plugged"])
        if rec["nearest_doc_well_m"] is not None:
            rec["nearest_doc_well_m"] = round(float(rec["nearest_doc_well_m"]), 1)
        records.append(rec)
    return records


def merge_and_write(unet_records: list[dict]) -> tuple[int, int]:
    """Strip prior ``unet_*`` from the LBNL base, append fresh, write back.

    Returns (lbnl_kept, total).
    """
    path = PROC / "candidates.base.json"
    existing = json.loads(path.read_text()) if path.exists() else []
    lbnl = [r for r in existing if not str(r.get("well_id", "")).startswith("unet_")]
    merged = lbnl + unet_records
    with open(path, "w") as f:
        json.dump(merged, f, separators=(",", ":"), default=str)
    print(f"[write] {path.relative_to(ROOT)}  "
          f"(LBNL {len(lbnl):,} + U-Net {len(unet_records):,} = {len(merged):,})")
    return len(lbnl), len(merged)


def update_meta(total: int) -> None:
    """Refresh ``candidate_count`` + ``candidate_by_region`` over the merged set."""
    path = PROC / "meta.json"
    if not path.exists():
        print("[meta] meta.json absent; skipping update")
        return
    meta = json.loads(path.read_text())
    base = json.loads((PROC / "candidates.base.json").read_text())
    region = pd.Series([r["county_group"] for r in base]).value_counts()
    meta["candidate_count"] = total
    meta["candidate_by_region"] = region.to_dict()
    # Attribute the U-Net Appalachia rows (well_id 'unet_*') to THIS project's
    # own inference run, and never clobber the LBNL (CA/OK) citation count with
    # the merged total — that mis-credited all wells to the published paper.
    n_unet = sum(1 for r in base if str(r.get("well_id", "")).startswith("unet_"))
    cits = meta.setdefault("citations", {})
    if "lbnl" in cits:
        cits["lbnl"]["n"] = total - n_unet
    cits.setdefault("unet_appalachia", {
        "name": "Lost Wells U-Net detections — Appalachia (this project)",
        "description": ("Fine-tuned inference run of the LBNL CATALOG U-Net "
                        "(Ciulla et al. 2024) over USGS historical topographic quads"),
        "model": "LBNL CATALOG U-Net (Ciulla et al. 2024)",
        "regions": "PA, WV, OH, KY",
    })["n"] = n_unet
    with open(path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"[write] {path.relative_to(ROOT)}  "
          f"(candidate_count={total:,}, regions={len(region):,})")


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #
def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)

    df = read_unet_features()
    features_in = len(df)

    lookup = build_scale_lookup()
    df = attach_scale(df, lookup)
    scale_exact = df.attrs.get("scale_exact", 0)
    scale_ambiguous = df.attrs.get("scale_ambiguous", 0)
    scale_default = df.attrs.get("scale_default", 0)
    scale_from_inv = scale_exact + scale_ambiguous

    df = synthesize(df)

    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326"
    )
    gdf = attach_county_group(gdf)
    county_fallback = gdf.attrs.get("county_fallback", 0)

    docs = load_documented()
    gdf = B.attach_nearest_documented(gdf, docs)
    nearest_null = int(gdf["nearest_doc_well_m"].isna().sum())

    unet_records = _project(gdf)
    lbnl_kept, total = merge_and_write(unet_records)
    update_meta(total)

    # --- Validation report --------------------------------------------------
    ids = [r["well_id"] for r in unet_records]
    dup_ids = len(ids) - len(set(ids))
    print("\n========== U-Net ingest report ==========")
    print(f"  features in            : {features_in:,}")
    print(f"  scale from inventory   : {scale_from_inv:,} "
          f"({100*scale_from_inv/features_in:.2f}%)")
    print(f"    - exact-unique       : {scale_exact:,}")
    print(f"    - ambiguous (->24000): {scale_ambiguous:,}")
    print(f"  scale defaulted (24000): {scale_default:,}")
    print(f"  county resolved        : {features_in - county_fallback:,}")
    print(f"  county fallback Unknown: {county_fallback:,} "
          f"({100*(features_in-county_fallback)/features_in:.1f}% hit)")
    print(f"  nearest-well null      : {nearest_null:,}")
    print(f"  LBNL rows kept         : {lbnl_kept:,}")
    print(f"  U-Net rows written     : {len(unet_records):,}")
    print(f"  total merged           : {total:,}")
    print(f"  duplicate well_id      : {dup_ids}")
    print("=========================================")
    assert dup_ids == 0, f"duplicate well_id detected: {dup_ids}"
    print("[done] U-Net candidates merged ->", (PROC / "candidates.base.json").relative_to(ROOT))


if __name__ == "__main__":
    main()
