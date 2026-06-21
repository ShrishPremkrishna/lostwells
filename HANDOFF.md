# Lost Wells — Engineering Handoff

> **Audience:** a fresh Claude Code session in this same environment (same
> `ANTHROPIC_API_KEY`, full outbound web access). **Goal:** take the current
> honest-but-shallow prioritization dashboard and build it into the intended
> product — a **live national "lost wells" intelligence & advocacy platform**
> organized as a three-section value chain: **Discover → Diagnose → Act**.
>
> Everything below was **researched and reachability-probed on 2026-06-20**.
> HTTP codes, record counts, field names, and file sizes are real observations,
> not guesses. Every external dependency has **ranked backup plans** so you never
> dead-end. When a primary fails, walk down its backup list before changing scope.

---

## 0. How to read this document

- **§1 product brief + §2 codebase map + §3 principles** = read first, always.
- **Section 1 / 2 / 3** = the three product sections, each self-contained with
  exact endpoints, auth, query patterns, the repo files to create/extend, and a
  **BLOCKERS + RANKED BACKUPS** block.
- **§7 live backend / UI / deploy** = the cross-cutting delivery layer.
- **§8 sequencing**, **§9 master endpoint table**, **§10 floors** = execution.
- **Agent manuals (companion files):** `BROWSER_BASED_AGENT_TRAINING.md` =
  investigative-agent doctrine + per-goal query ladders (the spec for the §2D
  investigator); `STRUCTURED_PROPERTY_INFORMATION.md` = coordinate→parcel-owner via
  free ArcGIS REST (the spec for §3.6 landowner lookup). Read them before building
  the agent layer.
- Symbols: ✅ probed live & working · ⚠️ works but flaky/caveated · ❌ dead (use
  the mirror). "FREE" = no key, no payment unless stated.

**Prime directives (do not violate):**
1. **Positioning: we are a router / intelligence / advocacy layer — NOT a
   marketplace and NOT a licensed plugging operator.** The product's verb is
   **mobilize, not plug**. For every well it produces a *case file naming who can
   act* (responsible party, funder, pressure point) + a sourced story. Never
   imply we take money, hold liability, or perform abandonment.
2. **Free-first.** Every capability must work on free, keyless (or free-key)
   public data. Paid sources (Regrid, PACER, ND bulk, Enverus) are *optional
   upgrades* that must degrade gracefully to a free fallback.
3. **U-Net detections are USER-PROVIDED.** The user is training/running the LBNL
   U-Net collaboratively in a separate session and will hand you a detections
   file. You do **not** need a GPU. You ingest the artifact (see §Section 1.1).
   If it has not arrived, the consolidated DB is itself a valid Section-1 floor.
4. **Honesty is a feature.** Every named operator / liability / landowner /
   actor claim must be **sourced + confidence-tagged**. "Here's what the public
   record shows," never an accusation. Detection = "high-confidence candidate,"
   never "confirmed well." Keep the existing `PROGRESS.md` candor.

---

## 1. The product in one page

Today (`PROGRESS.md` is the honest audit): 117,672 USGS documented wells +
1,303 LBNL candidates, joined to CDC SVI + NCES schools, scored, with a live
12-well Claude web-search swarm. Its novelty is *integration*, not *new impact*:
0 net-new wells, methane is **one constant** across all candidates, human
exposure is only ~82% computed (no drinking water / hospitals), and there is **no
path to action**. The three sections below fix exactly those gaps.

| Section | Verb | Output | The gap it closes |
|---|---|---|---|
| **1 Discover** | *find & consolidate* | one deduped `lost_wells` datastore = USGS DOW + LBNL + **new U-Net detections** + state registries | 0 net-new wells → a few genuinely new discoveries + a far larger consolidated universe |
| **2 Diagnose** | *build the case* | complete evidence profile for **every** well (deterministic) + deep agentic dossier for the **top ~100–300** | constant methane / 82% exposure / no liability research → differentiated, fully-computed, sourced |
| **3 Act** | *mobilize* | per-well **pathway-to-plugging + actor map + sourced story** → `case_files.json` | no path to action → a named who-can-act for any well, live |

**Hackathon win condition:** a unified browsable/searchable DB; a *few* genuine
U-Net discoveries; a *big* number of wells through the deterministic loop;
~100–300 fully cased; the **full loop demonstrable live on an arbitrary well**;
and **≥1 well cased end-to-end through a named landowner**.

---

## 2. What already exists (reuse map)

Repo root: `/home/user/lostwells`. Branch in use: **`main`** (the build session
worked on `main` per direction; `PROGRESS.md` §3.11 notes this). Last commit
`caed230`. **Confirm with the user which branch to continue on** before pushing —
this handoff itself goes wherever the user directs.

```
services/
  ingest/   download.py  normalize.py  build_datastore.py  enrich.py  heroes.py
  engine/   methane.py  plugcost.py  carbon.py  scoring.py  score_candidates.py  tests/test_engine.py
  swarm/    investigator.py  graph.py  run_swarm.py        # LangGraph Send map-reduce
  unet/     infer.py  README.md                            # documented, never run (no GPU)
apps/web/   (Next.js App Router + TS + Tailwind + MapLibre + deck.gl)
  app/page.tsx  app/layout.tsx
  components/  MapView.tsx  RankedList.tsx  DossierPanel.tsx  SwarmPanel.tsx  TopoDissolve.tsx  Legend.tsx  IntroOverlay.tsx  ScoreBar.tsx
  lib/  data.ts  types.ts  colors.ts  format.ts
  scripts/copy-data.mjs            # copies data/processed/*.json -> public/data at pre(dev|build)
data/processed/  *.json            # committed datastore (the app reads these)
data/cache/enrich.sqlite           # enrichment response cache
```

**Reuse as-is (these are good):**
- **`services/swarm/investigator.py`** — the *exact proven pattern* to port to TS
  for the live route (raw `anthropic` SDK, `web_search_20260209` with
  `_20250305` fallback, `client.messages.stream()` → `stream.get_final_message()`,
  `pause_turn` continuation loop, source extraction from `web_search_tool_result`,
  `<dossier>…</dossier>` JSON parse). Driven by SDK (not LangChain) because
  `ChatAnthropic` **hangs** in this sandbox; **streaming** because non-streaming
  web search gets **idle-dropped** by the egress proxy. Keep both lessons.
  **Note (§2W):** keep the `web_search_*` server tool as the free, default web
  layer; the only addition is **one** `browser_task` tool (Browserbase Stagehand)
  for facts behind a form/login/WAF that `web_search` can't reach — the streaming,
  the continuation loop, the sentinel, and the `<dossier>` parse all stay.
- **`services/ingest/enrich.py`** — generic `(lat,lon)→dict` thread-pool + SQLite
  cache. Extend with new `lookup_*()` funcs and the tract-dedup key (§Section 2A).
- **`services/engine/scoring.py`** — `METRIC_CONFIG` / `DEFAULT_WEIGHTS` /
  `GROUPS` / `METRIC_LABELS`; percentile-normalized; breakdown sums to composite;
  missing metrics renormalized (not zeroed). Extend with new metric keys.
- **`services/engine/methane.py`** — replace the two constant EF tuples with the
  GHGI regional factors (§Section 2B). `plugcost.py`, `carbon.py` stay.
- **`apps/web/components/MapView.tsx`** (~L99–124) — deck.gl **binary-attribute**
  ScatterplotLayer (already correct; 60fps to ~1M points, no tiling needed).
- **`data/processed/wells.documented.json`** — already **columnar** (`count` +
  `state_legend` + parallel arrays) → 703 KB gzip for 117,672 wells. Keep this
  format; it is exactly what deck.gl binary attrs and the CDN want.

**Create new:** `apps/web/app/api/investigate/[id]/route.ts` (live SSE),
`services/engine/pathways.py`, `services/engine/actors.py`,
`services/engine/story.py`, `services/engine/assemble_cases.py`, plus
`services/ingest/enrich_tract.py` (or extend `enrich.py`), a
`state_registries.py` ingester, and `services/swarm/web/cache.py` (the §2R Redis
semantic-cache wrapper).

