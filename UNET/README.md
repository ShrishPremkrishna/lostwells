# UNET — Detect Undocumented Orphaned Wells in Appalachia (CATALOG U-Net)

Run LBNL's **pretrained** CATALOG U-Net (Ciulla et al. 2024) on historical USGS
topographic maps to find oil/gas **well symbols**, then keep the ones **>100 m
from any documented well** as candidate **Undocumented Orphaned Wells (UOWs)**.

**Plan = inference-first.** The recommended path is to run the released
`unet_model.h5` *as-is* on Appalachian quads — the USGS well symbol is national
and standardized, so the CA/OK-trained model transfers. Fine-tuning is an
**optional fallback**, included here, only if Appalachian accuracy disappoints.

Everything below is grounded in primary sources: LBNL's own `predict.ipynb` +
`requirements.txt`, the released checkpoint's embedded training config, and the
open-access paper (PMC11656717). Verified facts that drove the code:

| Thing | Verified value | Source |
|---|---|---|
| Model | `sm.Unet('resnet34', classes=1, activation='sigmoid')`, input `[None,None,None,3]` | checkpoint config + predict.ipynb |
| Preprocessing | `sm.get_preprocessing('resnet34')` (ImageNet) — **not** `/255` | predict.ipynb |
| Tiling | 256×256, **25 px overlap**; pad short edges with 255 | predict.ipynb |
| Blob filter | `cv2.connectedComponentsWithStats`, keep **area ≥ 45 px** | predict.ipynb |
| Collar | crop the map margin via the FGDC XML bbox before tiling | predict.ipynb |
| UOW rule | detection **> 100 m** (haversine) from any documented well | predict.ipynb |
| Train loss/opt | `BinaryFocalCrossentropy(γ=2)`, Adam **lr≈5e-5**, `BinaryIoU(0.5)` | released checkpoint |
| Labels (paper) | **manual Labelme** annotation, 11,046 wells, **r=4px discs** @ ~2 m/px | PMC11656717 |

---

## 0. Environment (pick ONE)

The model was saved in 2022 with **TF 2.8 / Keras 2.8 / segmentation-models
1.0.1**. The blocker: segmentation-models 1.0.1 needs **Keras 2**; stock TF 2.16+
ships Keras 3 and `import segmentation_models` then fails
(`AttributeError: module 'keras.utils' has no attribute 'generic_utils'`). Three
working runtimes, in order of preference:

**A. Your own GPU host / Modal / Docker, Python ≤ 3.11 (cleanest):**
```bash
conda create -n unet python=3.10 -y && conda activate unet
conda install -c conda-forge gdal -y          # GDAL python bindings (osgeo)
pip install -r requirements.txt               # TF 2.15 + sm 1.0.1 + numpy<2, etc.
```
TF 2.15 is the **last** TF where `tensorflow.keras` *is* Keras 2 — so the `.h5`
loads with **no shims**. A free Colab **T4 (16 GB)** is plenty; a quad predicts in
tens of seconds.

**B. Google Colab (ships Python 3.12 + TF 2.19 + Keras 3 — can't install old TF):**
use the official legacy-Keras-2 shim. First cell, **before any import**:
```python
import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
os.environ["SM_FRAMEWORK"] = "tf.keras"
!pip install -q tf_keras keras_applications image-classifiers==1.0.0 \
    efficientnet==1.1.1 segmentation-models==1.0.1 "numpy<2" \
    opencv-python-headless simplekml geopandas
!apt-get -qq install -y gdal-bin libgdal-dev && pip install -q GDAL==$(gdal-config --version)
```
Then load the `.h5` and **verify it deserializes** before going further.

**C. Exact 2022 reproduction (most faithful):** the NVIDIA NGC container ships
TF 2.8.0:
```bash
docker run --gpus all -it nvcr.io/nvidia/tensorflow:22.05-tf2-py3
pip install segmentation-models==1.0.1 "numpy<2" opencv-python simplekml geopandas
conda install -c conda-forge gdal   # or apt libgdal-dev
```

> NumPy **must** be `<2` for all three (TF<2.18 + sm 1.0.1 predate the NumPy-2 ABI).

---

## 1. Get the model + reference data (DOE EDX, free, no login)

```bash
cd scripts
python get_model.py --out ../data/lbnl        # unet_model.h5 (~294 MB) + predict.ipynb,
                                              # CalGEM CSV, sample quad, published UOWs
```
Resolves files via EDX's CKAN API (robust to URL changes). `--list` to preview.

## 2. Validate on Kern County FIRST (go/no-go)

Reproduce LBNL's published Kern detections before trusting new ground.
```bash
# get a few Kern, CA quads (sample quad already comes with get_model.py)
python download_maps.py --states CA --limit 10 --out ../data/maps      # or use EDX sample
python validate_kern.py \
    --quads ../data/maps/California \
    --model ../data/lbnl/unet_model.h5 \
    --documented ../data/lbnl/CalGEM_AllWells_20231128.csv \
    --published ../../data/raw/lbnl/found_potential_UOWs/Kern_CA_UOWs.csv
```
**PASS** = ≥70 % of published Kern UOWs reproduced within ~60 m. If it fails, fix
the env (model load / preprocessing / threshold) before Appalachia — don't push on.

## 3. Run inference on Appalachia (the main event)

```bash
# a) maps: Appalachian HTMC quads (1:24k, 7.5-min, 1947-1992) + FGDC XML sidecars
python download_maps.py --states PA OH WV KY --out ../data/maps
#    (preview size first with --manifest-only)

# b) documented wells for dedup (state registries are best; or reuse the USGS DOW)
python download_wells.py --states OH WV KY PA --out ../data/wells
python dow_to_geojson.py --states Pennsylvania Ohio "West Virginia" Kentucky \
    --out ../data/wells/dow_appalachia.geojson

# c) detect, per quad
python ../unet/infer.py \
    --tif ../data/maps/Ohio/OH_Somequad_..._geo.tif \
    --xml ../data/maps/Ohio/OH_Somequad_..._geo.xml \
    --model ../data/lbnl/unet_model.h5 \
    --documented ../data/wells/OH.geojson \
    --out-dir ../outputs
```
Each run writes `<quad>_UOWs.geojson`. Loop over the quads in `../data/maps/<State>/`.
If a quad's XML is missing, pass `--bbox WEST EAST NORTH SOUTH` from
`../data/maps/manifest.csv` instead (the collar crop still works).

**Hand-off to the app:** merge the per-quad `*_UOWs.geojson` and drop the
collection at `data/raw/unet_detections/<region>.geojson` — the Lost Wells
pipeline ingests it (see repo `HANDOFF.md` §Section 1.1; the 100 m dedup tags
anything >100 m from a documented well as a discovery).

---

## 4. (Optional) Fine-tune — only if Appalachian inference is poor

⚠️ **Honest caveat:** LBNL trained on **manual Labelme annotations**, not database
points. Auto-labeling from a well database (below) is an approximation: the UOWs
you want aren't in the DB (so they're unlabeled → caps recall), and post-map wells
must be date-filtered out. Prefer inference-first; fine-tune only as a fallback,
ideally adding some manual annotation. Fine-tuning starts FROM `unet_model.h5`
(never from scratch) at the checkpoint's own LR (5e-5).

