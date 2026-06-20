"""Plugging / decommissioning cost model.

Grounded in Raimi, Krupnick, Shah & Thompson (2021), Environ. Sci. Technol.
55, 10224-10230, DOI 10.1021/acs.est.1c02234, fit on ~19,500 wells:
  - median ~ $20,000 plugging only; ~ $76,000 plugging + surface reclamation
  - +20% per additional 1,000 ft of depth
  - natural-gas wells +9% vs oil
  - +3% per additional 10 ft of elevation change in the surrounding 5 acres
  - wide state variation; bulk discounts for batched programs
RFF's 2026 six-state working paper reports a newer ~$35k median (sensitivity).

Depth is absent from the USGS DOW schema and undefined for U-Net detections,
so the depth term defaults to 1.0 (flagged ``depth_known=False``) rather than
inventing a number — honest base estimate over false precision.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

BASE_PLUG_ONLY = 20_000        # Raimi median, plugging only
BASE_RECLAMATION = 76_000      # Raimi median, plugging + surface reclamation
RFF_SENSITIVITY_MEDIAN = 35_000  # RFF 2026 six-state working paper

GAS_MULTIPLIER = 1.09          # gas wells +9% vs oil
DEPTH_PER_1000FT = 1.20        # +20% per 1,000 ft
ELEV_PER_10FT = 1.03           # +3% per 10 ft elevation change


@dataclass
class PlugCostEstimate:
    plug_only_usd: int
    reclamation_usd: int      # decision-relevant figure for sites near people
    point_usd: int
    low_usd: int
    high_usd: int
    depth_known: bool
    is_gas: bool
    drivers: dict

    def to_dict(self) -> dict:
        return asdict(self)


def estimate_plug_cost(
    *,
    type_norm: str = "unknown",
    depth_ft: Optional[float] = None,
    elevation_change_ft: Optional[float] = None,
    state_cost_index: float = 1.0,
) -> PlugCostEstimate:
    """Estimate plugging cost (USD) from the Raimi 2021 cost drivers."""
    is_gas = type_norm in ("gas", "oil_gas")
    depth_factor = DEPTH_PER_1000FT ** (depth_ft / 1000.0) if depth_ft else 1.0
    elev_factor = ELEV_PER_10FT ** (elevation_change_ft / 10.0) if elevation_change_ft else 1.0
    gas_factor = GAS_MULTIPLIER if is_gas else 1.0
    mult = state_cost_index * depth_factor * elev_factor * gas_factor

    plug_only = BASE_PLUG_ONLY * mult
    reclamation = BASE_RECLAMATION * mult
    return PlugCostEstimate(
        plug_only_usd=int(round(plug_only, -2)),
        reclamation_usd=int(round(reclamation, -2)),
        point_usd=int(round(reclamation, -2)),
        low_usd=int(round(RFF_SENSITIVITY_MEDIAN * mult, -2)),
        high_usd=int(round(reclamation * 1.6, -2)),  # upper band within observed spread
        depth_known=depth_ft is not None,
        is_gas=is_gas,
        drivers={
            "base_reclamation_usd": BASE_RECLAMATION,
            "state_cost_index": round(state_cost_index, 3),
            "depth_factor": round(depth_factor, 3),
            "elevation_factor": round(elev_factor, 3),
            "gas_factor": gas_factor,
        },
    )
