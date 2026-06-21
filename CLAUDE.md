# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

# Project Specific Context

## What this is

Lost Wells finds candidate *undocumented* orphaned oil & gas wells, sends a Claude
agent swarm to investigate each, and ranks them by human impact. It is a monorepo:
a Python ingestion/scoring/swarm pipeline that materializes a committed JSON
datastore, and a Next.js web app that serves that datastore statically (no backend
at runtime).

## Core architecture: ingest once, serve from cache

Federal data endpoints are unreliable (move, rate-limit, time out), so **nothing
fragile runs at demo/serve time**. The Python pipeline hits each source exactly
once and writes `data/processed/*.json` (committed to git). The web app and the
swarm read only from that datastore. Pipeline stages, in order:

1. `services/ingest/download.py` → fetch raw sources into `data/raw/`
2. `services/ingest/build_datastore.py` → `wells.documented.json` (117,672 DOW wells, compact columnar), `candidates.base.json` (1,303 LBNL U-Net candidates), `meta.json`
3. `services/ingest/enrich.py` → `enrichment.json` (CDC SVI + NCES schools; threaded, SQLite-cached in `data/cache/enrich.sqlite`)
4. `services/ingest/heroes.py` then `enrich.py --input heroes.base.json --output heroes.enrichment.json`
5. `services/engine/score_candidates.py` → `candidates.scored.json` (ranked), `heroes.json`
6. `services/swarm/run_swarm.py` → `dossiers.json` (needs `ANTHROPIC_API_KEY`)

The app's `predev`/`prebuild` hook runs `scripts/copy-data.mjs`, copying
`data/processed/*.json` into `apps/web/public/data/`. The app `fetch`es these as
static files (`apps/web/lib/data.ts`), so it deploys to Vercel with no server.

## Commands

```bash
# Web app (apps/web/)
cd apps/web && npm install
npm run dev          # http://localhost:3000 (predev copies the datastore)
npm run build        # prebuild copies the datastore
npm run lint

# Ranking engine tests (pure-compute, no network)
pip install -r services/engine/requirements.txt
cd services/engine && pytest tests/                 # 11 unit tests
pytest tests/test_engine.py::test_breakdown_sums_to_composite   # single test

# Re-materialize the datastore from source (rarely needed; it's committed)
pip install -r services/ingest/requirements.txt -r services/engine/requirements.txt
python services/ingest/download.py
python services/ingest/build_datastore.py
python services/ingest/enrich.py
python services/engine/score_candidates.py

# Agent swarm (spends real API credits; default skips already-cached wells)
pip install -r services/swarm/requirements.txt
python services/swarm/run_swarm.py --total 12       # 3 heroes + 9 top candidates
python services/swarm/run_swarm.py --smoke 1        # one well, live sanity check
python services/swarm/run_swarm.py --total 12 --force   # re-investigate cached wells
```

## Subsystem notes

### Ranking engine (`services/engine/`)
Network-independent pure compute. `scoring.py` is the heart: a transparent 0–100
composite where each sub-metric is normalized by **percentile rank across the
candidate set**, combined with adjustable weights (`DEFAULT_WEIGHTS`). Two
invariants the tests enforce and you must preserve:
- The per-well `breakdown` sums exactly to `composite`.
- **Missing metrics are renormalized over the present metrics, never imputed as zero.**

`score_candidates.py` scores candidates + heroes together so they share one
percentile distribution. `methane.py`/`plugcost.py`/`carbon.py` produce modeled
estimates (always labeled as such in the UI). Note: for undocumented candidates,
methane/plug-cost/program-match are near-constant, so real ranking is driven by
population, schools, SVI, and EJ (see `PROGRESS.md` §2.3).

### Agent swarm (`services/swarm/`)
LangGraph `Send` map-reduce: `graph.py` fans out one `Send` per well to the
`investigate` node; results fan in via an `operator.add` reducer; a `MemorySaver`
checkpointer survives superstep failures; `max_concurrency` throttles parallel
calls. `investigator.py` drives Claude via the **official `anthropic` SDK with
streaming** + server-side web search — *not* `langchain_anthropic`, which hangs
in the sandbox network (the LangGraph orchestration is unchanged; only the LLM
client differs). Each worker returns a sentinel dossier on failure instead of
raising. Model is `claude-sonnet-4-6` (override via `SWARM_MODEL`).

### Web app (`apps/web/`)
Next.js App Router + TypeScript + Tailwind + MapLibre GL (no token) + deck.gl +
Framer Motion. `app/page.tsx` is the single stateful page wiring all panels.
`lib/types.ts` mirrors the datastore JSON shapes — keep it in sync with the
Python writers when you change a record schema. `MapView` is dynamically imported
with `ssr: false`. The 117k documented wells render as a deck.gl binary backbone;
candidates as score-colored points with picking and `flyTo`.

### U-Net (`UNET/`)
The real, runnable LBNL inference pipeline (documented, GPU-only, not executed
here — the app serves LBNL's pre-computed candidates). Use `UNET/unet/infer.py`;
`services/unet/infer.py` is a superseded sketch. See `UNET/README.md` for the
TF 2.15 / Keras 2 / segmentation-models 1.0.1 environment constraints.

## Conventions

- Python pipeline scripts compute paths from `ROOT = Path(__file__).resolve().parents[2]` and use sibling-module imports via `sys.path.insert`. Run them as files, not as `python -m`.
- The datastore JSON is committed; don't regenerate it casually (enrichment/swarm hit live APIs and spend credits).
- This product is societal-impact and honesty-critical: many numbers are modeled estimates or proxies. `PROGRESS.md` is a candid self-audit of every data limitation — read it before presenting or extending any metric, and never strip the "modeled estimate"/proxy disclosures from the UI.
