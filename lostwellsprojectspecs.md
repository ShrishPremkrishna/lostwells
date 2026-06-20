# Build-Ready Methodology & Technical Spec: National Undocumented Orphaned Well Detection + Claude Agent Swarm + Award-Grade Map UI

## TL;DR
- **Feasible and high-ceiling, with one honest constraint:** Build the reliable core first (real well data + free proximity-join APIs + an award-grade map), pre-compute the risky parts (national U-Net inference, agent-swarm dossiers), and present them live with disclosed fallbacks. The 24h project is achievable for a strong builder; "national" U-Net inference should be a real but SPARSE stratified pass across many states, not full dense national coverage.
- **The novel core is defensible:** extend LBNL's CATALOG U-Net (Ciulla et al. 2024, *Environ. Sci. Technol.*, DOI 10.1021/acs.est.4c04413) beyond its 4 case-study counties, and run a Claude Agent SDK orchestrator-worker swarm (one investigator subagent per well) that builds an impact+economics dossier from scattered free public data, ranked by a transparent composite impact score under the finite ~$4.7B federal plugging budget.
- **Methane is an ESTIMATED proxy (EPA factors), never a satellite-methane gate** — abandoned wells emit grams/hour, far below satellite/aircraft detection floors (tens of kg/hr). Carbon credits are a secondary "this can pay for itself" kicker that only pencils for rare deep high-rate gas wells.

## Key Findings

### Feasibility verdict
- All required primary data sources are LIVE and mostly free/no-auth: USGS TNM Access API, USGS DOW dataset (117,672 wells), the LBNL U-Net model + 1,301 pre-computed candidates, Census Geocoder + Data API, NCES EDGE, CDC/ATSDR SVI, EJScreen mirrors.
- The Claude Agent SDK natively supports the orchestrator-worker subagent pattern. Per Anthropic Engineering's "How we built our multi-agent research system" (authors Jeremy Hadfield, Barry Zhang, Kenneth Lien, Florian Scholz, Jeremy Fox, Daniel Ford), "a multi-agent system with Claude Opus 4 as the lead agent and Claude Sonnet 4 subagents outperformed single-agent Claude Opus 4 by 90.2% on our internal research eval." LangGraph's Send API is a solid backup with per-node checkpointing.
- Full dense national U-Net inference (~57,000 7.5-minute quads for the lower 48; ~131,000 of ~190,000 HTMC maps usable) is NOT realistically feasible in the prep window. A stratified, multi-state sparse pass IS feasible and legitimately "national."

### National inference plan
- HTMC = ~190,000 scanned quads (1884–2006); >178,000 currently in the collection. The 7.5-minute / 1:24,000 series (consistent oil/gas symbology 1947–1992) is the target; ~57,000 7.5-minute maps cover the lower 48.
- Download programmatically via TNM Access API (`https://tnmaccess.nationalmap.gov/api/v1/products`) and the nightly-refreshed HTMC CSV inventory from topoView. The model expects georeferenced GeoTIFFs (topoView GeoTIFF + XML metadata).

