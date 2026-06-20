"""Build the Lost Wells canonical datastore from raw sources.

Inputs (downloaded by ``download.py`` into ``data/raw/``):
  - USGS DOW   : data/raw/dow/US_orphaned_wells.csv   (117,672 documented wells)
  - LBNL UOWs  : data/raw/lbnl/found_potential_UOWs/*.csv  (1,303 candidate UOWs)

Outputs (committed, read by the web app + engine):
  - data/processed/wells.documented.json  compact columnar backbone (all 117k)
  - data/processed/candidates.base.json   canonical candidate records + provenance
  - data/processed/meta.json              counts, state breakdown, citations

The candidate "nearest documented well" distance reproduces the LBNL rule
(a detection >100 m from any documented well is a candidate UOW); we surface
the actual distance as evidence rather than a hard gate.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import normalize as N  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
METRIC_CRS = "EPSG:5070"  # CONUS Albers Equal Area (meters)

CITATIONS = {
    "dow": {
        "name": "USGS Documented Unplugged Orphaned Oil and Gas Well Dataset",
        "authors": "Merrill, M.D., Grove, C.A., Gianoutsos, N.J., and Freeman, P.A., 2023",
        "doi": "10.3133/dr1167",
        "data_doi": "10.5066/P91PJETI",
        "sciencebase": "62ebd67bd34eacf539724c56",
        "n": None,
    },
    "lbnl": {
        "name": "U-Net detected potential Undocumented Orphaned Wells (UOWs)",
        "authors": "Ciulla, F., Santos, A.L.D., Jordan, P., Kneafsey, T., Biraud, S.C., Varadharajan, C., 2024",
        "doi": "10.1021/acs.est.4c04413",
        "data_doi": "10.18141/2452768",
        "n": None,
    },
}


def round6(x):
    return round(float(x), 6)


def build_documented() -> gpd.GeoDataFrame:
    """Load + normalize the 117k DOW documented orphaned wells."""
    print("[documented] reading DOW csv ...")
    df = pd.read_csv(RAW / "dow" / "US_orphaned_wells.csv", low_memory=False)
    df = df.dropna(subset=["Latitude", "Longitude"]).copy()
    df["type_norm"] = df["Type"].map(N.classify_type)
    df["status_norm"] = df["Status"].map(N.classify_status)
    df["is_plugged"] = df["status_norm"].map(N.is_plugged)
    df["state_abbr"] = df["State"].map(N.STATE_ABBR)
    df = df.rename(columns={
        "Well identifier": "well_id", "State": "state", "County": "county",
        "Well name": "name", "Type": "type_raw", "Status": "status_raw",
        "Latitude": "lat", "Longitude": "lon", "Source": "source",
    })
    df["layer"] = "documented"
    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326"
    )
    print(f"[documented] {len(gdf):,} wells | unplugged={int((~gdf['is_plugged']).sum()):,}")
    return gdf


def build_candidates() -> gpd.GeoDataFrame:
    """Load + parse the LBNL candidate UOWs with quad provenance."""
    print("[candidates] reading LBNL csvs ...")
    rows = []
    cdir = RAW / "lbnl" / "found_potential_UOWs"
    for csv in sorted(cdir.glob("*.csv")):
        county_group = csv.stem.replace("_UOWs", "")
        df = pd.read_csv(csv)
        for _, r in df.iterrows():
            uid = r["Potential UOW id"]
            lat, lon = N.parse_coordinates(r["Coordinates"])
            if lat is None:
                continue
            prov = N.parse_candidate_id(uid)
            rows.append({
                "well_id": uid,
                "layer": "candidate",
                "name": f"{prov['quad_name']} detection #{prov['detection_index']}",
                "county_group": county_group,
                "state_abbr": prov["state_abbr"],
                "state": N.ABBR_STATE.get(prov["state_abbr"], prov["state_abbr"]),
                "quad_name": prov["quad_name"],
                "quad_id": prov["quad_id"],
                "quad_year": prov["quad_year"],
                "quad_scale": prov["quad_scale"],
                "detection_index": prov["detection_index"],
                "type_norm": N.TYPE_UNKNOWN,
                "status_norm": N.STATUS_UNDOCUMENTED,
                "is_plugged": False,
                "lat": lat, "lon": lon,
            })
    df = pd.DataFrame(rows)
    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326"
    )
    print(f"[candidates] {len(gdf):,} candidate UOWs across {df['county_group'].nunique()} regions")
    return gdf


def attach_nearest_documented(cands: gpd.GeoDataFrame, docs: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """For each candidate, distance (m) to the nearest documented well."""
    print("[dedup] computing nearest documented well (CONUS Albers) ...")
    c_m = cands.to_crs(METRIC_CRS)
    d_m = docs[["well_id", "name", "geometry"]].to_crs(METRIC_CRS)
    joined = gpd.sjoin_nearest(c_m, d_m, how="left", distance_col="nearest_doc_well_m",
                               lsuffix="cand", rsuffix="doc")
    joined = joined[~joined.index.duplicated(keep="first")]
    cands = cands.copy()
    cands["nearest_doc_well_m"] = joined["nearest_doc_well_m"].round(1).values
    over100 = int((cands["nearest_doc_well_m"] > 100).sum())
    print(f"[dedup] {over100:,}/{len(cands):,} candidates are >100 m from any documented well")
    return cands


def write_documented(gdf: gpd.GeoDataFrame) -> None:
    """Compact columnar JSON: small ints + rounded coords for fast browser load."""
    states = sorted(gdf["state"].dropna().unique().tolist())
    types = sorted(gdf["type_norm"].unique().tolist())
    statuses = sorted(gdf["status_norm"].unique().tolist())
    s_idx = {s: i for i, s in enumerate(states)}
    t_idx = {t: i for i, t in enumerate(types)}
    st_idx = {s: i for i, s in enumerate(statuses)}
    out = {
        "count": len(gdf),
        "state_legend": states,
        "type_legend": types,
        "status_legend": statuses,
        "lon": [round(v, 5) for v in gdf["lon"].tolist()],
        "lat": [round(v, 5) for v in gdf["lat"].tolist()],
        "state_idx": [s_idx.get(s, -1) for s in gdf["state"].tolist()],
        "type_idx": [t_idx[t] for t in gdf["type_norm"].tolist()],
        "status_idx": [st_idx[s] for s in gdf["status_norm"].tolist()],
    }
    path = PROC / "wells.documented.json"
    with open(path, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"[write] {path.relative_to(ROOT)}  ({path.stat().st_size/1e6:.1f} MB)")


def write_candidates(gdf: gpd.GeoDataFrame) -> None:
    keep = [
        "well_id", "layer", "name", "county_group", "state_abbr", "state",
        "quad_name", "quad_id", "quad_year", "quad_scale", "detection_index",
        "type_norm", "status_norm", "is_plugged", "lat", "lon", "nearest_doc_well_m",
    ]
    records = []
    for _, r in gdf.iterrows():
        rec = {k: (None if pd.isna(r[k]) else r[k]) for k in keep}
        rec["lat"] = round6(rec["lat"]); rec["lon"] = round6(rec["lon"])
        rec["is_plugged"] = bool(rec["is_plugged"])
        records.append(rec)
    path = PROC / "candidates.base.json"
    with open(path, "w") as f:
        json.dump(records, f, separators=(",", ":"), default=str)
    print(f"[write] {path.relative_to(ROOT)}  ({len(records)} candidates)")


def write_meta(docs: gpd.GeoDataFrame, cands: gpd.GeoDataFrame) -> None:
    import datetime as dt
    cit = json.loads(json.dumps(CITATIONS))
    cit["dow"]["n"] = len(docs)
    cit["lbnl"]["n"] = len(cands)
    meta = {
        "generated_utc": dt.datetime.utcnow().isoformat() + "Z",
        "documented_count": len(docs),
        "candidate_count": len(cands),
        "documented_by_state": docs["state"].value_counts().to_dict(),
        "candidate_by_region": cands["county_group"].value_counts().to_dict(),
        "citations": cit,
    }
    path = PROC / "meta.json"
    with open(path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"[write] {path.relative_to(ROOT)}")


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    docs = build_documented()
    cands = build_candidates()
    cands = attach_nearest_documented(cands, docs)
    write_documented(docs)
    write_candidates(cands)
    write_meta(docs, cands)
    print("\n[done] datastore materialized ->", PROC.relative_to(ROOT))


if __name__ == "__main__":
    main()
