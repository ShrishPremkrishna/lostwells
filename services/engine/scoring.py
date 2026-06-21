"""Transparent composite impact score (0-100).

Design goals (spec §4.4): explainable, adjustable, honest about missing data.
Each sub-metric is normalized to 0-1 by **percentile rank across the candidate
set** (robust to the heavy right tails in this domain), then combined with
transparent, user-adjustable weights. The per-well breakdown sums exactly to
the composite so a judge can see *why* a well ranks where it does.

Missing data is handled by renormalizing over the metrics actually present for
that well (and recorded), rather than silently imputing zeros.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

# weight key -> (raw field in record['metrics'], normalization mode)
#   pct      : percentile-rank across set, higher raw = higher score
#   pct_inv  : percentile-rank then invert (lower raw = higher score)
#   direct   : value already in 0-1, used as-is
METRIC_CONFIG = {
    "population":       ("population", "pct"),
    "schools":          ("schools", "pct"),
    "hospitals":        ("hospitals", "pct"),
    "drinking_water":   ("drinking_water", "pct"),
    "svi":              ("svi", "pct"),
    "ej":               ("ej", "pct"),
    "methane":          ("methane", "pct"),
    "fundability_cost": ("plug_cost", "pct_inv"),
    "program_match":    ("program_match", "direct"),
}

# Phase 5 rebalance: with SVI + schools + EJ now at near-full coverage across all
# ~38k wells, the near-constant program_match (≈1.0 for every well) was diluting
# the real signal, so it is halved; the freed weight flows to the mission-core
# climate (methane), equity (ej), and the genuinely discriminating plug cost.
# Sum = 1.00. Groups: human_exposure 0.44 / equity 0.22 / methane 0.17 / fundability 0.17.
DEFAULT_WEIGHTS = {
    "population": 0.15, "schools": 0.12, "hospitals": 0.05, "drinking_water": 0.12,
    "svi": 0.12, "ej": 0.10,
    "methane": 0.17,
    "fundability_cost": 0.12, "program_match": 0.05,
}

GROUPS = {
    "human_exposure": ["population", "schools", "hospitals", "drinking_water"],
    "equity": ["svi", "ej"],
    "methane": ["methane"],
    "fundability": ["fundability_cost", "program_match"],
}

METRIC_LABELS = {
    "population": "Population within 1 mi",
    "schools": "Schools within 1 mi",
    "hospitals": "Hospitals / sensitive sites",
    "drinking_water": "Drinking-water service area",
    "svi": "Social Vulnerability (SVI)",
    "ej": "EJ burden (CEJST/EJI)",
    "methane": "Methane proxy (modeled)",
    "fundability_cost": "Low plug cost (tractable)",
    "program_match": "Funding-program match",
}


def _normalized_columns(records: list[dict], weights: dict) -> dict[str, list[Optional[float]]]:
    """Compute the 0-1 normalized column for every weighted metric."""
    norms: dict[str, list[Optional[float]]] = {}
    for key in weights:
        raw_field, mode = METRIC_CONFIG[key]
        raw = [r.get("metrics", {}).get(raw_field) for r in records]
        if mode == "direct":
            norms[key] = [None if v is None else max(0.0, min(1.0, float(v))) for v in raw]
            continue
        s = pd.Series(raw, dtype="float64")
        pct = s.rank(pct=True)
        if mode == "pct_inv":
            pct = 1.0 - pct
        norms[key] = [None if pd.isna(v) else round(float(v), 4) for v in pct]
    return norms


def score_set(records: list[dict], weights: Optional[dict] = None) -> list[dict]:
    """Attach a ``score`` block to each record. Mutates and returns ``records``."""
    weights = weights or DEFAULT_WEIGHTS
    norms = _normalized_columns(records, weights)

    for i, rec in enumerate(records):
        present, contrib = {}, {}
        for key, w in weights.items():
            nv = norms[key][i]
            if nv is not None:
                present[key] = (w, nv)
        wsum = sum(w for w, _ in present.values()) or 1.0
        composite = sum(w * nv for w, nv in present.values()) / wsum * 100.0
        for key, (w, nv) in present.items():
            contrib[key] = round(w * nv / wsum * 100.0, 2)
        group_breakdown = {
            g: round(sum(contrib.get(k, 0.0) for k in ks), 2) for g, ks in GROUPS.items()
        }
        rec["score"] = {
            "composite": round(composite, 1),
            "breakdown": contrib,                       # sums to composite
            "group_breakdown": group_breakdown,
            "normalized": {k: norms[k][i] for k in weights},
            "present_metrics": list(present.keys()),
            "missing_metrics": [k for k in weights if k not in present],
            "weights": weights,
        }
    return records


def program_match_score(state_abbr: Optional[str]) -> float:
    """Eligibility for the federal (BIL) orphaned-well program, 0-1.

    All states in the USGS DOW + the LBNL detection regions participate in the
    $4.7B BIL formula/grant program, so eligibility is ~1.0; we keep this as a
    hook for future state-program nuance (match rates, set-asides).
    """
    return 1.0 if state_abbr else 0.5
