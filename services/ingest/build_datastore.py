"""Build the Lost Wells canonical datastore from raw sources.

Inputs (downloaded by ``download.py`` into ``data/raw/``):
  - USGS DOW   : data/raw/dow/US_orphaned_wells.csv   (117,672 documented wells)
  - LBNL UOWs  : data/raw/lbnl/found_potential_UOWs/*.csv  (1,303 candidate UOWs)

Optional state-registry consolidation (§1.3, ``--states``):
  - data/raw/state_registries/<ST>.geojson  (written by state_registries.py)

Outputs (committed, read by the web app + engine):
  - data/processed/wells.documented.json  compact columnar backbone (DOW ∪ state)
  - data/processed/candidates.base.json   canonical candidate records + provenance
  - data/processed/lost_wells.json        consolidated array (documented ∪ state-added)
  - data/processed/meta.json              counts, state breakdown, citations

The candidate "nearest documented well" distance reproduces the LBNL rule
(a detection >100 m from any documented well is a candidate UOW); we surface
the actual distance as evidence rather than a hard gate.

State registries play a dual role: they *attach* depth/type/status/operator onto
existing documented wells (by API#, spatial fallback ≤50 m) and *expand* the
universe with orphan/abandoned wells the DOW never captured.
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
    "state_registries": {
        "name": "State oil & gas well registries (depth/type/status/operator)",
        "sources": {
            "OH": "Ohio DNR Division of Oil & Gas Resources Management (ArcGIS)",
            "WV": "WV DEP Office of Oil & Gas (TAGIS ArcGIS)",
            "PA": "PA DEP Oil & Gas Locations (PASDA item 1088)",
            "NY": "NY DEC Oil, Gas & Other Regulated Wells (data.ny.gov szye-wmt3)",
            "KY": "Kentucky Geological Survey Oil & Gas (KGS, kyog_dd)",
        },
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
    # DOW's well_id is the API number; canonicalize for the registry join.
    df["api_number"] = df["well_id"].map(N.normalize_api)
    # Attribute slots filled by state-registry consolidation (None until then).
    df["operator"] = None
    df["depth_ft"] = None
    df["discovered_via"] = "usgs_dow"
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


def build_state_registries(states: list[str]) -> gpd.GeoDataFrame:
    """Read the per-state GeoJSON intermediates into one canonical GeoDataFrame."""
    sdir = RAW / "state_registries"
    frames = []
    for st in states:
        path = sdir / f"{st}.geojson"
        if not path.exists():
            print(f"[state] {st}: no intermediate ({path.name}); run state_registries.py")
            continue
        g = gpd.read_file(path)
        if g.empty:
            continue
        g["state_abbr"] = st
        g["state"] = N.ABBR_STATE.get(st, st)
        frames.append(g)
        print(f"[state] {st}: {len(g):,} wells")
    if not frames:
        return gpd.GeoDataFrame(
            columns=["api", "type", "status", "operator", "depth",
                     "state_abbr", "state", "geometry"],
            geometry="geometry", crs="EPSG:4326",
        )
    gdf = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")
    # Canonical schema for the consolidate step.
    gdf = gdf.rename(columns={
        "api": "api_number", "type": "type_norm",
        "status": "status_norm", "depth": "depth_ft",
    })
    gdf["lat"] = gdf.geometry.y
    gdf["lon"] = gdf.geometry.x
    gdf["is_plugged"] = gdf["status_norm"].map(N.is_plugged)
    gdf["layer"] = "state"
    gdf["source"] = "state_" + gdf["state_abbr"].str.lower()
    print(f"[state] total {len(gdf):,} state-registry wells across {len(frames)} states")
    return gdf


def consolidate(
    docs: gpd.GeoDataFrame, state_gdf: gpd.GeoDataFrame, max_snap_m: float = 50.0
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, dict]:
    """Attach state attributes onto DOW wells, then expand with new orphan wells.

    1. **Attach (API):** exact join on 10-digit ``api_number``.
    2. **Attach (spatial):** ``sjoin_nearest`` ≤ ``max_snap_m`` for unmatched.
    3. **Expand:** remaining state wells (no API match, > snap distance) are
       genuinely new orphan/abandoned wells added to the universe.
    """
    stats = {
        "state_wells": int(len(state_gdf)),
        "attached_by_api": 0,
        "attached_by_spatial": 0,
        "new_wells": 0,
        "new_wells_by_state": {},
        "attached_attribute_counts": {"depth_ft": 0, "operator": 0,
                                      "type_norm": 0, "status_norm": 0},
    }
    docs = docs.copy()
    if state_gdf.empty:
        stats["depth_coverage_pct"] = 0.0
        empty = docs.iloc[0:0].copy()
        return docs, empty, stats

    attr_cols = ["depth_ft", "operator", "type_norm", "status_norm"]

    def _apply_attrs(doc_idx, srow) -> None:
        for c in attr_cols:
            val = srow.get(c)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                continue
            # Only overwrite empty DOW slots for depth/operator; for type/status
            # prefer the more-specific state value when DOW is unknown.
            if c in ("depth_ft", "operator"):
                if pd.isna(docs.at[doc_idx, c]) or docs.at[doc_idx, c] is None:
                    docs.at[doc_idx, c] = val
                    stats["attached_attribute_counts"][c] += 1
            else:  # type_norm / status_norm
                cur = docs.at[doc_idx, c]
                unknown = cur in (None, "unknown", "undocumented")
                if unknown and val not in (None, "unknown"):
                    docs.at[doc_idx, c] = val
                    stats["attached_attribute_counts"][c] += 1

    def _clean_api(a) -> str | None:
        # Guard against NaN (float, truthy!) / None / empty so unmatched wells
        # don't all collide on a bogus shared key.
        if a is None or (isinstance(a, float) and pd.isna(a)):
            return None
        s = str(a).strip()
        return s or None

    # --- 1. Attach by API ---------------------------------------------------
    matched_state = set()
    doc_by_api: dict[str, int] = {}
    for idx, a in docs["api_number"].items():
        a = _clean_api(a)
        if a and a not in doc_by_api:
            doc_by_api[a] = idx
    for s_idx, srow in state_gdf.iterrows():
        a = _clean_api(srow.get("api_number"))
        if a and a in doc_by_api:
            _apply_attrs(doc_by_api[a], srow)
            matched_state.add(s_idx)
            stats["attached_by_api"] += 1

    # --- 2. Spatial fallback for unmatched state wells ----------------------
    remaining = state_gdf.drop(index=list(matched_state))
    if not remaining.empty:
        docs_m = docs[["geometry"]].to_crs(METRIC_CRS)
        rem_m = remaining.to_crs(METRIC_CRS)
        joined = gpd.sjoin_nearest(
            rem_m, docs_m, how="left", distance_col="snap_m",
            lsuffix="state", rsuffix="doc",
        )
        joined = joined[~joined.index.duplicated(keep="first")]
        snapped_state = set()
        for s_idx, jrow in joined.iterrows():
            dist = jrow.get("snap_m")
            doc_idx = jrow.get("index_doc")
            if dist is not None and not pd.isna(dist) and dist <= max_snap_m \
                    and doc_idx is not None and not pd.isna(doc_idx):
                _apply_attrs(int(doc_idx), state_gdf.loc[s_idx])
                snapped_state.add(s_idx)
                stats["attached_by_spatial"] += 1
        matched_state |= snapped_state

    # --- 3. Expand: genuinely new state wells -------------------------------
    new_wells = state_gdf.drop(index=list(matched_state)).copy()
    if not new_wells.empty:
        ids, names = [], []
        for i, (a, st) in enumerate(
                zip(new_wells["api_number"], new_wells["state_abbr"])):
            api = _clean_api(a)
            ids.append(f"state_{api}" if api else f"state_{st}_{i}")
            names.append(f"{st} orphan well {api}".strip() if api
                         else f"{st} orphan well")
        new_wells["well_id"] = ids
        new_wells["name"] = names
        new_wells["county"] = None
        new_wells["discovered_via"] = "state_registry"
        new_wells["layer"] = "documented"  # part of the documented universe now
        stats["new_wells"] = int(len(new_wells))
        stats["new_wells_by_state"] = (
            new_wells["state_abbr"].value_counts().to_dict())

    depth_known = int(docs["depth_ft"].notna().sum())
    if not new_wells.empty:
        depth_known += int(new_wells["depth_ft"].notna().sum())
    total = len(docs) + (0 if new_wells.empty else len(new_wells))
    stats["depth_coverage_pct"] = round(100.0 * depth_known / total, 2) if total else 0.0
    print(f"[consolidate] attached: {stats['attached_by_api']:,} by API + "
          f"{stats['attached_by_spatial']:,} spatial; "
          f"new wells: {stats['new_wells']:,}; "
          f"depth coverage {stats['depth_coverage_pct']}%")
    return docs, new_wells, stats


def _union_universe(docs: gpd.GeoDataFrame, new_wells: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """DOW (attribute-enriched) ∪ state-added wells, aligned on shared columns."""
    if new_wells is None or new_wells.empty:
        return docs
    cols = [c for c in docs.columns if c in new_wells.columns]
    merged = pd.concat([docs[cols], new_wells[cols]], ignore_index=True)
    return gpd.GeoDataFrame(merged, geometry="geometry", crs="EPSG:4326")


def write_lost_wells(universe: gpd.GeoDataFrame) -> None:
    """The §1.4 deliverable: consolidated array-of-objects with new attributes."""
    keep = ["well_id", "layer", "name", "state", "state_abbr", "county",
            "type_norm", "status_norm", "is_plugged", "api_number", "operator",
            "depth_ft", "discovered_via", "lat", "lon"]
    keep = [c for c in keep if c in universe.columns]
    records = []
    for _, r in universe.iterrows():
        rec = {k: (None if (k in r and pd.isna(r[k])) else r[k]) for k in keep}
        if "lat" in rec and rec["lat"] is not None:
            rec["lat"] = round6(rec["lat"])
        if "lon" in rec and rec["lon"] is not None:
            rec["lon"] = round6(rec["lon"])
        if "is_plugged" in rec and rec["is_plugged"] is not None:
            rec["is_plugged"] = bool(rec["is_plugged"])
        if "depth_ft" in rec and rec["depth_ft"] is not None:
            rec["depth_ft"] = float(rec["depth_ft"])
        records.append(rec)
    path = PROC / "lost_wells.json"
    with open(path, "w") as f:
        json.dump(records, f, separators=(",", ":"), default=str)
    print(f"[write] {path.relative_to(ROOT)}  ({len(records):,} wells, "
          f"{path.stat().st_size/1e6:.1f} MB)")


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


def write_meta(
    docs: gpd.GeoDataFrame,
    cands: gpd.GeoDataFrame,
    universe: gpd.GeoDataFrame | None = None,
    consolidate_stats: dict | None = None,
) -> None:
    import datetime as dt
    cit = json.loads(json.dumps(CITATIONS))
    cit["dow"]["n"] = len(docs)
    cit["lbnl"]["n"] = len(cands)
    universe = universe if universe is not None else docs
    meta = {
        "generated_utc": dt.datetime.utcnow().isoformat() + "Z",
        "documented_count": len(docs),
        "candidate_count": len(cands),
        "consolidated_count": int(len(universe)),
        "documented_by_state": docs["state"].value_counts().to_dict(),
        "candidate_by_region": cands["county_group"].value_counts().to_dict(),
        "citations": cit,
    }
    if consolidate_stats:
        cit["state_registries"]["n"] = consolidate_stats.get("state_wells")
        meta["new_wells_by_state"] = consolidate_stats.get("new_wells_by_state", {})
        meta["attached_attribute_counts"] = consolidate_stats.get(
            "attached_attribute_counts", {})
        meta["attached_by_api"] = consolidate_stats.get("attached_by_api", 0)
        meta["attached_by_spatial"] = consolidate_stats.get("attached_by_spatial", 0)
        meta["depth_coverage_pct"] = consolidate_stats.get("depth_coverage_pct", 0.0)
    path = PROC / "meta.json"
    with open(path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"[write] {path.relative_to(ROOT)}")


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--states", default="OH,WV,PA,NY,KY",
                   help="state registries to consolidate (empty to skip)")
    args = p.parse_args()
    states = [s.strip().upper() for s in args.states.split(",") if s.strip()]

    PROC.mkdir(parents=True, exist_ok=True)
    docs = build_documented()
    cands = build_candidates()
    cands = attach_nearest_documented(cands, docs)

    consolidate_stats = None
    universe = docs
    if states:
        state_gdf = build_state_registries(states)
        docs, new_wells, consolidate_stats = consolidate(docs, state_gdf)
        universe = _union_universe(docs, new_wells)
        write_lost_wells(universe)

    write_documented(universe)
    write_candidates(cands)
    write_meta(docs, cands, universe, consolidate_stats)
    print("\n[done] datastore materialized ->", PROC.relative_to(ROOT))


if __name__ == "__main__":
    main()
