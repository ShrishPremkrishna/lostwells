#!/usr/bin/env python3
"""Download Appalachian HTMC topographic quads for U-Net training.

Acquires georeferenced USGS Historical Topographic Map Collection (HTMC) GeoTIFFs
filtered to the series the LBNL CATALOG model targets: **1:24,000 scale,
7.5-minute series, published 1947-1992**. These scanned quads are the U-Net's
input imagery; documented wells drilled on/before each quad's date supply the
training labels (see ``make_labels.py``).

Data path (all FREE, no key, verified reachable 2026-06-20):
  1. Pull the nightly HTMC inventory CSV (one ~17.5 MB zip -> 184 MB CSV, 186,062
     rows) from the public USGS S3 bucket. This avoids the TNM Access API's
     1000-row pagination entirely.
  2. Filter rows to scale 24000 + grid "7.5 X 7.5 Minute" + 1947<=year<=1992 +
     the requested states.
  3. Download each row's ``geotiff_url`` (a direct, anonymous S3 object) — copy
     the field verbatim rather than constructing paths (the GeoTIFF tree is flat
     by state and map names contain spaces / special chars).

The inventory column order and the S3 layout were probed live; see
``UNET/README.md`` for provenance.

Usage:
    python download_maps.py --states PA OH WV KY --out ../data/maps
    python download_maps.py --states PA --limit 25 --out ../data/maps   # small test
    python download_maps.py --manifest-only --states PA OH WV KY        # list, don't download
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

# Public USGS S3 — anonymous HTTPS, no key. Nightly-refreshed HTMC-only inventory.
INVENTORY_URL = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Maps/Metadata/historicaltopo.zip"
INVENTORY_CSV_NAME = "historicaltopo.csv"

# The series the CATALOG U-Net was trained on (Ciulla et al. 2024).
TARGET_SCALE = "24000"
TARGET_GRID = "7.5 X 7.5 Minute"  # note the capital X, verbatim from the CSV
YEAR_MIN, YEAR_MAX = 1947, 1992

# Appalachian basin states (EPA GHGI "Appalachia" set) + the LBNL well-symbol
# region overlap. `primary_state` in the inventory is the full state name.
APPALACHIA = {
    "PA": "Pennsylvania", "OH": "Ohio", "WV": "West Virginia",
    "KY": "Kentucky", "NY": "New York", "TN": "Tennessee", "VA": "Virginia",
    "MD": "Maryland",
}

CSV_FIELDS_WE_NEED = (
    "scan_id", "map_name", "primary_state", "date_on_map", "map_scale",
    "grid_size", "geotiff_url", "metadata_url", "westbc", "eastbc", "northbc",
    "southbc", "product_filesize",
)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "lost-wells-unet/1.0 (research; training-data fetch)"
    return s


def fetch_inventory(cache_dir: Path) -> Path:
    """Download + extract the HTMC inventory CSV once; cache it locally."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    csv_path = cache_dir / INVENTORY_CSV_NAME
    if csv_path.exists() and csv_path.stat().st_size > 10_000_000:
        print(f"[maps] using cached inventory {csv_path} "
              f"({csv_path.stat().st_size/1e6:.0f} MB)")
        return csv_path
    print(f"[maps] downloading inventory {INVENTORY_URL} (~17.5 MB zip) ...")
    r = _session().get(INVENTORY_URL, timeout=300)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        name = next((n for n in zf.namelist() if n.endswith(".csv")), None)
        if name is None:
            sys.exit("[maps] FATAL: no .csv inside the inventory zip")
        with zf.open(name) as src, open(csv_path, "wb") as dst:
            dst.write(src.read())
    print(f"[maps] extracted {csv_path} ({csv_path.stat().st_size/1e6:.0f} MB)")
    return csv_path


