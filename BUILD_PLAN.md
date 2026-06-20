# Lost Wells — Build Plan & Session Handoff

> **Purpose of this file:** the authoritative, session-independent record of confirmed
> decisions, the network-whitelist setup, the feasibility audit, the architecture, and the
> build order. If a new Claude Code session starts (e.g. after changing the network policy),
> **read this file first** — it carries all context that a fresh session would otherwise lose.

Working branch: `claude/vibrant-tesla-mim5ea` — develop, commit, and push here only.

---

## 1. What we're building

A three-pillar, award-grade product from `lostwellsprojectspecs.md`:

1. **Detection (U-Net):** extend LBNL's CATALOG U-Net (Ciulla et al. 2024) that finds oil/gas
   well symbols on historical USGS topo maps; a detected symbol >100 m from any documented
   well = candidate **undocumented orphaned well (UOW)**. Backbone/fallback = USGS DOW
   (117,672 documented wells) + LBNL's 1,301 pre-computed candidates.
2. **Claude agent swarm:** an investigator per well builds an impact + economics **dossier**
   from free public data + open-ended web search (operator history, bankruptcy, news).
3. **Ranking engine + award-grade map UI:** composite impact score (human exposure, equity,
   methane proxy, fundability) feeding a designed investigative map experience with the
   signature "1950s topo dissolving into present-day satellite over a school/home" reveal and
   a live agent-swarm visualization.

Prize targets: Claude **societal-impact** + **UI/UX**.

---

## 2. Confirmed decisions (locked with the user)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Map rendering stack | **MapLibre GL, no token** (free/open tiles; Carto dark basemap; ESRI World Imagery for satellite; bundled georeferenced topo overlays for hero wells). |
| 2 | Agent swarm engine | **LangGraph `Send` map-reduce** (Python) with `langchain_anthropic` Claude subagents — chosen over the Claude Agent SDK. |
| 3 | Scope / U-Net depth | **Full app** (UI + swarm + ranking) to demo quality; **U-Net = complete documented runnable Python**, executed where a GPU/model/data exist (not in the sandbox). |
| 4 | Data strategy | **Whitelist domains** (preferred) so we ingest real data once; **commit data files** as the fallback if whitelisting fails. App must NOT depend on fragile live streams at demo time. |
| 5 | Build timing | **Wait for whitelist confirmation** before building the foundation, then verify reachability + ingest, then build against real data. |
| 6 | Swarm auth | User will provide **`ANTHROPIC_API_KEY`** in the environment; swarm runs live with cached dossiers as fallback. |

Web search for the swarm: use **Anthropic's server-side web search tool** bound to
`ChatAnthropic` — it runs on Anthropic's servers via the already-allowed `api.anthropic.com`,
so it needs **no extra domain and no extra API key**.

---

## 3. Network whitelist (Claude Code on the web)

The sandbox uses an allowlist proxy (`x-deny-reason: host_not_allowed`). Default **Trusted**
level allows npm/PyPI/GitHub/`api.anthropic.com` but blocks all gov data + the model host +
map tiles.

**To extend:** claude.ai/code → environment (cloud) icon → edit environment → **Network
access = Custom** → paste the domains below into **Allowed domains** (one per line) →
✅ **check "Also include default list of common package managers"** (keeps npm/PyPI/GitHub +
`api.anthropic.com`) → Save → **start a fresh session**.

```
*.sciencebase.gov
www.sciencebase.gov
pubs.usgs.gov
ngmdb.usgs.gov
tnmaccess.nationalmap.gov
*.nationalmap.gov
edx.netl.doe.gov
www.osti.gov
geocoding.geo.census.gov
api.census.gov
www2.census.gov
nces.ed.gov
*.arcgis.com
onemap.cdc.gov
data.cdc.gov
data.epa.gov
enviro.epa.gov
echo.epa.gov
aqs.epa.gov
pedp-ejscreen.azurewebsites.net
```

