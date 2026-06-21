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
services/unet/       LBNL U-Net inference pipeline (documented; run on a GPU host)
data/processed/      Committed datastore the app serves (ingest-once, serve-from-cache)
docs/                ARCHITECTURE.md, DEMO_SCRIPT.md
BUILD_PLAN.md        Session-independent build plan & decisions
```

## Quick start

```bash
# 1) Python datastore (already committed; re-materialize from source if needed)
python -m venv .venv && . .venv/bin/activate
pip install -r services/ingest/requirements.txt -r services/engine/requirements.txt
python services/ingest/download.py          # fetch raw sources
python services/ingest/state_registries.py --states OH,WV,PA,NY,KY   # §1.3 depth/type/status/operator
python services/ingest/build_datastore.py --states OH,WV,PA,NY,KY    # -> wells.documented.json, candidates.base.json, lost_wells.json
python services/ingest/enrich.py            # CDC SVI + NCES joins (cached)
# §2A tract-dedup enrichment (drinking water, hospitals, true 1-mi population, EJ).
# Needs CENSUS_API_KEY for ACS block-group population; --with-downloads fetches
# the light-budget layers (PWS service areas ~570MB, hospitals, CEJST, EJI).
export CENSUS_API_KEY=...                    # free: https://api.census.gov/data/key_signup.html
python services/ingest/enrich_tract.py --input lost_wells.json --states OH,WV,PA,NY,KY --with-downloads
python services/ingest/heroes.py
python services/ingest/enrich.py --input heroes.base.json --output heroes.enrichment.json
python services/engine/score_candidates.py  # -> candidates.scored.json, heroes.json

# 2) Agent swarm (needs ANTHROPIC_API_KEY) -> data/processed/dossiers.json
pip install -r services/swarm/requirements.txt
python services/swarm/run_swarm.py --total 12

# 3) Web app
cd apps/web && npm install && npm run dev   # http://localhost:3000
```


See `BUILD_PLAN.md` for the full feasibility audit and `docs/ARCHITECTURE.md`
for the system design.