def filter_rows(csv_path: Path, state_names: set[str],
                year_min: int, year_max: int) -> list[dict]:
    """Stream the 184 MB CSV and keep the target series in the target states."""
    keep: list[dict] = []
    # The CSV has 43 columns; DictReader handles ordering by header.
    with open(csv_path, newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("map_scale") != TARGET_SCALE:
                continue
            if (row.get("grid_size") or "").strip() != TARGET_GRID:
                continue
            if row.get("primary_state") not in state_names:
                continue
            try:
                year = int(row.get("date_on_map") or 0)
            except ValueError:
                continue
            if not (year_min <= year <= year_max):
                continue
            if not row.get("geotiff_url"):
                continue
            keep.append({k: row.get(k) for k in CSV_FIELDS_WE_NEED})
    return keep


def write_manifest(rows: list[dict], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    man = out_dir / "manifest.csv"
    with open(man, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS_WE_NEED)
        w.writeheader()
        w.writerows(rows)
    print(f"[maps] wrote manifest of {len(rows)} quads -> {man}")
    return man


def _fetch(url: str, dest: Path, sess: requests.Session) -> None:
    with sess.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
        tmp.rename(dest)


def _download_one(row: dict, out_dir: Path, sess: requests.Session) -> tuple[str, str]:
    url = row["geotiff_url"]
    fname = url.rsplit("/", 1)[-1].replace("%20", " ")
    dest = out_dir / row["primary_state"].replace(" ", "_") / fname
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Also fetch the FGDC metadata XML sidecar (infer.py needs it for the collar
    # crop + dates). Saved next to the GeoTIFF as <stem>.xml.
    xml_url = row.get("metadata_url")
    xml_dest = dest.with_suffix(".xml")
    if dest.exists() and dest.stat().st_size > 0 and xml_dest.exists():
        return ("skip", fname)
    try:
        if not (dest.exists() and dest.stat().st_size > 0):
            _fetch(url, dest, sess)
        if xml_url and not xml_dest.exists():
            try:
                _fetch(xml_url, xml_dest, sess)
            except Exception:  # noqa: BLE001 — XML optional; bbox also in manifest
                pass
        return ("ok", fname)
    except Exception as e:  # noqa: BLE001
        return ("err", f"{fname}: {e}")


def download(rows: list[dict], out_dir: Path, workers: int = 6) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    sess = _session()
    ok = skip = err = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_download_one, r, out_dir, sess) for r in rows]
        for i, fut in enumerate(as_completed(futs), 1):
            status, msg = fut.result()
            if status == "ok":
                ok += 1
            elif status == "skip":
                skip += 1
            else:
                err += 1
                print(f"[maps]   ERROR {msg}")
            if i % 25 == 0 or i == len(futs):
                print(f"[maps] {i}/{len(futs)}  (ok={ok} skip={skip} err={err})")
    print(f"[maps] DONE: {ok} downloaded, {skip} already present, {err} failed "
          f"-> {out_dir}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--states", nargs="+", default=["PA", "OH", "WV", "KY"],
                    help="2-letter state codes (default: PA OH WV KY)")
    ap.add_argument("--out", default="../data/maps", help="output dir for GeoTIFFs")
    ap.add_argument("--cache", default="../data/inventory",
                    help="dir to cache the HTMC inventory CSV")
    ap.add_argument("--year-min", type=int, default=YEAR_MIN)
    ap.add_argument("--year-max", type=int, default=YEAR_MAX)
    ap.add_argument("--limit", type=int, default=None,
                    help="cap number of quads (for a quick test)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--manifest-only", action="store_true",
                    help="write the manifest and exit (no downloads)")
    args = ap.parse_args()

    unknown = [s for s in args.states if s.upper() not in APPALACHIA]
    if unknown:
        print(f"[maps] note: {unknown} not in the built-in Appalachia set "
              f"{sorted(APPALACHIA)} — pass full state names via the inventory if needed.")
    state_names = {APPALACHIA[s.upper()] for s in args.states if s.upper() in APPALACHIA}
    if not state_names:
        sys.exit("[maps] no valid states resolved; nothing to do.")

    out_dir = Path(args.out).resolve()
    cache_dir = Path(args.cache).resolve()

    csv_path = fetch_inventory(cache_dir)
    rows = filter_rows(csv_path, state_names, args.year_min, args.year_max)
    print(f"[maps] {len(rows)} quads match: scale {TARGET_SCALE}, '{TARGET_GRID}', "
          f"{args.year_min}-{args.year_max}, states={sorted(state_names)}")
    if args.limit:
        rows = rows[:args.limit]
        print(f"[maps] limited to {len(rows)} quads")

    write_manifest(rows, out_dir)
    if args.manifest_only:
        total_mb = sum(int(r["product_filesize"] or 0) for r in rows) / 1e6
        print(f"[maps] manifest-only: ~{total_mb:.0f} MB if fully downloaded. "
              f"Drop --manifest-only to fetch.")
        return
    download(rows, out_dir, workers=args.workers)


if __name__ == "__main__":
    main()
