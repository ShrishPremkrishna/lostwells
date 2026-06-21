"""Actor map (§3.3): coordinate -> the named people/bodies who can act.

For a well we resolve four kinds of actor, honestly degrading when offline:
  - **US senators** (2 per state) + **US House representative** (by district)
  - **state legislators** (upper + lower chamber, by district)
  - **state oil-&-gas regulator** (the program that actually plugs)
  - **community / EJ organizations** that can apply pressure

Data sources (all free / CC0, no key): the **Census geocoder** (coord -> 119th
congressional + state legislative districts), **unitedstates/congress-legislators**
(CC0), **OpenStates** per-state rosters (CC0), and the hand-built
`data/static/state_regulators.csv` + `ej_orgs.csv`. Network results are cached
under `data/cache/`; if the network is unavailable we still return the state-level
actors (senators, regulator, EJ orgs) and mark district-specific ones unavailable.

Stdlib only (urllib/sqlite3/csv/json) so it runs in the pure-compute engine env.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "data" / "static"
CACHE = ROOT / "data" / "cache"
CACHE.mkdir(parents=True, exist_ok=True)

LEGIS_URL = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
OPENSTATES_URL = "https://data.openstates.org/people/current/{st}.csv"
GEOCODER = (
    "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
    "?x={lon}&y={lat}&benchmark=Public_AR_Current&vintage=Current_Current"
    "&layers=all&format=json"
)
TIMEOUT = 15


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "lost-wells/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310 (trusted gov/CC0 hosts)
        return r.read()


# --------------------------------------------------------------------------- #
# Bulk rosters (downloaded once, cached on disk)                              #
# --------------------------------------------------------------------------- #
_LEGIS: Optional[list] = None
_OPENSTATES: dict[str, list[dict]] = {}


def _legislators() -> list:
    global _LEGIS
    if _LEGIS is not None:
        return _LEGIS
    cache = CACHE / "legislators-current.json"
    if not cache.exists():
        try:
            cache.write_bytes(_get(LEGIS_URL))
        except Exception:  # noqa: BLE001 — offline: degrade to empty roster
            _LEGIS = []
            return _LEGIS
    _LEGIS = json.loads(cache.read_text())
    return _LEGIS


def _openstates(st: str) -> list[dict]:
    st = st.lower()
    if st in _OPENSTATES:
        return _OPENSTATES[st]
    cache = CACHE / f"openstates_{st}.csv"
    if not cache.exists():
        try:
            cache.write_bytes(_get(OPENSTATES_URL.format(st=st)))
        except Exception:  # noqa: BLE001
            _OPENSTATES[st] = []
            return _OPENSTATES[st]
    with open(cache, newline="") as f:
        _OPENSTATES[st] = list(csv.DictReader(f))
    return _OPENSTATES[st]


# --------------------------------------------------------------------------- #
# Hand-built CSVs                                                              #
# --------------------------------------------------------------------------- #
def _csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _regulator(state_abbr: str) -> Optional[dict]:
    for row in _csv(STATIC / "state_regulators.csv"):
        if row.get("state_abbr") == state_abbr:
            return {
                "agency": row.get("agency"),
                "division": row.get("division"),
                "program": row.get("program_name"),
                "url": row.get("program_url") or row.get("agency_url"),
                "phone": row.get("phone") or None,
                "email": row.get("email") or None,
            }
    return None


def _ej_orgs(state_abbr: str) -> list[dict]:
    out = []
    for row in _csv(STATIC / "ej_orgs.csv"):
        if row.get("state_abbr") in (state_abbr, "ALL"):
            out.append({"org": row.get("org"), "scope": row.get("scope"),
                        "focus": row.get("focus"), "url": row.get("url")})
    return out


# --------------------------------------------------------------------------- #
# Geocoder (coord -> districts), SQLite-cached                                 #
# --------------------------------------------------------------------------- #
def _geo_db() -> sqlite3.Connection:
    db = sqlite3.connect(CACHE / "actors.sqlite")
    db.execute("CREATE TABLE IF NOT EXISTS geo (k TEXT PRIMARY KEY, v TEXT)")
    return db


def _districts(lat: float, lon: float) -> Optional[dict]:
    """Return {state_fips, cd, sldu, sldl} for a coordinate (cached)."""
    key = f"{lat:.5f},{lon:.5f}"
    db = _geo_db()
    row = db.execute("SELECT v FROM geo WHERE k=?", (key,)).fetchone()
    if row:
        return json.loads(row[0])
    try:
        raw = _get(GEOCODER.format(lon=lon, lat=lat))
    except Exception:  # noqa: BLE001 — offline
        return None
    g = json.loads(raw).get("result", {}).get("geographies", {})

    def basename(layer_key: str) -> Optional[str]:
        for k, v in g.items():
            if layer_key in k and v:
                return v[0].get("BASENAME")
        return None

    cd_list = next((v for k, v in g.items() if "Congressional Districts" in k and v), None)
    out = {
        "state_fips": (cd_list[0].get("STATE") if cd_list else None),
        "cd": basename("Congressional Districts"),
        "sldu": basename("State Legislative Districts - Upper"),
        "sldl": basename("State Legislative Districts - Lower"),
    }
    db.execute("INSERT OR REPLACE INTO geo VALUES (?,?)", (key, json.dumps(out)))
    db.commit()
    return out


def _num(s: Optional[str]) -> Optional[str]:
    """Strip a district label down to its core number/code for matching."""
    if not s:
        return None
    s = s.strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    return str(int(digits)) if digits else s.upper()


def _legislator_dict(st: str, district: Optional[str]) -> dict:
    """US senators (by state) + the House rep (by district) from congress-legislators."""
    reps, sens = [], []
    dnum = _num(district)
    for p in _legislators():
        terms = p.get("terms") or []
        if not terms:
            continue
        t = terms[-1]
        if t.get("state") != st:
            continue
        name = (p.get("name") or {}).get("official_full") or ""
        actor = {"name": name, "party": t.get("party"), "phone": t.get("phone"),
                 "url": t.get("url"), "type": t.get("type")}
        if t.get("type") == "sen":
            sens.append(actor)
        elif t.get("type") == "rep" and dnum is not None and _num(str(t.get("district"))) == dnum:
            reps.append(actor)
    return {"us_senators": sens, "us_representative": reps[0] if reps else None}


def _state_legs(st: str, sldu: Optional[str], sldl: Optional[str]) -> list[dict]:
    out = []
    rows = _openstates(st)
    for chamber, dist in (("upper", sldu), ("lower", sldl)):
        dnum = _num(dist)
        if dnum is None:
            continue
        for r in rows:
            if r.get("current_chamber") == chamber and _num(r.get("current_district")) == dnum:
                out.append({"name": r.get("name"), "chamber": chamber,
                            "district": r.get("current_district"),
                            "party": r.get("current_party"), "email": r.get("email") or None})
                break
    return out


def actors_for(lat: float, lon: float, state_abbr: Optional[str] = None) -> dict:
    """Resolve the full actor map for one well coordinate."""
    geo = _districts(lat, lon)
    st = state_abbr
    fed = {"us_senators": [], "us_representative": None}
    state_legs: list[dict] = []
    if st:
        fed = _legislator_dict(st, geo.get("cd") if geo else None)
        if geo:
            state_legs = _state_legs(st, geo.get("sldu"), geo.get("sldl"))
    return {
        "responsible_regulator": _regulator(st) if st else None,
        "can_fund": _regulator(st) if st else None,  # the state program is the funder of record
        "can_pressure": {
            "us_senators": fed["us_senators"],
            "us_representative": fed["us_representative"],
            "state_legislators": state_legs,
            "ej_orgs": _ej_orgs(st) if st else [],
        },
        "districts": geo,
        "available": {"federal": bool(fed["us_senators"] or fed["us_representative"]),
                      "state_legislators": bool(state_legs),
                      "regulator": bool(st and _regulator(st))},
    }


if __name__ == "__main__":  # manual test: Cincinnati West candidate (Hamilton OH)
    import sys
    lat, lon, st = (float(sys.argv[1]), float(sys.argv[2]), sys.argv[3]) if len(sys.argv) > 3 \
        else (39.14446, -84.56525, "OH")
    print(json.dumps(actors_for(lat, lon, st), indent=2))
