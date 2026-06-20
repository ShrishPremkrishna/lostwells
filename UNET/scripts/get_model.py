#!/usr/bin/env python3
"""Download LBNL's pretrained CATALOG U-Net + reference data from DOE EDX.

Dataset: "U-Net based USGS Quadrangles Oil and Gas Well Symbols Identification"
(DOI 10.18141/2452768), FREE, no login. We resolve the file list through EDX's
CKAN API (`package_show`) rather than hard-coding storage URLs (those rotate).

Files in the dataset (≈281 MB total):
  unet_model.h5 (~294 MB)            the trained ResNet34-U-Net weights
  predict.ipynb                      LBNL's reference inference notebook
  vetting_tool.py                    LBNL's manual vetting helper
  requirements.txt                   LBNL's original pinned env (TF 2.8 era)
  readme.pdf                         dataset readme
  CA_OilCenter_..._geo.tif / .xml    a sample georeferenced HTMC quad + FGDC meta
  CalGEM_AllWells_*.csv              CA documented wells (for the Kern/CA validation)
  found_potential_UOWs.zip           the published candidate set (validation truth)

Usage:
    python get_model.py --out ../data/lbnl              # all files
    python get_model.py --out ../data/lbnl --only unet_model.h5 predict.ipynb
"""
from __future__ import annotations

import argparse
from pathlib import Path

import requests

CKAN_API = ("https://edx.netl.doe.gov/api/3/action/package_show"
            "?id=u-net-based-usgs-quadrangles-oil-and-gas-well-symbols-identification")
DATASET_PAGE = ("https://edx.netl.doe.gov/dataset/"
                "u-net-based-usgs-quadrangles-oil-and-gas-well-symbols-identification")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "lost-wells-unet/1.0 (research; model fetch)"
    return s


def list_resources(sess: requests.Session) -> list[dict]:
    r = sess.get(CKAN_API, timeout=60)
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"CKAN package_show failed: {data}")
    res = data["result"]["resources"]
    return [{"name": x.get("name") or x.get("url", "").rsplit("/", 1)[-1],
             "url": x.get("url"), "format": x.get("format"),
             "size": x.get("size")} for x in res if x.get("url")]


def download(res: dict, out_dir: Path, sess: requests.Session) -> None:
    name = res["name"]
    # ensure a file extension if CKAN 'name' lacks one
    if "." not in Path(name).name:
        ext = (res.get("format") or "").lower()
        if ext:
            name = f"{name}.{ext}"
    dest = out_dir / Path(name).name
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[model] skip (exists): {dest.name}")
        return
    print(f"[model] downloading {dest.name}  <- {res['url']}")
    with sess.get(res["url"], stream=True, timeout=900) as rr:
        rr.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as fh:
            for chunk in rr.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
        tmp.rename(dest)
    print(f"[model]   -> {dest} ({dest.stat().st_size/1e6:.1f} MB)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="../data/lbnl", help="output dir")
    ap.add_argument("--only", nargs="*", default=None,
                    help="substrings of filenames to fetch (default: all)")
    ap.add_argument("--list", action="store_true", help="list resources and exit")
    args = ap.parse_args()

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    sess = _session()

    try:
        resources = list_resources(sess)
    except Exception as e:  # noqa: BLE001
        raise SystemExit(
            f"[model] could not list EDX resources ({e}).\n"
            f"[model] Open the dataset page and download manually: {DATASET_PAGE}")

    print(f"[model] {len(resources)} resources in the EDX dataset:")
    for r in resources:
        print(f"   - {r['name']}  ({r.get('format')}, {r.get('size')} bytes)")
    if args.list:
        return

    want = resources
    if args.only:
        want = [r for r in resources if any(s.lower() in r["name"].lower() for s in args.only)]
        print(f"[model] filtered to {len(want)} via --only {args.only}")

    for r in want:
        try:
            download(r, out_dir, sess)
        except Exception as e:  # noqa: BLE001
            print(f"[model] ERROR {r['name']}: {e}")
    print(f"[model] done -> {out_dir}")


if __name__ == "__main__":
    main()
