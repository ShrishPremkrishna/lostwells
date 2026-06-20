"""Methane emission proxy for orphaned/abandoned wells.

This is a MODELED ESTIMATE from EPA/literature emission factors — never a
measurement. Abandoned wells emit on the order of grams/hour, far below
satellite/aircraft detection floors (tens of kg/hr), so a per-well figure can
only be an estimate with a wide, right-skewed band.

Emission factors (g CH4 / hr / well):
  - unplugged point ~31 g/hr, plugged point ~0.4 g/hr
    (project-established figures consistent with Kang et al. 2016 PNAS;
     Townsend-Small et al. 2016 GRL; EPA GHG Inventory abandoned-wells method).
  - Heavy right tail: Williams et al. 2021 find the top ~10% of wells
    (>10 g/hr) emit ~91% of the total; regional means run higher
    (N. Louisiana mean 57.4 g/hr, range 0-1368; Driscoll et al. 2025).
We therefore report a low/point/high band, not a single false-precise number.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

HOURS_PER_YEAR = 8760
# CO2-equivalence (IPCC AR5/AR6). Use GWP-100=30 for any money/credit/inventory
# math; GWP-20=84 only as a labeled "20-year urgency" sidebar.
GWP100_FOSSIL = 30
GWP20_FOSSIL = 84

# g/hr anchors by plugging status: (low, point, high)
EF_UNPLUGGED = (3.0, 31.0, 100.0)
EF_PLUGGED = (0.05, 0.4, 2.0)


@dataclass
class MethaneEstimate:
    g_per_hr_point: float
    g_per_hr_low: float
    g_per_hr_high: float
    t_ch4_per_yr_point: float
    t_ch4_per_yr_low: float
    t_ch4_per_yr_high: float
    t_co2e_gwp100_point: float
    t_co2e_gwp100_low: float
    t_co2e_gwp100_high: float
    t_co2e_gwp20_point: float
    plugged: bool
    label: str = "modeled estimate (EPA/Kang emission factors); heavy right tail"

    def to_dict(self) -> dict:
        return asdict(self)


def _t_ch4(g_hr: float) -> float:
    return g_hr * HOURS_PER_YEAR / 1e6


def estimate_methane(plugged: bool) -> MethaneEstimate:
    """Return a low/point/high methane estimate for a well by plugging status."""
    low, point, high = EF_PLUGGED if plugged else EF_UNPLUGGED
    ch4_lo, ch4_pt, ch4_hi = _t_ch4(low), _t_ch4(point), _t_ch4(high)
    return MethaneEstimate(
        g_per_hr_point=point, g_per_hr_low=low, g_per_hr_high=high,
        t_ch4_per_yr_point=round(ch4_pt, 4),
        t_ch4_per_yr_low=round(ch4_lo, 4),
        t_ch4_per_yr_high=round(ch4_hi, 4),
        t_co2e_gwp100_point=round(ch4_pt * GWP100_FOSSIL, 3),
        t_co2e_gwp100_low=round(ch4_lo * GWP100_FOSSIL, 3),
        t_co2e_gwp100_high=round(ch4_hi * GWP100_FOSSIL, 3),
        t_co2e_gwp20_point=round(ch4_pt * GWP20_FOSSIL, 3),
        plugged=plugged,
    )
