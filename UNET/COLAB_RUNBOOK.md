# Appalachian U-Net Colab Runbook

This is the operator guide for the full 2,705-map inference run. The four state
workers are resumable and intended for two computers using two free Colab
accounts.

## 1. Understand the output

The workers do not output documented wells. They:

1. Detect printed well symbols on historical maps.
2. Measure each detection against all four loaded state registries.
3. Discard detections within 100 m of a documented coordinate.
4. Save detections more than 100 m away as candidate undocumented locations.

Candidates still require additional registry and imagery review. They are not
confirmed wells.

The committed first-pass manifest contains the latest eligible 1947–1992,
1:24,000, 7.5-minute map edition for each quadrangle:

| State | Maps |
|---|---:|
| Pennsylvania | 809 |
| West Virginia | 435 |
| Ohio | 760 |
| Kentucky | 701 |
| **Total** | **2,705** |

## 2. What belongs in GitHub and Drive

GitHub contains code, notebooks, and
`manifests/core_appalachia_latest.csv`. Do not commit the model, registries,
GeoTIFFs, or outputs.

Account 1 should already have:

```text
MyDrive/lostwells_unet/
  lbnl/
    unet_model.h5
  wells/
    PA.geojson
    WV.geojson
    OH.geojson
    KY.geojson
  outputs/
```

All four registry files are required by every worker because maps and the 100 m
nearest-well search can cross state borders.

## 3. Give account 2 access to inputs

On account 1:

1. Open Google Drive.
2. Share the `lostwells_unet` folder with account 2.
3. Viewer access is sufficient for reading inputs. Do not use that shared folder
   for account 2's outputs.

On account 2:

1. Open **Shared with me**.
2. Select the shared `lostwells_unet` folder.
3. Choose **Organize → Add shortcut**.
4. Add the shortcut directly under **My Drive** and keep its name
   `lostwells_unet`.
5. Create `MyDrive/lostwells_unet_outputs/` for account 2's own output files.

The resulting account-2 Drive tree must look like this:

```text
MyDrive/
  lostwells_unet/                 # shortcut to account 1's shared input folder
    lbnl/
      unet_model.h5
    wells/
      PA.geojson
      WV.geojson
      OH.geojson
      KY.geojson
  lostwells_unet_outputs/         # real folder owned by account 2; initially empty
```

The blank `lostwells_unet_outputs` folder by itself is not sufficient. The OH
and KY workers must also be able to read the model and all four registries
through `MyDrive/lostwells_unet`. The committed manifest comes from the GitHub
checkout and does not need to be copied into Drive.

The OH and KY notebooks default to reading the shortcut and writing to
`lostwells_unet_outputs`. If the shortcut has a different name, edit only
`INPUT_ROOT` in section 2 of those notebooks.

### Extra files in account 1's `lostwells_unet`

Extra folders do not affect inference. Workers read only the exact model and
registry paths above and write only to their configured output paths. Do not
delete extra files merely to make the folder look cleaner.

If Drive storage becomes constrained, the following are normally safe to
remove after checking the required inputs and outputs exist:

- Previously downloaded `.tif` map images; the workers download maps into
  temporary Colab storage.
- Cached USGS inventory ZIP/CSV files; the exact manifest is committed in Git.
- Extracted PA/KY shapefile folders after `PA.geojson` and `KY.geojson` exist.
- Temporary pilot or review GeoTIFFs.

Keep:

- `lbnl/unet_model.h5`.
- All four `wells/<STATE>.geojson` files.
- Every state output directory and merged GeoJSON.
- California reference files if you want to rerun the optional Kern validation.

## 4. Push the code before opening Colab

The generated notebooks clone the `main` branch from GitHub. Local changes must
therefore be committed and pushed first. From the repository root, review and
then run:

```bash
git status
git add UNET
git commit -m "Add resumable state Colab inference workers"
git push origin main
```

