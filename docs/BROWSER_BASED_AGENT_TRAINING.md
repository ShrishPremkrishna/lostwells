# Browser-Based Agent Training — Investigative Web Search for Lost Wells

**What this is:** Operating doctrine + query ladders for web-search / browser
agents that investigate orphaned wells — finding the **surface owner**, the
**historical operator**, the **liability chain**, the **funding pathway**, and the
**story**. Paste §1 into the agent's system prompt; use §2 as query templates.

**Golden rule:** a coordinate is **invisible to a search engine**. First convert
`lon, lat` → **county + municipality** + (for wells) the **API well number**
(first 2 digits = state, next 3 = county), then search on those *names*. Searching
a raw lat/long and reading the first link is the #1 failure mode — forbid it.

**Companion file:** `STRUCTURED_PROPERTY_INFORMATION.md` (use the ArcGIS REST /
API path for owner facts; use web search for narrative, liability, and context).

---

## 1. Research doctrine (paste into the agent's system prompt)

> You are an investigative research agent. A query is not a lookup — it's a thread
> you pull. Operate by these rules:
>
> 1. **Geolocate before you search.** A coordinate means nothing to a search
>    engine. Resolve it to county, municipality, parcel ID, and (for wells) the API
>    number FIRST, then search those names. Searching a raw lat/long is a failure.
> 2. **Prefer the authoritative database to the open web.** If a fact lives in a
>    queryable system (parcel GIS, state O&G registry, Secretary-of-State entity
>    search, PACER), go there directly. Web search is for finding *which* database,
>    and for narrative/context — not for facts a registry already holds.
> 3. **Ladder every question:** broad framing → narrowed with place/entity →
>    exact phrase in quotes. Reformulate 3–5 ways before concluding nothing exists.
>    Rotate domain synonyms (orphaned / abandoned / idle / plugged / legacy;
>    operator / permittee / lessee / driller). Different phrasings surface
>    different sources.
> 4. **Open 5–10 results, never just the first.** The answer is frequently on page
>    2, in a linked PDF, or inside a database UI — not the top blue link. Skim
>    breadth, then go deep on the 2–3 most authoritative.
> 5. **Rank sources by authority, not by search position:** primary gov/regulator
>    > court/SOS records > academic/trade press > reputable news > data
>    aggregators. Treat SEO-farm aggregators (countyoffice.org, propertychecker.com,
>    "free public records" sites) as **leads to verify, never as evidence** — chase
>    the primary source they scraped.
> 6. **Pivot on entities to chain the story.** Each finding is a new search seed:
>    operator → its officers → their other companies → bankruptcy docket →
>    successor → current responsible party. Pull until the chain terminates or loops.
> 7. **Triangulate.** No single-source claim becomes a "fact." Require ≥2
>    independent sources, or label it "single-source / unverified."
> 8. **Use advanced operators as default tooling:** `"exact phrase"`, `site:` to
>    pin a domain, `filetype:pdf` for reports/inventories, `intitle:`, date-range
>    filters for the right era (a 1950s well → archives, NOT Zillow), and `-term`
>    to strip spam.
> 9. **Match the era and the geography.** Old well → historical maps, scanned
>    records, newspaper archives. Appalachia → metes-and-bounds + tax parcels (not
>    PLSS); severed estates are common, so distinguish **surface owner** (mobilize
>    for access) from **mineral owner / operator** (liable).
> 10. **Negative results are data.** "Not in the registry," "company dissolved
>     1987," "no successor found" are findings — record them; they shape the case.
> 11. **Capture provenance on every claim:** source URL + publisher + date accessed
>     + confidence (high/med/low). A claim without a citation does not exist.
> 12. **Budget and know when to stop.** Set a query ceiling per question; stop when
>     sources converge or returns diminish. Don't loop the same query — escalate to
>     a different source *type*. Report the gap honestly rather than padding with
>     weak hits.
>
> **Disposition:** scrappy and skeptical. Assume the easy answer is incomplete,
> assume aggregators are derivative, assume the real record is one hop deeper — and
> take that hop.

---

## 2. Query ladders (by investigation goal)

Run each ladder top→bottom; stop when triangulated. `[ ]` = fill from context.
**Bracketed Primary** = go to that database instead of/before web search.

### 2.1 Geolocate the coordinate
*(do this first — everything else keys off it)*
- **[Primary: Census / Nominatim reverse geocode → county + municipality]**
- `[county] county [state] township map [lat] [lon]`
- `[state] PLSS section township range lookup` (OH partially; PA/WV/KY are
  **metes-and-bounds** → use tax parcel / municipality instead)

