# Lost Wells

**Finding America's undocumented orphaned oil & gas wells — and ranking them by
who's living on top of them.**

There are 310,000–800,000 *undocumented* orphaned wells in the U.S.; only 117,672
are documented. For the undocumented ones, human exposure is literally uncounted —
wells under a school gym, six feet from a family's drinking water. Lost Wells
finds candidate undocumented wells, sends a Claude agent swarm to investigate each,
and ranks them by human impact under the finite **$4.7B** federal plugging budget.

Three pillars:

1. **Detection** — extends LBNL's CATALOG U-Net (Ciulla et al. 2024) that finds
   oil/gas well symbols on historical USGS topo maps. A detection >100 m from any
   documented well = a candidate **Undocumented Orphaned Well (UOW)**. We serve
   LBNL's 1,301 pre-computed candidates over the 117,672-well USGS DOW backbone.
2. **Claude agent swarm** — a LangGraph `Send` map-reduce swarm runs one Claude
   investigator per well, using Anthropic server-side web search for open-ended
   operator / bankruptcy / local-news investigation → a structured dossier.
3. **Ranking + award-grade map** — a transparent composite impact score (human
   exposure, equity, methane proxy, fundability) feeding a designed investigative
   map with the signature 1950s-topo→satellite reveal and a live swarm view.

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
python services/ingest/build_datastore.py   # -> data/processed/wells.documented.json, candidates.base.json
python services/ingest/enrich.py            # CDC SVI + NCES joins (cached)
python services/ingest/heroes.py
python services/ingest/enrich.py --input heroes.base.json --output heroes.enrichment.json
python services/engine/score_candidates.py  # -> candidates.scored.json, heroes.json

# 2) Agent swarm (needs ANTHROPIC_API_KEY) -> data/processed/dossiers.json
pip install -r services/swarm/requirements.txt
python services/swarm/run_swarm.py --total 12

# 3) Web app
cd apps/web && npm install && npm run dev   # http://localhost:3000
```

## Honesty notes (by design)

- **Methane** is a modeled EPA/Kang-factor *estimate* (grams/hour), never a
  measurement — abandoned wells emit far below satellite detection floors.
- **Carbon credits** rarely pay for a plug; we surface the few that can and say so.
- **EJ** uses a SVI-derived demographic-index proxy (federal EJScreen was removed
  Feb 2025); provenance is disclosed throughout.
- **U-Net** detection is the LBNL pre-computed set here; the inference code is
  real and runnable on a GPU host (`services/unet/`), validated on Kern County.

See `BUILD_PLAN.md` for the full feasibility audit and `docs/ARCHITECTURE.md`
for the system design.
