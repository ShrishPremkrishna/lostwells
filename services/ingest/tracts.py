"""Census-tract / block-group resolution — the scaling foundation for §2A.

Resolving each well to its 11-digit census tract GEOID lets tract-keyed
enrichment dedup ~117k wells down to a few thousand unique tracts, so the full
universe enriches in minutes instead of hours. Block-group polygons additionally
power true 1-mile population via areal interpolation (see ``enrich_tract.py``).

TIGER/Line shapefiles are downloaded once per needed state (cached, idempotent),
then joined locally — no API, no quota, fully offline after the first pull.

CLI:
    python services/ingest/tracts.py --states OH,WV,PA,NY,KY --kind tract
"""
from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "tiger"

# HANDOFF §2A: TIGER2025 (posted 2025-09-22) is primary; 2024 is the fallback.
TIGER_BASE = "https://www2.census.gov/geo/tiger"
TIGER_YEARS = ("2025", "2024")

# 2-digit state FIPS for the state abbreviations we ingest.
STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08",
    "CT": "09", "DE": "10", "FL": "12", "GA": "13", "HI": "15", "ID": "16",
    "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21", "LA": "22",
    "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28",
    "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34",
    "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39", "OK": "40",
    "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46", "TN": "47",
    "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53", "WV": "54",
    "WI": "55", "WY": "56",
}
FIPS_STATE = {v: k for k, v in STATE_FIPS.items()}


def _zip_url(fips: str, kind: str, year: str) -> str:
    sub = "TRACT" if kind == "tract" else "BG"
    name = "tract" if kind == "tract" else "bg"
    return f"{TIGER_BASE}/TIGER{year}/{sub}/tl_{year}_{fips}_{name}.zip"


def _fetch_one(fips: str, kind: str, dest: Path) -> bool:
    """Try each TIGER year in turn; write the first that succeeds to ``dest``."""
    for year in TIGER_YEARS:
        url = _zip_url(fips, kind, year)
        try:
            with requests.get(url, stream=True, timeout=300) as r:
                if r.status_code != 200:
                    continue
                total = int(r.headers.get("content-length", 0))
                with open(dest, "wb") as f, tqdm(
                    total=total, unit="B", unit_scale=True,
                    desc=f"  tl_{year}_{fips}_{kind}") as bar:
                    for chunk in r.iter_content(chunk_size=1 << 16):
                        f.write(chunk)
                        bar.update(len(chunk))
            return True
        except Exception as e:  # noqa: BLE001 — try the next year
            print(f"[tiger] {year} {fips} {kind} failed: {e}")
            continue
    return False


def download_tiger(states: list[str], kind: str = "tract") -> list[Path]:
    """Fetch + cache TIGER tract/BG zips for each state. Idempotent.

    Tries TIGER2025 first, falling back to TIGER2024 per HANDOFF §2A.
    """
    RAW.mkdir(parents=True, exist_ok=True)
    paths = []
    for st in states:
        fips = STATE_FIPS.get(st.upper())
        if not fips:
            print(f"[tiger] no FIPS for {st}; skip")
            continue
        dest = RAW / f"tl_{fips}_{kind}.zip"
        paths.append(dest)
        if dest.exists() and dest.stat().st_size > 0:
            print(f"[skip] {dest.relative_to(ROOT)} ({dest.stat().st_size/1e6:.1f} MB)")
            continue
        print(f"[get ] {dest.relative_to(ROOT)}")
        if not _fetch_one(fips, kind, dest):
            print(f"[tiger] all years failed for {st} {kind}")
    return paths


def load_polygons(states: list[str], kind: str = "tract") -> gpd.GeoDataFrame:
    """Load TIGER polygons for the given states into one GeoDataFrame (EPSG:4326)."""
    download_tiger(states, kind)
    geoid_col = "GEOID"
    frames = []
    for st in states:
        fips = STATE_FIPS.get(st.upper())
        if not fips:
            continue
        zpath = RAW / f"tl_{fips}_{kind}.zip"
        if not zpath.exists():
            continue
        g = gpd.read_file(f"zip://{zpath}")
        keep = [c for c in (geoid_col, "ALAND", "geometry") if c in g.columns]
        frames.append(g[keep])
    if not frames:
        return gpd.GeoDataFrame(columns=[geoid_col, "geometry"],
                                geometry="geometry", crs="EPSG:4326")
    gdf = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)
    if str(gdf.crs).upper() != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


def _states_in(wells_df: pd.DataFrame) -> list[str]:
    """Infer the states present from a well frame (state_abbr or lat/lon)."""
    if "state_abbr" in wells_df.columns:
        vals = sorted({str(s).upper() for s in wells_df["state_abbr"].dropna()
                       if str(s).upper() in STATE_FIPS})
        if vals:
            return vals
    return []


def resolve_tracts(wells_df: pd.DataFrame, states: list[str] | None = None,
                   kind: str = "tract") -> pd.DataFrame:
    """Attach the 11-digit tract GEOID (or 12-digit BG) to each well via PIP.

    Expects ``lat``/``lon`` columns. Loads only the states present in the well
    set. Returns a copy of ``wells_df`` with a ``tract_geoid`` (or ``bg_geoid``)
    column. Local, offline, no quota.
    """
    states = states or _states_in(wells_df)
    out_col = "tract_geoid" if kind == "tract" else "bg_geoid"
    df = wells_df.copy()
    if not states:
        df[out_col] = None
        return df

    polys = load_polygons(states, kind)
    if polys.empty:
        df[out_col] = None
        return df

    wells = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326"
    )
    joined = gpd.sjoin(wells, polys[["GEOID", "geometry"]],
                       how="left", predicate="within")
    joined = joined[~joined.index.duplicated(keep="first")]
    df[out_col] = joined["GEOID"].values
    n_resolved = int(df[out_col].notna().sum())
    n_tracts = int(df[out_col].nunique())
    print(f"[tracts] resolved {n_resolved:,}/{len(df):,} wells "
          f"-> {n_tracts:,} unique {kind}s")
    return df


def main() -> None:
    import json
    p = argparse.ArgumentParser()
    p.add_argument("--states", default="OH,WV,PA,NY,KY")
    p.add_argument("--kind", default="tract", choices=["tract", "bg"])
    p.add_argument("--input", default="lost_wells.json",
                   help="well file under data/processed to resolve")
    args = p.parse_args()
    states = [s.strip().upper() for s in args.states.split(",") if s.strip()]

    proc = ROOT / "data" / "processed"
    src = proc / args.input
    if src.exists():
        wells = pd.DataFrame(json.loads(src.read_text()))
        resolve_tracts(wells, states, args.kind)
    else:
        # Just warm the TIGER cache.
        download_tiger(states, args.kind)


if __name__ == "__main__":
    main()
