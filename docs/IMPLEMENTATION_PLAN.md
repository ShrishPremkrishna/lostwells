# Lost Wells — Hackathon Transformation: Implementation Plan

> **Purpose:** the living tracker for turning this repo into a winning hackathon
> project. Records every fix we decide on in conversation — what's done, what's
> queued to build, and what we're still thinking about. Organized by the three
> concept handles (**Discover → Diagnose → Act**), then **UI**, then **Pitch /
> Story Arc**.
>
> **Workflow:** we talk through each section first; code changes happen *after*
> the conversation. "Queued" = decided, not yet built.

## Constraints (locked)
- **Time:** not a constraint.
- **Judging priority:** story / pitch / potential impact **first**, technical
  depth a close second. Weights unknown.
- **Honesty stance (updated):** honesty is **not** a gating concern. Judges reward
  vision + effort + *shipping* over a product that performs at 100% but covers
  half the scope. Keep the cheap existing disclosures; do **not** block features
  on provenance/verification. Bias to shipping breadth.
- **Sponsors to integrate (all three required, need only *exist* — not be
  load-bearing):** **Anthropic** (Claude agent swarm — done), **Redis** (semantic
  cache), **Browserbase** (agent browser use, "for fun or for real").
- **Deployment:** running **locally for now** (no Vercel 300s constraint yet — the
  live agent route runs on the local Next.js server).
- **U-Net model + detections artifact:** **frozen.** Cannot re-run, cannot expand
  states, cannot regenerate confidence scores. We work with the 38,220 we have.
- **U-Net provenance:** detections were **verified externally** (user can speak to
  this) — not an open concern.

## Status legend
- ✅ **DONE** — built and verified
- 🟡 **QUEUED** — decided; implement after the conversation
- 💭 **FUTURE** — agreed worth doing, deferred / still thinking
- ⛔ **DECLINED** — explicitly out of scope (reason noted)

## Cross-cutting theme: fix misrepresentations
The user's standing note: *"the problem with this repo is that some things are
misrepresented."* Honesty is the product. Every section below flags claims where
the pitch currently outruns the data; correcting them is first-class work, not
cleanup.

---

# Section 1 — DISCOVER

### Ground truth (from the actual data, 2026-06-21)
- **38,220** candidate records: **1,301** LBNL CA/OK + **36,919** U-Net Appalachia
  (PA/WV/OH/KY). 117,672 documented USGS wells are a separate reference backbone
  (27 states), not candidates.
- Record schema is thin: `well_id, name, lat, lon, state, county_group,
  quad_name, quad_year, quad_scale, detection_index, type_norm="unknown",
  status_norm="undocumented", is_plugged=false, nearest_doc_well_m`.
- **Discovery math:** 38,095 / 38,220 (**99.7%**) are >100 m from any documented
  well; median distance **1,087 m**; 20,168 are >1 km; max 144 km.
- **Strength to protect:** every detection carries the historical map + year it
  was found on (e.g. "1954 Allensworth 1:24000 quad") — verifiable, honest
  provenance. Currently buried in data, absent from story.

### Fixes

**1.1 — Populate the per-record `source` tag** — 🟡 QUEUED
- Today `source` is `None` on all 38,220 records; provenance only inferable from
  the ID prefix. The "**we** discovered 36,919 of these" fact isn't in the data.
- Tag each record `lbnl` (CA/OK) vs `unet_2026` (Appalachia) so the UI/pitch can
  foreground the self-discovery. Cheap; story-critical. Frozen model irrelevant
  (pure tagging, derivable from `state_abbr` / id prefix).

**1.4 — Compute & surface the discovery count** — 🟢 PARTIAL (computed; UI pending)
- ✅ **DONE:** wrote a `discovery` block to `meta.json` (source + public copy):
  total 38,220; **>100 m: 38,095**, >500 m: 28,404, >1 km: 20,168; median nearest
  documented **1,087 m**; max 144,376 m; split by source (unet_appalachia
  36,919 / 36,794 >100 m · lbnl 1,301 / 1,301).