**Sponsor tools — tightly scoped (do not spread them):** **Redis** (`redisvl`)
is the one semantic cache in front of the agent investigation (§2R); **Browserbase**
(`@browserbasehq/stagehand`) is the one browser-automation escalation for facts
behind a form/login/WAF that Claude's free `web_search` can't reach — chiefly the
landowner lookup for the demo subset (§2W, §3.6). The general web layer stays free
Anthropic `web_search`. Each sponsor earns its place against a real blocker;
neither is wired anywhere else. `graph.py` keeps its in-process `MemorySaver()`
as-is.

---

## 3. Cross-cutting principles

1. **Ingest once, serve from cache.** Federal endpoints move and throttle. A
   Python pipeline hits each source *once*, materializes committed JSON; the app
   + live route read that. Nothing fragile fetches on stage.
2. **Tract-dedup point-in-polygon is the scaling key (read §Section 2A first).**
   Never call a per-well API at 119k scale. Resolve wells → census tract via a
   *local* PIP against downloaded TIGER tracts, dedup to ~15–25k unique tracts,
   query each tract once (or download the national tract table and join locally).
   The whole national enrichment then runs in **< 1 hour**, dominated by file
   downloads, not API calls.
3. **Detection ≠ confirmation; naming names has stakes.** See prime directives.
4. **Live backend is real and free (see §7).** Vercel **Fluid compute** (default
   since 2025-04-23) gives the **Hobby** plan **300 s** function duration, so a
   ~120 s streaming Claude investigation runs live on the free tier — no Pro, no
   separate Python service required.

---

# SECTION 1 — DISCOVER & CONSOLIDATE

**Goal:** emit `data/processed/lost_wells.json` (+ documented columnar) = USGS
DOW ∪ LBNL ∪ **new U-Net detections** ∪ (optionally) state registries, each
tagged `source`, `documented|undocumented`, `status`, with the 100 m
nearest-documented dedup applied. New U-Net points >100 m from any documented
well = **wells this project discovered**.

## 1.1 U-Net detections — USER-PROVIDED integration contract

The user runs/trains the LBNL CATALOG U-Net (Ciulla et al. 2024) and hands you an
artifact. **Your job is integration, not inference.** Define and accept this
contract:

- **Expected artifact:** a GeoJSON `FeatureCollection` (or CSV with `lat,lon`) of
  detections, ideally one file per region, dropped at
  `data/raw/unet_detections/<region>.geojson`.
- **Per-feature fields you should consume (degrade gracefully if absent):**
  `lon, lat` (required), `confidence` (0–1), `quad_name`, `quad_year`,
  `quad_scale`, `source_quad_url`, `model_version`. If only `lat,lon` arrive,
  synthesize a `well_id` (`uow_<region>_<index>`), default `confidence=null`,
  `status_norm="undocumented"`, `source="unet_2026"`.
- **Integration point:** extend `services/ingest/build_datastore.py` to treat the
  detections as a new source in its union, then run the existing
  `attach_nearest_documented` 100 m rule. Anything ≥100 m from a documented well
  is a **discovery**; tag it and count it in `meta.json`
  (`discovery_count_by_region`, `discovery_count_by_source`).
- **Validation gate (do this when the artifact arrives):** if the user includes a
  **Kern County** run, reproduce against LBNL's published
  `data/raw/lbnl/found_potential_UOWs/Kern_CA_UOWs.csv` — detections should land
  within ~10 m of LBNL's. That is the go/no-go for trusting new ground.
- **Spot-check** a sample of new detections against satellite imagery (ESRI
  `World_Imagery`) and keep the `confidence` flag visible in the UI. Report "N
  high-confidence candidate UOWs, validated vs satellite," never "confirmed."

**Floor:** if no detections arrive in time, ship the consolidated
DOW+LBNL+state DB (itself novel as a unified, enriched, actionable layer) and
frame U-Net discovery as the *live novel layer to extend*. Do not let the demo
ride on the model behaving.

## 1.2 HTMC topo acquisition (context for the U-Net session — you likely won't run this)

This is documented so the doc is complete and so you can help the user's training
session if asked. The existing `services/unet/infer.py` already does
tile→predict→threshold→centroid→reproject→100 m-dedup; it needs georeferenced
1:24000 7.5-minute HTMC quads, 1947–1992.

**★ PRIMARY — topoView nightly CSV inventory (best for bulk date/scale filtering):**
- HTMC-only inventory ZIP (~17.5 MB → `historicaltopo.csv`, 184 MB, 186,062 rows):
  `https://prd-tnm.s3.amazonaws.com/StagedProducts/Maps/Metadata/historicaltopo.zip` ✅ (nightly refresh)
