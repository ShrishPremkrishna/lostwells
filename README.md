# Lost Wells

**Finding America's undocumented orphaned oil & gas wells — and ranking them by
who's living on top of them.**

There are 310,000–800,000 *undocumented* orphaned wells in the U.S.; only 117,672
are documented. For the undocumented ones, human exposure is literally uncounted —
wells under a school gym, six feet from a family's drinking water. Lost Wells
finds candidate undocumented wells, sends a Claude agent swarm to investigate each,
and ranks them by human impact under the finite **$4.7B** federal plugging budget.

## Repo layout

```
apps/web/            Next.js + TS + Tailwind + MapLibre GL + deck.gl + Framer Motion
services/ingest/     Pull USGS DOW + LBNL + CDC SVI + NCES once -> committed datastore
services/engine/     Methane proxy, Raimi plug cost, carbon kicker, composite score (+tests)
services/swarm/      LangGraph Send map-reduce; Claude (Sonnet 4.6) + web search investigators
UNET/                LBNL U-Net inference pipeline (real, runnable; GPU host). services/unet/ is a superseded sketch
data/processed/      Committed datastore the app serves (ingest-once, serve-from-cache)
docs/                OVERVIEW.md, ARCHITECTURE.md, DEMO_SCRIPT.md, archive/
CLAUDE.md            Agent-context: setup, conventions, gotchas
```

New here? Start with **[`docs/OVERVIEW.md`](docs/OVERVIEW.md)** (5-minute
product overview) and **[`CLAUDE.md`](CLAUDE.md)** (setup + conventions).

## Quick start

```bash
# 1) Python datastore (already committed; re-materialize from source if needed)
python -m venv .venv && . .venv/bin/activate
pip install -r services/ingest/requirements.txt -r services/engine/requirements.txt
python services/ingest/download.py          # fetch raw sources
python services/ingest/state_registries.py --states OH,WV,PA,NY,KY   # §1.3 depth/type/status/operator
python services/ingest/build_datastore.py --states OH,WV,PA,NY,KY    # -> wells.documented.json, candidates.base.json (LBNL CA/OK 1,303), lost_wells.json
python services/ingest/build_unet_candidates.py                     # + U-Net Appalachia (36,919 PA/KY/WV/OH) -> merge into candidates.base.json (~38,222)
python services/ingest/enrich.py            # CDC SVI + NCES joins (cached)
# §2A tract-dedup enrichment (drinking water, hospitals, true 1-mi population, EJ).
# Needs CENSUS_API_KEY for ACS block-group population; --with-downloads fetches
# the light-budget layers (PWS service areas ~570MB, hospitals, CEJST, EJI).
export CENSUS_API_KEY=...                    # free: https://api.census.gov/data/key_signup.html
python services/ingest/enrich_tract.py --input lost_wells.json --states OH,WV,PA,NY,KY --with-downloads
python services/ingest/heroes.py
python services/ingest/enrich.py --input heroes.base.json --output heroes.enrichment.json
python services/engine/score_candidates.py  # -> candidates.scored.json, heroes.json + slim web payload

# NOTE: candidates.scored.json (~114 MB) is gitignored and must be regenerated
# by the score step above. The web app reads the committed slim payload
# (candidates.web.json + detail/NN.json shards) that score_candidates.py emits.

# 2) Agent swarm (needs ANTHROPIC_API_KEY) -> data/processed/dossiers.json
pip install -r services/swarm/requirements.txt
python services/swarm/run_swarm.py --total 12

# 3) Web app
cd apps/web && npm install && npm run dev   # http://localhost:3000
```


See `docs/OVERVIEW.md` for the product overview, `docs/ARCHITECTURE.md` for the
system design, and `PROGRESS.md` for an honest build-session self-audit.
Historical build specs live under `docs/archive/`.