### Claude Agent SDK swarm (primary) + LangGraph-Claude (backup)
- Primary: Claude Agent SDK orchestrator fans out one `well_investigator` subagent per well; each runs in an isolated context, uses tools (data-API MCP tools + WebSearch), and returns a structured dossier; a single ranking node aggregates (single-threaded writes per Cognition's caveat).
- Backup: LangGraph `Send` API map-reduce, one Send per well to a `well_investigator` node, `operator.add` reducer fan-in, `max_concurrency` throttle, checkpointing to survive superstep all-or-nothing failure.

### Impact ranking engine
- Methane proxy from EPA/Kang emission factors (~grams/hour), convert to tonnes CH4/yr → CO2e using BOTH GWP-100 (28–30) and GWP-20 (~80+); use GWP-100 for ACR/credit math and GWP-20 only as a labeled "short-term climate urgency" framing.
- Plugging cost from Raimi, Krupnick, Shah & Thompson (*Environ. Sci. Technol.* 2021, 55, 10224–10230, DOI 10.1021/acs.est.1c02234): "median decommissioning costs are roughly $20,000 for plugging only and $76,000 for plugging and surface reclamation… Each additional 1,000 feet of well depth increases costs by 20%… natural gas wells are 9% more expensive than wells that produce oil."
- Composite impact score combining population, schools/hospitals, drinking-water, SVI/EJ, methane proxy, plug cost, and fundability.

---

## Details

### 1. NATIONAL INFERENCE PLAN + REGIONAL FALLBACKS

**1.1 The model and pre-computed assets (already public)**
- Paper: Ciulla, Santos, Jordan, Kneafsey, Biraud & Varadharajan, 2024, *Environmental Science & Technology*, DOI 10.1021/acs.est.4c04413 (also OSTI 2479818; PMC11656717).
- Model + code: DOE EDX, DOI 10.18141/2452768 — `unet_model.h5` (U-Net semantic segmentation), TensorFlow 2.0 training/inference code, a sample CA map, `CalGEM_AllWells_20231128.csv`, and `found_potential_UOWs.zip` (1,301 candidate UOWs across 4 counties in CA + OK, over >40,000 km²). EDX page: `https://edx.netl.doe.gov/dataset/u-net-based-usgs-quadrangles-oil-and-gas-well-symbols-identification`.
- Method: detect oil/gas well symbols on georeferenced HTMC quads → a detected symbol >100 m from any documented well = candidate UOW. The paper states the framework "can be scaled to identify potential UOWs across the US since the historical maps are available for the entire nation." They confirmed 29 UOWs from satellite imagery + 15 from magnetic surveys, ~10 m spatial accuracy.
- **Gotcha (flag and validate live):** the model was trained on the 1947–1992 7.5-minute / 1:24,000 series with consistent well symbology. Performance will degrade on different-era (pre-1947), different-scale (1:62,500, 1:250,000), or different-region symbology. **Validate on a known LBNL county first** (e.g., Kern County, CA) to confirm your pipeline reproduces their published detections before trusting new ground.

**1.2 USGS HTMC bulk download — exact endpoints**
- **TNM Access API** (HTTP GET/POST, no key): base `https://tnmaccess.nationalmap.gov/api/v1/products`. Key params (confirmed from leafmap/USGS docs):
  - `bbox` = `minx,miny,maxx,maxy` (decimal degrees) or `polygon` = space-delimited `x,y` list
  - `datasets` = dataset tag (HTMC = "USGS Historical Topographic Map Collection"; current = "US Topo")
  - `prodFormats` = `GeoTIFF` (also GeoPDF, JPEG, KMZ)
  - `polyType` = `state|huc2|huc4|huc8`, `polyCode` = the code
  - `dateType` = `dateCreated|lastUpdated|Publication`, `start`/`end` = `YYYY-MM-DD`
  - `outputFormat` = `JSON|CSV|pjson`, `offset`, `max`
  - **Limit: ~50 files per request** (USGS guidance via the VisiMod repo) — keep bounding boxes small enough that each query returns <50 tiles; paginate with `offset`.
  - Example: `https://tnmaccess.nationalmap.gov/api/v1/products?bbox=-122.5,37.5,-122,38&datasets=US%20Topo&prodFormats=GeoTIFF`
- **Nightly CSV inventory** (best for bulk/scripted selection): topoView publishes an inventory of all HTMC + US Topo products refreshed nightly (CSV), explicitly intended to "write download scripts." Reachable from the topoView site (`https://ngmdb.usgs.gov/topoview/`). Fields include map name, state, scale, date, series, and GeoTIFF/GeoPDF download URLs. **Filter to scale=1:24,000 + series=7.5-minute + date 1947–1992** to isolate the consistent-symbology subset.
- **Direct cloud browse:** USGS stages products on the Amazon `prd-tnm` S3 bucket, reachable via the `downloadURL` field in API/CSV responses — fetch GeoTIFFs directly, no auth.
- **ScienceBase** backs the catalog. Note: the catalog shuts down ~11pm–1am Mountain for nightly backup → "Inventory request failure" errors; schedule downloads around it.
- File sizes: HTMC GeoTIFFs are tens of MB (US Topo median ~22 MB; HTMC similar order). A sparse national pass of ~500–1,000 quads ≈ ~10–40 GB — manageable.

**1.3 Compute/time budget — honest estimate**
- Lower-48 7.5-minute coverage ≈ 57,000 quads. Each tiled into 256×256 patches (LBNL pipeline) → a 1:24,000 GeoTIFF (~5,000–7,000 px/side) yields a few hundred to ~1,000 patches each. Full dense national = tens of millions of patch inferences + tens of TB of downloads + georeferencing.
- **Single-GPU U-Net inference** at 256×256 runs at hundreds of patches/sec on a modern GPU (T4/A10/L4), but the bottleneck is download + GeoTIFF I/O + georeferencing, not the matmul. Realistic end-to-end: **single-digit to low-tens of quads per minute per worker** including I/O.
- **Verdict:** Full dense national in 24h = INFEASIBLE. A **stratified sparse national pass is FEASIBLE and defensible**: pick ~10–20 quads in each of ~15–25 heavy oil/gas legacy states, ~300–600 quads total. At even ~5 quads/min that's a few hours of pre-compute. This legitimately supports "we ran the detector on new ground in N states nationwide" without overclaiming. **Recommendation: do the sparse stratified national pass during PREP, cache all detections as GeoJSON, and frame live national inference as a demo on 1–3 fresh quads on stage.**

**1.4 Regional fallback targets (NOT LBNL's 4 counties: LA Co. & Kern Co. CA, Osage & Oklahoma Co. OK)**
- **Appalachia / Pennsylvania** — oldest US oil region (Drake well, Titusville 1859; Bradford field). PA DEP "tracks approximately 27,000 wells in our database with no viable owner to plug in PA" (PA DEP CCAC presentation, 4/22/2025), and estimates "As many as 300,000 to 760,000 wells have been drilled in PA; between 100,000 and 560,000 oil and gas wells remain unaccounted for in state records." EDF cites "300,000 to 700,000… but only 30,000 have been documented." A peer-reviewed data-driven estimate (Science of the Total Environment, 2025) puts ~340,827 undocumented orphan wells in PA. Excellent historical map coverage and dense human exposure.
- **Ohio** — ~19,662+ documented orphaned; about 24% of Ohioans live within 1 mile of an active well; strong school-exposure story.
- **West Virginia** — about half of WV's ~1.8M residents live within 1 mile of an active well (highest % in the nation); dense legacy wells.
- **Secondary options:** LA Basin urban wells (rich exposure even if partly LBNL); Oklahoma beyond Osage; Illinois Basin; Texas Panhandle.

**1.5 Cinematic demo wells (specific, sourced)**
- **Vowinckel, Clarion County, PA** — an orphaned gas well **6 feet** from a family's only drinking-water well; PA DEP confirmed iron contamination made the water unusable for ~5 months; plugged Oct 2024. PA DEP press release: "This gas well is located just six feet away from the family's potable water well – and the DEP had confirmed iron from the gas well was getting into the water well." **This is your hero "topo-dissolve" candidate** for an Appalachian drinking-water story.
- **Admiral King Elementary School, Lorain, Ohio (2014)** — 375 students/teachers evacuated; ODNR found a leaking, undocumented oil/gas well **under the school gym** after a 5-week search; >$100k and ~3 months to remediate (NRDC). **This is the schoolyard hero.**
- **AllenCo / University Park, Los Angeles** — 21 wells <1,000 ft from St. Vincent School, ~800 people within 600 ft, ~80% Latino; decades of fumes/illness; permanently plugged 2026 (LA Times / Center for Public Integrity / CBS LA). The site has been an oil site since the 1950s/1963 — **a perfect 1950s-topo → modern-satellite reveal** and the urban-exposure hero.
- National framing: Payne Institute (Colorado School of Mines): "Over 4.6 million people live within 1 kilometer of a documented orphan well and 35% of documented orphans are located within 1 km of a groundwater well."

**1.6 No-inference alternate plan (if U-Net fails entirely in-hackathon)**
- Load `found_potential_UOWs.zip` (1,301 LBNL candidates) + USGS DOW directly as GeoJSON. Per USGS Data Report 1167 (Merrill, Grove, Gianoutsos & Freeman, 2023; data by Grove and Merrill, 2022; DOI 10.3133/dr1167): "The DOW dataset includes 117,672 wells across 27 states," compiled in support of the Bipartisan Infrastructure Law program that "included nearly $4.7 billion" for orphaned-well plugging and remediation. Every well already has coordinates, so all proximity joins and the agent swarm work with zero new inference.
- Frame national inference as "extending the pipeline," and show whatever sparse new detections succeeded in prep as the novel layer atop the documented backbone. This guarantees a working demo regardless of inference success.

**1.7 TensorFlow 2.0 setup + georeferencing + dedup**
- Env: `tensorflow==2.x`, `rasterio` (GeoTIFF + embedded CRS), `numpy`, `geopandas`, `shapely`, `Pillow`. Load model: `model = tf.keras.models.load_model("unet_model.h5", compile=False)`.
- Pipeline: read GeoTIFF with rasterio → window into 256×256 patches → `model.predict` → threshold the segmentation mask → centroid of each detected symbol blob → use rasterio's affine `transform` (`rasterio.transform.xy`) to convert pixel (row,col) → map CRS → reproject to EPSG:4326 lon/lat.
- Dedup against documented wells: load DOW + state-DB points into a GeoPandas GeoDataFrame, reproject to a metric CRS (UTM or EPSG:5070 CONUS Albers), buffer documented wells by 100 m, spatial-join (`gpd.sjoin`) detections; any detection NOT within 100 m of a documented well = candidate UOW (exactly the LBNL rule).
- Gotcha: HTMC maps use outdated datums (NAD27 etc.) embedded in the GeoTIFF — let rasterio read the embedded CRS and reproject; don't assume WGS84.

### 2. CLAUDE AGENT SDK SWARM (PRIMARY) + LANGGRAPH-CLAUDE (BACKUP)

**2.1 Claude Agent SDK (2025–2026)**
- The SDK (renamed from "Claude Code SDK" in Sept 2025) is the same harness that powers Claude Code, exposed as a library (TypeScript + Python). It handles the agent loop, tool execution, context compaction, and subagents — you don't write the `stop_reason`/tool-result plumbing.
- **Subagents:** define agent types in the `agents` parameter (each with description, system prompt, restricted tools, optional different model). Include `Task` (the Agent tool) in `allowedTools` so the orchestrator can spawn them. Each subagent runs in its own fresh isolated context; only its final message returns to the parent. Multiple subagents run concurrently. **Subagents cannot spawn their own subagents** (never put `Task`/`Agent` in a subagent's tools) — enforce no-recursion at the orchestration layer (Anthropic's own caveat).
- **Built-in tools** (referenced by name as strings): Read, Write, Bash, Glob, Grep, **WebSearch, WebFetch**, and more. Custom tools plug in as MCP servers via the same `allowedTools` pattern.
- **Scale caveat:** subagents are tuned for a few delegated tasks per turn; for "dozens to hundreds of agents" Anthropic recommends the Workflow tool (TS SDK v0.3.149+), which moves orchestration into a script run outside the conversation context. For a hackathon (tens of wells), batch the subagent fan-out (e.g., 5–10 wells/turn) rather than 100 at once.
- Reference architecture: Anthropic "How we built our multi-agent research system" — orchestrator-worker; Opus 4 lead + Sonnet 4 subagents beat single-agent Opus 4 by **90.2%**; lead spins up 3–5 subagents in parallel, each uses 3+ tools in parallel, cutting research time up to 90%. Token cost ~**15×** a single chat. Contract per subagent: objective, output format, tool/source guidance, clear boundaries.

**2.2 Concrete orchestrator-worker design (per well)**
- Orchestrator system prompt: "You are the lead investigator. For each well in the provided list, delegate to the `well_investigator` subagent with the well's ID, lat/lon, and known attributes. Do not investigate wells yourself. After all subagents return, pass their structured dossiers to the `ranking` step." Mention the subagent by name to force delegation.
- `well_investigator` subagent (one per well): tools = custom MCP data tools (`census_lookup`, `schools_nearby`, `svi_lookup`, `water_system_lookup`, `airnow_lookup`) + `WebSearch`/`WebFetch`. Output: a strict JSON dossier (operator history, bankruptcy/shell-transfer findings, proximity metrics, methane proxy, plug-cost estimate, fundability, narrative).
- **Agentic-not-theater requirement:** at least the operator/bankruptcy/news investigation MUST be open-ended `WebSearch` (find original operator, bankruptcy filings, shell-company transfers, local news). This is the defensible "real agent" showcase for sophisticated judges — deterministic API lookups alone are not "agentic."
- Aggregation = **single-threaded writes**: each subagent returns its dossier; ONE ranking node computes the composite score and ordering. Don't let parallel agents write shared ranking state (Cognition "Don't Build Multi-Agents" caveat — context/decisions must be linearized at the write step).
- Note: the user can ALSO use **Claude Code as the build tool** for the hackathon itself (scaffolding the Next.js app, wiring APIs) — distinct from the runtime swarm.

**2.3 LangGraph-with-Claude backup**
- Model: `from langchain_anthropic import ChatAnthropic; llm = ChatAnthropic(model="claude-sonnet-4-...")`.
- Map-reduce fan-out: a router function returns `[Send("well_investigator", {"well_id": w}) for w in state["wells"]]`; each `Send` spawns an independent branch with its own payload (keep payload tiny — send IDs, let the node fetch data).
- Fan-in: state field `Annotated[list, operator.add]` reducer concatenates each branch's dossier.
- Concurrency: `graph.invoke(inputs, config={"max_concurrency": 8})` to throttle and avoid 429s.
- **Critical robustness:** a superstep is transactional — if one branch fails, ALL branches in the superstep lose state updates. Mitigate with (a) per-node try/except returning a partial-dossier sentinel instead of raising, (b) checkpointing (a checkpointer saves successful nodes so only failed branches retry on resume), and (c) batching Sends.

**2.4 Which to use — recommendation**
- **Primary: Claude Agent SDK** — least boilerplate, native subagents + parallelism + context isolation, built-in WebSearch (the agentic showcase), and it doubles as your build tool. Best for a working demo fast.
- **Fallback trigger → switch to LangGraph** if: (a) you need fine-grained control over concurrency/retries that the SDK's auto-scheduling fights you on, (b) you hit Agent-SDK rate/permission friction with many parallel subagents, or (c) you want deterministic checkpoint/replay for the on-stage demo.
- Watch: **token cost ~15× single-agent** — for a demo, cap to ~10–30 wells investigated live, pre-compute the rest. Use Sonnet for subagents, Opus/Sonnet for the lead. Respect Anthropic API rate limits (batch fan-out 5–10/turn).

### 3. DATA SOURCES / APIs FOR THE PER-WELL DOSSIER (validated, with query patterns)

For every source: prefer free/no-auth; cache every response keyed by (source, lat/lon rounded) to a local SQLite/JSON cache so the live demo never refetches.

**3.1 Population / demographics**
- **Census Geocoder (no key)** — point → FIPS: `https://geocoding.geo.census.gov/geocoder/geographies/coordinates?x={lon}&y={lat}&benchmark=Public_AR_Current&vintage=Current_Current&format=json`. Returns State/County/Tract/Block. Note: no CORS → call server-side or use `format=jsonp` + callback. Returns block GEOID you then use against ACS.
- **Census Data API (ACS 5-year)** — `https://api.census.gov/data/2023/acs/acs5?get=B01003_001E,B17001_002E&for=tract:{tract}&in=state:{st}+county:{co}`. Returns total population, poverty, etc. A free key is recommended for volume. Cache per tract.

**3.2 Schools**
- **NCES EDGE public school point ArcGIS REST** (no key): e.g. `https://nces.ed.gov/opengis/rest/services/K12_School_Locations/EDGE_GEOCODE_PUBLICSCH_2223/MapServer/0/query` (use latest year). Query within radius: `?geometry={lon},{lat}&geometryType=esriGeometryPoint&distance=1609&units=esriSRUnit_Meter&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=SCH_NAME,LEA_NAME,LCITY&returnGeometry=true&f=json`. CSV bulk via `data-nces.opendata.arcgis.com`.

**3.3 Hospitals / healthcare**
- **HIFLD Open hospitals** ArcGIS Hub layer (no key) — point-radius query like NCES. (HIFLD hosting has changed; the PEDP "hifld-next" GitHub mirror is a backup if the federal layer moves.)

**3.4 Drinking water**
- **EPA Envirofacts / SDWIS** (no key): SDWIS REST for community water systems. **EPA Community Water System Service Area boundaries** for point-in-polygon (which system serves this well's location). **ECHO** (`echo.epa.gov`) for facility/violation context. Cache aggressively; these can be slow.

**3.5 Environmental justice (federal tools removed early 2025 — use mirrors, disclose provenance)**
- **EJScreen v2.3 reconstruction (Public Environmental Data Partners):** `https://pedp-ejscreen.azurewebsites.net/` (UI) + PEDP GitHub (`Public-Environmental-Data-Partners/EJScreen`, `EJAM-API`, `ejamdata`) for data/API. Also mirrored at `screening-tools.com/epa-ejscreen` and Yale Energy History. **Disclose: "EPA removed EJScreen from federal sites Feb 5, 2025; we use the PEDP community reconstruction of v2.3."**
- **Backup (still federal, no-auth): CDC/ATSDR SVI** ArcGIS REST point query: `https://onemap.cdc.gov/OneMapServices/rest/services/SVI/CDC_ATSDR_Social_Vulnerability_Index_2022_USA/FeatureServer/{layer}/query?geometry={lon},{lat}&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=RPL_THEMES&returnGeometry=false&f=json`. `RPL_THEMES` = overall percentile vulnerability 0–1. Use the tract layer.
- **CDC PLACES** (Socrata SODA, no key for moderate use): `https://data.cdc.gov/resource/cwsq-ngmh.json?$where=...` for tract-level health outcomes (asthma, etc.).

**3.6 Air quality**
- **EPA AirNow API** (free key): `https://docs.airnowapi.org` — current/forecast AQI by lat/lon. **EPA AQS API** (`https://aqs.epa.gov/data/api`, free email/key) for historical monitor data. Monitors are sparse → AirNow may return nothing rural; treat as optional garnish.

**3.7 Well records (dedup/confirmation)**
- **USGS DOW** (117,672 wells, 27 states) — the backbone for dedup and the no-inference fallback (USGS DR1167; Boutot et al. 2022, DOI 10.1021/acs.est.2c03268).
- State DBs: **Texas RRC**, **CalGEM AllWells** (CSV used by LBNL), **PA DEP**, **Ohio DNR**, **Oklahoma Corporation Commission**. Use for confirmation and richer attributes; formats vary (download CSV/shapefile, cache).

**3.8 Ownership / parcels (be honest about cost)**
- **Regrid** parcel API — paid, ~1-week trial, gives a **current-owner snapshot only (no title chains)**. Recommend surfacing current owner only, or scoping out entirely for the hackathon. **PLSS/BLM** for legal land descriptions (free).

**3.9 Operator / bankruptcy**
- **Open-ended LLM WebSearch** (the agentic showcase): original operator, bankruptcy filings (PACER/news), shell-company transfers, local news. No fixed API — this is deliberately agentic.

### 4. FINANCIAL / IMPACT RANKING ENGINE

**4.1 Methane proxy (estimate, clearly labeled)**
- Sources: EPA GHG Inventory abandoned-wells methodology; Kang et al. 2016 EFs (g/hr/well by plugging status, coal-area, oil vs gas); Townsend-Small et al. (plugged vs unplugged, east vs west); Williams et al. 2021 (top 10% of wells, >10 g/hr, emit ~91% of emissions — heavy right tail).
- Representative point factors: **unplugged ~31 g/hr; plugged ~0.4 g/hr** (project's established figures), with the caveat that regional studies (e.g., N. Louisiana mean 57.4 g/hr, range 0–1,368; Driscoll et al. 2025) show much higher right tails. Treat as ESTIMATE; show a range, not false precision.
- Conversion: `g/hr × 24 × 365 / 1e6 = tonnes CH4/yr`. Example unplugged: `31 × 8760 / 1e6 ≈ 0.27 t CH4/yr` (order ~0.13 t/yr cited as typical — consistent within the spread). Then `t CH4/yr × GWP = t CO2e/yr`.
- **GWP guidance (don't get caught):** State both. **GWP-100 = 28 (biogenic) / 30 (fossil)** per IPCC AR5 — the value EPA + ACR use for inventories and credits → **use GWP-100 for all carbon-credit and official-inventory math.** **GWP-20 ≈ 84–86 (AR5) / ~81–83 (AR6 fossil)** → use ONLY as an explicitly labeled "20-year climate-urgency" framing for the pitch, never mixed into credit math. AR6 GWP-100 ≈ 29.8 (fossil ~30). Recommendation: default GWP-100=30 (fossil methane) for any number that touches money; show GWP-20≈84 as a "short-term impact" sidebar.

**4.2 Plugging cost model (Raimi et al. 2021, DOI 10.1021/acs.est.1c02234)**
- From ~19,500 wells: **median ~$20,000 plug-only; ~$76,000 plug + surface reclamation**; rare cases >$1M.
- Cost drivers (verbatim from the paper): **+20% per additional 1,000 ft of depth**; older wells cost more; **gas wells +9% vs oil**; **+3% per additional 10 ft of elevation change** in the 5-acre surrounding area; wide state variation; bulk discounts for batched programs.
- Usable formula: `cost ≈ base_state_median × (1.20)^(depth_ft/1000) × (1.09 if gas) × age/elevation adjustments`. Use the $76k reclamation median as the decision-relevant figure for surface sites near people. (RFF's 2026 six-state working paper reports a ~$35k median in a newer dataset — cite as a sensitivity range.)

**4.3 Carbon-credit kicker (secondary, clearly labeled)**
- ACR Orphan Well Methodology (first published 2023); credits = avoided methane converted at GWP-100. Apply ACR's **buffer-pool deduction**, the defined crediting period, and additionality rules. EPA estimates orphaned/abandoned wells emit ~7–20 MMT CO2e/yr nationally.
- **Real transaction:** Zefiro Methane Corp. press release (Newsfile, Aug 19, 2025): "issuance of certified carbon credits from American Carbon Registry ('ACR') Project 959 ('ACR959') reflecting confirmed emissions reductions of 92,956 metric tonnes of CO2 equivalent… Completed delivery of the first tranche… to Mercuria Energy America, LLC." The well (Custer County, OK) was plugged/monitored ~June 21, 2025; VVB validation ~July 29, 2025; credits delivered in four equal 25% tranches; EDF Trading completed payment Aug 29, 2025; CEO Catherine Flax called it "a landmark development." First-ever sale under ACR's orphan-well methodology.
- **Price:** voluntary-market average ~$6.34/tonne in 2024 (Ecosystem Marketplace "State of the VCM 2025," via Environmental Finance: "the average price of credits sits at $6.34 per tonne… down from $6.71 in 2023"). MSCI Carbon Markets 2025 reports a two-tier market — high-rated credits (A–AAA) averaged ~$14.80/ton vs ~$3.50/ton for low-quality (CCC–B). Grist reports experts estimate orphan-well credits "can fetch at least $10 to $30 per credit." No Zefiro per-tonne price was publicly disclosed. **Volatile, two-tier, nascent market — cite a $10–$30 range, not a point.**
- **Honest math:** at ~0.27 t CH4/yr × 30 = ~8 t CO2e/yr/well, even over a 10-year crediting period (~80 t CO2e) at $15/t ≈ ~$1,200/well — **far below the ~$76k plug cost.** Credits only pencil for **rare deep, high-rate gas wells** (the >10 g/hr right tail). Present this honestly: "self-funding is the exception, not the rule; that's why public funding (the ~$4.7B federal program) is needed and why prioritization matters."

**4.4 Composite impact score (transparent, explainable)**
- Normalize each sub-metric to 0–1 (min-max or percentile across the candidate set), then weighted sum. Suggested transparent default:
  - **Human exposure 45%:** population within 1 mi (15%), schools/daycares within 1 mi (12%), hospitals/sensitive sites (5%), drinking-water proximity / served system (13%)
  - **Equity 20%:** SVI percentile (12%) + EJ burden (8%)
  - **Methane proxy 15%** (estimate-flagged)
  - **Tractability/fundability 20%:** inverse plug cost (10%) + funding eligibility / state-program match (10%)
- Output a per-well score 0–100 with a **breakdown bar** so judges see exactly why a well ranks high. Make weights adjustable via a UI slider panel (shows it's a decision tool, not a black box). Always label methane as "modeled estimate (EPA factors)."

### 5. AWARD-GRADE UI/UX

**5.1 Stack**
- **Next.js (App Router) + React + TypeScript.** Map: **Mapbox GL JS** for the signature swipe (mature `mapbox-gl-compare` plugin) + **deck.gl** overlay for performant thousands-of-points rendering. (MapLibre GL is the no-token open alternative; `maplibre-gl-compare` exists too.) Use Mapbox for the hero style + satellite, deck.gl `ScatterplotLayer` for wells.
- **Framer Motion** for motion design; **Tailwind** for layout but with a custom design system (NOT the default shadcn look).

**5.2 Signature moment — "1950s topo dissolving into present-day satellite over a school"**
- Use **`mapbox-gl-compare`** (v0.4.0): two synced maps, draggable swipe slider. Load script/CSS from `https://api.mapbox.com/mapbox-gl-js/plugins/mapbox-gl-compare/v0.4.0/`. Code:
  ```js
  const before = new mapboxgl.Map({ container:'before', style: histStyle, center, zoom });
  const after  = new mapboxgl.Map({ container:'after',  style:'mapbox://styles/mapbox/satellite-v9', center, zoom });
  new mapboxgl.Compare(before, after, '#wrap', { mousemove:true, orientation:'vertical' });
  ```
- **Historical layer** = USGS topoView HTMC GeoTIFF for the hero quad. Convert to web tiles (rio-tiler / `gdal2tiles`) or use a georeferenced raster source in the `before` style. **Modern layer** = Mapbox Satellite (`satellite-v9`, up to 5 cm in cities) or ESRI World Imagery.
- For an automated cinematic reveal (not just manual drag), animate `compare.setSlider(x)` over time, OR crossfade with `setPaintProperty(map,'raster-opacity', t)` on a stacked raster layer. Land on the well marker pulsing over the school/home.
- **Pre-build this for 1–2 hero wells in prep** (Vowinckel PA drinking-water well; AllenCo/University Park LA school well) — don't generate it live.

**5.3 Design direction**
- **Custom Mapbox Studio style** (NOT default streets): dark, desaturated "investigation" basemap — near-black land, muted teal water, thin warm-grey roads, so the data and topo pop.
- **Typography:** a confident editorial pairing — a grotesk/serif display (GT Sectra, Tiempos, or Fraunces) for headlines + a clean grotesk (Inter, Söhne, or Geist) for UI/data. Tabular numerals for metrics.
- **Color system (restrained, environmental-investigation):** desaturated base + ONE urgent accent (amber/ember) for high-impact wells, a cool secondary (teal) for documented wells, danger red reserved only for confirmed contamination/exposure. Sequential ramp for the impact score.
- **Dossier presentation:** each well = a beautiful card/panel — header (well name, operator, status), the score with a breakdown bar, a mini topo-dissolve thumbnail, proximity chips (🏫 0.3 mi, 💧 served by X system), the methane estimate (clearly labeled), plug-cost estimate, and the **agent's narrative findings** (operator history, bankruptcy, news) as the "investigation" section. Motion: cards stagger in with Framer Motion.
- **Layout:** left = ranked list (virtualized), center/right = map; click a well → `flyTo()` + dossier panel slides in. Reference best-in-class: NYT/Bloomberg/Reuters investigative scrollytelling map pieces, The Pudding, and ProPublica map investigations.

**5.4 Live agent-swarm visualization (make AI visible)**
- A panel showing N investigator agents as nodes; as each subagent runs, animate its status (searching → found operator → checking bankruptcy → scoring), stream tool-call labels, and "land" each completed dossier onto its map pin with a pulse. Stream from the Agent SDK's event stream (or LangGraph's per-node events). This is the on-stage "the AI is really working" moment — pre-record a fallback video in case live streaming stutters.

**5.5 Performance**
- Thousands of well points: deck.gl `ScatterplotLayer` (GPU) or Mapbox `circle` layer with **clustering** at low zoom; render dossiers only on demand. Keep payloads lean (GeoJSON with minimal props; lazy-load full dossier on click). Debounce map-move queries. Pre-tile the hero topo. Target 60fps by keeping map state out of the React render path (avoid re-renders on map move).

### 6. 24-HOUR BUILD PLAN + PITCH

**6.1 Pre-hackathon prep (if allowed)**
- Run the **sparse stratified national U-Net pass** (~300–600 quads across 15–25 states); cache detections as GeoJSON.
- Validate the model on **Kern County** to confirm pipeline correctness.
- Load DOW (117,672) + LBNL 1,301 candidates; pre-run proximity joins + composite scores for the full set; cache all API responses.
- Pre-run the **agent swarm on ~20–50 hero/representative wells**; store dossiers as JSON.
- Pre-build the **topo-dissolve** for 1–2 hero wells (Vowinckel, AllenCo).
- Build the custom Mapbox style.

**6.2 Hour-by-hour (front-load the reliable core)**
- **H0–3:** Next.js scaffold, Mapbox map with custom style, load DOW + candidate GeoJSON, deck.gl ScatterplotLayer with clustering. (Reliable core visible.)
- **H3–7:** Wire free no-auth APIs (Census Geocoder + ACS, NCES, CDC SVI) as server-side cached tools; compute + render composite score + breakdown for visible wells. (Real proximity joins working.)
- **H7–11:** Dossier panel + ranked list + click-to-fly UX; integrate pre-computed dossiers; polish typography/motion.
- **H11–15:** Claude Agent SDK orchestrator + `well_investigator` subagent with MCP data tools + WebSearch; run live on a small batch; build the swarm visualization panel. (LangGraph backup ready if SDK fights you.)
- **H15–18:** Wire the topo-dissolve hero interaction into the UI; EJScreen/AirNow garnish; carbon-credit kicker math + label.
- **H18–21:** Polish — empty/error states, loading shimmer, color/motion pass, demo-path hardening; cache everything; pre-record fallback video of the live swarm.
- **H21–24:** Rehearse the demo script; freeze code; deploy (Vercel); buffer for breakage.

**6.3 Live vs. pre-computed (disclose)**
- **Live:** map exploration, click-to-dossier, composite-score recompute on slider change, the topo-dissolve, and a SMALL live agent-swarm run (5–10 wells).
- **Pre-computed-and-disclosed:** the national U-Net detections, the bulk of agent dossiers, the hero topo tiles. Say so explicitly — judges respect honest engineering.

**6.4 Biggest risks ranked + backups**
1. **National U-Net inference doesn't finish / model degrades on new maps** → Backup: sparse prep pass + no-inference DOW/1,301-candidate fallback; validate on Kern first; frame as "extending the pipeline."
2. **Live agent swarm stutters/rate-limits on stage** → Backup: pre-computed dossiers + pre-recorded swarm video; cap live run to 5–10 wells; LangGraph checkpoint/replay.
3. **Federal data tool moved/down (EJScreen, HIFLD)** → Backup: PEDP mirrors + CDC SVI (still federal); cache all responses pre-demo so nothing fetches live.
4. **Mapbox token/billing or topo-tile issues** → Backup: MapLibre + ESRI World Imagery; pre-tiled local topo.
5. **GeoTIFF georeferencing/datum errors** → Backup: let rasterio read embedded CRS; validate against known wells; if off, fall back to documented-well coordinates.
6. **Token cost blowup (~15×)** → Backup: Sonnet subagents, cap live wells, batch fan-out 5–10/turn.

**6.5 Pitch framing (human exposure first)**
- **Hook (human):** Czolowski et al., *Environmental Health Perspectives*, Aug 23, 2017 (PSE Healthy Energy / UC Berkeley / Harvey Mudd), the first peer-reviewed nationwide proximity study: "An estimated 17.6 million Americans live within one mile of an active oil or gas well" — including ~1.4M children under 5 (West Virginia ~50% of residents, Oklahoma 47%). For undocumented orphaned wells the exposure is literally uncounted — wells under a school gym (Admiral King, Ohio), 6 ft from a family's drinking water (Vowinckel, PA), across from a school (AllenCo, LA). Payne Institute: "Over 4.6 million people live within 1 kilometer of a documented orphan well and 35% of documented orphans are located within 1 km of a groundwater well."
- **Scale of the problem:** 310,000–800,000 undocumented orphaned wells exist (Ciulla et al.; IOGCC); only 117,672 documented (USGS DOW, DR1167).
- **The money:** the BIL allocated "nearly $4.7 billion" for orphaned-well plugging and remediation; **~$20k–$76k per well** (Raimi et al. 2021); tens of billions in national liability. Prioritization under a finite budget is exactly what decision-makers need — that's our product.
- **Self-funding kicker (honest):** carbon credits (ACR orphan-well methodology; Zefiro's 92,956 tCO2e ACR959 sale to Mercuria/EDF, Aug 2025) can offset some cost — but only for rare deep high-rate gas wells; most wells need public funds. We surface which wells can pay for themselves.
- **Defend the architecture (proactive slide):** Anthropic orchestrator-worker beat single-agent by 90.2%; we use isolated-context subagents per well with open-ended web investigation (real agency, not theater), and single-threaded writes at the ranking step (Cognition's caveat) to avoid context corruption.
- **Tie to prizes:** Claude **societal-impact** prize (a real public-health + climate prioritization tool built on a Claude agent swarm) + **UI/UX** prize (a designed investigative product with a signature topo-to-satellite reveal, not a Streamlit dashboard).

## Recommendations
1. **Now → prep:** download the LBNL model + DOW + 1,301 candidates; validate on Kern County; run the sparse stratified national pass; pre-compute joins/scores; pre-build the two hero topo-dissolves; pre-run ~20–50 agent dossiers. **Threshold to change course:** if Kern validation doesn't reproduce LBNL detections within a few hours, **drop live inference entirely** and go no-inference + "extending the pipeline."
2. **Build order:** reliable core (map + real data + free APIs) before risky core (swarm + national inference). **Trigger:** if by H15 the Agent SDK is fighting parallelism/rate limits, **switch to LangGraph** immediately.
3. **Demo discipline:** everything fragile is cached and disclosed; live run capped to 5–10 wells; fallback video recorded.
4. **Honesty as a weapon:** label methane as a modeled estimate, disclose data mirrors, and state pre-computed vs. live — this defends against sophisticated judges better than overclaiming, and directly supports the societal-impact narrative.

## Caveats
- The "national" claim must be framed as a real-but-sparse stratified pass, not comprehensive coverage; full dense national inference is infeasible in 24h.
- The U-Net was trained on 1947–1992 1:24,000 symbology; detection quality on other eras/scales/regions is unvalidated — flag and spot-check.
- Methane figures are EPA-factor estimates with a heavy right tail; never present as measured. Satellite/aircraft methane sensors cannot detect typical abandoned wells (grams/hr vs tens-of-kg/hr floors) — use Carbon Mapper only for the rare visible super-emitter garnish.
- Carbon-credit prices are volatile and the orphan-well market is nascent; the per-tonne range (~$10–$30) is an informed expert estimate (Grist) — no Zefiro per-tonne price was publicly disclosed.
- Federal data tools (EJScreen, HIFLD) have already moved once in 2025; verify every endpoint is live the day before the demo and cache responses.
- Regrid parcel data is paid and current-owner-only (no title chains) — scope ownership carefully.
- PA orphaned-well counts vary by source/definition; the cleanest defensible pairing is ~27,000–30,000 documented (PA DEP / EDF) vs. 300,000–700,000 estimated total, backed by a peer-reviewed ~340,000-undocumented estimate (Science of the Total Environment, 2025).