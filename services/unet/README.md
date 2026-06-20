# U-Net UOW detection — documented pipeline

Extends LBNL's CATALOG U-Net (Ciulla et al. 2024, *Environ. Sci. Technol.*,
DOI [10.1021/acs.est.4c04413](https://doi.org/10.1021/acs.est.4c04413)) to detect
oil/gas well symbols on historical USGS topographic maps. A detected symbol
**>100 m** from any documented well is a candidate **Undocumented Orphaned Well (UOW)**.

> **Why this isn't run in the Lost Wells app:** there is no GPU in the build
> sandbox, and the model degrades off the 1947–1992 1:24,000 symbology it was
> trained on. The app instead serves LBNL's **1,301 pre-computed candidates** as
> the detection layer (already ingested). This pipeline is the real, runnable
> "extend the detector to new ground" path — run it on a GPU host.

## 1. Get the model + data (DOE EDX, DOI 10.18141/2452768)

From <https://edx.netl.doe.gov/dataset/u-net-based-usgs-quadrangles-oil-and-gas-well-symbols-identification>:

| File | Purpose |
|---|---|
| `unet_model.h5` (294 MB) | the trained U-Net weights |
| `CA_OilCenter_293661_1954_24000_geo.tif` | a sample georeferenced HTMC quad |
| `predict.ipynb`, `vetting_tool.py` | LBNL's reference inference + vetting |
| `CalGEM_AllWells_20231128.csv` | CA documented wells (for dedup) |
| `found_potential_UOWs.zip` | the 1,301 published candidates (validation truth) |

Documented wells for national dedup come from the USGS DOW already ingested here:
`data/processed/wells.documented.json` (convert to GeoJSON, or export from the
ingest step).

## 2. Install + run

```bash
pip install -r requirements.txt   # tensorflow, rasterio, geopandas, scipy, ...

python infer.py \
  --model      unet_model.h5 \
  --geotiff    CA_OilCenter_293661_1954_24000_geo.tif \
  --documented documented_wells.geojson \
  --threshold  0.5 \
  --out        detections_uows.geojson
```

`infer.py` tiles the GeoTIFF into 256×256 patches, runs the U-Net, thresholds the
mask, takes each blob's centroid, reprojects pixel→map CRS→EPSG:4326 (rasterio
reads the embedded NAD27/other datum — it does **not** assume WGS84), then keeps
detections >100 m from any documented well.

## 3. Validate on Kern County FIRST

Before trusting new ground, reproduce LBNL's published detections:

1. Download the Kern County HTMC quads (TNM Access API / topoView CSV inventory,
   filtered to **scale 1:24,000, 7.5-minute series, 1947–1992**).
2. Run `infer.py` over them with `CalGEM_AllWells` as `--documented`.
3. Compare your candidate UOWs against `Kern_CA_UOWs.csv` from
   `found_potential_UOWs.zip` (304 published Kern candidates). You should land
   within ~10 m of their detections.

**Threshold to change course (spec §6):** if Kern validation doesn't reproduce
LBNL's detections within a few hours, drop live inference and rely on the
pre-computed candidates + DOW backbone — the app already does exactly this.

## 4. National sparse pass (prep, not live)

Pick ~10–20 quads in each of ~15–25 legacy oil/gas states (~300–600 quads),
cache detections as GeoJSON, and merge into `data/processed/candidates.*`. This
is a real, defensible "national" pass — **not** dense national coverage, which
is infeasible in the prep window (tens of millions of patch inferences).
