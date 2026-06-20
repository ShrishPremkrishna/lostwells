# Demo script

A ~4-minute walk that leads with human exposure, shows real agentic AI, and stays
honest about what's live vs pre-computed.

## 0. The hook (human first)

> "An estimated **17.6 million Americans** live within a mile of an oil or gas well
> (Czolowski et al., *EHP* 2017). For the **undocumented** orphaned wells — somewhere
> between 310,000 and 800,000 of them — that exposure is literally uncounted. There
> are wells under a school gym, six feet from a family's drinking water. Only 117,672
> are even documented."

Open the app → the intro overlay states exactly this. Click **Explore the map**.

## 1. The map (reliable core)

- The dim teal field is the **117,672 documented orphaned wells** (USGS DOW, real).
- The bright amber points are **1,303 candidate undocumented wells** detected by
  LBNL's U-Net on historical topo maps, colored and sized by impact score.
- Click the top of the ranked list → the map flies to **Britton, Oklahoma City**:
  a pre-1951 detected well, tract population ~5,200, **6 schools within a mile**,
  nearest TULAKES Elementary, SVI 0.99. "This is the thesis: undocumented wells
  beside schools in the most vulnerable communities."

## 2. The dossier (transparent ranking)

Open the dossier panel:
- **Why it ranks here** — the breakdown bar sums exactly to the score; population,
  schools, and social vulnerability dominate. Note the renormalized line: we don't
  invent data we don't have.
- **Methane** — clearly labeled a *modeled estimate* (g/hr), with GWP-100 and a
  GWP-20 urgency sidebar. Never presented as measured.
- **Plugging economics** — Raimi 2021 base estimate; depth unknown is stated.
- **Carbon kicker** — honest: covers a few percent of the plug cost. "Most wells
  need public funds — that's why prioritization under the $4.7B program matters."

## 3. The agent swarm (real agency, not theater)

Toggle **Agent swarm** → **Replay swarm**. Twelve investigator agents light up.

> "Each well gets an isolated-context Claude investigator that does **open-ended web
> search** — original operator, bankruptcy filings, shell-company transfers, local
> news — and writes a structured dossier. This is a LangGraph `Send` map-reduce:
> one branch per well, single-threaded write at the ranking step. Anthropic's
> orchestrator-worker beat single-agent by 90.2% on their research eval."

Open an investigated well → read the **Claude investigation** section: the operator
history, liability findings, and cited sources are real web results. For an
undocumented well the agent honestly reports "no operator on record" and pivots to
the county/state program context — that honesty is the point.

## 4. The signature reveal (topo → today)

Open a **hero well** (red) → **Reveal topo → today**. Drag the swipe:

- **AllenCo / St. Vincent School, LA** — 21 urban oil wells under 1,000 ft from a
  school; the 1953 topo dissolves into today's satellite, the marker pulsing over
  the neighborhood.
- **Admiral King Elementary, OH** — the leaking well found under the school gym (2014).
- **Vowinckel, PA** — six feet from a family's only drinking water; ranks *low* on
  aggregate exposure but is a textbook individual-harm case — the score measures
  population impact, and we say so.

## 5. Close (the product)

> "Detection extends a published U-Net; the swarm is real agentic investigation; the
> ranking is a transparent, adjustable decision tool. Under a finite $4.7B budget,
> prioritization is exactly what decision-makers need — that's the product."

## Live vs. pre-computed (disclose)

- **Live:** map exploration, click-to-dossier, the topo-dissolve, and a small live
  swarm run (`python services/swarm/run_swarm.py --total 12`).
- **Pre-computed & disclosed:** the LBNL U-Net detections, the cached dossiers, the
  enrichment joins. All cached so nothing fragile fetches on stage.

## Fallbacks

- Swarm rate-limits → cached `dossiers.json` already powers the panel; "Replay" is
  deterministic.
- Tile/network hiccup → the deck.gl data layers render from local JSON regardless.
- Record a screen capture of the swarm + topo-dissolve as a backup video.