Optional (only to let Claude verify the map visually in-sandbox; the deployed app's tiles
render in the user's browser regardless): `*.basemaps.cartocdn.com`, `*.tile.openstreetmap.org`,
`*.arcgisonline.com`.

`*.amazonaws.com` is already a Trusted default → USGS S3 GeoTIFFs (`prd-tnm`) work with no addition.

**On resume, FIRST re-run the reachability probe** (some past versions of the field didn't
apply to container egress — verify, don't assume):

```bash
for h in www.sciencebase.gov edx.netl.doe.gov geocoding.geo.census.gov \
  api.census.gov nces.ed.gov onemap.cdc.gov data.cdc.gov enviro.epa.gov \
  tnmaccess.nationalmap.gov; do
  printf "%-32s %s\n" "$h" "$(curl -s -o /dev/null -w '%{http_code}' "https://$h" || echo FAIL)"
done
```

---

## 4. Feasibility audit (verified against primary sources)

| Resource | Status | Notes / risk |
|---|---|---|
| USGS DOW (117,672 wells, 27 states) | ✅ verified | ScienceBase item `62ebd67bd34eacf539724c56`, DOI `10.5066/P91PJETI`. Static, reliable. Backbone. |
| LBNL U-Net + 1,301 candidates | ✅ verified | DOE EDX + OSTI mirror (`osti.gov/dataexplorer/.../2452768`). Download low-risk; **running** inference is the risk (no GPU; degrades off 1947–1992 1:24k symbology). |
| Census Geocoder / ACS | ✅ no key | **500 geocodes/day per IP** — must cache + use the batch endpoint (≤10k/file) to resolve all wells once. |
| CDC SVI / PLACES, NCES EDGE | ✅ | ArcGIS REST point queries; reliable; still federal. CORS irrelevant (server-side calls). |
| EPA SDWIS / Envirofacts / ECHO | ⚠️ | Works but historically slow/flaky → cache hard. |
| EJScreen | ⚠️ | Federal version removed Feb 2025. Prefer PEDP data via GitHub (`raw.githubusercontent`, already allowed) or fall back to CDC SVI for the equity metric. |
| AirNow | ⚠️ optional | Needs a free key; sparse rural coverage → opt-in garnish only. |
| Swarm web search | ✅ big win | Anthropic server-side web search via `ChatAnthropic` → only needs `api.anthropic.com`. |

**Key architectural consequence — ingest once, serve from cache:** federal endpoints move
(EJScreen/HIFLD already did in 2025), Census caps at 500/day, EPA times out. So a Python
**ingestion pipeline** hits each source ONCE and materializes a committed datastore
(SQLite + GeoJSON/Parquet); the app + swarm read from that (optional live refresh). Nothing
fragile runs during a demo. This doubles as the whitelist-fallback: the files to commit are
just this pipeline's outputs.

---

## 5. Architecture & repo layout (planned)

```
lostwells/
  apps/
    web/            Next.js (App Router) + TS + Tailwind + Framer Motion
                    MapLibre GL + deck.gl; ranked list / map / dossier panel;
                    topo-dissolve swipe; live swarm visualization
  services/
    ingest/         Python — pull all sources once -> data/processed datastore
    engine/         Python — ranking engine (methane proxy, Raimi plug-cost, composite score)
    swarm/          Python — LangGraph Send map-reduce; Claude subagents + web search;
                    per-node try/except + checkpointing + max_concurrency
    unet/           Python — rasterio + TF inference pipeline (documented; run where GPU/data)
  data/
    raw/            downloaded source data (gitignored / LFS)
    processed/      wells.geojson, candidates.geojson, dossiers.json, scores.parquet
    cache/          SQLite API cache keyed by (source, lat/lon rounded)
  docs/             ARCHITECTURE.md, DEMO_SCRIPT.md
  BUILD_PLAN.md     (this file)
```

### Ranking engine (network-independent; spec §4)
- **Methane proxy (labeled estimate):** EPA/Kang factors — unplugged ~31 g/hr, plugged ~0.4
  g/hr; `g/hr × 8760 / 1e6 = t CH4/yr`; CO2e via **GWP-100 = 30 (fossil)** for any money/credit
  math, **GWP-20 ≈ 84** only as a labeled "short-term urgency" sidebar. Show a range.
- **Plug cost (Raimi et al. 2021):** base state median × `1.20^(depth_ft/1000)` × `1.09 if gas`
  × age/elevation adjustments; medians ~$20k plug-only / ~$76k + reclamation; RFF ~$35k as
  sensitivity.
- **Composite score 0–100 (transparent, adjustable weights):** human exposure 45% (pop 15,
  schools 12, hospitals 5, drinking-water 13) + equity 20% (SVI 12, EJ 8) + methane 15% +
  fundability 20% (inverse plug cost 10, program match 10). Output a breakdown bar.
- **Carbon-credit kicker (honest):** ACR orphan-well methodology, GWP-100, buffer-pool;
  ~$10–$30/t range; pencils only for rare deep high-rate gas wells. Cite Zefiro ACR959.

### Swarm (spec §2.3 backup path, now primary)
- LangGraph router returns `[Send("well_investigator", {"well_id": w}) for w in batch]`;
  fan-in via `Annotated[list, operator.add]`; `max_concurrency` throttle; per-node try/except
  returns a partial-dossier sentinel; checkpointer for resume. **Single-threaded ranking node**
  writes the composite score (Cognition caveat). Open-ended web search = the "real agent" showcase.

### UI (spec §5)
- Dark desaturated "investigation" basemap (Carto dark / custom MapLibre style); one amber/ember
  accent for high-impact, teal for documented, red reserved for confirmed contamination.
- Editorial type pairing + tabular numerals. Left = virtualized ranked list; center/right = map;
  click → `flyTo` + dossier panel. `mapbox-gl-compare` → use **`@maplibre/maplibre-gl-compare`**
  for the swipe. Pre-build topo-dissolve for hero wells (Vowinckel PA; AllenCo LA; Admiral King OH).
- Swarm viz panel: agent nodes streaming status (searching → found operator → checking
  bankruptcy → scoring) landing dossiers onto map pins.

### Hero wells (sourced in spec §1.5)
- **Vowinckel, Clarion County, PA** — orphaned gas well 6 ft from a family's drinking-water well.
- **Admiral King Elementary, Lorain, OH** — leaking undocumented well under the school gym (2014).
- **AllenCo / University Park, LA** — urban wells across from St. Vincent School.

---

## 6. Build order (after whitelist verified + ingest done)

1. Verify reachability (probe above). Run `services/ingest` → materialize datastore. If any
   source fails, fall back per the audit (SVI for EJ, skip AirNow, etc.).
2. Ranking engine + unit tests (pure compute — can also start before ingest using sample wells).
3. Next.js + MapLibre + deck.gl skeleton; load wells/candidates; clustering; dark style.
4. Free-API joins surfaced; composite score + breakdown; ranked list + dossier panel + flyTo.
5. LangGraph swarm live on a small batch; swarm visualization; cached dossiers as seed/fallback.
6. Topo-dissolve hero interaction; carbon-credit kicker; polish (motion, empty/error states).
7. U-Net pipeline code + Kern County validation instructions (run where GPU/data exist).
8. Demo script + fallback video notes; deploy.

---

## 7. Whitelist-failure fallback — files for the user to commit

If Custom network access can't be made to work, commit these (then tell Claude the paths):

1. **USGS DOW** — from ScienceBase item `62ebd67bd34eacf539724c56` (DOI `10.5066/P91PJETI`):
   the data-release CSV/GeoPackage of 117,672 wells → `data/raw/dow/`.
2. **LBNL 1,301 candidates** — `found_potential_UOWs.zip` from EDX dataset
   `u-net-based-usgs-quadrangles-oil-and-gas-well-symbols-identification` → `data/raw/lbnl/`.
3. *(Only if attempting inference)* `unet_model.h5` + sample CA map + `CalGEM_AllWells_20231128.csv`
   from the same EDX dataset → `models/unet/` and `data/raw/calgem/`.

Per-well dossier API data can't be hand-committed; with `api.anthropic.com` available, the swarm's
web-search investigation still works, and EJScreen data comes from the PEDP GitHub mirror
(`raw.githubusercontent`, already allowed). Remaining keyed/federal lookups degrade gracefully.

---

## 8. Status log

- [x] Spec analyzed; environment probed; allowlist proxy identified.
- [x] Six decisions confirmed with user (table §2).
- [x] Whitelist mechanism + audited domain list delivered; feasibility audit done.
- [x] This handoff/plan committed.
- [ ] **NEXT:** user whitelists domains + starts fresh session, or commits fallback files.
- [ ] Re-verify reachability → run ingest → build per §6.
