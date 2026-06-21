#!/usr/bin/env python3
"""Run resumable U-Net inference over a map manifest.

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
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote, urlparse

import numpy as np
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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


def output_is_complete(path: Path) -> bool:
    """Only a parseable FeatureCollection is a valid resume checkpoint."""
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        return json.loads(path.read_text()).get("type") == "FeatureCollection"
    except (OSError, json.JSONDecodeError):
        return False


def write_json_atomic(path: Path, value: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_text(json.dumps(value, separators=(",", ":")))
    tmp.replace(path)


def is_oom(exc: Exception) -> bool:
    message = f"{type(exc).__name__}: {exc}".lower()
    return "resourceexhausted" in message or "out of memory" in message or "oom" in message


def detect_adaptive(tif: Path, bbox, model, preprocess, doc_lat, doc_lon,
                    requested_batch: int) -> tuple[list[dict], int]:
    """Retry a map with smaller tile batches after a GPU-memory failure."""
    batch = requested_batch
    while True:
        try:
            detections = detect_quad(str(tif), bbox, model, preprocess,
                                     doc_lat, doc_lon, batch_size=batch)
            return detections, batch
        except Exception as exc:  # noqa: BLE001 - TensorFlow exception type varies by runtime
            if not is_oom(exc) or batch == 1:
                raise
            smaller = max(1, batch // 2)
            print(f"[batch]   GPU memory exhausted at batch={batch}; retrying batch={smaller}")
            batch = smaller


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
    ap.add_argument("--batch-size", type=int, default=32,
                    help="initial image tiles per GPU prediction batch (default: 32; OOM halves it)")
    ap.add_argument("--keep-maps", action="store_true",
                    help="retain downloaded GeoTIFFs (default deletes after each map)")
    args = ap.parse_args()

    out_dir = Path(args.out_dir).resolve()
    scratch = Path(args.scratch).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)

    rows = load_manifest(Path(args.manifest), set(args.states) if args.states else None)
    pending = [r for r in rows
               if not output_is_complete(out_dir / f"{safe_id(r)}_UOWs.geojson")]
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
    retry = Retry(total=4, connect=4, read=4, backoff_factor=1,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET",))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    failure_log = out_dir / "failures.jsonl"

    completed = failed = 0
    active_batch = args.batch_size
    started = time.monotonic()

    def download_row(row: dict) -> Path:
        ident = safe_id(row)
        tif_name = Path(unquote(urlparse(row["geotiff_url"]).path)).name
        tif = scratch / f"{ident}_{tif_name}"
        fetch(row["geotiff_url"], tif, session)
        return tif

    # One background worker downloads map N+1 while the GPU processes map N.
    with ThreadPoolExecutor(max_workers=1) as downloads:
        download_future = downloads.submit(download_row, pending[0])
        for index, row in enumerate(pending, 1):
            ident = safe_id(row)
            tif = None
            next_future = (downloads.submit(download_row, pending[index])
                           if index < len(pending) else None)
            out = out_dir / f"{ident}_UOWs.geojson"
            map_started = time.monotonic()
            try:
                bbox = tuple(float(row[k]) for k in ("westbc", "eastbc", "northbc", "southbc"))
                print(f"[batch] {index}/{len(pending)} {row.get('primary_state')} / "
                      f"{row.get('map_name')} ({row.get('date_on_map')})")
                tif = download_future.result()
                detections, used_batch = detect_adaptive(
                    tif, bbox, model, preprocess, doc_lat, doc_lon, active_batch)
                if used_batch < active_batch:
                    active_batch = used_batch
                    print(f"[batch]   using batch={active_batch} for remaining maps")
                write_json_atomic(out, feature_collection(row, detections))
                completed += 1
                elapsed = time.monotonic() - map_started
                average = (time.monotonic() - started) / index
                eta_hours = average * (len(pending) - index) / 3600
                print(f"[batch]   wrote {len(detections)} candidates -> {out.name} "
                      f"({elapsed:.1f}s; ETA {eta_hours:.1f}h)")
            except Exception as exc:  # noqa: BLE001 - continue and checkpoint batch failures
                failed += 1
                record = {"scan_id": row.get("scan_id"), "map_name": row.get("map_name"),
                          "error": f"{type(exc).__name__}: {exc}"}
                with failure_log.open("a") as fh:
                    fh.write(json.dumps(record) + "\n")
                print(f"[batch]   ERROR {record['error']}")
            finally:
                if tif is not None and not args.keep_maps:
                    tif.unlink(missing_ok=True)
                    tif.with_suffix(tif.suffix + ".part").unlink(missing_ok=True)
                download_future = next_future

    print(f"[batch] done: completed={completed}, failed={failed}, output={out_dir}")


if __name__ == "__main__":
    main()
