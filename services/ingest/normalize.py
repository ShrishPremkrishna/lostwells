"""Normalization helpers for the Lost Wells ingestion pipeline.

The USGS DOW source carries messy, agency-specific free text for `Type` and
`Status` (59k nulls, codes like ``OR``/``HP``/``AB`` mixed with prose like
``"Oil & Gas"``). We collapse those into a small, well-defined vocabulary so the
ranking engine and UI can reason about oil-vs-gas (plug-cost driver) and
plugged-vs-unplugged (methane-proxy driver) consistently.

Key fact: the dataset is the *Documented Unplugged Orphaned* well dataset
(USGS DR1167) — so a well is treated as **unplugged** unless its status text
explicitly says otherwise.
"""
from __future__ import annotations

import math
import re
from typing import Optional

# --- Well type vocabulary -------------------------------------------------
TYPE_OIL = "oil"
TYPE_GAS = "gas"
TYPE_OIL_GAS = "oil_gas"
TYPE_DRY = "dry"
TYPE_INJECTION = "injection"
TYPE_OTHER = "other"
TYPE_UNKNOWN = "unknown"


def classify_type(raw: Optional[str]) -> str:
    """Map free-text well type to a controlled vocabulary."""
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return TYPE_UNKNOWN
    s = str(raw).strip().lower()
    if not s or s in {"not listed", "not available", "no product specified", "nt", "unknown"}:
        return TYPE_UNKNOWN
    has_oil = bool(re.search(r"\boil\b|^o$|^o&?g", s)) or "oil" in s
    has_gas = "gas" in s or s == "g"
    if (has_oil and has_gas) or s in {"og", "o&g", "o & g"}:
        return TYPE_OIL_GAS
    if has_gas:
        return TYPE_GAS
    if has_oil:
        return TYPE_OIL
    if "dry" in s:
        return TYPE_DRY
    if s in {"wi", "swd", "di"} or "inject" in s or "disposal" in s:
        return TYPE_INJECTION
    if any(k in s for k in ("strat", "test", "vertical", "core", "obs", "monitor")):
        return TYPE_OTHER
    return TYPE_OTHER


# --- Well status vocabulary ----------------------------------------------
STATUS_ORPHAN = "orphan"
STATUS_ABANDONED = "abandoned"
STATUS_PLUGGED = "plugged"
STATUS_IDLE = "idle"
STATUS_UNDOCUMENTED = "undocumented"  # LBNL detections — not in any registry
STATUS_UNKNOWN = "unknown"

_PLUGGED_RE = re.compile(r"plug|reclamation|^pa$|^p&a$|^p & a$", re.I)
_ORPHAN_RE = re.compile(r"orphan|^or$|forfeit|deserted", re.I)
# ``DV`` = dry & abandoned (state code); D&A / dry hole also land here.
_ABANDON_RE = re.compile(r"abandon|^ab$|^dv$|^d&a$|d\s*&\s*a|dry\s*hole", re.I)
# ``TA`` = temporarily abandoned -> idle; ``SI`` shut-in; ``II`` inactive.
_IDLE_RE = re.compile(r"idle|shut[\s-]?in|^si$|^ta$|^ii$|temporarily|inactive|suspend", re.I)


def classify_status(raw: Optional[str]) -> str:
    """Map free-text status to a controlled vocabulary.

    Order matters: an explicit plugged/reclamation signal wins, because that is
    the only thing that flips a well out of the high-methane bucket.
    """
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return STATUS_UNKNOWN
    s = str(raw).strip()
    if not s:
        return STATUS_UNKNOWN
    if _PLUGGED_RE.search(s):
        return STATUS_PLUGGED
    if _ORPHAN_RE.search(s):
        return STATUS_ORPHAN
    if _ABANDON_RE.search(s):
        return STATUS_ABANDONED
    if _IDLE_RE.search(s):
        return STATUS_IDLE
    return STATUS_UNKNOWN


def is_plugged(status_norm: str) -> bool:
    """A well is plugged only if explicitly classified as such.

    The DOW is by definition a dataset of *unplugged* orphaned wells, so every
    other status (orphan/abandoned/idle/unknown) is treated as unplugged for
    the methane proxy — the conservative, source-consistent choice.
    """
    return status_norm == STATUS_PLUGGED


