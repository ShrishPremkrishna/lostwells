# Lost Wells — Codebase Audit

> **Date:** 2026-06-21 · **Branch:** `claude/loving-davinci-n7k148` ·
> **Auditor:** Claude (in-repo, run-everything pass)
>
> This is a working audit: I installed every toolchain, ran each stage of the
> pipeline, ran the engine tests, regenerated the scored payload offline, ran a
> **live** 1-well agent investigation, built and served the web app, and probed
> the external APIs the unbuilt parts depend on. Every number below is an
> observation from this environment, not a guess. Where I changed anything, it is
> listed in **§8 Safe fixes applied**.

---

## 0. TL;DR verdict

**What you have is a genuinely strong, honest _Discover → Diagnose_ dashboard that
runs end-to-end. What your pitch sells is _Discover → Diagnose → **Act**_ — and the
entire "Act" half (actionable plugging pathways, the property/owner scraper, the
living knowledge doc, the live agent) is _not built yet_.** The repo today proves
"we found ~38k undocumented wells and ranked them by who lives on top of them." It
does **not** yet prove "…and here's the named, sourced path to plug almost all of
them." That second clause is your whole differentiator and your headline impact
number depends on it.

Everything that exists **works**: 25/25 engine tests pass, the scorer reproduces
its published numbers, enrichment coverage is high (97–100% on the core metrics),
the web app type-checks/builds/serves, and the live Claude+web-search swarm
**actually runs in this environment** and returns well-sourced dossiers. The base
is solid. The gap is scope, not breakage.

**Three things to act on first** (detail in §3, §4, §7):
1. **Build the Act layer** — it's the project, and it's missing.
2. **Substantiate or restate the "30 million tonnes CO₂" claim** — the repo's own
   methane model implies ~208k t/yr; 30 Mt is a ~50–144 year cumulative figure
   that nothing in the code currently computes or labels (§4.1). A judge will do
   this division.
3. **Refresh the demo narrative + headline numbers** — `DEMO_SCRIPT.md` still says
   "1,303 candidates / Britton OK"; the data is now 38,222 and the top wells are in
   OH/PA (§4.4).

---

## 1. What I ran (evidence log)

