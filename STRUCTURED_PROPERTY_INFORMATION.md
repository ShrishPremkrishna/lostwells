# Structured Property Information — Owner Lookup for Lost Wells

**What this is:** Queryable, *structured* sources to resolve a well's coordinate
(`lon, lat`) → current **parcel + owner**, for the Appalachian target states
(OH / WV / KY / PA). Prefer these over open web search — they are **databases,
not pages**: one HTTP request returns a clean, deterministic answer.

**Primary technique:** point-in-polygon query against a state/county **ArcGIS REST**
parcel service. Send a point, get back the parcel polygon + attributes (owner,
mailing address, parcel ID, assessed value). No scraping, no guessing.

**When to use which:** OH/WV/KY → free state ArcGIS REST (below). PA + any gap →
a national API free trial (§3). Need a phone/email for one landowner → §4.

---

## 1. The ArcGIS REST recipe (the valuable part)

US parcels live in county/state GIS as ArcGIS Feature/Map services. Each exposes
a REST `/query` endpoint. The whole lookup is four steps.

### Step 1 — find the service URL
From a state portal (§2), open the parcels item → **"I want to use this" / "View
Full Details" / "API Resources"** → copy the **Feature Service** or **GeoService**
URL. Or browse the org's service directory directly:
```
https://<host>/arcgis/rest/services?f=json
https://services.arcgis.com/<orgId>/arcgis/rest/services?f=json
```
GET the service root with `?f=pjson` to list its layers and their numeric ids;
pick the parcels layer. Final query endpoint is:
```
<service>/MapServer/<layerId>/query      (or .../FeatureServer/<layerId>/query)
```

### Step 2 — discover field names FIRST (the owner column name varies)
```
GET  <service>/MapServer/<layerId>?f=pjson
```
Read the `fields` array. Owner columns seen in the wild — match case-insensitively
on `/own|name|taxpay|deed/`:
`OWNER, OWNER_NAME, OWNERNME1, OWNER1, NAME, PARCELOWNER, DEEDED_OWNER, TAXPAYER`.

### Step 3 — point-in-polygon query (coord → parcel)
```
<service>/MapServer/<layerId>/query
    ?geometry=<lon>,<lat>
    &geometryType=esriGeometryPoint
    &inSR=4326
    &spatialRel=esriSpatialRelIntersects
    &outFields=*
    &returnGeometry=true
    &f=geojson
```
| Param | Value | Why |
|---|---|---|
| `geometry` | `<lon>,<lat>` | ArcGIS point is **x,y = lon,lat** (not lat,lon) |
| `inSR` | `4326` | declare WGS84 input or the service assumes its own SR |
| `geometryType` | `esriGeometryPoint` | a single point |
| `spatialRel` | `esriSpatialRelIntersects` | parcel containing the point |
| `outFields` | `*` | return all attributes (owner, APN, mailing) |
| `f` | `geojson` | or `pjson` for the Esri JSON shape |

**Concrete example** (host/layer are placeholders — resolve from §2):
```bash
curl "https://<host>/arcgis/rest/services/Parcels/MapServer/0/query?\
geometry=-81.52,40.21&geometryType=esriGeometryPoint&inSR=4326&\
spatialRel=esriSpatialRelIntersects&outFields=*&returnGeometry=true&f=geojson"
```
```python
import requests
def owner_at(host, layer, lon, lat):
    r = requests.get(f"{host}/{layer}/query", params={
        "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint",
        "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*", "returnGeometry": "true", "f": "geojson"})
    feats = r.json().get("features", [])
    return feats[0]["properties"] if feats else None
```

### Step 4 — reverse: search by owner name (find all parcels of an owner)
```
.../query?where=OWNER_NAME LIKE '%SMITH%'&outFields=*&f=geojson
```
Useful for tying a defunct operator to land it still holds.

### Scale notes
- One GET per well; **cache by parcel ID** — many wells fall on the same parcel.
- Add a small delay; respect `maxRecordCount`. Point queries return one feature.
- If `f=geojson` is rejected by an old server, use `f=json` (Esri shape) and read
  `features[].attributes`.

---

## 2. State entry portals (resolve the REST URL from these)

