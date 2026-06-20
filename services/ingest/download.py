"""Download raw source data for Lost Wells (idempotent — skips existing files).

Sources (verified live, see BUILD_PLAN.md §4):
  - USGS DOW  : ScienceBase item 62ebd67bd34eacf539724c56 (DOI 10.5066/P91PJETI)
  - LBNL UOWs : DOE EDX dataset (DOI 10.18141/2452768)

The 294 MB U-Net model weights and the 54 MB CalGEM CSV are intentionally NOT
downloaded here — the U-Net stays documented-but-not-run in this environment
(no GPU). ``services/unet/README.md`` lists their URLs for a GPU host.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import requests
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"

SB = "https://www.sciencebase.gov/catalog/file/get/62ebd67bd34eacf539724c56"
EDX = "https://edx.netl.doe.gov/storage/f/edx"

FILES = {
    "dow/US_orphaned_wells.csv":
        f"{SB}?f=__disk__11%2Fe9%2F27%2F11e927c652d995f46129f282b400063b5d262369",
    "lbnl/found_potential_UOWs.zip":
        f"{EDX}/2024/10/2024-10-16T14:21:37.735330/278aa0a3-0575-475b-96e7-5a5050942349/found_potential_UOWs.zip",
    "lbnl/visible_potential_UOWs.zip":
        f"{EDX}/2024/10/2024-10-16T14:21:22.439497/b4603daf-006a-45f8-a57a-800694ac84c2/visible_potential_UOWs.zip",
}


def fetch(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[skip] {dest.relative_to(ROOT)} ({dest.stat().st_size/1e6:.1f} MB)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"[get ] {dest.relative_to(ROOT)}")
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        with open(dest, "wb") as f, tqdm(total=total, unit="B", unit_scale=True) as bar:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)
                bar.update(len(chunk))


def main() -> None:
    for rel, url in FILES.items():
        fetch(url, RAW / rel)
    for z in RAW.glob("lbnl/*.zip"):
        with zipfile.ZipFile(z) as zf:
            zf.extractall(z.parent)
        print(f"[unzip] {z.name}")
    print("[done] raw sources ready ->", RAW.relative_to(ROOT))


if __name__ == "__main__":
    main()