# --- State-registry attribute normalizers --------------------------------
# Placeholder operator tokens that carry no information (drop to None).
_OPERATOR_PLACEHOLDERS = {
    "", "UNKNOWN", "N/A", "NA", "NONE", "NULL", "TBD", "UNASSIGNED",
    "NOT AVAILABLE", "NOT LISTED", "NOT REPORTED", "ORPHAN", "ORPHANED",
}
# Sentinel numeric depths used by several state registries to mean "no value".
_DEPTH_SENTINELS = {0.0, -1.0, -999.0, -9999.0, 99999.0, 999999.0}
_NONDIGIT_RE = re.compile(r"\D+")


def normalize_api(raw) -> Optional[str]:
    """Canonicalize a well API number to its 10-digit (state+county+well) form.

    Handles dashed ``SS-CCC-SSSSS`` and undashed inputs alike, strips any
    directional/event suffix (API-14 -> API-10), and rejects strings without a
    plausible state+county+well core. Returns ``None`` for missing/garbage.
    """
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return None
    digits = _NONDIGIT_RE.sub("", str(raw))
    if not digits:
        return None
    # API-14 carries directional sidetrack/event codes after the 10-digit core;
    # truncate to the canonical 10. Shorter strings are left-padded only when a
    # leading state-code zero was plausibly dropped (<=9 digits).
    if len(digits) >= 14:
        digits = digits[:10]
    elif len(digits) > 10:
        digits = digits[:10]
    elif len(digits) < 10:
        digits = digits.zfill(10)
    # A valid API-10 has a nonzero 2-digit state code.
    if digits[:2] == "00":
        return None
    return digits


def normalize_operator(raw) -> Optional[str]:
    """Trim/upper-case an operator name; drop placeholder/empty tokens."""
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return None
    s = " ".join(str(raw).strip().upper().split())
    if not s or s in _OPERATOR_PLACEHOLDERS:
        return None
    return s


def normalize_depth(raw) -> Optional[float]:
    """Coerce a total-depth value to numeric feet; guard 0/null/sentinels."""
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return None
    try:
        # tolerate strings like "4,200 ft" / "4200.0"
        s = str(raw).strip().lower().replace(",", "").replace("ft", "").strip()
        if not s:
            return None
        val = float(s)
    except (ValueError, TypeError):
        return None
    if val <= 0 or val in _DEPTH_SENTINELS:
        return None
    return round(val, 1)


# --- LBNL candidate id provenance ----------------------------------------
# e.g. "CA_Allensworth_287908_1954_24000_geo_16"
#       state quad        quadid year scale  _ idx
def parse_candidate_id(uid: str) -> dict:
    """Decode an LBNL ``Potential UOW id`` into quad provenance fields."""
    out = {
        "state_abbr": None,
        "quad_name": None,
        "quad_id": None,
        "quad_year": None,
        "quad_scale": None,
        "detection_index": None,
    }
    parts = str(uid).split("_")
    if len(parts) < 7:
        return out
    # tail layout: ... <quad_id> <year> <scale> "geo" <idx>
    try:
        out["detection_index"] = int(parts[-1])
    except ValueError:
        pass
    # locate the "geo" marker for robustness against multi-token quad names
    try:
        geo_i = max(i for i, p in enumerate(parts) if p.lower() == "geo")
    except ValueError:
        geo_i = len(parts) - 2
    out["quad_scale"] = parts[geo_i - 1] if geo_i - 1 >= 0 else None
    out["quad_year"] = parts[geo_i - 2] if geo_i - 2 >= 0 else None
    out["quad_id"] = parts[geo_i - 3] if geo_i - 3 >= 0 else None
    out["state_abbr"] = parts[0]
    out["quad_name"] = " ".join(parts[1:geo_i - 3]) if geo_i - 3 > 1 else None
    return out


def parse_coordinates(raw: str) -> tuple[Optional[float], Optional[float]]:
    """Parse an LBNL ``"lat,lon"`` coordinate string -> (lat, lon)."""
    try:
        lat_s, lon_s = str(raw).split(",")
        return float(lat_s), float(lon_s)
    except (ValueError, AttributeError):
        return None, None


# --- US state name <-> abbreviation --------------------------------------
STATE_ABBR = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI",
    "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
    "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}
ABBR_STATE = {v: k for k, v in STATE_ABBR.items()}
