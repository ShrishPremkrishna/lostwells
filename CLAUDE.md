# CLAUDE.md

Agent-context for this repo. Part (a) is a reusable Karpathy-style skeleton;
part (b) fills it in for Lost Wells. If you're an AI agent working here, read
part (b) — and `docs/OVERVIEW.md` — before making changes.

---

## (a) Template (generic agent-instructions skeleton)

The canonical sections for an `AGENTS.md` / `CLAUDE.md`:

1. **Project overview** — one paragraph: what it does and why.
2. **Setup / build / run** — exact commands to install, build, and run.
3. **Codebase structure** — top-level map; where to find what.
4. **Code conventions** — patterns, idioms, and design rules to follow.
5. **Testing** — how to run tests; what "green" means before you commit.
6. **Do / Don't (gotchas)** — sharp edges, footguns, and hard rules.
7. **PR / commit etiquette** — branch, message, and review norms.

---

## (b) Lost Wells

### 1. Overview

Lost Wells discovers and ranks **undocumented orphaned oil & gas wells** by
human + climate impact, to help target the **$4.7B federal plugging fund**.
~38,222 candidate wells (CA, OK, PA, WV, OH, KY) scored against a 117,672-well
documented backbone. Full product overview: **[`docs/OVERVIEW.md`](docs/OVERVIEW.md)**.

### 2. Setup / run

Per-service Python venvs; **four `requirements.txt`** (ingest, engine, swarm,
unet) plus a fifth under `UNET/`. There is no lock file / `pyproject.toml` /
pinned Python yet (known gap). Geospatial stages need **GDAL + geopandas**
installed at the system level.

```bash
# Python (datastore is already committed; re-materialize only if needed)
python -m venv .venv && . .venv/bin/activate
pip install -r services/ingest/requirements.txt -r services/engine/requirements.txt

# Ingest -> enrich -> score
python services/ingest/build_datastore.py          # LBNL CA/OK base (1,303)
python services/ingest/build_unet_candidates.py    # + U-Net Appalachia -> merge -> ~38,222
python services/ingest/enrich_tract.py --input candidates.base.json --states CA,OK --with-downloads
python services/engine/score_candidates.py         # -> candidates.scored.json + slim web payload

# AI dossier swarm (needs ANTHROPIC_API_KEY) -> data/processed/dossiers.json
pip install -r services/swarm/requirements.txt
python services/swarm/run_swarm.py --total 12

# Web app
cd apps/web && npm install && npm run dev           # http://localhost:3000
```

`enrich_tract.py` needs `CENSUS_API_KEY` for ACS block-group population
(free key: https://api.census.gov/data/key_signup.html). `--with-downloads`
fetches the heavy layers (PWS service areas, hospitals, CEJST, EJI).

### 3. Regenerate data

**`data/processed/candidates.scored.json` is gitignored** (~114 MB, exceeds
GitHub's limit) and is **required to regenerate the web payload**. A fresh clone
has the slim payload committed, but to rebuild from source:

```bash
python services/engine/score_candidates.py
```

This reads `candidates.base.json` + `enrichment.json` (+ the `super_emitter`
sidecars) and writes `candidates.scored.json` plus the slim
`candidates.web.json` + `detail/NN.json` shards the web app loads.

### 4. Structure

```
apps/web/             Next.js + TS + Tailwind + MapLibre GL + deck.gl + Framer Motion
services/ingest/      Pull sources once -> committed datastore; tract-join enrichment
services/engine/      Scoring (9 metrics / 4 groups) + 25 unit tests
services/swarm/       LangGraph Send map-reduce; Claude + web-search investigators
services/unet/        U-Net INFERENCE module (authoritative for inference; GPU host)
UNET/                 U-Net RESEARCH tree (EDX dataset notes, training scratch) — NOT the inference path
data/raw/             Bulky raw sources + caches (gitignored)
data/cache/           Download/HTTP caches (gitignored)
data/processed/       Committed datastore the app serves (ingest-once, serve-from-cache)
docs/                 OVERVIEW.md, ARCHITECTURE.md, DEMO_SCRIPT.md, archive/
```

**Two U-Net trees, on purpose:** `services/unet/` is the inference module the
pipeline calls; `UNET/` is the research/training tree. Different lifecycles —
do not merge them. For inference, `services/unet/` is authoritative.

### 5. Conventions

- **Ingest-once, serve-from-cache.** The web app reads committed JSON in
  `data/processed/`; there is no live backend. New data = re-run a pipeline
  stage, don't add a server.
- **Percentile-rank scoring with renormalize-on-missing.** Metrics are scored
  as percentiles across the combined candidate+hero distribution; when a metric
  is absent for a well, its weight is renormalized out rather than imputed.
- **Slim web payload + detail shards (Phase 4).** Never ship the full
  `candidates.scored.json` to the browser — emit `candidates.web.json` + lazy
  `detail/NN.json` shards.

### 6. Testing

```bash
pytest services/engine/tests        # 25 tests; must stay green
cd apps/web && npx tsc --noEmit     # web type-check
cd apps/web && npm run build        # production build must compile
```

The map requires **WebGL** and will not render in headless QA — type-check and
build are the automatable web gates.

### 7. Do / Don't (gotchas)

- **Don't `git add .` blindly.** Large files lurk in the tree; stage specific
  paths.
- **Don't commit `*.geojson` scratch** (root is gitignored via `/*.geojson`) or
  **`candidates.scored.json`** (gitignored; regenerable).
- **`program_match` is a placeholder** (uniq=1, weight 0.05) — not a bug; don't
  "fix" it by treating it as a real signal.
- **`super_emitter` / `heroes.super_emitter` JSONs are empty `{}` placeholders**
  but are live scoring inputs and back a real UI badge — keep them; populate via
  `super_emitter.py` to activate the feature.
- **Map needs WebGL** — it fails in headless browsers; verify visuals in a real
  browser before a demo.

### 8. PR / commit etiquette

- Branch off `main`; small, focused commits.
- Keep hygiene (file moves, ignores) separate from logic where practical.
- Run the testing gates in §6 before opening a PR.

### Skill routing (optional)

This repo is used with gstack skills (e.g. `/browse`, `/ship`, `/review`).
Optional — mention but don't force. Use `/browse` for any web browsing.