```bash
# 1) auto-generate (image, mask) tiles: r=4px discs at documented wells whose
#    date <= the quad's map year. --date-field names the DB's date column.
python make_labels.py --maps ../data/maps/Ohio \
    --wells ../data/wells/OH.geojson --date-field COMPLETIONDATE \
    --out ../data/patches/OH

# 2) fine-tune from the pretrained checkpoint
python finetune.py --tiles ../data/patches/OH ../data/patches/WV \
    --model ../data/lbnl/unet_model.h5 \
    --out ../checkpoints/unet_appalachia.h5 --epochs 25 --batch 8

# 3) infer with the fine-tuned model (same infer.py, swap --model)
```
Per-state date fields to confirm before labeling: OH (permit/completion date on
the ODNR layer), WV (`WellStatus`/spud on TAGIS), KY (status/date in the KGS
shapefile attrs), PA (no depth; spud/permit on PASDA). Verify the exact column
name in the GeoJSON `properties` before trusting the temporal filter.

---

## Files

```
UNET/
  README.md              this file
  AGENT_HANDOFF.md       brief for a coding agent to take over
  requirements.txt       pinned env (TF 2.15 + sm 1.0.1 + numpy<2)
  unet/infer.py          detection — faithful port of LBNL predict.ipynb (USE THIS)
  scripts/
    get_model.py         fetch unet_model.h5 + refs from EDX (CKAN API)
    download_maps.py     Appalachian HTMC quads + FGDC XML (topoView inventory -> S3)
    download_wells.py    documented wells per state (dedup + labels)
    dow_to_geojson.py    convert the committed USGS DOW datastore to GeoJSON
    validate_kern.py     reproduce LBNL's Kern detections (go/no-go)
    make_labels.py       (optional) auto-label tiles for fine-tuning
    finetune.py          (optional) fine-tune from unet_model.h5
  data/ outputs/ checkpoints/   created at runtime (git-ignored)
```

## Notes & gotchas (all verified)

- **Resolution:** HTMC 1:24k GeoTIFFs are ~2 m/px, matching the model's training
  scale, so native-res tiling (what `infer.py`/`predict.ipynb` do) is correct. If
  a particular quad is much finer than ~2 m/px, downsample to ~2 m/px (and raise
  the label disc radius proportionally for fine-tuning).
- **Datum:** HTMC maps are often NAD27. The ~20-40 m eastern-US NAD27→WGS84 shift
  is *larger* than a well symbol, so coordinates are always reprojected through
  the GeoTIFF's embedded CRS (`infer.py` does this) — never stamped as raw WGS84.
- **`area≥45`** at inference is the matched counterpart of the paper's r=4px
  (area≈49) training disc — keep them consistent if you fine-tune.
- **No GPU? loading still works on CPU** (slow); the wheels just require Python ≤
  3.11 for TF 2.15 (or use the Colab/NGC paths).
- The repo's older `services/unet/infer.py` is a superseded sketch — **use
  `UNET/unet/infer.py`**, which reproduces LBNL's method exactly.
