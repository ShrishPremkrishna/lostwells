# Lost Wells — Progress, Limitations & Next Steps

> An honest self-audit of the build session. For a societal-impact tool, candor
> about data limits is a feature, not a footnote — this file is meant to be read
> alongside the demo, so no number here is mistaken for more than it is.

**Status:** full app built end-to-end on `main` (7 commits), working tree clean.
Builds compile; the live agent swarm ran on real data with the provided API key.
**Not yet done:** in-browser visual QA, real georeferenced hero topo, and any
U-Net execution.

**Update (§2A enrichment RAN LIVE on the CA/OK candidates — data regenerated):**
the tract-dedup human-exposure/EJ enrichment (§2A) has now been **executed live**
against all 1,303 candidates and `data/processed/{enrichment,candidates.scored,
heroes}.json` were **regenerated with real data** (`enrich_tract.py --input
candidates.base.json --states CA,OK --with-downloads` → `score_candidates.py`).
Results — the two zero-coverage gaps are closed:
- **drinking_water 1,303/1,303** (was 0; 76 distinct values, EPA CWS service areas)
- **hospitals 1,303/1,303** (was 0; 0–13 within 5 mi, USGS National Map layer 14)
- **population_1mi 1,303/1,303** (true 1-mile areal interpolation; median 241 vs the
  tract proxy's 3,092 — the proxy was over-counting rural tracts, see §2.4)
- **eji_rank 953/1,303** (CDC EJI 2022; SVI proxy fills the remainder)
- top candidate now scores on **all 9 metrics with zero renormalization**;
  **1,299/1,303 candidates changed rank** vs the pre-enrichment order.

Endpoint/robustness fixes were required to make the live run succeed: hospitals
switched from the (dead/partial) HIFLD mirrors to USGS National Map structures
layer 14 + graceful failure; EJI fields are lowercase (`geoid`/`rpl_eji`/
`stateabbr`); PWS auto-falls-back to the anon FeatureServer (GDAL can't read the
570 MB zip); CEJST→CloudFront mirror, TIGER2025, ACS 2023.

**Still NOT run live:** the §1.3 state-registry consolidation (OH/WV/PA/NY/KY) —
`state_registries.py` + `build_datastore.py --states` remain **code-complete +
unit-tested but unexecuted**, so `lost_wells.json` is not yet materialized and the
depth/operator/type attach + universe-expand has not happened. Note these are
**Appalachia**, which does **not** overlap the CA/OK candidates above — so §1.3
does not affect the current candidate scores (it widens/annotates the *documented*
universe). §2.3's methane/plug-cost flatness is therefore **not** resolved by this
run (it depends on §1.3 depth/type + §2B factors).

---

## 1. What was delivered (against the directives)

| Directive / locked decision | Status | Notes |
|---|---|---|
| Verify whitelist reaches container egress (reachability probe) | ✅ | All gov/data hosts returned 2xx/3xx. |
| Ingest real datastore (USGS DOW 117,672 + LBNL candidates) | ✅ | DOW 117,672; LBNL **1,303** rows (lit. says 1,301 — see §3.7). |
| Cached dossier API data | ✅ | CDC SVI + NCES cached; swarm dossiers cached. |
| Ranking engine → UI → swarm → topo-dissolve → polish → U-Net (the §6 order) | ✅ | All stages present. |
| MapLibre, no token | ✅ | Carto dark + ESRI tiles, browser-side. |
| LangGraph `Send` map-reduce swarm | ✅ (with caveat) | Architecture intact; **LLM client swapped** — see §2.1. |
| Full app + U-Net as documented code | ✅ | U-Net documented + runnable, **not executed** (§2.5). |
| Ingest-once-then-serve-from-cache | ✅ | App reads committed `data/processed/*.json`; no backend. |
| Wire swarm to `ANTHROPIC_API_KEY` from env, cached fallback | ✅ | Ran live on 12 wells; 12/12 complete, avg 8 cited sources. |
| §1.3 state-registry consolidation (depth/type/status/operator + expand) | ✅ code | `state_registries.py` (OH/WV/PA/NY/KY, config-driven) + `consolidate()` (attach by API → spatial ≤50 m → expand). **Awaiting live ingest run.** |
| §2A tract-dedup enrichment (drinking water, hospitals, 1-mi pop, EJ) | ✅ **ran live** | `tracts.py` PIP + `enrich_tract.py` (PWS/USGS-hospitals/ACS-BG/CEJST/EJI). **Executed on all 1,303 CA/OK candidates** → drinking_water 1,303/1,303, hospitals 1,303/1,303, population_1mi 1,303/1,303, eji_rank 953/1,303; data regenerated. |

**Genuinely real and working:** the 117,672-well backbone; the 1,303 detected
candidates; the SVI/NCES proximity joins; the transparent composite scorer with
11 passing unit tests; the live Claude+web-search investigations (e.g. the swarm
independently identified **ARCO / St. James Oil** as AllenCo's original operator
and recounted the 2014 Admiral King gym evacuation, with sources).

---

## 2. Where I fell short / deviated

### 2.1 `langchain_anthropic` → raw `anthropic` SDK (deviation from a locked decision)
The locked decision named `langchain_anthropic` Claude subagents. `ChatAnthropic`
**hung** in this sandbox's network (even a no-tool call never returned), while the
raw `anthropic` SDK + curl worked in ~1.6 s. I kept LangGraph, `Send`, the reducer,
the checkpointer, and `max_concurrency` (the actual architecture) but drove Claude
via the official SDK with **streaming** (server-side web search holds the HTTP
connection open while searching; non-streaming got idle-dropped by the egress
proxy and hung). Faithful to the architecture, not the letter of the client choice.

### 2.2 Human-exposure metrics — was the biggest gap, now closed live
The composite weights **drinking-water proximity at 13%** and **hospitals at 5%** —
together 18% of the design, and drinking water is the single largest exposure
sub-weight and the heart of the Vowinckel story. As originally built, **neither was
computed**: the HIFLD hospitals layer probe failed and EPA SDWIS service-area joins
are heavy, so the scorer renormalized those two weights out uniformly — **0 of
1,303 candidates** had a hospitals or drinking-water value.

> **RESOLVED LIVE (§2A):** `enrich_tract.py` was run on the CA/OK candidates and now
> populates **drinking_water 1,303/1,303** (EPA CWS service-area PIP; 76 distinct
> values) and **hospitals 1,303/1,303** (USGS National Map structures layer 14,
> nearest-feature; 0–13 within 5 mi). `score_candidates.py` reads both, so the two
> weights **no longer renormalize out** — the top candidate scores on all 9 metrics.

### 2.3 The candidate ranking is driven by 4 metrics, not 9
Undocumented detections carry no type/depth/status, so three sub-metrics are
effectively constant across all 1,303 candidates:
- **Methane proxy:** ~~**1 distinct value** (8.147 t CO₂e/yr)~~ → **§2B rebuilt the
  engine** to differentiate by region × status × type (EPA GHGI × Kang 2016).
  For the **attributed** universe this breaks the tie: heroes now span
  **0.079 / 8.034 / 12.352 t CO₂e/yr** (oil / OH-unknown / PA-gas) instead of one
  collapsed value. The 1,303 CA/OK candidates share region=`rest_us`,
  type=`unknown`, status=unknown, so they remain near-uniform — but at an
  **honest ~1.82 t blend** (0.69·unplugged + 0.31·plugged) carrying an explicit
  `differentiated=false` flag + UI "undifferentiated estimate" badge, rather than
  a falsely-precise single constant. The only per-candidate tiebreaker is a nearby
  EPA Super-Emitter event (cross-referenced live in §2B; **0 CA/OK matches** —
  the program is sparse and in deregulatory delay — handled gracefully).
- **Plug cost:** **2 values** ($76k, or $95k in CA via a state cost index).
- **Program match:** **1 value** (1.0).

So methane (15%) and fundability (20%) contribute a near-constant offset, and the
actual ordering comes almost entirely from **population, schools, SVI, and EJ**
(the four real enrichment signals). This is honest in the code, but a viewer could
read the per-well methane/plug-cost figures as well-specific when they are template
estimates. They are labeled "modeled estimate," and (post-§2B) the methane
uniformity **is now surfaced** via the `differentiated=false` candor flag/badge.

> **Partially resolved in code (§1.3 + §2B):** documented/hero wells now inherit
> real `depth_ft` (de-flattens plug cost via `plugcost.py`'s depth factor) and
> `type_norm`/`status_norm` from state registries; **§2B** then differentiates
> their methane by region/status/type. LBNL undocumented detections still carry no
> type/depth/status by nature — the methane flatness there is intrinsic until a
> detection is matched to a registry well, but it is no longer **hidden**: the
> blend is modeled-not-measured, badged "undifferentiated," and the only
> per-candidate signal (EPA super-emitter proximity) is cross-referenced.

### 2.4 Source/precision compromises in the metrics
- **Population is tract-level** (CDC SVI `E_TOTPOP`), presented as "population
  nearby." For a large rural tract this can badly mis-estimate a true 1-mile count;
  the spec asked for population *within 1 mile*. Labeled "(tract)" but still a proxy.
- **EJ is a SVI-derived proxy** — `mean(poverty %, minority %)`, mirroring
  EJScreen's demographic index — not the **PEDP EJScreen** mirror the spec
  preferred. Disclosed in the UI, but a deviation.

> **RESOLVED LIVE (§2A):** `enrich_tract.py` was run and now provides true 1-mi
> population (block-group areal interpolation over ACS5; **1,303/1,303**, median 241
> vs the tract proxy's 3,092 — the proxy was over-counting rural tracts) and the real
> EJ signal (`cejst_disadvantaged` Justice40 + `eji_rank` CDC EJI, **953/1,303**,
> SVI proxy fills the rest), tract-joined on FIPS. `score_candidates.py` now uses
> `population_1mi`/`eji_rank` in place of the old proxies for the CA/OK candidates.

### 2.5 Hero wells: approximate coordinates, placeholder citations, generic topo
- **Coordinates were estimated from memory**, not geocoded from authoritative
  addresses. The SVI/schools numbers shown for the hero wells depend on whatever
  tract those approximate points land in — they could describe a neighbor tract.
- **Hero citation URLs are placeholder homepages** (`pa.gov/dep`, `nrdc.org`,
  `latimes.com`), not the actual press releases/articles. (The *swarm dossiers*,
  by contrast, carry real web-search source URLs.)
- The topo-dissolve "before" layer is ESRI `USA_Topo_Maps` (scanned USGS quads),
  but the **vintage shown is whatever ESRI mosaics for that spot** — the "1953
  topo" caption is aspirational, not a guaranteed match to that year's quad. The
  spec wanted pre-built georeferenced HTMC tiles for the hero quads.

### 2.6 U-Net is documented but never executed or validated
No GPU here (as planned), so `services/unet/infer.py` has **never run** — the
patch/threshold/reproject/dedup logic is unverified and could contain bugs. The
app's detection layer is purely LBNL's pre-computed candidates. The "extends the
U-Net to new ground" claim is real-but-unexecuted, and detection covers only
**CA + OK** (LBNL's four counties) — calling the current app "national" would
overclaim (the spec itself flags this).

### 2.7 UI/feature gaps vs the spec
- **No adjustable-weight slider panel** (spec §4.4). The scorer fully supports
  custom weights (`score_set(records, weights)`); the UI just doesn't expose them.
- **No live in-browser investigation.** The deployed app serves cached dossiers;
  the swarm panel's "Replay" is a *simulated* animation, not a live stream. Live
  runs happen via the Python CLI (which works). There is no Next API route that
  runs a real investigation in the browser.

---

## 3. Flags & concerns: data integrity, correctness, responsible use

These are the things most likely to mislead a user or a judge if presented without
caveats. Several are already disclosed in-product; all are listed here for honesty.

1. **Template numbers can read as well-specific.** Per-candidate methane, CO₂e,
   carbon value, and (mostly) plug cost are **identical or near-identical** across
   all candidates (§2.3). Risk: false precision. Mitigation in place: "modeled
   estimate" labels. Mitigation missing: explicitly showing that these are
   class-level defaults for undocumented wells.
2. **Hero enrichment may describe the wrong place** because coordinates were
   estimated (§2.5). Any population/SVI/school figure on a hero card should be
   treated as indicative until the wells are geocoded to their real parcels.
3. **"Population nearby" ≠ population within 1 mile** (§2.4). Could over- or
   under-state exposure, especially rural — directly affects ranking.
4. **EJ is a community-built proxy, not the federal tool** (§2.4). Defensible and
   disclosed, but contestable; don't present it as official EJScreen output.
5. **Swarm dossiers are LLM web-search summaries.** Despite a strict "never invent
   an operator/date/citation" instruction and cited sources, **residual
   hallucination risk remains**, and I did **not** verify each factual claim against
   its cited source. Operator/bankruptcy assertions in a dossier should be treated
   as leads to verify, not adjudicated fact. (The agent does correctly say "no
   operator on record" for genuinely undocumented wells — good — but specific
   historical claims still warrant a human check.)
6. **Topo vintage labels are not guaranteed** (§2.5) — don't claim "this is the
   1953 map" on stage without bundling the actual georeferenced quad.
7. **LBNL count discrepancy:** 1,303 ingested rows vs 1,301 in the paper. Two extra
   could be duplicates or a parsing artifact; not de-duplicated/reconciled.
8. **Scope honesty:** detection is CA+OK only. The "national" framing must be stated
   as "a real but sparse pass we *can* extend nationally," never as current coverage.
9. **No visual verification** (§4) — there may be rendering/perf bugs I never saw.
10. **API spend:** the live swarm consumed real credits (12 Sonnet-4.6 + web-search
    runs, a few dollars). Re-running `--force` spends again; default runs skip cached.
11. **Worked on `main`** per your direction, overriding the session's configured
    feature branch — noted so the provenance is clear.

---

## 4. What I could NOT verify

- **No browser / headless rendering.** Carto + ESRI tiles are blocked *in-sandbox*
  (they render in your browser); there is no browser here. So I confirmed the
  production build compiles and the server serves the page + every data file, but
  I have **not** seen the map draw, the 117k-point deck.gl layer perform, the
  topo-dissolve swipe behave, or the dossier panel animate. Please run
  `cd apps/web && npm run dev` and eyeball it before any demo.
- **U-Net inference** (no GPU) — never executed (§2.6).
- **Per-claim factual accuracy of dossiers** — not audited (§3.5).