Do not use `git add -f` on ignored data. Confirm no `.h5`, `.tif`, registry
GeoJSON, or output files appear in the commit.

## 5. Worker allocation

Run one GPU worker per free Colab account:

| Computer/account | First worker | Second worker |
|---|---|---|
| A | `run_WV_colab.ipynb` | `run_PA_colab.ipynb` |
| B | `run_OH_colab.ipynb` | `run_KY_colab.ipynb` |

This balances the map counts reasonably well. Do not run two GPU notebooks
simultaneously under the same free account.

## 6. Start a state worker

For each state:

1. In GitHub, open `UNET/notebooks/run_<STATE>_colab.ipynb`.
2. Choose **Open in Colab**.
3. In Colab choose **Runtime → Change runtime type → T4 GPU**.
4. Run section 1, the dependency installer.
5. Choose **Runtime → Restart session** after installation completes.
6. Run section 2 to mount Drive and clone/update the repository.
7. Verify `INPUT_ROOT` and `OUTPUT_ROOT` printed by the cell.
8. Run section 3. Do not continue unless it prints `Input gate: PASS` and shows
   a GPU.
9. Run section 4 and record the completed/pending counts.
10. Run section 5. Leave it running.

The runner begins with 32 image tiles per GPU call. If that exhausts GPU memory,
it automatically retries at 16 and uses 16 for the remainder of that invocation.
The next GeoTIFF downloads in the background during current-map inference.

## 7. Resume after a Colab interruption

Each completed map is saved atomically as a valid `*_UOWs.geojson`. A partially
written file is not accepted as complete.

If the tab disconnects but the runtime still exists:

1. Reconnect.
2. Rerun sections 2–5.

If Colab deleted the runtime:

1. Select a T4 GPU again.
2. Rerun section 1.
3. Restart the session.
4. Rerun sections 2–5.

Do not redownload the model or registries. The runner scans Drive and skips every
valid completed map. A map that failed or was interrupted is retried.

## 8. Monitor the run

For each map, the worker prints:

- State, quadrangle, and year.
- Candidate count.
- Elapsed seconds.
- Estimated remaining hours for the current invocation.

An unusually large count can be legitimate in a dense historical field, as the
Venango pilot showed. It should be sampled visually rather than automatically
discarded.

`failures.jsonl` records failed attempts. It can contain old failures that later
succeeded, so completion is determined by valid per-map GeoJSON files, not by
the raw number of log lines.

## 9. Finish a state

When section 5 ends, run section 6. A complete state reports:

```text
completed <state map count>/<state map count> maps
```

Section 6 also writes `<STATE>_candidates_merged.geojson`. The original per-map
files remain unchanged.

The 60 m merge radius is only for duplicate model detections from overlapping
map coverage. It is independent from the 100 m documented-well exclusion rule.

## 10. Transfer account 2 outputs

After OH and KY complete, account 2 should share
`lostwells_unet_outputs` with account 1. On account 1, add a shortcut under
`MyDrive` named `account2_outputs`.

The expected paths on account 1 are then:

```text
/content/drive/MyDrive/lostwells_unet/outputs/PA
/content/drive/MyDrive/lostwells_unet/outputs/WV
/content/drive/MyDrive/account2_outputs/OH
/content/drive/MyDrive/account2_outputs/KY
```

## 11. Final cross-state merge

Open `notebooks/lost_wells_colab.ipynb` and run its final merge cell. Confirm the
four `STATE_OUTPUT_DIRS` paths match the paths above.

The final standalone result is:

```text
MyDrive/lostwells_unet/outputs/core_appalachia_candidates.geojson
```

This merge is reversible: all per-map state evidence remains available.

## 12. Do not fine-tune during this run

This is pretrained-model inference, not training. Fine-tuning requires manually
complete Appalachian symbol annotations and a quadrangle-level validation split.
Database points alone are not sufficient labels because undocumented wells are
missing from the databases by definition.
