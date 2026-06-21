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


## Redis & Browserbase: caching + browser automation

Two infra tools back the agent investigation layer. Both are **fail-open** — on
any outage they degrade to a live/uncached path rather than breaking the demo.

**Already wired (baseline):**
- **Redis** — exact-key dossier cache (`dossier:{well_id}`, 30-day TTL) shared by
  the batch swarm (`services/swarm/web/cache.py`) and the live SSE route
  (`apps/web/lib/redis-cache.ts`). Also mirrors the knowledge base (`knowledge:all`).
- **Browserbase** — a `browse_page` escalation tool the batch investigator calls
  when `web_search` hits a JS/WAF wall (`services/swarm/web/browserbase_client.py`),
  SQLite-cached per URL, returning a `replay_url` for provenance.

Today Redis means "don't re-investigate the same well" and Browserbase means "let
the agent open one stubborn page." The roadmap below extends both. Each entry
notes **where** it lands and **how** it's built.

### Redis — planned enhancements

| Enhancement | How it's implemented |
|---|---|
| **Operator/entity cache** (biggest cost lever) | New namespace `operator:{normalized_name}` storing operator history / parent company / bankruptcy status, reused across every well tied to that operator. `investigator.py` checks it before the per-well agent loop; kept strictly separate from `dossier:{well_id}` so a well-specific claim is never cross-served. |
| **Semantic cache** | Wrap the Claude call with a RedisVL `SemanticCache`; scope each entry with `filterable_fields` on `well_id`/`county` + a conservative `distance_threshold` so look-alike wells reuse *context* without bleeding facts. Lands in `services/swarm/web/cache.py` (+ live-route twin). |
| **Distributed rate limiter** | Redis token-bucket (`INCR` + key expiry) in front of flaky ArcGIS hosts (WV TAGIS, PA PASDA, OH ArcGIS) and the Anthropic API, shared across parallel ingest workers and serverless invocations. A small `services/ingest/ratelimit.py` helper wraps `requests`. |
| **Single-flight lock (live route)** | `SETNX` lock + Pub/Sub in `app/api/investigate/[id]/route.ts`: concurrent clicks on the same well run once; the second subscriber streams the same result. |
| **Promote ingest caches SQLite → Redis** | Move the hot tract/point/registry lookups (`enrich.sqlite`, `enrich_tract.sqlite`, `registries.sqlite`) behind a Redis-backed cache interface so CI, serverless, and dev share one TTL-managed store. |
| **Knowledge base as a vector index** | Index `knowledge.json` entries with RedisVL so agents semantically retrieve applicable funding/programs/contractors per well instead of loading the whole file — the "living document referenced by future swarms." Lands in `services/swarm/knowledge.py`. |
| **Tiered TTLs** | Per-key freshness: news ~7d, operator facts ~90d, parcel ownership ~180d, demographic enrichment ~1yr, dossiers 30d. |
| **SSE resumability + fan-out** | Store live progress in a Redis Stream so dropped connections resume and multiple viewers of one well share a log (Vercel functions are stateless). |

### Browserbase — planned enhancements

| Enhancement | How it's implemented |
|---|---|
| **`browse_page` in the live route** | Wire the existing `browse_page` tool (today batch-only) into `app/api/investigate/[id]/route.ts` so live investigations also cross form/login/WAF walls. |
| **EPA ECHO super-emitter scrape** | Browserbase + Stagehand drives the ECHO interactive map and intercepts its backing network calls to extract events — fills the empty `data/processed/super_emitter.json` that `score_candidates.py` already reads and that backs the DossierPanel "EPA super-emitter nearby" badge. New `services/ingest/super_emitter_browser.py`. |
| **Parcel lookup for OH/KY/PA** | Stagehand fills county assessor search forms (by address/parcel) and extracts the owner for states with no ArcGIS REST endpoint, completing the `surface_owner` actor in the CaseFile. Extends `services/swarm/web/parcel.py` (WV is the only state wired today). |
| **Authoritative bankruptcy / corporate status** | Browserbase automates operator-name → PACER bankruptcy case and → state Secretary-of-State business-status lookups (form/WAF/login-walled), replacing news-inferred `bankruptcy_findings` with sourced provenance. |
| **Funding & carbon-credit portal checks** | Navigate state plugging-program portals and carbon registries (ACR/CAR) to confirm eligibility/deadlines (feeding the knowledge base) and **draft-fill** an application package — never submitting (regulatory line). |
| **Screenshot + replay evidence** | Capture a screenshot at fetch time alongside the existing `replay_url`, store as immutable evidence, and surface both in the DossierPanel/CaseFile so a claim's source survives even if the page later changes or dies. |

> Guardrails carried through all of the above: **scope cache keys tightly**
> (well-specific vs. entity-level vs. program-level, so honesty is never
> compromised by a fuzzy match) and **keep everything fail-open** (an outage
> degrades to live/uncached, never a broken demo).

See `docs/OVERVIEW.md` for the product overview, `docs/ARCHITECTURE.md` for the
system design, and `PROGRESS.md` for an honest build-session self-audit.
Historical build specs live under `docs/archive/`.