| Stage | Command | Result |
|---|---|---|
| Python deps | `pip install -r {engine,swarm,ingest}/requirements.txt` | ✅ all install clean (geopandas 1.1.3, shapely 2.1.2, anthropic 0.111, langgraph 1.2.6, pandas 3.0.3) |
| Engine tests | `pytest services/engine/tests` | ✅ **25 passed** (2 need the geo stack; they *skip*, not fail, when it's absent) |
| Score (offline) | `python services/engine/score_candidates.py` | ✅ 38,222 scored in ~15 s; composite min/med/max **21.7 / 51.9 / 79.6** (matches docs) |
| Payload reproducibility | regen vs committed `candidates.web.json` | ✅ 0 rows added/dropped; **15 / 38,222** wells shift ±0.1 (pandas/numpy version churn); rank churn only within score ties |
| Live agent swarm | `python services/swarm/run_swarm.py --smoke 1 --force` | ✅ **works live through the proxy** — Sonnet 4.6 + server-side web search, complete dossier, **8 real cited sources** |
| Web type-check | `npx tsc --noEmit` (apps/web) | ✅ clean |
| Web build | `npm run build` | ✅ static, 143 kB first-load JS |
| Web serve | `npm start` + curl | ✅ homepage 200; `/data/*.json` all 200 at expected sizes |
| Web lint | `npm run lint` | ⚠️ **not configured** — drops into interactive ESLint setup; can't run in CI |
| Parcel-scraper feasibility | ArcGIS REST point-queries (WV DEP, KY GIS) | ✅ mechanism reachable & returns JSON from this env; per-state service URLs still need discovery |
| Network egress | curl probes | ⚠️ **selective**: CDC/ArcGIS/Census reachable; `sciencebase.gov` blocked (000) |

Environment: fresh container, Python 3.11.15, Node 22, `ANTHROPIC_API_KEY` set
(via an `ANTHROPIC_BASE_URL` proxy), **no** `CENSUS_API_KEY`, `data/raw/` empty.

---

## 2. Current state by section

### §1 Discover — **built & verified.** Grade: strong.
- **38,222 candidates** (100% have lat/lon/state/county/quad) + **117,672**
  documented columnar backbone (27 states). Heroes (3) fold in at score time.
- Provenance split confirmed via id prefix: **1,303** LBNL CA/OK + **36,919**
  U-Net Appalachia. State spread: PA 14,647 · KY 10,802 · WV 7,723 · OH 3,747 ·
  OK 762 · CA 541.
- **Flags:** (a) the `source` field is `None` on **all 38,222** records — the
  `lbnl`/`unet_2026` provenance tag the build schema supports is never populated,
  so source is only inferable from the id prefix (§4.2). (b) **2 duplicate
  `well_id`s** (`CA_Fairmont Butte_…_geo_1/2`); removing them yields exactly
  **1,301** unique CA/OK, which finally reconciles the long-noted "1,303 vs 1,301
  paper" discrepancy (PROGRESS §3.7) — these are real dupes, not a parsing mystery.

### §2 Diagnose — **built & verified.** Grade: strong, with known intrinsic flatness.
- Tract-join enrichment coverage across the full 38,222: population_1mi **98.2%**,
  schools **100%**, hospitals **100%**, drinking_water **100%**, SVI **97.5%**,
  EJ **97.6%**, EJI rank **84.5%**, CEJST **84.5%**. This is materially better than
  the "82% / CA-OK-only" picture some older docs imply — the §2A enrichment clearly
  scaled to the whole merged set.
- Scorer is clean: percentile-rank composite, breakdown sums to composite, missing
  metrics renormalized (not zeroed) — all enforced by tests, all reproduced here.
- **Intrinsic flatness (already disclosed, confirmed quantitatively):** every
  candidate is `type_norm=unknown`, `status_norm=undocumented`, `depth_ft` 0%
  coverage. Result: methane CO₂e has only **2 distinct values** across 38,222
  wells, and plug-cost depth premium is never applied. Ranking is genuinely driven
  by population / schools / SVI / EJ (the 4 real signals). The UI badges this
  honestly ("Undifferentiated estimate").

### §3 Act — **NOT built.** Grade: absent (this is the headline gap; see §3 below).

### §4 Serve (web app) — **built & verified.** Grade: strong UI, with documented gaps.
- Type-checks, builds, serves; clean single-stateful-page architecture; deck.gl
  binary backbone + score-colored candidates; dossier panel with **intact honesty
  disclosures** (modeled-estimate badges, EJ-proxy disclaimer, depth-unknown note,
  ">100 m ⇒ candidate" provenance, renormalized-metrics line). The UX is genuinely
  award-caliber in structure.
- **Gaps (pre-existing, confirmed):** no adjustable-weight slider (the scorer
  supports custom weights; the UI doesn't expose them); the "Replay swarm" is a
  **simulated `setTimeout` animation**, not a live run; `DossierPanel` has an
  "Investigate live" button + `onInvestigate` prop that **`page.tsx` never wires**
  (no live route exists to wire it to).

---

## 3. The central gap — the **Act** layer is missing

Your own framing ("section three") and `docs/archive/HANDOFF.md` (§Section 3 + §2D,
§2W, §2R, §7) spec a complete action layer. **None of it exists in the tree:**

| Intended artifact (HANDOFF) | Purpose in your vision | Status |
|---|---|---|
| `services/engine/pathways.py` | rank funding routes (BIL/IIJA, state programs, carbon credits, charity, landowner) | ❌ missing |
| `services/engine/actors.py` | lat/lon → US rep / state legislators / regulator / EJ orgs (the "who can act") | ❌ missing |
| `services/engine/story.py` | Claude-synthesized, **sourced** advocacy narrative per well | ❌ missing |
| `services/engine/assemble_cases.py` → `case_files.json` | merge evidence+pathway+actors+story | ❌ missing |
| **Property/parcel scraper** (`STRUCTURED_PROPERTY_INFORMATION.md`) | coord → surface owner via ArcGIS REST | ❌ missing |
| **Living knowledge doc** (`knowledge.json`) | agents append carbon-credit / funding / contractor findings for reuse | ❌ missing |
| `app/api/investigate/[id]/route.ts` | **live** in-browser agent (the "real, live, on any well" demo) | ❌ missing (no `app/api` at all) |
| Redis semantic cache / Browserbase escalation | spend control + form/WAF-walled lookups | ❌ missing |
| Agent doctrine from `BROWSER_BASED_AGENT_TRAINING.md` | geolocate-first, query ladders, source-authority ranking, per-claim provenance | ❌ not implemented — see below |

**The one Section-3 piece that does exist** is the batch dossier swarm
(`run_swarm.py` → `dossiers.json`). It works and is well-engineered (LangGraph
`Send` map-reduce, streaming, `pause_turn` loop, per-well sentinel, source
extraction). **But it is the "thin-prompt" version**, not the doctrine you wrote:
- System prompt is ~3 sentences; it does **not** do geolocate-to-county/API-number-
  first, query ladders, source-authority tiers, entity-pivoting, or triangulation.
- Dossier schema is `narrative / operator_history / bankruptcy_findings /
  news_findings` — **not** the structured, per-claim provenance schema
  (`source_url, publisher, source_tier, confidence, corroboration`) that
  `BROWSER_BASED_AGENT_TRAINING.md §4` requires and that "no provenance, no ship"
  depends on. (Sources are collected as a flat URL list, which is a start.)
- No ownership/liability **structured fields**, no surface-owner-vs-liable-operator
  separation, no parcel lookup.

**Good news from the probes:** the two hardest feasibility questions for Act both
came back green in this environment — (1) the **live agent path works** (the smoke
test proves Claude + server-side web search streams through the proxy), and (2) the
**ArcGIS REST parcel mechanism is reachable** (point-queries return JSON). So Act is
a build-effort problem, not a "can it even work here" problem.

---

## 4. Honesty & accuracy flags (ranked by how likely a judge bites)

This product is explicitly honesty-critical, and the hackathon will be judged partly
on impact claims. These are the spots where the pitch currently outruns the code.

### 4.1 ⚠️ The "30 million tonnes CO₂" headline is not traceable to the model
The repo's own methane estimates, summed over all 38,222 candidates:
- **~208,117 t CO₂e/yr** at GWP-100 (mean 5.44 t/well/yr)
- **~582,677 t CO₂e/yr** at GWP-20 (mean 15.24 t/well/yr)

To reach **30,000,000 t** you need **~144 years** of avoided emissions at GWP-100, or
**~51 years** at GWP-20. The repo computes **no cumulative/lifetime avoided-emissions
number** and labels nothing as a multi-decade figure. As an *annual* claim, 30 Mt is
~144× too high. **Fix:** either (a) state it explicitly as "X tonnes/yr × an N-year
well lifetime = 30 Mt cumulative, GWP-20" with the math shown, or (b) lead with the
honest annual number, or (c) lead with the **cost** framing instead — which is far
stronger and fully defensible:

> **It would cost ~$2.92B to plug every one of the 38,222 wells we found — inside the
> finite $4.7B federal fund.** (Mean $76,269/well, from the Raimi 2021 model already
> in the repo.)

### 4.2 ⚠️ `meta.json` credits all 38,222 wells to the LBNL paper's DOI
`meta.json.citations.lbnl` carries `n: 38222` under the Ciulla et al. 2024 paper
(DOI 10.18141/2452768), but that paper only covers the **1,301** CA/OK detections.
The **36,919** Appalachia wells came from *your own* fine-tuned U-Net inference run —
which is the most impressive part of the project and is currently **mis-attributed to
someone else's paper**. This both *understates your work* and is technically
incorrect. **Fix:** split into two citations (LBNL CA/OK n=1,301 + "Lost Wells U-Net
Appalachia inference, 2026" n=36,919) and populate the per-record `source` tag so the
UI can say "discovered by *us*." (This is a provenance/attribution decision, so I left
it for you rather than auto-editing — see §8.)

### 4.3 ⚠️ "We found ~39,000 / ~38,222" includes 2 duplicate rows
True unique count is **38,220**. Trivial, but the headline number should match a
de-duplicated dataset. **Fix:** drop the 2 `CA_Fairmont Butte` dupes in
`build_unet_candidates.py`/`build_datastore.py` (also makes CA/OK = 1,301, matching
the paper). Left for you because it shifts the number you cite publicly.

### 4.4 ⚠️ `DEMO_SCRIPT.md` is stale vs the current data and your pitch
It still says "**1,303** candidate undocumented wells," flies to "**Britton,
Oklahoma**" as the top well, and frames detection as "extends a published U-Net." The
current dataset is 38,222 and the rescored top-3 are **OH (Cincinnati-West, Toledo)
and PA (Pittsburgh)** — i.e. the Appalachia story you now lead with. The demo script
undersells exactly the thing you're most proud of.

### 4.5 ℹ️ "Population nearby" label vs scored metric
The exposure card shows `Pop. (tract)` from `enrichment.population` (tract-level),
while the **scorer** ranks on `population_1mi` (the better areal-interpolated 1-mi
value). Both are honest individually, but the number a viewer *sees* isn't the number
that drives the rank. Consider surfacing `population_1mi` in the card too.

### 4.6 ℹ️ Dossiers are LLM web-search summaries (residual hallucination risk)
Already disclosed in PROGRESS §3.5; restating because Act will lean harder on agent
output. The doctrine in `BROWSER_BASED_AGENT_TRAINING.md` (triangulate, confidence-
tag, "leads to verify not facts") is the right mitigation — but it isn't implemented
in the current investigator yet (§3).

---

## 5. Engineering trouble areas

- **No CI** (now partially fixed, §8). 25 good tests existed but nothing ran them.
- **No dependency pinning / no lockfile / 4× `requirements.txt` / no `pyproject`.**
  Concretely bit this audit: a newer pandas/numpy shifted 15/38,222 composite scores
  by ±0.1 (§1). Harmless now, but it means "regenerate the datastore" is not
  byte-reproducible. **Pin `pandas`/`numpy`** (and ideally a top-level
  `requirements.txt` or `pyproject.toml`).
- **`npm run lint` is unrunnable** (no ESLint config; interactive prompt). I did
  *not* auto-add ESLint deps (it changes `package.json`/lockfile and can surface new
  errors) — flagging instead. Add `apps/web/.eslintrc.json` (`extends:
  next/core-web-vitals`) + the `eslint`/`eslint-config-next` devDeps when you want it.
- **`candidates.web.json` is a 15 MB eager download** (the slim payload the app loads
  on first paint). Fine over gzip/CDN, but it's the biggest single client cost; if
  first-paint latency matters for the demo, consider gzipping/streaming or trimming.
- **Network fragility is real but mitigated by design** — `sciencebase.gov` is
  blocked in this env, several federal EJ endpoints are documented-dead (mirrors in
  HANDOFF). The "ingest once, serve from cache" principle is the right call; just
  know a *fresh* full regeneration can't be done here for the sciencebase-sourced
  layers.
- **Two U-Net trees** (`UNET/` real vs `services/unet/` superseded sketch) — already
  documented; not a bug, but a newcomer trap.

---

## 6. What's genuinely good (don't regress these)

- The **honesty scaffolding** is the project's best feature and it's everywhere:
  renormalize-don't-impute, "modeled estimate" badges, the `differentiated=false`
  flag, coord precision/source provenance, the candid PROGRESS.md. This is exactly
  what makes a societal-impact project credible. Protect it as you build Act.
- The **scorer** is small, transparent, tested, and reproducible.
- The **swarm architecture** (LangGraph `Send`, streaming, sentinels, caching) is
  the right backbone — Act mostly needs a richer prompt/schema on top of it, not a
  rewrite.
- The **web app** is well-structured and the UX is differentiated (topo-dissolve,
  ranked list + dossier, restrained design system). Strong base for the UX award.

---

## 7. Proactive observations (things worth rethinking)

A few non-obvious things about how this is currently framed:

1. **Your strongest, truest headline is the cost-coverage one, not the CO₂ one.**
   "$2.9B to plug all 38k wells we found, inside a $4.7B fund that nobody knows where
   to point" is concrete, defensible from the repo's own numbers, and *is the
   product thesis* (prioritization under a finite budget). Lead with it; treat CO₂ as
   a labeled, horizon-explicit secondary number.

2. **The Appalachia U-Net run is your moat and you're under-crediting it.** Right now
   the 36,919 self-discovered wells are attributed to someone else's paper (§4.2) and
   the demo script still leads with LBNL's 1,303. The single highest-leverage
   *narrative* fix is to make the app say, loudly and correctly, "**we** found these
   36,919 — here's the model, the quads, the validation." That's the eyebrow-raiser.

3. **"Actionable pathways to plug almost all of them" is a promise the code doesn't
   keep yet — and judges will click to check.** A demo that *says* "clear path to
   plugging" but only shows a methane/score dashboard is the most likely place to
   lose credibility. Prioritize building *one* fully-cased well end-to-end (named
   surface owner via the ArcGIS parcel lookup → matched state/BIL program → drafted
   advocacy letter → the regulator/legislator who receives it) over broad-but-shallow
   coverage. The HANDOFF's own win condition says exactly this: "≥1 well cased
   end-to-end through a named landowner."

4. **Positioning discipline matters for the impact story.** HANDOFF Prime Directive
   #1 ("we mobilize, not plug; router/advocacy layer, never a marketplace or licensed
   operator") is the safe and honest framing. Keep the verb "mobilize." Avoid any UI
   copy that implies you file paperwork, take money, or hold liability.

5. **The "living knowledge document" is a great idea and a great _demo beat_, but
   needs a guard.** A doc that agents append to (carbon programs, funders, plugging
   contractors) is compelling — just scope each entry with provenance + a "verify
   before relying" tag, or it becomes a laundered-guess store. Same honesty bar as
   dossiers.

6. **Decide the Act scope as "deep on a handful" not "shallow on 38k."** The
   deterministic parts (BIL eligibility, congressional district → rep, state program
   match) *can* run for all wells cheaply; the agentic/parcel/story parts should run
   for the top ~100–300 (and a hand-picked hero or two for the live demo). Don't let
   the swarm or parcel API touch 38k.

---

## 8. Safe fixes applied this pass

Per the agreed scope ("document + safe fixes; flag anything larger"):

- **Added `.github/workflows/ci.yml`** — runs the engine tests (with the geo stack so
  all 25 execute) and the web `tsc --noEmit` + production build on every push/PR.
  Everything it runs is already green in this audit. It deliberately does **not** run
  ingest/swarm (live APIs / credits) or lint (not configured).

**Deliberately _not_ auto-changed (left as recommendations, because they alter
committed data, public-facing numbers, or attribution — your call):**
- The `meta.json` LBNL-vs-U-Net citation split + per-record `source` tag (§4.2).
- De-duping the 2 `CA_Fairmont Butte` rows / the 38,222→38,220 number (§4.3).
- Refreshing `DEMO_SCRIPT.md` to the current data + pitch (§4.4).
- Pinning `pandas`/`numpy` for byte-reproducible scoring (§5).
- Adding ESLint config + deps (§5).

*(Verification side-effect: I regenerated `candidates.scored.json` — gitignored,
regenerable — to run the scoring/swarm checks. All tracked data files were restored
to their committed state; `git status` is clean apart from this audit + the CI file.)*

---

## 9. Suggested priority order

1. **Pick the Act scope and build the end-to-end "one cased well"** (parcel owner →
   pathway → actors → sourced story → case file). This is the demo and the project.
2. **Fix the impact-claim honesty** (§4.1 CO₂ math, §4.2 attribution, §4.3 count) —
   cheap, high-credibility, do before any judging.
3. **Upgrade the investigator to the `BROWSER_BASED_AGENT_TRAINING` doctrine** +
   structured per-claim provenance schema (you already wrote the spec).
4. **Wire the live `/api/investigate` route** so "Investigate live on any well" is
   real (the DossierPanel button is already waiting for it).
5. **Refresh `DEMO_SCRIPT.md` + headline numbers; surface the U-Net-Appalachia
   discovery prominently in the UI.**
6. **Polish for the UX award** — adjustable-weight slider (scorer already supports
   it), and make the swarm panel reflect real runs.
7. **Hygiene** — pin deps, add ESLint, keep CI green.

---

*Audit complete. The foundation is real and runs; the work ahead is building the
"Act" half that the vision promises and making the impact numbers match the model.*
