#!/usr/bin/env python3
"""Generate the master and state-specific Colab notebooks.

The notebooks are generated so dependency installation, Drive paths, resume
semantics, and worker commands cannot drift independently between states.
"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks"
COUNTS = {"PA": 809, "WV": 435, "OH": 760, "KY": 701}
NAMES = {"PA": "Pennsylvania", "WV": "West Virginia", "OH": "Ohio", "KY": "Kentucky"}


def markdown(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(text: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": text.splitlines(keepends=True)}


def notebook(cells: list[dict], name: str) -> dict:
    return {"nbformat": 4, "nbformat_minor": 5,
            "metadata": {"colab": {"name": name},
                         "kernelspec": {"name": "python3", "display_name": "Python 3"}},
            "cells": cells}


INSTALL = '''import os, subprocess, sys, importlib.metadata as metadata
os.environ["TF_USE_LEGACY_KERAS"] = "1"
os.environ["SM_FRAMEWORK"] = "tf.keras"

def run(command):
    print("RUN:", " ".join(command))
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    print(result.stdout[-12000:])
    if result.returncode:
        raise RuntimeError(f"command failed with exit code {result.returncode}")

run(["apt-get", "-qq", "update"])
run(["apt-get", "-qq", "install", "-y", "gdal-bin", "libgdal-dev"])
tf_version = metadata.version("tensorflow")
print("Installed TensorFlow:", tf_version)
if not tf_version.startswith("2.20."):
    raise RuntimeError(f"Expected Colab TensorFlow 2.20.x, found {tf_version}; stop and report this")
run([sys.executable, "-m", "pip", "install", "--upgrade",
     "numpy==1.26.4", "opencv-python-headless==4.10.0.84"])
run([sys.executable, "-m", "pip", "install", "--upgrade", "tf_keras==2.20.1"])
run([sys.executable, "-m", "pip", "install", "--upgrade", "--no-deps",
     "keras_applications==1.0.8", "image-classifiers==1.0.0",
     "efficientnet==1.1.1", "segmentation-models==1.0.1"])
run([sys.executable, "-m", "pip", "install", "--upgrade",
     "simplekml==1.3.6", "geopandas", "requests"])
gdal_version = subprocess.check_output(["gdal-config", "--version"], text=True).strip()
run([sys.executable, "-m", "pip", "install", f"GDAL=={gdal_version}"])
print("Install complete. Use Runtime > Restart session before continuing.")'''


def worker_notebook(state: str) -> dict:
    name, count = NAMES[state], COUNTS[state]
    default_output = ("/content/drive/MyDrive/lostwells_unet/outputs"
                      if state in {"PA", "WV"}
                      else "/content/drive/MyDrive/lostwells_unet_outputs")
    cells = [
        markdown(f'''# {name} Lost-Wells Worker ({state})

This notebook processes exactly **{count} latest-edition historical maps** for {name}.
It writes only well-symbol detections more than **100 m** from every loaded documented-well registry point. These are candidates, not confirmed undocumented wells.

Run only one worker per free Colab account. Every completed map is an atomic Drive checkpoint, so reopening and rerunning safely resumes.'''),
        markdown('''## 1. Install the runtime

Choose **Runtime → Change runtime type → T4 GPU**, run this cell once, then choose **Runtime → Restart session**. A restart clears the old NumPy/Keras modules.'''),
        code(INSTALL),
        markdown('''## 2. Mount Drive, configure paths, and update the code

Run this after the restart. Usually only `INPUT_ROOT` or `OUTPUT_ROOT` needs editing. Account 2 should make its shared input-folder shortcut appear as `MyDrive/lostwells_unet`.'''),
        code(f'''import os, subprocess, sys
from pathlib import Path
os.environ["TF_USE_LEGACY_KERAS"] = "1"
os.environ["SM_FRAMEWORK"] = "tf.keras"

from google.colab import drive
drive.mount("/content/drive")

STATE = "{state}"
INPUT_ROOT = Path("/content/drive/MyDrive/lostwells_unet")
OUTPUT_ROOT = Path("{default_output}")
REPO = Path("/content/lostwells")

if REPO.exists():
    subprocess.run(["git", "-C", str(REPO), "pull", "--ff-only"], check=True)
else:
    subprocess.run(["git", "clone", "https://github.com/ShrishPremkrishna/lostwells.git", str(REPO)], check=True)

UNET = REPO / "UNET"
os.chdir(UNET)
print("state:", STATE)
print("inputs:", INPUT_ROOT)
print("outputs:", OUTPUT_ROOT)
print("code:", UNET)'''),
        markdown('''## 3. Prerequisite and GPU gate

All four registries are required even for one state because quadrangles and the 100 m search can cross state borders.'''),
        code('''import json
import tensorflow as tf
import segmentation_models as sm
from osgeo import gdal

MODEL = INPUT_ROOT / "lbnl" / "unet_model.h5"
WELLS = [INPUT_ROOT / "wells" / f"{s}.geojson" for s in ("PA", "WV", "OH", "KY")]
MANIFEST = UNET / "manifests" / "core_appalachia_latest.csv"
STATE_OUT = OUTPUT_ROOT / STATE
STATE_OUT.mkdir(parents=True, exist_ok=True)

required = [MODEL, MANIFEST, *WELLS]
missing = [str(p) for p in required if not p.exists() or p.stat().st_size == 0]
if missing:
    raise FileNotFoundError("Missing required input(s):\\n" + "\\n".join(missing))
gpus = tf.config.list_physical_devices("GPU")
if not gpus:
    raise RuntimeError("No GPU. Select a T4 runtime before inference.")
print("TensorFlow", tf.__version__, "GPU", gpus[0].name)
print("Input gate: PASS")'''),
        markdown('''## 4. Progress before starting

An output counts as complete only when it is valid GeoJSON, including maps with zero candidates.'''),
        code('''import csv, json

with MANIFEST.open(newline="") as fh:
    state_rows = [r for r in csv.DictReader(fh) if r["primary_state"] == {
        "PA":"Pennsylvania", "WV":"West Virginia", "OH":"Ohio", "KY":"Kentucky"}[STATE]]

valid_outputs = []
candidate_count = 0
for path in STATE_OUT.glob("*_UOWs.geojson"):
    try:
        fc = json.loads(path.read_text())
        if fc.get("type") == "FeatureCollection":
            valid_outputs.append(path)
            candidate_count += len(fc.get("features", []))
    except Exception:
        pass

print(f"{STATE}: total maps={len(state_rows)}, completed={len(valid_outputs)}, "
      f"pending={len(state_rows)-len(valid_outputs)}, candidates so far={candidate_count}")'''),
        markdown('''## 5. Run or resume full-state inference

Leave this cell running. The next map downloads in the background while the GPU processes the current map. Batch size starts at 32 and automatically halves after a GPU-memory error. If Colab disconnects, repeat sections 1–5; completed maps are skipped.'''),
        code('''command = [
    sys.executable, "scripts/run_batch.py",
    "--manifest", str(MANIFEST),
    "--model", str(MODEL),
    "--documented", *map(str, WELLS),
    "--out-dir", str(STATE_OUT),
    "--scratch", f"/content/lostwells_maps_{STATE}",
    "--states", STATE,
    "--batch-size", "32",
]
print("Starting/resuming", STATE)
subprocess.run(command, check=True)'''),
        markdown('''## 6. State completion report and reversible 60 m deduplication

The original per-map files remain untouched. The merged file combines nearby repeated detections caused by overlapping map coverage.'''),
        code('''valid_outputs = []
candidate_count = 0
for path in STATE_OUT.glob("*_UOWs.geojson"):
    try:
        fc = json.loads(path.read_text())
        if fc.get("type") == "FeatureCollection":
            valid_outputs.append(path)
            candidate_count += len(fc.get("features", []))
    except Exception:
        pass

print(f"{STATE}: completed {len(valid_outputs)}/{len(state_rows)} maps; "
      f"raw candidates={candidate_count}")
failure_log = STATE_OUT / "failures.jsonl"
if failure_log.exists():
    failures = [line for line in failure_log.read_text().splitlines() if line.strip()]
    print(f"Logged failure attempts: {len(failures)} (reruns retry unfinished maps)")

merged = OUTPUT_ROOT / f"{STATE}_candidates_merged.geojson"
subprocess.run([sys.executable, "scripts/merge_detections.py",
                "--inputs", str(STATE_OUT), "--out", str(merged),
                "--radius-m", "60"], check=True)
print("Merged state output:", merged)'''),
    ]
    return notebook(cells, f"Lost Wells — {state} Worker")


def master_notebook() -> dict:
    cells = [
        markdown('''# Lost Wells — Colab Master Guide

This is the educational setup, validation, and final-merge notebook. Full inference runs in the four state worker notebooks.

**Meaning of an output:** the U-Net finds printed well symbols; a result is saved only when its nearest loaded documented-well coordinate is more than 100 m away. It is a candidate undocumented location, not a confirmed well.'''),
        markdown('''## Architecture from first principles

1. A scanned map is a pixel grid.
2. The pretrained U-Net assigns each pixel a well-symbol probability.
3. Adjacent positive pixels form a connected component; tiny components are rejected.
4. GeoTIFF metadata converts the component center from pixels to WGS84 coordinates.
5. The nearest documented registry point is measured with a great-circle distance.
6. Distances over 100 m are retained as candidates.
7. A separate 60 m merge step removes repeated model detections without deleting the original evidence.'''),
        markdown('''## 1. Optional master-notebook runtime setup

The state workers contain the same installer. For validation or pilot work here, choose **Runtime → Change runtime type → T4 GPU**, run this cell, then choose **Runtime → Restart session**.'''),
        code(INSTALL),
        markdown('''## 2. Mount Drive, update the repository, and verify inputs

Run after restarting. This master notebook never calls the rate-limited EDX API. It uses the files already stored in Drive.'''),
        code('''import os, subprocess, sys, csv
from pathlib import Path
os.environ["TF_USE_LEGACY_KERAS"] = "1"
os.environ["SM_FRAMEWORK"] = "tf.keras"
from google.colab import drive
drive.mount("/content/drive")

INPUT_ROOT = Path("/content/drive/MyDrive/lostwells_unet")
REPO = Path("/content/lostwells")
if REPO.exists():
    subprocess.run(["git", "-C", str(REPO), "pull", "--ff-only"], check=True)
else:
    subprocess.run(["git", "clone", "https://github.com/ShrishPremkrishna/lostwells.git", str(REPO)], check=True)
UNET = REPO / "UNET"
os.chdir(UNET)

MODEL = INPUT_ROOT / "lbnl" / "unet_model.h5"
WELLS = [INPUT_ROOT / "wells" / f"{s}.geojson" for s in ("PA", "WV", "OH", "KY")]
MANIFEST = UNET / "manifests" / "core_appalachia_latest.csv"
missing = [str(p) for p in [MODEL, MANIFEST, *WELLS]
           if not p.exists() or p.stat().st_size == 0]
if missing:
    raise FileNotFoundError("Missing required input(s):\\n" + "\\n".join(missing))
print("Master input gate: PASS")'''),
        markdown('''## 3. Inspect the committed first-pass population

These counts are maps, not wells. The number of candidate wells is unknown until inference runs.'''),
        code('''from collections import Counter
with MANIFEST.open(newline="") as fh:
    manifest_rows = list(csv.DictReader(fh))
counts = Counter(r["primary_state"] for r in manifest_rows)
size_gb = sum(int(r["product_filesize"] or 0) for r in manifest_rows) / 1e9
print("Maps by state:", dict(counts))
print("Total maps:", len(manifest_rows))
print(f"Transient downloads if every map is processed: {size_gb:.1f} GB")
assert len(manifest_rows) == 2705'''),
        markdown('''## 4. Optional Kern reproduction gate

Run this only when the five California reference files remain in `lbnl/`. It proves model loading, preprocessing, tiling, coordinate conversion, and thresholding against released results. Missing optional files skip this gate rather than triggering an API download.'''),
        code('''import zipfile
LBNL = INPUT_ROOT / "lbnl"
sample_tif = LBNL / "CA_OilCenter_293661_1954_24000_geo.tif"
calgem = LBNL / "CalGEM_AllWells_20231128.csv"
archive = LBNL / "found_potential_UOWs.zip"

if all(p.exists() for p in (sample_tif, calgem, archive, MODEL)):
    extract_dir = LBNL / "found_potential_UOWs"
    extract_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(extract_dir)
    published = next(extract_dir.rglob("Kern_CA_UOWs.csv"))
    subprocess.run([sys.executable, "scripts/validate_kern.py",
                    "--quads", str(sample_tif.parent), "--model", str(MODEL),
                    "--documented", str(calgem), "--published", str(published),
                    "--batch-size", "16"], check=True)
else:
    print("Optional Kern files are incomplete; skipping reproduction gate.")'''),
        markdown('''## Repository and Drive layout

Code and the 2,705-map manifest live in GitHub. Large inputs and all outputs remain in Drive:

```text
MyDrive/lostwells_unet/
  lbnl/unet_model.h5
  wells/PA.geojson
  wells/WV.geojson
  wells/OH.geojson
  wells/KY.geojson
  outputs/
```

See `COLAB_RUNBOOK.md` for the complete two-computer procedure.'''),
        markdown('''## Worker allocation

- Computer/account A: `run_WV_colab.ipynb`, then `run_PA_colab.ipynb`.
- Computer/account B: `run_OH_colab.ipynb`, then `run_KY_colab.ipynb`.

Run one GPU notebook per free account. Each worker is restartable.'''),
        markdown('''## Final cross-state merge

Run this after all state outputs are accessible from one Drive account. Set `STATE_OUTPUT_DIRS` to the four per-map directories, not the already-merged state files. The merged GeoJSON retains every original feature, exact source coordinate, property, scan ID, documented-well distance, and input filename under `source_records`.'''),
        code('''import os, subprocess, sys
from pathlib import Path
from google.colab import drive
drive.mount("/content/drive")

REPO = Path("/content/lostwells")
if REPO.exists():
    subprocess.run(["git", "-C", str(REPO), "pull", "--ff-only"], check=True)
else:
    subprocess.run(["git", "clone", "https://github.com/ShrishPremkrishna/lostwells.git", str(REPO)], check=True)
UNET = REPO / "UNET"

# Adjust account-2 paths to the Drive shortcut you created.
STATE_OUTPUT_DIRS = [
    Path("/content/drive/MyDrive/lostwells_unet/outputs/PA"),
    Path("/content/drive/MyDrive/lostwells_unet/outputs/WV"),
    Path("/content/drive/MyDrive/account2_outputs/OH"),
    Path("/content/drive/MyDrive/account2_outputs/KY"),
]
missing = [str(p) for p in STATE_OUTPUT_DIRS if not p.exists()]
if missing:
    raise FileNotFoundError("Update STATE_OUTPUT_DIRS; missing:\\n" + "\\n".join(missing))

FINAL = Path("/content/drive/MyDrive/lostwells_unet/outputs/core_appalachia_candidates.geojson")
subprocess.run([sys.executable, str(UNET/"scripts"/"merge_detections.py"),
                "--inputs", *map(str, STATE_OUTPUT_DIRS),
                "--out", str(FINAL), "--radius-m", "60"], check=True)
print("Final standalone candidate file:", FINAL)'''),
    ]
    return notebook(cells, "Lost Wells — Master Guide")


def main() -> None:
    NOTEBOOKS.mkdir(parents=True, exist_ok=True)
    outputs = {"lost_wells_colab.ipynb": master_notebook()}
    outputs.update({f"run_{state}_colab.ipynb": worker_notebook(state) for state in COUNTS})
    for filename, value in outputs.items():
        path = NOTEBOOKS / filename
        path.write_text(json.dumps(value, indent=1) + "\n")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