- Filter columns: `map_scale == 24000` AND `grid_size == "7.5 X 7.5 Minute"` AND
  `1947 <= date_on_map <= 1992`; then fetch the per-row **`geotiff_url`** (direct
  S3, ready to download — copy it verbatim, don't construct paths).

**★ SECONDARY — TNM Access API `/products`** (server-side bbox/polygon filtering):
- `https://tnmaccess.nationalmap.gov/api/v1/products?datasets=Historical%20Topographic%20Maps&bbox=<minX,minY,maxX,maxY>&prodFormats=GeoTIFF&prodExtents=7.5%20x%207.5%20minute&dateType=Publication&start=1947-01-01&end=1992-12-31&max=1000&offset=0&outputFormat=JSON` ✅
- Gotchas: `prodExtents=7.5 x 7.5 minute` is **required** (bbox alone returns
  mixed scales); `dateType=Publication` (the string `"Publication Date"` →
  HTTP 400 non-JSON body, guard for it); **`max` hard-caps at 1000** → paginate
  with `offset` until `offset ≥ total`.

**TERTIARY — direct S3 bucket** `https://prd-tnm.s3.amazonaws.com/` (anonymous,
listable via `?list-type=2&prefix=StagedProducts/Maps/HistoricalTopo/GeoTIFF/`).
GeoTIFF tree is **flat by state**: `…/GeoTIFF/{ST}/{ST}_{MapName}_{scan_id}_{year}_{scale}_geo.tif` (spaces → `%20`).

**Target regions (richest in *undocumented historical* wells):** Appalachia
(PA/OH/WV) first, then California outside LBNL's Kern/LA, then Illinois Basin.
De-prioritize the Permian (too modern/documented).

## 1.3 State orphaned/abandoned well registries — the consolidation floor

These widen the documented universe *and* (critically for Section 2) provide
**depth / type / status / operator** so methane and plug-cost stop being
constants. **Pattern:** nearly every state exposes a public **ArcGIS REST
`/query`** endpoint and/or a bulk download. Filter the master layer on its status
field for orphan/abandoned/plugged (most states don't keep a separate file).
Generic query shape:
`…/FeatureServer/<n>/query?where=1=1&outFields=*&f=geojson` (page with
`resultOffset`/`resultRecordCount`; caps are 1000–2000/req). Point query:
`…/query?geometry=<lon>,<lat>&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=*&f=json`.

**Attribute legend:** API=API# · LL=lat/lon · TYP=type · STAT=status · OP=operator · DEP=depth.

### Appalachia + Northeast
| State | Canonical endpoint | Count | API·LL·TYP·STAT·OP·DEP | Notes |
|---|---|---|---|---|---|
| **OH** | `https://services5.arcgis.com/ajRlmtxbNBjZggOT/arcgis/rest/services/Oil_And_Gas_Wells/FeatureServer/3` ✅ | 242,145 | Y·Y·Y·Y·Y·**Y** (`TOTAL_DEPTH`) | richest; status = `WELL_STATUS_DESCRIPTION`; one-shot CSV via Hub item `e03ec46046af49c49d879ab9be07f980` |
| **WV** | `https://tagis.dep.wv.gov/arcgis/rest/services/WVDEP_enterprise/oil_gas/MapServer/7` ✅ | 153,842 | Y·Y·Y·Y·Y·**Y** (`WellDepth`) | layer 4 = plugged; Open Data CSV item `371f4703e0974e3cb79d40a0ca4e8ee5` (`?layers=7` or `4`) |
| **PA** | PASDA 1088 (live registry, incl. orphan/abandoned status): `https://www.pasda.psu.edu/uci/DataSummary.aspx?dataset=1088` ✅ + REST `https://mapservices.pasda.psu.edu/server/rest/services/pasda/DEP/MapServer` | — | Y·Y·Y·Y·**Y**·**N** | **no depth**; legacy layer = PASDA 1137 (Historic O&G Wells); `OPERATOR` present in bulk |
| **NY** | Socrata `szye-wmt3` (full, queryable): `https://data.ny.gov/resource/szye-wmt3.json` ✅ + orphan subset `vgue-bamz` (7,948) | 47,407 | Y·Y·Y·Y·Y·**Y** (full depth suite) | nightly `wellDOS.zip` CSV alt; join `vgue-bamz`→`szye-wmt3` on `api_well_number` for coords |
| **KY** | KGS shapefile (162,132, weekly): `https://kgs.uky.edu/ogdata/kyog_dd.zip` ✅ + meta `…/kyog_info.txt` | 162,132 | Y·Y·Y·Y·Y·Y | no orphan-specific flag published; filter status field |

### Midwest / Plains
| State | Canonical endpoint | Count | Notes |
|---|---|---|---|
| **IL** | `https://maps.isgs.illinois.edu/arcgis/rest/services/ILOIL/Wells/MapServer/8` ✅ | 207,103 | all 6 attrs (`API_NUMBER,STATUS_TEXT,COMPANY_NAME,TOTAL_DEPTH`); `%Plugged%`=104,205, `%Abandoned%`=60,727 |
| **IN** | `https://gisdata.in.gov/server/rest/services/Hosted/OilAndGasWells/FeatureServer/0` ✅ (+ join `/1` on `igs_id` for TYP+DEP) | 78,257 | **no true API#** (keys `permit_number`/`igs_id`); depth only via Completion table (~42% coverage) |
| **MI** | `https://gisagocss.state.mi.us/arcgis/rest/services/OpenData/geology/MapServer/3` ✅ | 95,303 | all 6 (`api_wellno,well_type,well_stat,co_name,tvd`); dedicated orphan FS (1,026) at `utility.arcgis.com/usrsvcs/servers/359eff2fb8ee49528969bce36c731d55/rest/services/EGLE/OGMDOrphanedWells/FeatureServer/0`; **legacy `gisp.mcgi.state.mi.us/...DEQ/OilandGas` is DEAD** |
| **KS** | `https://services.kgs.ku.edu/arcgis8/rest/services/oilgas/oilgas_wells/MapServer/0` ✅ | 516,763 | all 6 (`API_NUMBER,WELL_TYPE,STATUS,OPERATOR_NAME,ROTARY_TOTAL_DEPTH`); NAD27 → request `f=geojson`; `www.kgs.ku.edu` host was 503 but `services.kgs.ku.edu` is fine |
| **OK** | `https://gis.occ.ok.gov/server/rest/services/Hosted/RBDMS_WELLS/FeatureServer/2` ✅ | — | `symbol_class='ORPHAN'`=18,482; **NO depth in any OCC GIS layer** (depth → RBDMS Data Explorer); orphan-funds layer 221 |
| **MO** | `https://gis.dnr.mo.gov/host/rest/services/geology/oil_gas_wells/MapServer/0` ✅ | 10,369 | all 6 (`API_NUMBER,WELL_TYPE,STATUS,OPERATOR,TOTAL_DPTH`); orphan/abandoned/plugged = 9,202 |

### West / API-number → operator (free ArcGIS REST `/query`, keyless)
| State | Operator-by-API endpoint | Operator field | API format |
|---|---|---|---|
| **CO** (ECMC) | `https://data.dnrgis.state.co.us/arcgis/rest/services/DNR_Public/OGCC_Wells/FeatureServer/0/query` ✅ | `Operator` | `API_Label` `05-123-19844`; bulk shapefile `https://ecmc.state.co.us/documents/data/downloads/gis/WELLS_SHP.ZIP` (daily) |
| **NM** (OCD) | `https://gis.emnrd.nm.gov/arcgis/rest/services/OCDView/Wells_Public/FeatureServer/0/query` ✅ | `ogrid_name` | `id` `30-045-08708` |
| **CA** (CalGEM) | `https://gis.conservation.ca.gov/server/rest/services/WellSTAR/Wells/MapServer/0/query` ✅ | `OperatorName` | `API` `0403300003`; bulk CSV `https://gis-cnra.hub.arcgis.com/api/download/v1/items/ef53080fdf894761858dd1728610b9a0/csv?layers=0` |
| **WY** (WSGS mirror) | `https://portal.wsgs.wyo.gov/ags/rest/services/OilGas/Data_layers/MapServer` (layer 11) ✅ | header DB | safer than WOGCC site |
| **TX** (RRC) | **operator NOT on GIS** — use EWA Wellbore Query `https://webapps2.rrc.texas.gov/EWA/ewaMain.do` ⚠️ (503 intermittent) or bulk Full Wellbore + **P-5 Organization** files (EBCDIC fixed-width) | — | join API→P-5 |
| **ND** (DMR) | per-well free `https://www.dmr.nd.gov/oilgas/findwellsvw.asp` ✅; **bulk index = paid** ($100–500/yr) | — | per-well only on free tier |

**API-matching caveat:** public layers key on the **10-digit** API (state-county-sequence). Truncate any 14-digit input to 10 digits. CO/NM store dashed `SS-CCC-SSSSS`; CA stores `04`+8 digits no dashes; KS has both `API_NUMBER` (dashed) and `API_NUM_NODASH`.

**RBDMS leverage:** KS, OK, NM, CA, ND run on **RBDMS Core** (near-identical
schema) — an extractor built for one ports cheaply to the others.

## 1.4 Dedup & unified datastore
Extend `build_datastore.py`: union all sources, normalize via `normalize.py`
field maps, apply `attach_nearest_documented` (100 m). Emit
`data/processed/lost_wells.json` (undocumented records, array-of-objects) +
documented columnar (keep existing format). Update `meta.json` with discovery +
consolidation counts by source/region.

## 1.5 BLOCKERS + RANKED BACKUPS (Section 1)
- **U-Net artifact late/absent** → (1) ship consolidated DOW+LBNL+state DB as the
  Section-1 deliverable; (2) frame U-Net as the live novel layer; (3) ingest a
  small hand-validated detection sample if the user provides one.
- **A state REST endpoint down** → every state above has a bulk download or Hub
  mirror fallback (listed); also the national USGS DOW already covers 27 states.
- **TX operator gap** → EWA query → P-5 bulk join → FracTracker TX extract
  (`https://www.fractracker.org/data/data-resources/`) as convenience cross-check.
- **Hosts that block automation** (`www.kgs.ku.edu` 503, ISGS clearinghouse WAF
  503, `gis.in.gov` curl 000, michigan.gov 403) → in every case an alternate open
  REST/FTP host exists (used above); use a browser User-Agent for HTML-only
  fallbacks — or, where a WAF blocks even that, a **Browserbase** real browser +
  proxy/stealth (§2W, demo subset only).

---

# SECTION 2 — DIAGNOSE (build the case)

**Goal:** a complete, honest evidence profile for **every** well, and deep
agentic investigation for the high-impact subset. Each datum = evidence for a
specific actor's decision.

## 2A — Scale deterministic enrichment to ALL ~119k wells

### ★ The tract-dedup strategy (governs the whole design — implement this first)
Naive per-well geocoding is infeasible (Census Geocoder caps at **500/day/IP** →
238 days for 119k). Instead:
1. **Download national TIGER tract polygons once** (per-state; there is **no**
   national single-file). `TIGER2025` (posted 2025-09-22), per-state pattern
   `https://www2.census.gov/geo/tiger/TIGER2025/TRACT/tl_2025_<SS>_tract.zip` ✅
   (national ≈700–900 MB zipped). Loop the **56 FIPS codes** (skip retired
   `03 07 14 43 52`): `01 02 04 05 06 08 09 10 11 12 13 15 16 17 18 19 20 21 22 23
   24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 44 45 46 47 48 49 50
   51 53 54 55 56 60 66 69 72 78`. Fallback: swap `TIGER2025/`→`TIGER2024/`.
2. **Resolve all 119k wells → tract GEOID by *local* PIP** (`shapely.STRtree` /
   GeoPandas `sjoin` / PostGIS `ST_Contains`). Seconds–minutes, offline, no quota.
   The 11-digit tract GEOID embeds state(2)+county(3)+tract(6) — tracts are all
   you strictly need (BG/CD optional).
3. **Dedup to unique tracts** (~15–25k of ~85k national).
4. **One tract-level call (or one bulk download + local join) per source.** Fan
   attributes back to wells by GEOID. Reuse `enrich.py`'s thread-pool + SQLite
   cache, but change the **cache key to the tract GEOID** (not lat/lon).

Net: the entire 119k enrichment runs **< 1 hour**, dominated by downloads.

### Equity / demographics (tract-level → dedup applies)
| Source | Endpoint / file | Auth | Key fields | Status |
|---|---|---|---|---|
| **CDC/ATSDR SVI 2022** | `https://onemap.cdc.gov/onemapservices/rest/services/SVI/CDC_ATSDR_Social_Vulnerability_Index_2022_USA/FeatureServer/2/query` | none | `RPL_THEMES`,`E_TOTPOP`,`EP_POV150`,`EP_MINRTY`,`FIPS` | ✅ (base is `/onemapservices/` **not** `/ArcGIS/`; tract layer = **2** not 8) |
| **Census ACS 5-yr** | `https://api.census.gov/data/2023/acs/acs5?get=NAME,B01003_001E&for=tract:*&in=state:<SS>+county:<CCC>&key=<KEY>` | **free key** (`https://api.census.gov/data/key_signup.html`) | `B01003_001E` total pop, `B17001_002E/_001E` poverty rate, `B19013_001E` median income, `B03002_*` race | ✅ (one call = all tracts in a county → ~3,200 calls national) |
| **CDC PLACES (health)** | `https://data.cdc.gov/resource/yjkw-uj5s.json` (2025; `k9zj-b28y`=2024) | app-token optional | wide: `<measure>_crudeprev` (`obesity_`,`diabetes_`,`bphigh_`), `tractfips`,`totalpopulation` | ✅ (GIS-friendly = wide; long format is a different 4x4) |
| **CEJST / Justice40** | PEDP CloudFront CSV `https://dblew8dgr6ajz.cloudfront.net/data-versions/2.0/data/score/downloadable/2.0-communities.csv` | none | CSV "Identified as disadvantaged" / "Census tract 2010 ID"; shapefile `SN_C`==1, `GEOID10_TRACT` | ✅ mirror (**federal `*.geoplatform.gov` is DNS-DEAD**) |
| **EJScreen v2.3** | Zenodo `https://zenodo.org/api/records/14767363/files/2024.zip/content` (5.21 GB) | none | block-group/tract `ID`, `EJ_INDEX_*`, `DEMOGIDX_2`, 13 env indicators + percentiles | ✅ mirror (**federal removed 2025-02-05**) |
| **CDC/ATSDR EJI** | `https://onemap.cdc.gov/onemapservices/rest/services/Hosted/Environmental_Justice_Index_2022_Hosted/FeatureServer/0` + download `https://www.atsdr.cdc.gov/place-health/php/eji/eji-data-download.html` | none | single tract EJI rank across 36 factors (+2024 Climate Burden) | ✅ **still official & live — the most reliable EJ source now** |

> **2025 federal EJ takedown — load-bearing:** EPA **EJScreen** offline
> 2025-02-05; **CEJST** offline ~2025-01-22; both `.gov` endpoints dead. Use the
> mirrors above and **self-host a copy** of any EJ dataset you depend on. CDC
> **EJI** survived and is the primary; CEJST drives Justice40 funding eligibility
> so keep it (mirror) for Section 3.

### Human exposure (schools, hospitals, drinking water, true 1-mile population)
| Source | Endpoint / file | Notes |
|---|---|---|
| **NCES public schools** | `https://services1.arcgis.com/Ua5sjt3LWTPigjyD/ArcGIS/rest/services/Public_School_Locations_Current/FeatureServer/0/query` ✅ | point-radius `distance=1609&units=esriSRUnit_Meter`; field is `NAME` (not `SCH_NAME`); **no enrollment** (CCD join for that). To stay offline at scale, download the point layer once and PIP locally. |
| **Drinking water (EPA CWS service areas)** | GitHub-LFS zip `https://github.com/USEPA/ORD_SAB_Model/raw/refs/heads/main/Version_History/PWS_Boundaries_Latest.zip` (570 MB) ✅; anon FeatureServer fallback `https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/services/Water_System_Boundaries/FeatureServer/0` (44,615 CWS) ✅ | **closes the 13% gap + the Vowinckel story.** PIP → `PWSID`,`PWS_Name`,`Population_Served_Count`. Rural wells outside any polygon = "no community water service," not missing. |
| **Hospitals / sensitive sites** | HIFLD-derived; nearest-feature. (Closes the 5% gap.) | If a HIFLD mirror is flaky, the EPA ECHO Exporter facility points or a downloaded hospitals layer serve as the PIP source. |
| **True 1-mile population** | areal interpolation over **block groups** `https://www2.census.gov/geo/tiger/TIGER2025/BG/tl_2025_<SS>_bg.zip` (national ≈1.2–1.6 GB) + ACS BG population | replaces the tract-pop proxy that `PROGRESS.md` §2.4 flags. |

### Environment (download national → local PIP / nearest-feature)
| Layer | Primary download | Size | Field(s) |
|---|---|---|---|
| **Surface water (NHDPlus HR)** | `https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/NHDPlusHR/National/GDB/NHDPlus_H_National_Release_2_GDB_2025-08-19.zip` ✅ | 20.5 GiB zip | layer 3 NetworkNHDFlowline, FType 460=Stream; reproject EPSG:5070, chunk by HU4 |
| **Principal Aquifers** | ScienceBase `aquifers_us.zip` (DOI 10.5066/P9Y2HOUJ) ✅ | 7.4 MB | `Aq_name`,`Rock_type`; 4,637 polys (sub-second PIP) |
| **Sole-Source Aquifers** | `https://edg.epa.gov/data/public/OW/EPA_Sole_Source_Aquifers.zip` ✅ | 7.3 MB | 84 polys; flag layer; FeatureServer is token-gated — use the download |
| **Wetlands (NWI)** | per-state FileGDB `https://documentst.ecosphere.fws.gov/wetlands/data/State-Downloads/{ST}_geodatabase_wetlands.zip` ⚠️ | 25–40 GB stitched | **no national file** → bucket wells by state, download only states with wells |
| **Flood (FEMA NFHL)** | hosted `https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28` ✅ (national GDB ~12 GB via MSC portal) | 12 GB | `FLD_ZONE`,`SFHA_TF`; query Availability layer 0 first → "unmapped" vs Zone X |

### Jurisdiction / land (drives the actor map + Justice40)
| Layer | Endpoint | Field(s) |
|---|---|---|
| **PAD-US 4.1** | ScienceBase FileGDB `https://www.sciencebase.gov/catalog/file/get/652d4fc5d34e44db0e2ee45e?name=PADUS4_1Geodatabase.zip` (1.52 GB) ✅ | `Mang_Type`,`Mang_Name`,`Own_Type` (FED/STAT/LOC/TRIB/PVT); **4.2 is embargoed → use 4.1** |
| **BLM SMA (federal surface mgr)** | `https://gis.blm.gov/arcgis/rest/services/lands/BLM_Natl_SMA_Cached_without_PriUnk/MapServer/1` ✅ | `ADMIN_AGENCY_CODE` (BLM/FS/NPS/FWS/BIA/BOR/DOD) |
| **BIA tribal land** | `https://biamaps.geoplatform.gov/server/rest/services/DivLTR/BIA_AIAN_National_LAR/FeatureServer/0` ✅ (use geoplatform host; doi.gov host 500s) | `LARNAME`; Census AIANNH `tl_2025_us_aiannh.zip` is the static fallback |
| **Census tract→congressional district** | from the same TIGER pull: `…/TIGER2025/CD/tl_2025_<SS>_cd119.zip` (119th) | `CD119`+state FIPS → join to legislators (§Section 3) |

**Precedence for jurisdiction:** tribal > federal > state > private (PAD-US can
have overlapping polygons — prefer Fee, resolve by precedence).

## 2B — Methane differentiation (kill the "one constant" problem)
Replace `methane.py`'s two constant EF tuples with the **EPA GHGI abandoned-well
emission factors** (public domain, government-blessed, machine-readable):
`https://www.epa.gov/sites/default/files/2018-04/documents/ghgemissions_abandoned_wells.pdf`

**Apply by (plugging status) × (Appalachia vs rest-US), g CH₄/hr/well:**
| | Appalachia (OH,PA,WV,NY,KY,TN) | Rest of U.S. |
|---|---|---|
| **Unplugged** | **30.57** | **10.02** |
| **Plugged** | **0.36** | **0.002** |

**Add the oil-vs-gas dimension** from Kang 2016 Table 1 (free via PMC5137730 or
the EPA memo, which reproduces it verbatim): gas-unplugged-noncoal ≈ **75**,
coal-area plugged-vented gas ≈ **47**, oil/combined ≈ **0.2–0.4** g/hr. Apply as a
production-type multiplier or substitute category means for Appalachian wells.
Pull each well's **plugging status / type** from the state DBs (§Section 1.3);
default ~**69% unplugged / 31% plugged** where unknown.

**Flag the visible tail separately:**
- High-emitter (heavy tail): unplugged gas / coal-area plugged-vented gas, ≥10⁴
  mg/hr (~0.09 t/yr). ~16% of wells → ~98% of volume.
- **Cross-reference EPA Super-Emitter Program** (≥100 kg/hr observed events):
  pull the current CSV from the ECHO Data Explorer
  `https://echo.epa.gov/trends/methane-super-emitter-program/data-explorer`
  (fields incl. `Emissions Rate (kg/hr)`, lat/long, operator). ⚠️ Program is in
  deregulatory delay (full implementation deferred to 2027, one certified
  notifier — Carbon Mapper); treat SEP as the rare visible tail, not coverage.
  Keep GWP-100=30 for money/credits, GWP-20=84 as the urgency sidebar (existing).

## 2C — Re-score
Extend `scoring.py` `METRIC_CONFIG`/`DEFAULT_WEIGHTS`/`GROUPS`/`METRIC_LABELS`
with the new metrics (drinking_water + hospitals now actually computed; PLACES
health; CEJST/EJI as the EJ signal replacing the SVI-only proxy). The
human-exposure pillar becomes **fully computed** (closes `PROGRESS.md` §2.2). Run
on all wells. Keep the existing invariant: breakdown sums to composite, missing
metrics renormalized. Surface any residual metric uniformity honestly.

## 2W — Browser automation: **Browserbase** (Stagehand) — the one interactive-only escalation

> **The brain and the general web stay free.** Claude keeps driving the
> investigation via the Anthropic SDK with **server-side `web_search`** (the proven
> `investigator.py` path) for everything readable on the open web — that is the
> free, default web layer and it is *not* replaced. **Browserbase earns exactly
> one job:** the facts that `web_search` and plain HTTP **cannot reach because they
> live behind a form, a login, or a WAF** — county assessor viewers with no REST
> service, Recorder-of-Deeds / skip-trace pages, and forms-only SOS / court entity
> searches (JS apps + Cloudflare/WAF). One keyed platform, used only where it
> genuinely unblocks the product (Prime Directive #2: free-first; sponsor tool not
> bolted on everywhere).

**How it wires to Claude (the brain stays the Anthropic SDK).** Keep
`investigator.py` exactly as proven — `web_search_*` server tool, streaming,
`pause_turn` loop, per-well sentinel, `<dossier>` parse, cached `dossiers.json` as
the floor. Add **one** new Claude tool-use function, `browser_task(site,
instruction, schema)`, backed by a **Stagehand** session
(`act`/`observe`/`extract`, `env:"BROWSERBASE"`; Agent Identity for legitimate
login, proxy/stealth for WAFs). For the **deterministic** pulls (parcel owner,
operator-by-name) call Stagehand **`extract(schema)`** directly (Zod/pydantic)
rather than a free-form agent, so output is structured + verifiable. Claude
escalates to `browser_task` **only** when `web_search` hits a wall; everything
else stays on the free path.

**Honesty dividend (serves Prime Directive #4).** Browserbase **session replays**
(stream within seconds, free on all plans) are a *verifiable provenance
artifact*: store the replay/session URL in the dossier `sources` beside every
browser-derived claim. "Here's the recorded session showing the assessor record"
is stronger sourcing than a bare URL — and keeps every claim sourced +
confidence-tagged (BROWSER_BASED_AGENT_TRAINING.md §4).

**Scope: batch precompute on the demo / top subset only** — never inside the live
SSE route (one browser session can blow the 300 s budget, §7.2). The free tier
(3 concurrent browsers) is sufficient because only the handful of wall-blocked
lookups in the demo subset ever touch a browser; the bulk runs on `web_search`.

**New / changed files:**
- `services/swarm/web/browserbase_client.py` (NEW) — thin `browser_extract(schema, instruction)` wrapper (Browserbase Python SDK + Stagehand-py); SQLite-cached like `enrich.py`.
- `services/swarm/investigator.py` — **add** the `browser_task` tool to the existing tool list; do **not** touch the `web_search` wiring, streaming, sentinel, or `<dossier>` parse.
- `apps/web/lib/browserbase.ts` (NEW) — TS Stagehand wrapper, used by the batch precompute (not the live route).
- Deps: `browserbase`, `stagehand-py` (Python); `@browserbasehq/sdk`, `@browserbasehq/stagehand` (web). Env: `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID` (server-side only).

**BLOCKERS + RANKED BACKUPS (§2W):**
1. **Sandbox egress reachability UNVERIFIED** (doc ethos: probe before trusting) →
   reachability-probe a Browserbase session-create from the container before
   relying on it. **Floor:** the free Anthropic `web_search` path already carries
   the whole investigation; if Browserbase is unreachable, the wall-blocked
   landowner fields fall back to manual assessor/deeds lookup for the few demo
   wells (§3.6) — nothing else regresses.
2. **Free-tier cap** (3 concurrent browsers) → only the demo-subset wall-blocked
   lookups use a browser; cache results (SQLite). The bulk never touches it.
3. **Site/DOM changes** → Stagehand self-heals (NL over the accessibility tree);
   still pin `extract` schemas and spot-check a sample.
4. **Captcha / hard auth (e.g. PACER)** → Agent Identity where legitimate;
   otherwise mark the field **unverified** (never invent) and fall back to the
   free `web_search` SOS/news path.

## 2D — Agentic investigation on the top ~100–300 (ownership / liability)
Extend `run_swarm.py` cohort 12 → top ~100–300 by score (+ heroes). Add a
**structured ownership/liability investigator** track in `investigator.py`. The
agent's system prompt and per-goal **query ladders** are specified in
`BROWSER_BASED_AGENT_TRAINING.md` — implement that doctrine, not the current thin
prompt: geolocate the coordinate → **county + API well number before searching**
(a raw lat/long is invisible to a search engine — the #1 failure mode); prefer the
authoritative database to the open web; ladder/reformulate each question 3–5 ways;
rank by source authority (gov/regulator > court/SOS > academic > news >
aggregators-as-leads-only); **pivot on entities** to chain
operator→officers→bankruptcy→successor; triangulate (≥2 sources or label
"unverified"); stop on convergence/budget. Tracks:
- *Documented wells:* operator (from state DB API→operator, §Section 1.3) →
  bankruptcy (PACER is **paid**; free: state SOS corporate registries, news) →
  shell transfers → current responsible party.
- *Undocumented wells:* current **surface owner** via the structured parcel
  lookup (§3.6 + `STRUCTURED_PROPERTY_INFORMATION.md`) + present context (the case
  is location-driven). Keep **surface owner** (parcel) distinct from **liable
  operator** (well registry) — severed estates are common in Appalachia.
- Extend the dossier schema to **structured fields** (operator, transfers,
  bankruptcy, current_owner), each carrying the per-claim **provenance schema**
  from `BROWSER_BASED_AGENT_TRAINING.md` §4 (`source_url`, `publisher`,
  `source_tier`, `date_accessed`, `confidence`, `corroboration`) — no provenance,
  no ship (Section 3 spends credibility). Keep the "never invent an
  operator/date/citation" instruction and the honest "no operator on record"
  behavior.
- **Spend:** route these agent calls through the §2R Redis semantic cache so
  repeat / look-alike investigations don't re-pay for search + generation
  (`PROGRESS.md` §3.10).

## 2R — Agent response caching: Redis (one job, one place)
The only part of the system that makes expensive, repeatable LLM + web-search
calls is the agentic investigation — the §2D batch swarm and its §7.2 live-route
port. `PROGRESS.md` §3.10 flags the cost: re-runs burn API credits, and the live
route re-investigates from scratch on every click (the swarm and route share no
cache today). The single most effective Redis use here is **one RedisVL
`SemanticCache`** in front of those calls — and Redis is used for nothing else.

- **Where:** wrap the Claude + web-search call in `services/swarm/investigator.py`
  with a small `services/swarm/web/cache.py` helper, and have the §7.2 live route
  import the same helper. The batch swarm and the live demo then share one cache.
- **How:** `check()` before calling → on hit, return the cached dossier instantly;
  on miss, run the agent then `store()`. Set a `ttl` so facts stay fresh; keep
  `distance_threshold` conservative; scope each entry with RedisVL
  `filterable_fields` on `well_id` + `county` + a content hash so one well's
  dossier can **never** be served for another (honesty guard).
- **Payoff:** the §3.10 spend problem fixed systemically, plus a fast, reliable
  demo — a repeat or look-alike investigation returns in milliseconds instead of
  ~120 s and sidesteps the egress idle-drop the swarm already hit.
- **Deliberately NOT used for** checkpointing, cross-agent memory, or vector
  search. Those are real Redis features, but they add moving parts (and a 30 MB
  free-tier cap to manage) without changing the demo outcome; `dossiers.json` and
  `enrich.sqlite` already cover durable file/point caching. Keep the footprint to
  the one semantic layer the existing caches can't provide.

**New / changed & deps:** `services/swarm/web/cache.py` (new — the `SemanticCache`
wrapper, used by both the investigator and the live route); dep `redisvl`
(+ `redis`); env `REDIS_URL`. Redis Cloud free tier (30 MB / 30 conns) is far
more than a cache of the cased subset needs; on any Redis outage `check()` simply
misses and the agent runs live, so caching never blocks the demo (floor = §7.5).

**Per-source browser playbooks (Browserbase `browser_task` of §2W — demo / top
subset only):** these are the form/auth/WAF walls free `web_search` can't cross,
reachable via Stagehand. Everything readable on the open web stays on `web_search`.
- *State SOS corporate registry* (bankruptcy / shell-company transfers): `act`
  "search for `<operator>`" → `extract` `{entity, status, officers, filing_dates,
  successor}`.
- *TX RRC EWA Wellbore Query* (operator absent from GIS, §1.3; 503-prone JS app):
  Stagehand drives EWA by API# → operator/lease; proxy/stealth + retry on 503.
- *ND DMR* free per-well form (§1.3, no free bulk): `act` + `extract` per demo well.
- *PA legacy / KY status fields* and other HTML-only registries: try `web_search`
  / plain fetch first; escalate to `browser_task` only if interactive.
- WAF-blocked state hosts (§1.5: ISGS / KGS / michigan.gov) → Browserbase real browser.

## 2E — BLOCKERS + RANKED BACKUPS (Section 2)
- **EPA endpoints flaky** (Envirofacts 500↔200, NWI query host 500, SSA token) →
  always pair a hosted service with a **download + local PIP**; the downloads are
  the primary, services are QA/fallback.
- **CEJST/EJScreen federal dead** → mirrors above; self-host; CDC EJI as primary.
- **NHDPlus HR / NWI are heavy (20–40 GB)** → bucket wells by state, download only
  needed states; simplify geometry; use Principal Aquifers (7 MB) as the cheap win.
- **PACER paywall for bankruptcy** → SOS corporate registries + news via the
  agentic search; mark bankruptcy "unverified" rather than guessing.
- **Coverage gaps where wells actually sit** (NFHL undigitized rural, NHD Alaska,
  CWS outside-service-area) → emit explicit flags (`unmapped`/`no_coverage`/
  `outside_service_area`), never silent nulls.

---

# SECTION 3 — ACT (pathway + actor map + story)

**Goal:** for each well, the action half of the case file — best pathway to
plugging, the named actors who can do it, and a compelling sourced story. **Never
facilitation.** Build on Section 2 outputs.

## 3.1 `services/engine/pathways.py` — rule-based funder matching
Rank pathways with rationale + rough timeline, from deterministic inputs:
- **Federal BIL/IIJA + state program eligibility** (from jurisdiction +
  CEJST/Justice40 disadvantaged flag). State plugging programs with downloadable
  inventories researched: **CA CalGEM** (WellSTAR CSV + orphan/deserted screening
  layers + PDF inventory), **NY DEC** (Socrata `vgue-bamz` orphan list, 7,948),
  **KY** State Bid Well Program (KGS shapefile; no orphan-specific list). Extend
  per state from §Section 1.3 + the IOGCC member list.
- **Carbon viability** (only the differentiated tail from §Section 2B) — ACR
  orphan-well methodology; honest self-funding ratio (≪1 for typical wells).
- **Charity match** (right profile only) and **landowner-corporation path**.

## 3.2 `services/engine/actors.py` — the actor map
Assemble *responsible/able*, *can fund*, *can pressure* per well. Deterministic
where possible; agentic enrich for the top subset.

**lat/lon → U.S. Representative (FREE, no key):**
1. Census Geocoder coordinates→geographies (also returns state-leg districts):
   `https://geocoding.geo.census.gov/geocoder/geographies/coordinates?x=<LON>&y=<LAT>&benchmark=Public_AR_Current&vintage=Current_Current&layers=all&format=json` ✅ → `119th Congressional Districts` (`CD119`,`STATE`). Or local PIP against the `cd119` TIGER shapefile (offline, no 500/day cap).
2. Join `state`+`CD119` → **`unitedstates/congress-legislators`** (CC0):
   `https://unitedstates.github.io/congress-legislators/legislators-current.json` ✅ (+ `legislators-district-offices` for office address/phone). JSON/CSV live on the **`gh-pages`** branch; YAML on `main`.
3. Optional live cross-check: Congress.gov API `/member/{state}/{district}?currentMember=true` (free key, 5k/hr).

**lat/lon → state legislators (often the real lever):** same geocoder call returns
`2024 State Legislative Districts - Upper/Lower`; join to **Open States** nightly
per-state CSV `https://data.openstates.org/people/current/<st>.csv` ✅ (CC0, no
key) — or the one-call `https://v3.openstates.org/people.geo?lat=&lng=` (free key,
soft limit).

**lat/lon → state regulator:** **no free structured dataset exists** — hand-build
`data/static/state_regulators.csv` (state, agency, division, orphan-program URL,
address, phone, email), seeded from the **IOGCC** member list
(`https://iogcc.ok.gov/member-states`) + GWPC + each agency site. Budget periodic
manual review.

**lat/lon → community/EJ orgs:** **no free point→org dataset** — derive
"impacted community" from EJI/CEJST tract scores; hand-compile orgs per region.
Claude's free `web_search` can surface candidate local orgs per region to seed
that hand-compiled list. Don't promise automated org lookup.

## 3.3 `services/engine/story.py` — Claude-synthesized sourced narrative
Evidence-grounded advocacy (not propaganda): a tailored call-to-action ("could be
plugged by next month if X acts"), **every claim cited + confidence-tagged**,
tuned to the chosen funder type. Reuse the `investigator.py` SDK+streaming
pattern over the free `web_search` layer for fresh sourcing; for any fact that
only came from a `browser_task` escalation (§2W), attach the Browserbase
session-replay URL as provenance.

## 3.4 `services/engine/assemble_cases.py`
Merge evidence + pathways + actors + story → `data/processed/case_files.json` for
the top ~100–300 (deterministic pathway/actor parts for **all** wells).

## 3.5 Routing destinations (intake adapters — outbound notification, not integration)
**No org exposes a well-submission API; all intake is email/web form.** Maintain a
per-org "intake adapter" registry; score a well then emit a structured
email/form-submission to the best match:
| Org | Intake | Fit | Routability |
|---|---|---|---|
| **Orphan Well Cooperative** | form at `https://orphanwell.org/` + `info@orphanwell.org` (has an explicit "report orphan well" field + public prioritization matrix) | nonprofit hub | **best** |
| **Rebellion Energy** | `data@rebellionenergy.com` | for-profit carbon, OK-centric, high-emission wells | best documented email |
| **Well Done Foundation** | `https://welldonefoundation.org/connect/` + `info@welldonefoundation.org` (Cloudflare-blocked site → email only) | adopt-a-well + carbon; ~$65k/well; methane-first selection | high value, email-only |
| **Zefiro Methane** | acquires via **state RFP bids** only → route to the **state regulator's** program, not Zefiro | state-program wells | not directly routable |
| **EDF** | not a plugger — `https://www.edf.org/orphanwellmap` is a **bulk data source** (120k-well dataset) | seed/ingest | data only |

Use free `web_search` to verify each org's *current* intake URL, email, and
required form fields before emitting — intake forms drift, and a stale address is
a silently dropped case. For form-only intakes (no email) behind a JS/WAF wall,
a Browserbase `browser_task` (§2W) `act` can pre-fill a draft submission for human
review (we **mobilize**, we don't auto-submit — Prime Directive #1).

## 3.6 BLOCKERS + RANKED BACKUPS (Section 3)
- **Parcel/landowner — database-first** (full recipe in
  `STRUCTURED_PROPERTY_INFORMATION.md`). There's no free *national* owner layer,
  but the Appalachian target states are largely solved with **free, deterministic
  ArcGIS REST `/query`** (point-in-polygon → owner, no scraping): → (1) **OH/WV/KY**
  statewide/county parcel REST services — discover the owner field via `?f=pjson`
  first (it varies: `OWNER`/`OWNER_NAME`/`TAXPAYER`/…), pass `inSR=4326`, and watch
  the NAD27→WGS84 reprojection (a 20–40 m miss loses the parcel); (2) **PA + any
  gap** → a national-API free trial (**ReportAll** = 1,000 free lookups, covers the
  demo; **ATTOM** free key adds deeds/sales for the documented-well transfer chain);
  (3) **interactive-only** county viewers / deeds / skip-trace with no queryable
  service → **Browserbase** (see below); (4) manual assessor lookup by
  APN/coordinate. Always separate **surface owner** (parcel) from **liable
  operator** (state O&G registry). Do the landowner case for the **demo subset** only.
- **No org API** → all routing is structured outbound email; partner directly
  (email OWC/WDF proposing Lost Wells as a referral pipeline) rather than scrape.
- **WDF Cloudflare-blocked** → official email/partnership, not scraping.
- **No state-regulator / EJ-org dataset** → hand-compiled CSVs (above).

**Browserbase — browser automation for the interactive-only fallback (the one
place it earns its keep).** Most landowner lookups are solved by the free ArcGIS
REST path above; Browserbase is the **last resort for facts that live only behind
a UI you cannot query** — PA county assessor viewers with no REST service, county
**Recorder-of-Deeds** and skip-trace/people-search pages (the "reach a real
person" step that *completes* the ≥1 end-to-end landowner case), and SOS / court
entity searches that are forms-only (JS apps + Cloudflare/WAF that plain HTTP and
Claude web search can't read). A Stagehand agent (`stagehand.act(...)` to drive
the form, `.extract(schema)` to pull the field) follows the same doctrine as the
rest of the swarm (`BROWSER_BASED_AGENT_TRAINING.md`: geolocate → county + APN
first, rank by authority, cite). Run it as a **batch precompute** over the demo
subset (not the live path); the Browserbase **session replay** is the provenance
artifact, and the result ships into the case file as a sourced, confidence-tagged
field. Deps `@browserbasehq/stagehand` (+ `@browserbasehq/sdk`); env
`BROWSERBASE_API_KEY` / `BROWSERBASE_PROJECT_ID`. Floor: if a queryable service
exists, use it; if Browserbase is unavailable, fall back to manual assessor/deeds
lookup for the handful of demo wells.

---

# 7. Cross-cutting — Live backend, UI, deploy

## 7.1 The critical blocker is NOT a blocker
**A ~120 s streaming Claude investigation runs live on Vercel — even free Hobby.**
Since **2025-04-23 Fluid compute is on by default**, giving **Hobby = 300 s**
function duration (Node.js). No Pro plan, no separate Python service, no
background-job/poll machinery required. The Python LangGraph swarm already proves
the SDK pattern; it just needs a thin TS port into a Route Handler.

```
Browser SwarmPanel ──fetch('/api/investigate/[id]')──▶ Next.js Route Handler (nodejs, maxDuration=300)
                       reads SSE / ReadableStream        │ anthropic SDK → client.messages.stream({
                                                          │   model, tools:[{type:'web_search_20260209', max_uses:8}] })
                                                          │ map Anthropic events → compact SSE progress frames
                                                          ▼
                                                  Anthropic API (server-side web search)
```

## 7.2 The live route — `apps/web/app/api/investigate/[id]/route.ts` (CREATE)
Load-bearing segment config:
```ts
export const runtime = 'nodejs';          // NOT edge (needs full SDK + 300s; edge must first-byte in 25s)
export const dynamic = 'force-dynamic';   // never cache an SSE route
export const maxDuration = 300;           // Hobby ceiling; 120s run fits well under
```
- Use `@anthropic-ai/sdk` `client.messages.stream({...})` with the server-side
  **`web_search`** tool (the free, proven path). **Port
  `services/swarm/investigator.py`'s** system prompt, `<dossier>` schema, source
  extraction, and `pause_turn` continuation loop verbatim. The live route runs on
  `web_search` only — Browserbase `browser_task` (§2W) is **not** called inside the
  SSE route (a browser session can blow the 300 s budget); any browser-derived
  field is precomputed in the Python batch and served from `dossiers.json` /
  `case_files.json`.
- Return `new Response(stream, { headers:{ 'Content-Type':'text/event-stream',
  'Cache-Control':'no-cache, no-transform', 'Connection':'keep-alive' }})`. Don't
  `await` the whole stream before returning — return the stream so Next flushes
  incrementally.
- **Emit a heartbeat / progress frame periodically** while Claude searches —
  HTTP/1.1 intermediaries drop idle connections (the exact idle-drop the Python
  swarm hit; streaming + heartbeat is the fix).
- Handle `stop_reason:"pause_turn"` (append the paused assistant message, call
  again). **Display source citations** (Anthropic policy); for any precomputed
  browser-derived fact, include its Browserbase **session-replay URL** (§2W
  honesty dividend). Enable web search once in the Claude Console (admin). Cost ≈
  $10/1k searches → bound `max_uses`.
- `ANTHROPIC_API_KEY` = server-side (unprefixed) Vercel env var, read only in the
  Route Handler. Model `claude-opus-4-8` or `claude-sonnet-4-6` (cheaper, fine).
- **Before invoking, check the §2R Redis `SemanticCache`** (`check()` → on hit,
  stream the cached dossier; on miss, run live then `store()`), sharing the cache
  with the batch swarm. Add `REDIS_URL` as a server-side Vercel env var; a Redis
  outage falls through to a live call, never blocking the route.

## 7.3 UI wiring (all additive)
- `SwarmPanel.tsx`: replace the simulated `replay()` with `fetch()` +
  `response.body.getReader()` SSE consumption (POST; `EventSource` is GET-only).
  Keep `replay()` as the labeled fallback.
- `DossierPanel.tsx`: wire the existing `onInvestigate`/`investigating` props to
  the new route.
- New `CaseFilePanel.tsx` (reuse `Card`/`Stat`/`ScoreBar`) for pathway + actor
  map + story + "act via X" links; extend `lib/types.ts` with
  `CaseFile`/`Actor`/`Pathway`.
- Reuse `MapView`/`RankedList`/`TopoDissolve`; add discovery/source layers + a
  "newly discovered" filter.

## 7.4 Data at scale + deploy
- **Keep committed static columnar JSON in `public/data/`.** 117k = 703 KB gzip;
  even 300k ≈ 1.8 MB gzip — one-time CDN download, no DB. deck.gl binary attrs
  hold 60 fps to ~1M points; **no tiling needed**. Client-side MiniSearch/FlexSearch
  index for instant text search.
- `predev`/`prebuild` runs `scripts/copy-data.mjs` (`data/processed/*.json` →
  `public/data/`). On Vercel set **Root Directory = `apps/web`** and verify the
  three-level `..` path resolves; if monorepo isolation breaks it, commit the JSON
  directly into `apps/web/public/data/` (un-ignore) and drop the copy step. Files
  in `public/` are static assets — they do **not** count against the 250 MB
  function bundle; the 4.5 MB body limit does **not** apply to static assets or
  streamed SSE.

## 7.5 Backend BLOCKERS + RANKED BACKUPS
1. ~~120 s timeout~~ → Fluid compute (default) = Hobby 300 s. Confirm the toggle
   is ON; set `maxDuration=300`, `runtime='nodejs'`.
2. Idle-connection drop → stream heartbeats continuously.
3. If a single run could exceed 300 s → **Pro plan** `maxDuration` 800 s (1800 s
   beta). Trivial escalation.
4. If you must move Python off-Vercel → **Modal** (sub-second cold start,
   best for the LangGraph swarm) > Fly.io > Render (free spins down) > avoid
   Railway (5-min cap). Route proxies to it.
5. Guaranteed demo floor → serve cached `dossiers.json` + labeled `replay()`.
   Keep this wired even when live works.

---

# 8. Sequencing (milestones)

1. **§Section 1 consolidate (floor) → integrate U-Net detections when they
   arrive (validate Kern)** → unified DB with a few discoveries + state depth/type/
   status/operator joined. — **✅ code-complete (Appalachia OH/WV/PA/NY/KY):**
   `state_registries.py` + `build_datastore.py consolidate()` (attach by API →
   spatial ≤50 m → expand → `lost_wells.json`). Awaiting live ingest run + U-Net.
2. **§Section 2A tract-dedup enrichment on all wells** (TIGER PIP + the national
   datasets) → human-exposure fully computed; **§Section 2B** GHGI methane;
   **§Section 2C** re-score. — **✅ §2A code-complete:** `tracts.py` (TIGER PIP) +
   `enrich_tract.py` (drinking water, hospitals, true 1-mi pop, CEJST/EJI),
   awaiting live ingest run. **§2B/§2C still TODO.**
3. **§Section 2D agentic + §Section 3 engines** → case files for top ~100–300
   (incl. ≥1 landowner case); deterministic pathway/actor for all wells. The agent
   runs on free `web_search`; put the **§2R Redis `SemanticCache`** in front of it.
   For the landowner case, do the free ArcGIS REST parcel lookup first (§3.6); for
   the wall-blocked remainder, reachability-probe a Browserbase session, then run
   the **§2W `browser_task`** lookup over the demo subset.
4. **§7 backend + UI** → live SSE route + CaseFile/actor-map UI; **deploy to
   Vercel**.
5. **Demo arc:** "found wells nobody knew existed → here's the complete case →
   here's exactly who can plug them, live, for any well in the country."

---

# 9. Master endpoint quick-reference (all FREE/keyless unless noted)

| Need | Endpoint | Status |
|---|---|---|
| Census tract PIP | `…/TIGER2025/TRACT/tl_2025_<SS>_tract.zip` | ✅ per-state, ~700–900 MB |
| coords→district/tract | `https://geocoding.geo.census.gov/geocoder/geographies/coordinates?...` | ✅ (500/day cap → use local PIP) |
| ACS demographics | `https://api.census.gov/data/2023/acs/acs5?...&key=` | ✅ free key |
| SVI 2022 | `https://onemap.cdc.gov/onemapservices/.../FeatureServer/2/query` | ✅ |
| EJI (live EJ) | `https://onemap.cdc.gov/onemapservices/.../Environmental_Justice_Index_2022_Hosted/FeatureServer/0` | ✅ |
| CEJST (mirror) | `https://dblew8dgr6ajz.cloudfront.net/data-versions/2.0/data/score/downloadable/2.0-communities.csv` | ✅ federal dead |
| EJScreen (mirror) | `https://zenodo.org/api/records/14767363/files/2024.zip/content` | ✅ federal dead |
| PLACES health | `https://data.cdc.gov/resource/yjkw-uj5s.json` | ✅ |
| schools | `https://services1.arcgis.com/Ua5sjt3LWTPigjyD/.../Public_School_Locations_Current/FeatureServer/0/query` | ✅ |
| drinking water | `https://github.com/USEPA/ORD_SAB_Model/raw/refs/heads/main/Version_History/PWS_Boundaries_Latest.zip` | ✅ 570 MB |
| surface water | `…/NHDPlusHR/National/GDB/NHDPlus_H_National_Release_2_GDB_2025-08-19.zip` | ✅ 20.5 GiB |
| flood | `https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28` | ✅ |
| jurisdiction | PAD-US 4.1 `…/file/get/652d4fc5d34e44db0e2ee45e?name=PADUS4_1Geodatabase.zip` | ✅ 1.52 GB |
| methane EFs | `https://www.epa.gov/sites/default/files/2018-04/documents/ghgemissions_abandoned_wells.pdf` | ✅ |
| super-emitter | `https://echo.epa.gov/trends/methane-super-emitter-program/data-explorer` | ✅ CSV |
| HTMC topo inventory | `https://prd-tnm.s3.amazonaws.com/StagedProducts/Maps/Metadata/historicaltopo.zip` | ✅ |
| reps | `https://unitedstates.github.io/congress-legislators/legislators-current.json` | ✅ CC0 |
| state legislators | `https://data.openstates.org/people/current/<st>.csv` | ✅ CC0 |
| state O&G operator-by-API | CO/NM/CA/OK/KS REST `/query` (§Section 1.3) | ✅ |
| agent web search (free, default) | Anthropic server-side `web_search` (`investigator.py`, ported to the live route) | ✅ ~$10/1k searches |
| agent browser: forms/auth/WAF | Browserbase Stagehand `browser_task` (`act`/`extract`, `env:"BROWSERBASE"`) | ✅ 3 free concurrent (demo subset) |
| live agent route | `apps/web/app/api/investigate/[id]/route.ts` (CREATE) | — |
| agent response cache (§2R) | RedisVL `SemanticCache` (`check()`/`store()`, `filterable_fields`); Redis Cloud free = 30 MB | ✅ sponsor |
| landowner owner lookup (§3.6) | parcel ArcGIS REST `/query` (OH/WV/KY, `?f=pjson` for owner field) + ReportAll/ATTOM trial (PA/gaps) | ✅ free/trial |
| interactive-only fallback (§3.6) | Browserbase Stagehand (`act`/`extract`) for PA viewers / deeds / skip-trace | ✅ sponsor |

---

# 10. Global floors (never call it quits)

- **No U-Net detections** → consolidated DOW+LBNL+state DB is the Section-1
  deliverable; U-Net is the live novel layer.
- **A heavy download (NHD/NWI) infeasible** → bucket by state; Principal Aquifers
  (7 MB) + flood + drinking water alone already lift exposure well past 82%.
- **A federal dataset moved** → every EJ/equity source has a mirror (above);
  self-host it.
- **Live backend slips** → precomputed case files + cached dossiers + labeled
  replay; the product is still a complete, browsable national case-file DB.
- **Parcel/owner data paid** → landowner case for the demo subset only; everything
  else is free.
- **Always:** detection = "candidate," claims = sourced + confidence-tagged,
  positioning = router not operator. Honesty is the product.

---

*Compiled from deep web research (reachability-probed 2026-06-20) + a full read of
the current codebase. Endpoints, counts, and sizes are live observations. When a
primary fails, walk its ranked backups before narrowing scope.*