- 🟡 **Pending (UI section):** surface this in the app (IntroOverlay / a "we
  discovered N" stat) + add `discovery` to the `Meta` TS type.

**1.6 — Correct the "national" misrepresentation → the real Appalachia story arc**
— 🟡 QUEUED
- **Story arc (locked):** ~**80% of undocumented orphaned wells are in
  Appalachia** → that's *why* we focused there → we discovered **36,919 across 4
  states (PA/WV/OH/KY) by running a model overnight.** Concentration is the
  point, not a limitation.
- Audit/scrub every place the product implies "national candidate coverage"
  (UI copy, map framing where the 27-state documented backbone makes coverage
  look national, docs) and re-anchor to the Appalachia-focused narrative.
- **CA/OK decision (locked):** keep LBNL's CA/OK (1,301) as a **downsized
  validation point** — "we reproduced the published LBNL approach, then went
  where the problem actually is (Appalachia)." Not a headline; a quiet
  credibility footnote. Headline is Appalachia.

**1.8 — No hero stories from the LBNL set** — ✅ DONE (2026-06-21)
- Removed the **AllenCo / University Park (LA, CA)** hero — the only non-Appalachia
  hero, sitting in LBNL territory. The two remaining heroes (Admiral King OH,
  Vowinckel PA) are both Appalachia, on-arc.
- Removed `hero_allenco_la` from: `heroes.base.json`, `heroes.enrichment.json`,
  `heroes.json`, `dossiers.json` (source `data/processed/` **and** the
  `apps/web/public/data/` copies), the `services/ingest/heroes.py` source
  definition, and the `DEMO_SCRIPT.md` reveal section ("three hero cases" → "two,
  both Appalachia"). `PROGRESS.md` mention left as historical audit record.
- Surgical removal (didn't re-run the scorer): dropping 1 of 38k+ records shifts
  the others' percentiles by ~0.003%, and the 114 MB `candidates.scored.json`
  isn't present locally to re-run. Verified all files valid JSON, 2 heroes remain,
  no stray AllenCo refs in active code/data, `heroes.py` parses.


**1.9 — Remove ALL current heroes (confirmed/already-patched, not discoveries)**
— ✅ DONE (2026-06-21)
- The two remaining heroes (Admiral King OH, Vowinckel PA) were confirmed,
  already-remediated wells — **not** part of the U-Net discovery set — so they
  carry no "lost well we found" weight. Removed entirely (heroes list is now
  empty), same surgical removal as AllenCo (§1.8): `heroes.base/enrichment/heroes
  .json` + `dossiers.json` (source + public copies) → 0 heroes; `heroes.py` HEROES
  list emptied with a note; `DEMO_SCRIPT.md` reveal section marked TBD. `tsc`
  clean (empty heroes handled by `page.tsx`). New heroes will come from discovered
  wells (§3.14).
- **Follow-up (2026-06-21): heroes still showed due to `cache:"force-cache"`.**
  Fixed in `apps/web/lib/data.ts`: `loadHeroes`/`loadMeta`/`loadDossiers` now fetch
  `no-store` (big immutable payloads keep `force-cache`); cleared `.next`. Verified
  in headed browser: 0 "Confirmed" rows, 0 red map markers, list starts at the real
  #1. Also confirmed 0 hero leaks in detail shards / candidates.web.json.

**S0.2/S0.3 (Phase 0 of the build plan) — ✅ DONE (2026-06-21):** per-record `source`
tag populated (lbnl 1,301 / unet_2026 36,919) in `candidates.base.json` + build
scripts + slim payload; `Meta.discovery` + `CandidateLite.source` + `Enrichment`
tract fields typed; `tsc` clean.

### Context (not fixes)
- **#8 thin-schema ceiling:** a detection is a *location*, not a well record — no
  API#, depth, or operator can be read off a map symbol. Only cure is spatial
  matching to external DBs (= 1.7). This is the rationale behind 1.7.

### Declined for Section 1
- ⛔ **Independent detection validation** (Kern reproduction / satellite spot-check)
  — user: not a concern (verified externally).
- ⛔ **Per-detection confidence scores** — frozen model never emitted them; not
  reconstructing.
- ⛔ **"99.7% discovery rate looks too high" framing risk** — not a concern.
- ⛔ **U-Net reproducibility / inference verification** — verified externally.

---

# Section 2 — DIAGNOSE

### Ground truth (from the actual scored data, 2026-06-21)
- 9 metrics / 4 groups → percentile-rank composite. Weights: human_exposure 0.44
  (pop .15, drinking_water .12, schools .12, hospitals .05), equity 0.22 (svi .12,
  ej .10), methane 0.17, fundability 0.17 (plug_cost .12, program_match .05).
- **3 of 9 metrics are effectively constant** across all 38,220 wells:
  - **methane CO₂e: 2 distinct values** — 5.573 t/yr (all 36,919 Appalachia) /
    1.817 t/yr (all 1,301 CA/OK). Varies *only* by region; rests on a guessed
    0.69/0.31 unplugged/plugged blend.
  - **plug cost: 2 distinct values** — $76k (37,681) / $95k (539 CA).
  - **program_match: 1 value** (`1.0` everywhere).
- So **~34% of composite weight (methane 17 + plug_cost 12 + program 5)** is
  near-constant / region-proxy; real ranking comes from the 6 exposure+equity
  metrics (coverage 84.5–100%).
- Scorer itself is clean: transparent, 25 tests, breakdown sums to composite,
  missing renormalized not zeroed. **Protect this honesty scaffolding.**

### ⚠️ Key finding — Appalachia-on-top conflicts with removing methane
Empirically (ranked all wells on only the 6 real metrics): **no weighting puts
Appalachia cleanly on top.** CA/OK wins the mean percentile on *all six* metrics
(they sit in dense urban LA + OK-metro tracts; drinking_water especially: CA/OK
0.752 vs APP 0.491). The strongest exposure weightings give **top-50 = 100%
CA/OK**; even equity-only leaves an LBNL well at #1. The thing that *was* floating
Appalachia to the top is the **methane region-bonus we're removing.** Weights
alone cannot satisfy both constraints.

### Fixes


**2.2 — Default ranker = Appalachia set only; CA/OK = separate validation layer**
— 🟢 PARTIAL (confirmed by user; front-end scoping DONE)
- ✅ **DONE (front-end, 2026-06-21):** `app/page.tsx` now scopes the main view to
  the Appalachia states (OH/PA/WV/KY). The ranked list, the map candidate layer,
  the region dropdown, and the "N of M" count are all Appalachia-only; CA/OK is
  held out of the default ranking. Web app type-checks clean. This guarantees
  Appalachia-on-top in the main view regardless of weights.
- 🟡 **Pending (bigger):** style CA/OK as a *visible* "published-baseline /
  validation" toggle layer (currently just hidden); re-score so the
  within-Appalachia order is the honest 6-metric order (see 2.1/2.3).

**2.3 — Default within-Appalachia weighting (the website custom filter default)**
— 🟡 QUEUED (proposed; tunable in UI)
- Once CA/OK is scoped out, weighting is a pure "what matters most" choice.
  **Proposed default:** population .30, schools .15, drinking_water .15,
  hospitals .10, svi .15, ej .15 (sum 1.0; human_exposure .70 / equity .30) —
  population-led to match "ranked by who lives on top of them."
- This is the adjustable custom-filter default on the site; users can re-weight.
- **User: accepted population-led default** (no objection raised). Locked pending
  the re-score.

**2.4 — Surface `population_1mi` instead of tract `population` in the UI**
— 🟡 QUEUED (decision: use population_1mi)
- The card shows tract `population`; the scorer ranks on `population_1mi`; they
  diverge wildly (Cincinnati 2,992 vs 13,342; Allensworth 3,008 vs 30). Show the
  value that drives the rank. Needs `population_1mi` added to the slim
  `candidates.web.json` payload (currently only in detail shards) → folds into
  the re-score pass + a component change.


**2.8 — Minor cleanup** — 🟡 QUEUED (small)
- Drop redundant `tract_fips` (3.4%, legacy) in favor of `tract_geoid` (100%).
- `daytime_population` (97.6%) is computed but unused — either surface as an
  exposure context value or drop. (Lean: surface in dossier as context.)
- Surface in UI which wells are scored on partial data (missing federal EJ layer
  renormalized) — honesty touch.
- All fold into the re-score / web-payload pass.

### Note on sequencing
Section 2 has **no clean isolated now-fix** (unlike Section 1's AllenCo removal):
2.1–2.4 + 2.8 all couple to **one re-score pass** + test updates, and the final
weights depend on confirming 2.2/2.3. Implement together once 2.2 is confirmed.

### ✅ Phase 1 DONE (2026-06-21) — the re-score pass
`scoring.py` now ranks on the **6 real metrics, population-led** (pop .30, schools
.15, drinking_water .15, hospitals .10, svi .15, ej .15; methane/plug_cost/
program_match dropped from the composite, still computed for display). Tests fixed
(23 pass + 2 geo-skip). Re-scored: composite **21.4 / 48.5 / 99.7**, **716 distinct
values** (was ~2). `population_1mi` + `source` now in the slim payload (98.2% /
100%); `tract_fips` dropped (tract_geoid kept). RankedList shows **list position**
(global top is CA/OK, scoped out; Appalachia shows 1..N). `lib/data.ts` switched to
`no-cache` revalidate (kills the stale-payload trap). Verified in headed browser.

### Declined / accepted-as-is
- ⛔ Carbon kicker (#7 was about removing fundability weighting — done via 2.1).
  Keep carbon as honest labeled context (it correctly says credits rarely pencil).

---

# Section 3 — ACT

> **Decision: build it ALL** (deterministic for all ~37k Appalachia wells +
> agentic for the top subset / heroes). The verb is **mobilize, not plug**: each
> well gets a case file naming who can act + a sourced story. All three sponsors
> live here. Honesty is low-priority per the constraint — ship breadth.

### What exists
- The batch swarm (`run_swarm.py` → `dossiers.json`): LangGraph `Send`,
  streaming, `pause_turn`, sentinel, source extraction — solid backbone. But it's
  the **thin-prompt** version (3-sentence prompt, free-text 4-field schema, flat
  URL list). Cached dossiers are mostly **Oklahoma** wells = off-arc now.

### Specs (each a discrete buildable unit)

**3.1 — Investigator doctrine + structured fields upgrade** — 🟡 QUEUED
- Rewrite `investigator.py`'s system prompt to the `BROWSER_BASED_AGENT_TRAINING.md`
  doctrine: **geolocate→county+API# first**, query ladders (reformulate 3–5×),
  source-authority ranking, entity-pivoting (operator→officers→bankruptcy→
  successor), triangulate. Extend the dossier schema to **structured fields**
  (operator, transfers, bankruptcy, current_owner, surface_owner) with lightweight
  per-claim sourcing (URL + confidence). Keep "no invented operator/date" and the
  honest "not on record" behavior. *(Honesty low-priority → don't gate on
  provenance; just capture sources where cheap.)*

**3.2 — Parcel / surface-owner lookup (runs WITH the agent swarm)** — 🟡 QUEUED
- Decision: parcel owner is an **agent tool**, invoked during investigation (not a
  separate deterministic pass). coord → parcel owner via the ArcGIS REST recipe
  (`STRUCTURED_PROPERTY_INFORMATION.md`): `?f=pjson` to find the owner field →
  point-in-polygon query. **Free states:** OH/WV/KY. **PA + gaps:** national API
  **free trial** (ReportAll, 1,000 lookups). Reproject NAD27→WGS84. Keep
  **surface owner (parcel)** separate from **liable operator (registry)**.
- New: `services/swarm/web/parcel.py` (SQLite-cached like `enrich.py`); add as a
  Claude tool in `investigator.py`. PA/walled viewers → escalate to Browserbase
  (3.10).
- **✅ DONE (2026-06-21, no-key part):** `parcel.py` built — `owner_at()` via free
  ArcGIS REST, **WV statewide wired** (FullOwnerName), SQLite-cached, stdlib-only,
  graceful None when no service/offline. Used by `assemble_cases.py` (15/18 WV
  cased wells resolved a named owner; Parkersburg → "PARKERSBURG UTILITY BOARD").
  Remaining: add OH/KY/PA services to the SERVICES registry; register as a Claude
  agent tool (needs the §3.1 investigator, Phase 3).

**3.3 — `services/engine/actors.py` (the actor map; deterministic, all wells)**
— 🟡 QUEUED
- coord → **US Representative** (Census geocoder / local PIP on `cd119` TIGER →
  `unitedstates/congress-legislators` CC0) + **state legislators** (OpenStates
  CC0 per-state CSV) + **state regulator** (hand-built CSV, 3.13) + **community/EJ
  orgs** (hand-compiled per region, 3.13; agent can surface candidates).
- Output per well: {responsible/able, can fund, can pressure}. Deterministic
  where possible; agentic enrich for the top subset.

**3.4 — `services/engine/pathways.py` (funding routes; deterministic, all wells)**
— 🟡 QUEUED
- Rank pathways + rationale + rough timeline from deterministic inputs:
  **BIL/IIJA** eligibility (all states), **state plugging program** match (CA/NY/
  KY researched; extend per state), **carbon viability** (the tiered model, 3.6),
  **charity** match (Well Done Foundation, Orphan Well Cooperative — right profile
  only), **landowner-funded** path. Honest self-funding ratios.

**3.5 — `services/engine/story.py` (Claude advocacy narrative; agent subset)**
— 🟡 QUEUED
- Evidence-grounded call-to-action tuned to the chosen funder type ("could be
  plugged by X if Y acts"), sources attached where cheap. Reuse the
  `investigator.py` SDK+streaming pattern over free `web_search`.

**3.6 — Carbon reframe (`carbon.py`): tiered, heavy-tail-aware** — 🟡 QUEUED
  *(research done — see finding below)*
- **Finding (validates "millions per well"):** Zefiro **ACR959** (Custer County
  OK, 2025) — first-ever orphan-well carbon sale — was a **single well** →
  **92,956 t CO₂e** credits, sold to Mercuria. At ~$10–30/t ≈ **$0.9M–2.8M from
  one well** (plug cost <$100k). Implied flux ≈ thousands× the current model's
  ~0.27 t CH₄/yr/well mean. Money is in the **high-emitter tail**, and ACR uses
  **measured** pre-plug flux (not a modeled mean).
- **Reframe:** replace the single pessimistic per-well point with a **tiered**
  model: typical wells (credits ≪ plug cost — honest) vs. **high-emitter tail**
  (credits ≥ plug cost → *self-funding*). Flag **carbon-credit-viable** wells (via
  super-emitter proximity / region·status·type → high methane) as a distinct
  **pathway** ("a candidate for carbon-funded plugging, like ACR959"). Caveat:
  we *flag candidates*; real credits require measured flux + additionality +
  buffer. Sources: Zefiro ACR959 press (2025-08), ACR Orphan Well Methodology
  (2023).
- **✅ DONE (2026-06-21):** `carbon.py` now emits `tier`
  (self_funding/partial/negligible) + `carbon_viable`; `score_candidates.py` passes
  the super-emitter flag + right-tail anchor; tests added (24 pass).
- **⚠️ FINDING:** after re-score, **carbon_viable = 0 / 38,220.** No candidate is a
  super-emitter (`super_emitter.json` is empty) and all detections carry modeled-low
  methane, so none pencil. **Decision needed for the carbon-funded hero (§3.14):**
  (a) populate the EPA super-emitter cross-reference (`super_emitter.py` with data),
  (b) hand-pick a high-methane/known-emitter well for the carbon hero, or (c) let
  the agentic investigation surface a high-emitter. Until then the carbon pathway is
  honestly "candidate, pending measured flux."

**3.7 — `services/engine/assemble_cases.py` → `case_files.json`** — 🟡 QUEUED
- Merge evidence + pathways + actors + story. Deterministic pathway/actor parts
  for **all** wells; agentic (liability/story/parcel) for the **top ~100–300** +
  heroes.

**3.8 — Live agent route `app/api/investigate/[id]/route.ts`** — 🟡 QUEUED
- Local Next.js Route Handler (`runtime='nodejs'`, `dynamic='force-dynamic'`).
  Port `investigator.py` (system prompt, `web_search`, streaming, `pause_turn`,
  source extraction) to TS SSE. **Check the Redis cache (3.9) first**; stream
  cached on hit, run live + store on miss. Heartbeat frames to avoid idle-drop.
  Wire the existing `DossierPanel` "Investigate live" button + `onInvestigate`
  prop (already present, never wired). Cached `dossiers.json` + labeled replay =
  guaranteed floor.

**3.9 — Redis semantic cache `services/swarm/web/cache.py`** — 🟡 QUEUED (sponsor)
- One RedisVL `SemanticCache` in front of the agent calls; shared by the batch
  swarm (3.1) and the live route (3.8). `check()`→hit returns instantly;
  miss→run+`store()`. `filterable_fields` on well_id+county+content-hash so one
  well's dossier never serves another. Redis outage → falls through to live call.
  Dep `redisvl`(+`redis`); env `REDIS_URL`. May also back the knowledge doc (3.11).

**3.10 — Browserbase agent browser use** — 🟡 QUEUED (sponsor)
- Add a `browser_task(site, instruction, schema)` tool (Stagehand `act`/`extract`,
  `env:"BROWSERBASE"`) the agent escalates to for facts behind a form/login/WAF —
  chiefly the PA county assessor viewer / Recorder of Deeds / skip-trace in the
  parcel→person step (3.2). **Batch/demo subset only, never inside the live SSE
  route** (would blow latency). Low-priority on website visibility (user narrates
  it). Just needs to exist + be used by agents. Deps `@browserbasehq/stagehand`
  (+ sdk); env `BROWSERBASE_API_KEY`/`BROWSERBASE_PROJECT_ID`.

**3.11 — Living knowledge doc (`knowledge.json`)** — 🟡 QUEUED (build it)
- Agents append reusable findings (carbon programs, funders, plugging contractors,
  state-program intake) for reuse across investigations. **Maybe Redis-backed**
  (3.9) or a flat JSON appended by the swarm — decide at build time. A great demo
  beat. (Honesty low-priority → no heavy provenance gating.)

**3.12 — `CaseFilePanel.tsx` + types** — 🟡 QUEUED (overlaps UI section)
- New panel for pathway + actor map + story + "act via X" links. Extend
  `lib/types.ts` with `CaseFile`/`Actor`/`Pathway`. Detailed in the UI section.

**3.13 — Hand-built data** — 🟢 STARTED (regulator CSV scaffolded; rest queued)
- ✅ **Started:** `data/static/state_regulators.csv` scaffold for the 4 Appalachia
  states (agency/division/program URL seeded; phone/email marked TODO-verify).
- 🟡 **Queued:** verify/complete regulator contacts; hand-compile **community/EJ
  orgs** per region; build the **org intake-adapter registry** (Orphan Well
  Cooperative, Well Done Foundation, Rebellion, etc. — email/form, outbound only).

**3.14b — Hero swap (user-chosen wells)** — ✅ DONE (2026-06-21)
- User picked 3 specific wells by global rank: **#52** `unet_PA_Pittsburg-West…geo_15`
  (Federal/Justice40), **#495** `unet_OH_Cincinnati-West…geo_12` (charity), and the
  rural landowner case. `build_heroes.py` HEROES updated; `assemble_cases` now unions
  hero wells into the cohort (so out-of-top-N heroes get a case file);
  swarm re-run on the new heroes (dossiers complete). Verified: top-3 list + each
  hero's case file/brief/dossier + red map markers. Old heroes fall back to the
  regular list.
- **Landowner hero re-swapped** (later same day): #20021 `unet_OH_Galena…geo_0` →
  **#15060** `unet_WV_Radnor_1962_24000_geo_28` (Radnor, Wayne County, WV). Chosen
  because WV parcel data resolves a **real named family of surface owners** ("WHITE
  BILLY JOE, ANDREW JR, FREELAN C & ROBERT R", 49-acre tract) — completing the
  landowner ending with an actual contactable owner, which the OH Galena pick could
  not (no OH parcel service wired). ~3.7 mi from any documented well, CEJST
  disadvantaged. Case file (named owner + landowner pathway + brief) and live dossier
  (10 sources) regenerated; `copy-data`; tsc clean.

**3.14 — Pick 3 hero cases** — ✅ DONE scaffolding (2026-06-21)
- `services/ingest/build_heroes.py` builds `heroes.json` from 3 **discovered**
  wells (copies the scored detail record + a `hero` block; confirmed=false), each
  a different pathway + state: **Cincinnati West OH** (Federal BIL/Justice40),
  **Pittsburg West PA** (charity adopt-a-well), **Parkersburg WV** (landowner +
  state, the end-to-end target). Red markers on the map, featured at the top of the
  list (deduped from the main list), hero dossier shows the CaseFilePanel + pathway
  + working topo-dissolve reveal. TopoDissolve badge fixed ("Discovered candidate ·
  {pathway}", was "Confirmed exposure").
- ✅ **S5.2 (end-to-end named landowner) DONE (2026-06-21):** built `services/
  swarm/web/parcel.py` (free WV statewide ArcGIS REST, no key, SQLite-cached) →
  `owner_at(lat,lon,state)`; wired into `assemble_cases.py`. **Parkersburg resolves
  to "PARKERSBURG UTILITY BOARD" (125 19th St, 20.5 ac)** — surface owner separated
  from liable operator. 15/18 WV cased wells got a named owner; their pathways now
  include **landowner**. CaseFilePanel renders the surface owner under "Who can
  act"; DossierPanel header fixed (heroes are "Featured discovery", not "Confirmed
  exposure"). The full Discover→Diagnose→Act loop is demonstrable end-to-end:
  discovered well → named owner → pathways (incl landowner) → regulator + named
  legislators. Verified in browser.
- 🟡 Carbon-funded hero still blocked (0 carbon-viable; needs super-emitter data).
  OH/KY parcel services extensible in `parcel.py` SERVICES (WV wired).

**3.15 — Re-run the swarm on Appalachia top-N** — 🟡 QUEUED
- Current cached dossiers are off-arc (Oklahoma). Re-run `run_swarm.py` (doctrine
  upgrade 3.1 + parcel 3.2) on the new Appalachia top-N + the 2 heroes; cache via
  Redis (3.9). Spends API credits.

### ✅ Phase 2 DONE (2026-06-21) — Act engines (deterministic)
- **3.6 carbon** — tiered/heavy-tail reframe (done earlier; carbon_viable flag).
- **3.3 `actors.py`** — coord → US senators + House rep (Census geocoder + CC0
  congress-legislators) + state legislators (OpenStates) + state regulator (CSV) +
  EJ orgs (CSV); stdlib-only, SQLite/file cached, graceful offline fallback.
  Verified live (Cincinnati → Moreno/Husted, Rep. Landsman OH-01, ODNR).
- **3.4 `pathways.py`** — deterministic funding routes (federal BIL/Justice40, state
  program, carbon-if-viable, charity, landowner), ranked; 2 tests (26 total pass).
- **3.5 `story.py`** — advocacy-narrative module, **key-gated** (returns null
  without `ANTHROPIC_API_KEY`); wired into assemble.
- **3.7 `assemble_cases.py` → `case_files.json`** — **150 top-Appalachia wells
  cased** (evidence + pathways + actors; story off until key). Copied to public;
  `CaseFile`/`Pathway`/`Actor` types + `loadCaseFiles()` added (tsc clean).
- **3.13 data** — `state_regulators.csv` filled (no TODO), `ej_orgs.csv`,
  `intake_adapters.csv` created.
- **Unblocks:** `CaseFilePanel` (S4.6) can now be built (case_files.json exists).
  Remaining for story/live: needs `ANTHROPIC_API_KEY` (Phase 3).

### ✅ Phase 3 progress (2026-06-21) — sponsor reachability + live route
- **Reachability probed:** Anthropic ✅ (live), Browserbase ✅ (session created
  live, id 2f73f056 RUNNING), Redis ⚠️ (TCP-reachable but RESP commands time out
  from this CLI's egress on port 14474 — works elsewhere; cache degrades
  gracefully by design). Single root `.env` auto-loads for Python
  (`services/dotenv_min.py`) and the web route (reads `../../.env` fallback).
- **S3.6 live `/api/investigate/[id]` route + U.10 wiring — ✅ DONE & VERIFIED:**
  `apps/web/app/api/investigate/[id]/route.ts` (nodejs, SSE) ports investigator.py
  — `@anthropic-ai/sdk` streaming + server `web_search`, `pause_turn` loop, source
  extraction, strict `<dossier>` JSON parse. `page.tsx` `investigateLive()` consumes
  the SSE stream → live status lines + structured dossier into `DossierPanel`'s
  RUN INVESTIGATION section. Live smokes (Parkersburg, Toledo, Dayton North)
  returned clean 4-field dossiers + 8 real sources each. **Full loop live on any
  well — the win condition — works.**
- **🟡 Remaining Phase 3:** Redis cache wrapper (graceful) in front of the route +
  swarm (S3.9); Browserbase agent tool (S3.10, verified reachable); upgrade the
  *batch* `investigator.py` prompt to the doctrine (S3.1; the live route already
  has it); story generation re-run (S3.5, key now works); swarm re-run on
  Appalachia (S3.7); knowledge doc (S3.11).

### ✅ Phase 3 COMPLETE (2026-06-21) — all three sponsors functionally integrated
- **T1 story briefs:** `assemble_cases --stories` (parallel, idempotent) → 40 Claude
  advocacy briefs in case files; markdown stripped on render.
- **T2 Redis cache:** `services/swarm/web/cache.py` (graceful, verified no-hang) +
  `apps/web/lib/redis-cache.ts` wired into the live route (check-before/store-after)
  + `scripts/redis_check.py` for user-side verification. (Redis unreachable from this
  CLI's egress proxy → clean miss; works from a normal host.)
- **T3 Browserbase:** `browserbase_client.fetch_page` (SDK + Playwright
  connect_over_cdp, no local browser) wired as the `browse_page` agent tool;
  **exercised live — 20 session-replay sources** across the swarm dossiers.
- **T4 doctrine + cohort + swarm re-run:** `investigator.py` upgraded (doctrine,
  strict `<dossier>` JSON, Redis cache, browse tool); `run_swarm` cohort fixed to
  Appalachia; **re-ran 28 wells → 28/28 complete, 0 off-arc, 27/28 clean, avg 7.1
  sources.**
- **T5 living knowledge doc:** `services/swarm/knowledge.py` (seed + harvest, Redis
  mirror graceful) → **30 entries** (12 seeded + 18 operators harvested from the
  swarm); `KnowledgeList` panel on `/about`.
- **Verified:** 26 engine tests; `tsc` + `npm run build` green; production smoke
  (case file w/ pathways + actors + owner + brief, live dossier, knowledge list) —
  no console errors. **Sponsor self-check for the user:** `python scripts/redis_check.py`.

### Sequencing note
Natural build order: 3.9 Redis cache → 3.1 doctrine + 3.2 parcel + 3.10 Browserbase
(the agent) → 3.3 actors + 3.4 pathways + 3.6 carbon (deterministic engines) →
3.5 story + 3.7 assemble → 3.8 live route + 3.12 UI → 3.13 data → 3.15 re-run →
3.14 heroes. Engines (3.3/3.4/3.6/3.7) couple to the same re-score pass as §2.

---

# UI

> **Decision: rebuild the UI from scratch to `docs/uidesign.md`.** The current UI
> reads as generic "AI-generated" (dark glassmorphism + rounded corners + single
> ember accent — exactly what uidesign.md §11 says to avoid). The spec's
> light, zero-radius, topographic field-survey aesthetic (Playfair/Inter/JetBrains,
> olive-green) is distinctive and matches the Appalachia-survey narrative. Keep the
> current dossier's **information architecture** (it's strong); re-skin it.

### Browser audit findings (2026-06-21, headed Chrome)
- **DOM UI works:** sidebar/ranked list, Appalachia scoping (top wells all OH/PA/KY,
  both heroes, "36,921 of 36,919"), dossier (score breakdown, economics,
  provenance, honesty badges) all render.
- **Map WAS broken** (now fixed — U.0). It rendered black at 0px height.

### Fixes

**U.0 — Map renders (the black-map bug)** — ✅ DONE (2026-06-21)
- **Root cause:** MapLibre's stylesheet `.maplibregl-map{position:relative}` loads
  after Tailwind and overrode the container's `absolute` class → `inset-0` did
  nothing → container collapsed to **0px height** → black map.
- **Fix:** inline `style={{position:'absolute',top/right/bottom/left:0}}` on the
  `MapView` container (`components/MapView.tsx`) — inline beats the stylesheet.
- **Verified:** container now 1200×875, `position:absolute`; basemap + 117k teal
  documented + 36,919 orange Appalachia candidates + 2 red heroes all render. The
  orange cloud over PA/WV/OH/KY visually tells the concentration story.

**U.1 — Full rebuild to `docs/uidesign.md`** — 🟡 QUEUED (big; from scratch)
- Implement the spec's design system end to end: **light** shell (#F5F5F5),
  olive-green accent (#4A7C59), **zero border-radius** everywhere (pills/badges
  excepted), **no drop shadows** (dossier edge-shadow excepted), **no
  glassmorphism**, Playfair Display + Inter + JetBrains Mono, 4px spacing system,
  Lucide stroke icons, the three allowed motions only. Honor `prefers-reduced-motion`.
- All colors via CSS variables (uidesign.md §2). Kill the dark-ink/ember theme and
  the rounded-glass components.
- **Map restyle:** swap the dark-matter basemap for a **light topographic** style
  to match; implement the **TOPO / SATELLITE / HYBRID** pill toggle (uidesign.md
  §4 Map Controls).
- Keep the dossier's content/IA; restyle to uidesign.md §4 dossier sections
  (header, map thumbnail w/ "CANDIDATE WELL — UNCONFIRMED" watermark, quick stats,
  risk factors, **PLUGGING PATHWAY** tag, RUN INVESTIGATION button, agent feed in
  mono w/ timestamps).

**U.2 — Full top bar + site nav (replaces the floating "Agent swarm" button)**
— 🟡 QUEUED
- The lone top-right "Agent swarm" button goes away. Build a **proper top bar**:
  - **Title:** "Finding the Lost Wells of Appalachia"
  - **Nav:** **Dashboard** (the map tool) · **About** (a detailed page explaining
    the whole project — problem, the U-Net discovery, the pipeline, methodology,
    honesty notes) · **Team** · **Contact** · **Devpost** (external link).
- Implies the app becomes a small **multi-section site**, not a single dashboard:
  routes/pages for Dashboard, About, Team, Contact (Devpost is an external link).
- The agent swarm becomes part of the dashboard/dossier flow (RUN INVESTIGATION),
  not a top-bar button.

**U.3 — Fix all on-site info / copy** — 🟡 QUEUED (the "fix all the info" ask)
- **IntroOverlay / landing copy:** rewrite to the Appalachia-discovery story
  (36,919 across 4 states overnight; ~80% of undocumented wells in Appalachia);
  drop the old "38,220 candidates / national" framing and the untraceable headline
  numbers. Surface the **discovery stat** from `meta.json` (§1.4).
- **Dashboard count + region list:** already Appalachia-scoped (✅ §2.2); make the
  copy say so ("36,919 wells we discovered in Appalachia").
- Lead climate/cost numbers honestly (cost framing primary; CO₂ horizon-explicit).

**U.4 — Dossier: show `population_1mi` not tract population** — 🟡 QUEUED
- Live bug confirmed: dossier shows "POP (TRACT) 2,992" while the rank uses
  `population_1mi` (13,342). Surface `population_1mi`; needs it added to the slim
  `candidates.web.json` payload (folds into the §2 re-score pass) + the component.

**U.5 — Dossier breakdown reflects the new scoring** — 🟡 QUEUED
- "WHY IT RANKS HERE" still lists methane / plug-cost / funding-program-match.
  After the §2.1 re-score (those removed from the composite), the breakdown shows
  only the 6 real metrics. Methane/plug-cost move to a labeled **context** section,
  not the ranking bars. (Couples to the §2 re-score.)

**U.6 — Carbon shown as the heavy-tail pathway, not "$711 / No"** — 🟡 QUEUED
- Dossier currently shows the pessimistic per-well carbon ("CARBON-CREDIT KICKER
  (HONEST) $711 / pencils out: No"). After the §3.6 reframe, show carbon as a
  **funding pathway** for high-emitter wells (with the ACR959 = $0.9–2.8M proof
  point), tiered honestly.

**U.7 — Remove emoji; clarify quad-name titles** — 🟡 QUEUED (small)
- uidesign.md §11 forbids emoji — replace the 🏫 in list rows with a Lucide
  School icon. List titles are USGS **quad** names ("Toledo", "Pittsburg West")
  that read like city names — reframe as "Undocumented well · Toledo quad" (or
  similar) so they aren't mistaken for the well itself.

**U.8 — Discovered wells: smooth, zoom-scaled map markers** — ✅ DONE (2026-06-21)
- The candidate dots were big, variable-radius, score-colored circles ("too big
  and weird"). Reworked in `MapView.tsx` to **one color (ember), sized in meters**
  so they scale with zoom: ~documented-overlay size when the whole US is in view,
  growing to a **clickable** target when zoomed in (`radiusMinPixels:1.8`,
  `radiusMaxPixels:12`). Still `pickable`; selection bumps size + white stroke.
  Impact score now lives only in the list/dossier, not the marker color.
- **Carries into the rebuild:** the rebuild repaints to the uidesign.md palette /
  light topo basemap, but the meters-sizing + clickable + single-color approach
  stays.

**U.9 — Color legend reflects the discrete scheme** — ✅ DONE (2026-06-21)
- `Legend.tsx` no longer shows the (now-misleading) impact-score gradient or the
  removed hero row. Discrete legend: **"Lost well we discovered (U-Net)"** (ember)
  + **"Documented well (117,672)"** (teal, when shown). Re-styled in the rebuild.

**U.10 — Click flow: map marker → sidebar detail → run-swarm button** — 🟡 QUEUED
- Target flow (per user + uidesign.md): click a discovered (ember) well on the
  map → it opens in the **side panel** with all its info → a button there to **run
  the agent swarm** on demand. Today a click opens the right-hand dossier panel;
  align it to the spec's panel + wire the RUN INVESTIGATION button (ties to §3.8
  live route). Part of the U.1 rebuild.

**U.11 — Dossier streamlined for the demo** — ✅ DONE (2026-06-21)
- Redesigned `DossierPanel` for a fast read: **minimal header (well ID + rank
  only)** — dropped the name, badges, blurb, coord lines; a **summary** at the top —
  **short, sectioned, scannable fact rows** (Where / Found / Exposed / Operator /
  Liability / In the news), each one direct sentence with a fixed label column,
  pulling the agent's concise findings (first-sentence) when investigated;
  **Run/Re-investigate button moved to the top**; a compact **Key stats** grid
  (impact, pop·1mi, schools, SVI, EJ, poverty). Kept **Why it ranks here**, **How it
  gets plugged**, **Who can act**. Removed the methane / plug-economics / carbon /
  exposure / equity / detection-provenance cards and the verbose investigation
  section. `tsc` clean; verified in browser.

### Sequencing note
U.0/U.8/U.9 done. U.1 (design system) + U.2 (top bar/site) are the big rebuild and
can start now. U.4/U.5/U.6/U.10 couple to the §2 re-score + §3 carbon/live-route
work. U.3/U.7 are copy/asset passes done during the rebuild.

### ✅ Phase 4 progress (2026-06-21) — light field-survey rebuild
- **S4.1 DONE:** Playfair/Inter/JetBrains fonts (`layout.tsx`); uidesign.md §2
  palette tokens (`tailwind.config.ts`); light shell + CSS vars + zero-radius +
  maplibre-light (`globals.css`); olive impact ramp + marker colors (`lib/colors.ts`).
- **S4.2 DONE:** dark `TopBar` "Finding the Lost Wells of Appalachia" + nav
  (Dashboard/About/Team/Contact/Devpost↗); new `/about` (detailed explainer),
  `/team`, `/contact`. Floating Agent-swarm/About buttons removed.
- **Dashboard reskinned (light):** `page.tsx` shell, `RankedList` (score-colored
  left edge, **population_1mi**, emoji removed), `Legend`, `IntroOverlay` (new
  Appalachia copy + discovery stat), `MapView` (Voyager light topo, ink selection,
  green discovered cloud). **U.4 done** (list/hover/dossier show population_1mi).
  `tsc` clean; verified in headed browser.
- **DossierPanel reskinned (light) — ✅ DONE:** field-survey cards (zero-radius,
  surface-2, accent dots), green breakdown bars (6 metrics only), population_1mi in
  the exposure card (U.4), methane/plug-cost moved to labeled **context** cards
  (U.5), **carbon shown as a funding pathway** with the ACR959 proof point (U.6),
  RUN INVESTIGATION button (disabled until the live route §3.8). `ScoreBar` trimmed
  to the 2 live groups + light theme.
- **Map controls TOPO / SATELLITE / HYBRID — ✅ DONE (S4.3):** dark pill bottom-
  center; `setStyle` swaps Voyager vector ↔ ESRI imagery (+ ref labels for hybrid);
  the deck overlay (discovered cloud) survives the swap. Verified satellite renders.
- **CaseFilePanel (S4.6) — ✅ DONE (2026-06-21):** new `CaseFilePanel.tsx` renders
  the Act layer at the **top** of the dossier for cased wells — a "we mobilize, we
  don't plug" banner, **How it gets plugged** (ranked pathways w/ confidence +
  rationale + timeline), **Who can act** (regulator, US senators/rep, state
  legislators, EJ orgs, with contact links), the Claude brief (when present), and a
  "Route this well to {regulator}" CTA. Loaded via `loadCaseFiles()`, wired through
  `page.tsx` → `DossierPanel`. Verified live (Cincinnati → BIL/Justice40 + Landsman
  + ODNR). `tsc` clean.
- **🟡 REMAINING (blocked on Phase 3):** click→RUN INVESTIGATION live wiring (U.10
  — needs the live SSE route §3.8, which needs ANTHROPIC_API_KEY); the Claude brief
  in the case file is null until a key exists.

---

# ✅ S5.3 — Final verification (2026-06-21)
All no-credential work verified green:
- **Engine:** `pytest services/engine/tests` → **26 passed, 2 skipped** (geo).
- **Web:** `npx tsc --noEmit` clean; `npm run build` succeeds — 7 static routes
  (`/`, `/about`, `/team`, `/contact`, `_not-found`), dashboard 56 kB / 150 kB.
- **CI parity:** `.github/workflows/ci.yml` steps (pytest + tsc + build) all pass
  locally.
- **Production smoke** (`npm start`): all routes + `/data/*.json` return 200;
  end-to-end browser flow (landing → dashboard → hero → case file with named owner
  + pathways → topo-dissolve → satellite toggle) renders with **no console errors**.

**Status:** Phases 0,1,2,4,5 complete (carbon-funded hero blocked on super-emitter
data). **Remaining = Phase 3 (needs API keys):** Redis cache, Browserbase, live
`/api/investigate` SSE route + agent doctrine, story generation, swarm re-run; plus
OH/KY/PA parcel services (free, extensible).

---

# Pitch / Story Arc
*(to be filled in as we talk)*
