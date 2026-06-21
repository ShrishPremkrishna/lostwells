"""Surface-owner lookup (§3.2): coordinate -> parcel owner via free ArcGIS REST.

Point-in-polygon against a state/county parcel service (no scraping, no key) per
`docs/STRUCTURED_PROPERTY_INFORMATION.md`. Returns the **surface owner** — kept
distinct from the **liable operator** (severed estates are common in Appalachia).
SQLite-cached; stdlib only (urllib/sqlite3) so it runs anywhere.

Currently wired: WV (statewide, free since SB 588). OH/KY/PA are extensible via the
SERVICES registry (discover the owner field with `?f=pjson` first).
"""
from __future__ import annotations

import json
import sqlite3
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "data" / "cache"
CACHE.mkdir(parents=True, exist_ok=True)
TIMEOUT = 20

# state -> {service query url, owner field, extra fields to return}.
SERVICES: dict[str, dict] = {
    "WV": {
        "url": "https://services.wvgis.wvu.edu/arcgis/rest/services/"
               "Planning_Cadastre/WV_Parcels/MapServer/0/query",
        "owner": "FullOwnerName",
        "extra": ["FullOwnerAddress", "FullPhysicalAddress", "Acres_C",
                  "CleanParcelID", "FullLegalDescription"],
    },
    # OH / KY / PA: add the county/state parcel /query endpoint + owner field here
    # (discover via ?f=pjson; OWNER field name varies). Absent -> graceful None.
}


def _db() -> sqlite3.Connection:
    db = sqlite3.connect(CACHE / "parcel.sqlite")
    db.execute("CREATE TABLE IF NOT EXISTS parcel (k TEXT PRIMARY KEY, v TEXT)")
    return db


def owner_at(lat: float, lon: float, state_abbr: str) -> Optional[dict]:
    """Return {owner, owner_address, physical_address, acres, parcel_id, legal,
    source_url, state} for the parcel containing the point, or None."""
    cfg = SERVICES.get((state_abbr or "").upper())
    if not cfg:
        return None
    key = f"{state_abbr}:{lat:.6f},{lon:.6f}"
    db = _db()
    row = db.execute("SELECT v FROM parcel WHERE k=?", (key,)).fetchone()
    if row:
        return json.loads(row[0]) if row[0] != "null" else None

    params = {
        "geometry": f"{lon},{lat}",          # ArcGIS point is x,y = lon,lat
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": ",".join([cfg["owner"], *cfg["extra"]]),
        "returnGeometry": "false",
        "f": "json",
    }
    url = cfg["url"] + "?" + urllib.parse.urlencode(params)
    result = None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lost-wells/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310
            feats = json.loads(r.read()).get("features", [])
        if feats:
            a = feats[0].get("attributes", {})
            result = {
                "owner": a.get(cfg["owner"]),
                "owner_address": a.get("FullOwnerAddress"),
                "physical_address": a.get("FullPhysicalAddress"),
                "acres": a.get("Acres_C"),
                "parcel_id": a.get("CleanParcelID"),
                "legal": a.get("FullLegalDescription"),
                "source_url": cfg["url"].replace("/query", ""),
                "state": state_abbr,
                "note": "surface owner (parcel) — distinct from the liable operator",
            }
    except Exception:  # noqa: BLE001 — offline / service down -> None (cached as miss)
        result = None

    db.execute("INSERT OR REPLACE INTO parcel VALUES (?,?)",
               (key, json.dumps(result) if result else "null"))
    db.commit()
    return result


if __name__ == "__main__":  # Parkersburg hero
    print(json.dumps(owner_at(39.281361, -81.556764, "WV"), indent=2))