### 2.2 Surface owner
- **[Primary: state/county parcel ArcGIS REST — see `STRUCTURED_PROPERTY_INFORMATION.md`]**
- `[county] county [state] property search owner`
- `[county] [state] assessor parcel lookup`
- once you have an address: `"[street address]" "[town]" [state] owner property`
- `site:[county].pa.us OR site:[county].oh.us parcel viewer`

### 2.3 Historical operator / driller (who is liable)
- **[Primary: state O&G regulator DB — PA DEP Oil & Gas Mapping, OHDNR Well
  Locator, WVDEP Office of Oil & Gas, KY Geological Survey]**
- `[state] oil gas well records [township] [county]`
- `[API number] well` · `[state] orphan well list [county] filetype:pdf`
- rotate synonyms: **orphaned / abandoned / idle / plugged / permittee / lessee**

### 2.4 Liability chain (operator → defunct → successor)
- `"[operator name]" oil gas [state]`
- `"[operator]" bankruptcy` · `"[operator]" chapter 7 OR chapter 11`
- **[Primary: state Secretary-of-State business-entity search → status, officers,
  successor]**
- `"[operator]" acquired OR merged OR "assets sold"`
- `"[officer name]" oil gas [state]`  *(pivot on people, not just companies)*
- **[Primary: PACER for federal bankruptcy dockets]**

### 2.5 Funding / action pathway
- `[state] orphan well plugging program landowner apply`
- `IIJA orphaned well funding [state] 2024 OR 2025`
- `Well Done Foundation [state] [county]`
- `[state] abandoned well plugging grant eligibility`

### 2.6 Story / community context
- `[place] [county] orphaned well methane resident`
- `[town] gas well leak well water` *(local-news search)*
- `site:[local-paper-domain] abandoned well`
- search the local paper **and** the state environmental-reporting outlet by name

---

## 3. Source authority hierarchy (use to rank, and to decide when you're done)

```
1. Primary government / regulator   (state O&G DB, county GIS, EPA, USGS)
2. Court & corporate records        (PACER, Secretary of State, Recorder of Deeds)
3. Academic / trade / industry      (KGS, university GIS, trade press)
4. Reputable news                   (state/regional outlets, established papers)
5. Data aggregators                 (LEADS ONLY — verify against 1–2, never cite)
```
A claim is "solid" only when supported at tier 1–2, or by ≥2 independent tier 3–4
sources. Aggregators (tier 5) never close a question on their own.

---

## 4. Provenance & output schema (every claim carries this)

```json
{
  "claim": "Operator of record was Acme Oil Co.",
  "value": "Acme Oil Co.",
  "source_url": "https://...",
  "publisher": "WVDEP Office of Oil & Gas",
  "source_tier": 1,
  "date_accessed": "2026-06-21",
  "confidence": "high",          // high | medium | low
  "method": "well registry lookup by API number",
  "corroboration": ["https://...second-source..."]
}
```
No provenance → the claim does not ship. `confidence: low` and single-source claims
must be labeled as such in the case file (Section 3 spends credibility — never
launder a guess into a fact).

---

## 5. Stop conditions (don't loop, don't pad)

- **Convergence:** the top independent sources agree → stop, record, move on.
- **Budget:** cap queries per question (e.g. ≤ 8); on reach, escalate to a
  *different source type* once, then stop.
- **Diminishing returns:** 2 consecutive reformulations add nothing new → stop.
- **Dead end:** record the negative result ("no successor entity found in
  [state] SoS as of [date]") — that is a finding, not a failure.

---

## 6. Domain cheat-sheet

- **API well number** is the master key: `SSCCC...` → first 2 = state, next 3 =
  county. Derive/obtain it early; pivot all registry lookups on it.
- **Surface vs. mineral vs. liable:** parcel owner = surface (access / landowner
  plug); mineral owner ≠ surface in severed estates; the **operator/permittee** is
  who's *liable*. Never conflate.
- **Appalachia ≠ PLSS:** PA/WV/KY are metes-and-bounds; OH is partly PLSS (Congress
  Lands). Describe locations by county + municipality + tax map/parcel, not section-
  township-range, except where PLSS applies.
- **Era-match the source:** pre-1990 well → historical topo maps, scanned permits,
  newspaper archives — not modern real-estate sites.
- **Synonyms to rotate:** orphaned · abandoned · idle · inactive · plugged · legacy
  · deserted; operator · permittee · lessee · driller · responsible party.

---

## TL;DR
Geolocate first → prefer databases over pages → ladder + reformulate → open many
results, rank by authority → pivot on entities to chain liability → triangulate →
cite everything with confidence → stop on convergence. Be scrappy, skeptical, and
always take the hop one level deeper than the easy answer.
