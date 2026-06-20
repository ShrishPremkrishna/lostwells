# UNET — Agent Handoff

Brief for a coding agent taking over the U-Net detection task. Read `README.md`
first; this adds the "why" and the failure-handling a fresh agent needs.

## Goal
Run LBNL's **pretrained** CATALOG U-Net (`unet_model.h5`) on Appalachian HTMC
quads to produce candidate UOWs as GeoJSON, hand off to the Lost Wells pipeline
(`data/raw/unet_detections/<region>.geojson`, ingested per repo `HANDOFF.md`
§Section 1.1). **Inference-first** — do not train from scratch; fine-tuning is a
documented fallback only.

## Ground truth (don't re-derive — these are primary-source-verified)
- Model: `sm.Unet('resnet34', classes=1, activation='sigmoid')`, sigmoid output,
  input `[None,None,None,3]`. Loaded via `keras.models.load_model(h5, compile=False)`
  AFTER `import segmentation_models` (which registers `swish`/`FixedDropout`).
- Preprocess `sm.get_preprocessing('resnet34')`; tile 256 w/ 25px overlap; blob
  `area≥45`; collar-crop via FGDC XML bbox; UOW = >100 m from documented.
- Checkpoint training config (from the weights): `BinaryFocalCrossentropy(γ=2)`,
  Adam lr≈5e-5, `BinaryIoU(0.5)`.
- Labels in the paper were **manual Labelme discs (r=4px)**, NOT DB rasterization
  — so `make_labels.py` (auto from DB) is an approximation; flag this to the user.
- The repo's `services/unet/infer.py` is a WRONG earlier sketch; the correct
  pipeline is `UNET/unet/infer.py`.

## Environment (the one real trap)
segmentation-models 1.0.1 needs Keras 2. Stock TF 2.16+ (Keras 3) breaks
`import segmentation_models`. Use ONE of: (A) TF 2.15 + sm 1.0.1 + numpy<2 on
Python ≤3.11 [cleanest]; (B) Colab via `tf_keras` shim
(`TF_USE_LEGACY_KERAS=1`, `SM_FRAMEWORK=tf.keras`, then pip the sm deps); (C) NGC
`nvcr.io/nvidia/tensorflow:22.05-tf2-py3` (TF 2.8). NumPy must be `<2`. GDAL via
conda-forge or `apt libgdal-dev` + `pip install GDAL==$(gdal-config --version)`.

## Run order
1. `get_model.py` → model + CalGEM + sample quad + published Kern UOWs.
2. `validate_kern.py` → must reproduce ≥70% of Kern UOWs within ~60 m. **Gate.**
3. `download_maps.py --states PA OH WV KY` (+ XML) and `download_wells.py` /
   `dow_to_geojson.py` for dedup.
4. `unet/infer.py` per quad → `*_UOWs.geojson`; merge; hand to the app.
5. Fine-tune only if Kern passes but Appalachia is noisy: `make_labels.py` →
   `finetune.py` (from `unet_model.h5`, lr 5e-5) → re-infer with the new weights.

## Failure handling (don't quit — escalate down this list)
- **Model won't load** (`generic_utils`/`get_custom_objects` AttributeError) →
  wrong Keras. Switch to env A (TF 2.15) or set the tf_keras shim (env B). Verify
  with a 1-line `load_model(..., compile=False)` before anything else.
- **Kern validation fails** → check (a) preprocessing is `sm.get_preprocessing`,
  not /255; (b) the collar is cropped (XML/bbox present); (c) threshold 0.5 +
  area≥45; (d) quad resolution ≈2 m/px. Only after these, consider the model file
  is corrupt (re-download via `get_model.py`).
- **A quad's XML 404s** → pass `--bbox` from `data/maps/manifest.csv`; infer.py
  still crops the collar.
- **Detections look like noise in the margin** → collar not cropped (missing
  bbox). Supply it.
- **State endpoint down** (download_wells) → every state has a bulk/mirror in repo
  `HANDOFF.md` §Section 1.3; or rely on `dow_to_geojson.py` (USGS DOW, 27 states).
- **No GPU** → inference runs on CPU (slow but works); or use Colab T4 (env B).

## Floors
- If fine-tuning underperforms, **ship inference-first results** — the pretrained
  model on Appalachia is the deliverable; new detections >100 m from documented
  wells are genuine discoveries.
- Report counts honestly: "N high-confidence candidate UOWs, validated vs
  imagery," never "confirmed wells."
