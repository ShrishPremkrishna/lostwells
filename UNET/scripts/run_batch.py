#!/usr/bin/env python3
"""Resumably run U-Net inference over a map manifest.

The model is loaded once. Each GeoTIFF is downloaded into scratch space,
processed, written as an independent GeoJSON checkpoint, then deleted by
default. This keeps a multi-thousand-map Colab run within a small disk budget.

Example:
    python scripts/run_batch.py \
      --manifest data/maps/manifest.csv \
      --model data/lbnl/unet_model.h5 \
      --documented data/wells/OH.geojson data/wells/WV.geojson \
                   data/wells/KY.geojson data/wells/PA.geojson \
      --out-dir outputs/per_quad --limit 10
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unet"))
from infer import detect_quad, load_documented, load_unet  # noqa: E402


STATE_CODES = {
    "PA": "Pennsylvania", "OH": "Ohio", "WV": "West Virginia",
    "KY": "Kentucky", "NY": "New York", "TN": "Tennessee",
    "VA": "Virginia", "MD": "Maryland",
}


def load_manifest(path: Path, states: set[str] | None = None) -> list[dict]:
    with path.open(newline="", encoding="utf-8", errors="replace") as fh:
        rows = list(csv.DictReader(fh))
    if states:
        names = {STATE_CODES.get(s.upper(), s) for s in states}
        rows = [r for r in rows if r.get("primary_state") in names]
    return rows


def load_all_documented(paths: list[str]) -> tuple[np.ndarray, np.ndarray]:
    lat_parts, lon_parts = [], []
    for path in paths:
        lat, lon = load_documented(path)
        lat_parts.append(lat)
        lon_parts.append(lon)
        print(f"[batch] documented: {len(lat):,} points <- {path}")
    if not lat_parts:
        return np.array([]), np.array([])
    return np.concatenate(lat_parts), np.concatenate(lon_parts)


def safe_id(row: dict) -> str:
    raw = row.get("scan_id") or Path(unquote(urlparse(row["geotiff_url"]).path)).stem
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)


def fetch(url: str, dest: Path, session: requests.Session) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    tmp = dest.with_suffix(dest.suffix + ".part")
    with session.get(url, stream=True, timeout=900) as response:
        response.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1 << 20):
                if chunk:
                    fh.write(chunk)
    tmp.replace(dest)


def feature_collection(row: dict, detections: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": [u["lon"], u["lat"]]},
         "properties": {
             "source": "unet_catalog",
             "scan_id": row.get("scan_id"),
             "quad": row.get("map_name"),
             "quad_year": row.get("date_on_map"),
             "state": row.get("primary_state"),
             "dist_to_documented_m": u["dist_to_documented_m"],
         }} for u in detections]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--documented", nargs="+", required=True,
                    help="one or more documented-well GeoJSON/CSV files")
    ap.add_argument("--out-dir", default="outputs/per_quad")
    ap.add_argument("--scratch", default="/tmp/lostwells_maps")
    ap.add_argument("--states", nargs="*", default=None)
    ap.add_argument("--limit", type=int, default=None,
                    help="maximum unfinished maps to process in this invocation")
    ap.add_argument("--batch-size", type=int, default=16,
                    help="image tiles per GPU prediction batch")
    ap.add_argument("--keep-maps", action="store_true",
                    help="retain downloaded GeoTIFFs (default deletes after each map)")
    args = ap.parse_args()

    out_dir = Path(args.out_dir).resolve()
    scratch = Path(args.scratch).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)

    rows = load_manifest(Path(args.manifest), set(args.states) if args.states else None)
    pending = [r for r in rows if not (out_dir / f"{safe_id(r)}_UOWs.geojson").exists()]
    already_complete = len(rows) - len(pending)
    if args.limit is not None:
        pending = pending[:args.limit]
    print(f"[batch] manifest={len(rows):,}; already complete={already_complete:,}; "
          f"this run={len(pending):,}")
    if not pending:
        return

    doc_lat, doc_lon = load_all_documented(args.documented)
    if len(doc_lat) == 0:
        raise SystemExit("[batch] no documented wells loaded; refusing to classify every detection as UOW")

    model, preprocess = load_unet(args.model)
    session = requests.Session()
    session.headers["User-Agent"] = "lost-wells-unet/1.0 (research; batch inference)"
    failure_log = out_dir / "failures.jsonl"

    completed = failed = 0
    for index, row in enumerate(pending, 1):
        ident = safe_id(row)
        tif_name = Path(unquote(urlparse(row["geotiff_url"]).path)).name
        tif = scratch / f"{ident}_{tif_name}"
        out = out_dir / f"{ident}_UOWs.geojson"
        try:
            bbox = tuple(float(row[k]) for k in ("westbc", "eastbc", "northbc", "southbc"))
            print(f"[batch] {index}/{len(pending)} {row.get('primary_state')} / "
                  f"{row.get('map_name')} ({row.get('date_on_map')})")
            fetch(row["geotiff_url"], tif, session)
            detections = detect_quad(str(tif), bbox, model, preprocess,
                                     doc_lat, doc_lon, batch_size=args.batch_size)
            out.write_text(json.dumps(feature_collection(row, detections), separators=(",", ":")))
            completed += 1
            print(f"[batch]   wrote {len(detections)} candidates -> {out.name}")
        except Exception as exc:  # noqa: BLE001 - continue and checkpoint batch failures
            failed += 1
            record = {"scan_id": row.get("scan_id"), "map_name": row.get("map_name"),
                      "error": f"{type(exc).__name__}: {exc}"}
            with failure_log.open("a") as fh:
                fh.write(json.dumps(record) + "\n")
            print(f"[batch]   ERROR {record['error']}")
        finally:
            if not args.keep_maps:
                tif.unlink(missing_ok=True)
                tif.with_suffix(tif.suffix + ".part").unlink(missing_ok=True)

    print(f"[batch] done: completed={completed}, failed={failed}, output={out_dir}")


if __name__ == "__main__":
    main()