| State | Portal (find the parcels service here) | Coverage | Notes |
|---|---|---|---|
| **OH** | [ohioparcels-geohio.hub.arcgis.com](https://ohioparcels-geohio.hub.arcgis.com/) · [ogrip-geohio.opendata.arcgis.com](https://ogrip-geohio.opendata.arcgis.com/) | **Statewide, standardized** | Best. Download GeoJSON/CSV **and** GeoService/WFS/WMS APIs |
| **WV** | [mapwv.gov/parcel](https://www.mapwv.gov/parcel/) · [WVGISTC clearinghouse](https://wvgis.wvu.edu/data/dataset.php?ID=371) | All **55 counties**, searchable by owner | Free since **SB 588 (2017)**; REST service backs the viewer |
| **KY** | [opengisdata.ky.gov](https://opengisdata.ky.gov/) · [kygeonet.ky.gov](https://kygeonet.ky.gov/) | County **PVA** parcels, statewide | Statewide parcel ArcGIS REST services |
| **PA** | [pasda.psu.edu](https://www.pasda.psu.edu/) · [pa-geo-data-pennmap.hub.arcgis.com](https://pa-geo-data-pennmap.hub.arcgis.com/) | ⚠️ **Incomplete** statewide; per-county | 67 autonomous counties → use county assessor REST or a national API (§3) |

---

## 3. National APIs (standardized, real free trials) — for bulk + PA gaps

| Provider | Free trial | Coverage | Owner fields | Use it for |
|---|---|---|---|---|
| **[ReportAll USA](https://reportallusa.com/products/api)** | **30 days, 1,000 free parcel lookups** + 20k tiles, no sales call | 160M (>99% pop) | owner, mailing addr, APN, acreage | **Start here** — best trial-to-API ratio |
| **[Regrid](https://regrid.com/api)** (Loveland/Landgrid) | ~1-week trial / 30-day eval, no card; API ~$500–2k/mo | ~158M | deeded owner, mailing | One clean **national schema** for bulk join |
| **[ATTOM](https://api.developer.attomdata.com/home)** | **30-day free API key**; from ~$95/mo | 160M (99% pop) | owner **+ deeds, mortgages, sales history** | **Documented-well liability / transfer chain** |

Skip CoreLogic / LightBox — enterprise, no real trial.

---

## 4. Owner name → a real person (demo subset only)

Parcel data gives **name + mailing address**. To reach them (your ≥1 end-to-end
landowner case):
- **Free:** county **Recorder of Deeds** (grantor/grantee, confirms current owner);
  TruePeopleSearch / FastPeopleSearch for phone/email.
- **Trial:** **BatchData** or **PropertyRadar** (skip-tracing, free-trial credits).

---

## 5. Gotchas (all real, all bite)

- **Surface ≠ mineral ≠ liable.** Appalachian estates are commonly **severed**.
  The parcel owner is the **surface owner** (mobilize for access / landowner-funded
  plug). The party **liable** for the well is the **operator/permittee** in the
  state O&G registry — not necessarily the surface owner. Keep them separate.
- **Coordinate order:** ArcGIS point geometry is **x,y = lon,lat**. Pass `inSR=4326`.
- **Datum:** historical well coords may be **NAD27**; reproject to WGS84 / the
  service SR or you miss the parcel by 20–40 m (bigger than a small lot).
- **Field names vary** per county/state — always discover via `?f=pjson` first;
  never hard-code `OWNER`.
- **PA is the weak link** — no complete free statewide owner layer; fall back to a
  county REST service or a national API.
- **`f=geojson` not supported** on some older ArcGIS Server versions → use `f=json`
  and read `features[].attributes` instead of `features[].properties`.

---

## TL;DR
1. OH/WV/KY: resolve the parcels **ArcGIS REST** service from the portal (§2) →
   `?f=pjson` to learn the owner field → point query (§1) → owner. Free, deterministic.
2. PA + gaps: **ReportAll** free trial (1,000 lookups covers the demo).
3. Liability/transfer history: **ATTOM** free key.
4. Reach a person: county deeds + a skip-trace trial (§4).
5. Always separate **surface owner** (parcel) from **liable operator** (well DB).
