# Lost Wells — Progress, Limitations & Next Steps

> An honest self-audit of the build session. For a societal-impact tool, candor
> about data limits is a feature, not a footnote — this file is meant to be read
> alongside the demo, so no number here is mistaken for more than it is.

**Status:** full app built end-to-end on `main` (7 commits), working tree clean.
Builds compile; the live agent swarm ran on real data with the provided API key.
**Not yet done:** in-browser visual QA, complete human-exposure metrics, real
georeferenced hero topo, and any U-Net execution.

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

### 2.2 Human-exposure metrics are incomplete (the biggest gap)
The composite weights **drinking-water proximity at 13%** and **hospitals at 5%** —
together 18% of the design, and drinking water is the single largest exposure
sub-weight and the heart of the Vowinckel story. **Neither is computed.** The
HIFLD hospitals layer probe failed and EPA SDWIS service-area joins are heavy, so
the scorer renormalizes those two weights out **uniformly** (honest, and flagged
in the UI), but it means the product does not yet measure drinking-water risk at
all. **0 of 1,303 candidates** have a hospitals or drinking-water value.

### 2.3 The candidate ranking is driven by 4 metrics, not 9
Undocumented detections carry no type/depth/status, so three sub-metrics are
effectively constant across all 1,303 candidates:
- **Methane proxy:** **1 distinct value** (8.147 t CO₂e/yr) for *every* candidate.
- **Plug cost:** **2 values** ($76k, or $95k in CA via a state cost index).
- **Program match:** **1 value** (1.0).

So methane (15%) and fundability (20%) contribute a near-constant offset, and the
actual ordering comes almost entirely from **population, schools, SVI, and EJ**
(the four real enrichment signals). This is honest in the code, but a viewer could
read the per-well methane/plug-cost figures as well-specific when they are template
estimates. They are labeled "modeled estimate," but the uniformity isn't surfaced.

### 2.4 Source/precision compromises in the metrics
- **Population is tract-level** (CDC SVI `E_TOTPOP`), presented as "population
  nearby." For a large rural tract this can badly mis-estimate a true 1-mile count;
  the spec asked for population *within 1 mile*. Labeled "(tract)" but still a proxy.
- **EJ is a SVI-derived proxy** — `mean(poverty %, minority %)`, mirroring
  EJScreen's demographic index — not the **PEDP EJScreen** mirror the spec
  preferred. Disclosed in the UI, but a deviation.

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



