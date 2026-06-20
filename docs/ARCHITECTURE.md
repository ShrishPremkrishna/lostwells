# Architecture

## Principle: ingest once, serve from cache

Federal data endpoints move (EJScreen and HIFLD both relocated in 2025), the
Census Geocoder caps at 500/day, and EPA times out. So a Python **ingestion
pipeline hits each source exactly once** and materializes a committed datastore;
the web app and the agent swarm read from that. Nothing fragile runs at demo time.

```
 SOURCES (hit once)                 PIPELINE                         DATASTORE (committed)
 ─────────────────                  ────────                         ────────────────────
 USGS DOW (ScienceBase) ───┐
 LBNL UOWs (DOE EDX) ──────┼──▶ ingest/download.py ──▶ build_datastore.py ──▶ wells.documented.json (117,672)
                           │                                                  candidates.base.json (1,303)
 CDC/ATSDR SVI 2022 ───────┼──▶ ingest/enrich.py (threaded, SQLite-cached) ─▶ enrichment.json
 NCES public schools ──────┘                                                  (pop, daytime pop, SVI,
                                                                               poverty, minority, EJ proxy,
                                                                               schools ≤1mi, nearest school)

                                engine/score_candidates.py ──▶ candidates.scored.json  (ranked + economics)
                                                               heroes.json

 api.anthropic.com  ──────▶  swarm/run_swarm.py (LangGraph) ─▶ dossiers.json
```

## Data sources (verified live)

| Source | What | Key | Use |
|---|---|---|---|
| USGS DOW (DR1167, DOI 10.5066/P91PJETI) | 117,672 documented orphaned wells, 27 states | none | backbone + dedup |
| LBNL U-Net (DOI 10.18141/2452768) | 1,301 candidate UOWs (CA + OK) | none | detection layer |
| CDC/ATSDR SVI 2022 (onemap.cdc.gov) | tract population, vulnerability, poverty, minority | none | exposure + equity |
| NCES Public Schools (ArcGIS) | schools within 1 mile | none | schoolyard exposure |
| Anthropic web search | operator/bankruptcy/news investigation | API key | swarm dossiers |

## Ranking engine (`services/engine/`, network-independent)

- **Methane proxy** (`methane.py`): EPA/Kang emission factors — unplugged ~31 g/hr,
  plugged ~0.4 g/hr, reported as a low/point/high band; `g/hr × 8760 / 1e6 = t CH4/yr`;
  CO₂e via **GWP-100 = 30** (money/credits) and **GWP-20 = 84** (urgency sidebar).
  Always labeled a modeled estimate.
- **Plug cost** (`plugcost.py`): Raimi et al. 2021 — base $20k plug-only / $76k
  reclamation, +20%/1,000 ft depth, +9% gas, RFF $35k sensitivity. Depth is absent
  in the source, so the depth term defaults to 1.0 (flagged), no false precision.
- **Carbon kicker** (`carbon.py`): ACR orphan-well methodology, GWP-100, buffer pool,
  $10–30/t; an honest self-funding ratio (≪1 for typical wells; cites Zefiro ACR959).
- **Composite score** (`scoring.py`): transparent 0–100 — human exposure 45
  (pop 15 / schools 12 / hospitals 5 / water 13) + equity 20 (SVI 12 / EJ 8) +
  methane 15 + fundability 20 (inverse plug cost 10 / program match 10). Percentile
  normalization across the set; missing metrics renormalized (not zeroed); the
  breakdown sums exactly to the composite. 11 unit tests.

## Agent swarm (`services/swarm/`, LangGraph `Send` map-reduce)

A router returns `[Send("investigate", {well}) for well in cohort]`; each `Send`
spawns an isolated worker. Fan-in via `Annotated[list, operator.add]`; a
`MemorySaver` checkpointer survives superstep failures; `max_concurrency` throttles
parallel Claude calls. Each worker runs a **Claude Sonnet 4.6 investigator** with
**Anthropic server-side web search** (open-ended operator / bankruptcy / local-news
investigation — the defensible "real agent" showcase, not deterministic lookups),
emitting a structured dossier; a per-node sentinel returns a partial dossier on
failure instead of raising. The aggregation/ranking write is single-threaded
(Cognition's "don't corrupt shared state" caveat). Cohort = 3 hero wells + top-9
candidates; results cached to `dossiers.json` and served by the app (live-refresh
optional). Drives Claude via the official `anthropic` SDK with **streaming** —
server-side web search holds the HTTP connection open while searching, and
streaming keeps it alive past the sandbox proxy's idle-drop.

## Web app (`apps/web/`)

Next.js (App Router) + TypeScript + Tailwind + **MapLibre GL (no token)** +
**deck.gl** + Framer Motion. The 117,672 documented wells render as a deck.gl
binary-attribute backbone; the 1,303 candidates as score-colored/sized points with
picking and `flyTo`. A restrained "investigation" design system (near-black ink,
one ember accent, teal documented, danger red for confirmed exposure), Fraunces +
Inter editorial type, tabular numerals. Left = virtualized ranked list; right =
dossier panel (score breakdown, exposure, equity, methane, plug cost, carbon kicker,
detection provenance, the Claude investigation). The signature **topo-dissolve**
swipes ESRI historical USGS topo against present-day satellite over a hero well;
the **swarm panel** visualizes investigator agents landing dossiers.

The committed `data/processed/*.json` is copied into `apps/web/public/data` at
`predev`/`prebuild`, so the app is statically deployable (Vercel) with no backend.

## U-Net (`services/unet/`, documented; not run in-sandbox)

Real, runnable LBNL inference pipeline: rasterio tiles the georeferenced HTMC quad
into 256×256 patches → U-Net predict → threshold → blob centroid → pixel→map-CRS→
EPSG:4326 reproject → 100 m dedup against documented wells. Validate on Kern County
before trusting new ground. Not run here (no GPU); the app serves LBNL's
pre-computed candidates instead.
