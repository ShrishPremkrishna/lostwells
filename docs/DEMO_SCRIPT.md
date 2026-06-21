# Demo script

A ~4-minute walk that leads with human exposure, foregrounds the **Appalachia
discovery**, shows real agentic AI, and stays honest about what's live vs
pre-computed. Numbers below match the current datastore (see `data/processed/meta.json`).

## 0. The hook (human first)

> "An estimated **17.6 million Americans** live within a mile of an oil or gas well
> (Czolowski et al., *EHP* 2017). For the **undocumented** orphaned wells — somewhere
> between 310,000 and 800,000 of them — that exposure is literally uncounted. There
> are wells under a school gym, six feet from a family's drinking water. Only 117,672
> are even documented."

Open the app → the intro overlay states exactly this. Click **Explore the map**.

## 1. The discovery (the headline)

> "We ran a fine-tuned LBNL CATALOG U-Net over historical USGS topo maps across
> Appalachia and surfaced **36,919 previously-undocumented candidate wells** in PA,
> WV, OH, and KY — on top of LBNL's 1,301 CA/OK detections, for **38,220 candidates**
> against a **117,672-well** documented backbone. Most of these Appalachian wells
> have never appeared in any modern inventory."

- The dim teal field is the **117,672 documented** orphaned wells (USGS DOW, real).
- The bright amber points are the **38,220 candidate undocumented wells**, colored and
  sized by impact score. The dense Appalachian clusters (Venango/McKean/Clarion PA,
  the WV panhandle, eastern KY) are **our** U-Net detections — that's the new ground.
- Attribution is explicit and correct: the CA/OK 1,301 are LBNL's published dataset;
  the 36,919 Appalachia detections are this project's own inference run (built on
  LBNL's model). See the About panel / `meta.json` citations.

## 2. The ranking (transparent, honest)

Click the top of the ranked list → the map flies to the top-scored wells (currently
urban Appalachia — **Cincinnati-West & Toledo OH, Pittsburgh-West PA** — undocumented
wells inside metro areas beside schools and dense population). Open the dossier:

- **Why it ranks here** — the breakdown bar sums exactly to the score; population,
  schools, and social vulnerability dominate. Note the renormalized line: we don't
  invent data we don't have. (Be candid: for these attribute-less detections, ranking
  is driven by the 4 real exposure/equity signals; methane/plug-cost are class-level
  modeled estimates, badged as such.)
- **Methane** — clearly labeled a *modeled estimate* (EPA GHGI × Kang 2016), with a
  GWP-20 urgency sidebar. Never presented as measured. (See the methane caveat in
  `AUDIT.md` §4.1 before quoting any aggregate CO₂ number.)
- **Plugging economics** — Raimi 2021 base estimate; depth unknown is stated.
- **Carbon kicker** — honest: covers only a few percent of the plug cost.

## 3. The agent swarm (real agency, not theater)

Toggle **Agent swarm** → **Replay swarm**. Investigator agents light up.

> "Each well gets an isolated-context Claude investigator that does **open-ended web
> search** — original operator, bankruptcy filings, shell-company transfers, local
> news — and writes a structured dossier. LangGraph `Send` map-reduce: one branch per
> well, single-threaded write at the ranking step."

Open an investigated well → read the **Claude investigation**: operator history,
liability findings, and cited sources are real web results. For an undocumented well
the agent honestly reports "no operator on record" and pivots to county/state program
context — that honesty is the point. *(The panel "Replay" is a deterministic
animation over cached dossiers; a live run is `python services/swarm/run_swarm.py
--total 12`, which works against the real API.)*

## 4. The signature reveal — hero cases (topo → today)

> **TBD — to be rebuilt.** The previous heroes (Admiral King OH, Vowinckel PA,
> AllenCo CA) were *confirmed / already-remediated* wells, not wells we
> discovered, so they were removed. The new heroes will be **3 wells we actually
> discovered**, each demonstrating a **different plugging pathway** (e.g.
> BIL/state-program · carbon-credit-funded · landowner/charity) and each ranking
> high on local negative impact — cased end-to-end and used for the topo → today
> reveal. See `docs/IMPLEMENTATION_PLAN.md` §3.14.

## 5. Close (the product)

> "We found ~37,000 wells nobody had inventoried, ranked them by who's living on top
> of them, and — at a modeled **~$76k per well** — it would cost about **$2.9B to plug
> every one of the 38,220 we surfaced, inside the finite $4.7B federal fund**. The
> problem was never the money. It was that nobody knew where the wells are. That's
> what this finds — and the path to plugging is what we build on top of it."

## Live vs. pre-computed (disclose)

- **Live:** map exploration, click-to-dossier, the topo-dissolve, and a small live
  swarm run (`run_swarm.py`) — verified working against the API.
- **Pre-computed & disclosed:** the U-Net detections, the cached dossiers, the
  enrichment joins. All cached so nothing fragile fetches on stage.

## Fallbacks

- Swarm rate-limits → cached `dossiers.json` already powers the panel; "Replay" is
  deterministic.
- Tile/network hiccup → the deck.gl data layers render from local JSON regardless.
- Record a screen capture of the swarm + topo-dissolve as a backup video.

## Honesty checklist before presenting (see `AUDIT.md`)

- Don't quote a single aggregate CO₂ figure without stating the horizon + GWP — the
  model implies ~208k t CO₂e/yr, not an annual 30 Mt (`AUDIT.md` §4.1).
- Say "candidate / high-confidence detection," never "confirmed well."
- Credit LBNL's **model** while claiming the **Appalachia discovery** as ours.
- Positioning: we **mobilize**, we don't plug, take money, or hold liability.
