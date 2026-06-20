"""Carbon-credit 'self-funding' kicker — secondary, clearly labeled.

Methodology: ACR (American Carbon Registry) Orphaned Well Methodology (2023);
credits = avoided methane (GWP-100) over a crediting period, minus the ACR
buffer-pool deduction, subject to additionality.

Reality check (be honest): at a point ~0.27 t CH4/yr x GWP-100 30 ~ 8 t CO2e/yr,
even a 10-year crediting period (~80 t CO2e) at ~$15/t is ~$1,200/well — far
below the ~$76k plug cost. Credits only pencil for the rare deep, high-rate gas
wells in the right tail. First real transaction: Zefiro Methane Corp ACR959,
92,956 t CO2e (Custer County, OK), delivered to Mercuria/EDF Trading, Aug 2025.

Voluntary-market prices are volatile and two-tier; we model a $10-$30/t range
(Grist expert estimate) rather than a point.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

ACR_BUFFER_POOL = 0.15        # buffer-pool deduction (illustrative within ACR range)
CREDITING_PERIOD_YEARS = 10
PRICE_LOW = 10.0              # $/t CO2e (orphan-well voluntary market)
PRICE_POINT = 15.0
PRICE_HIGH = 30.0


@dataclass
class CarbonKicker:
    creditable_tonnes: float
    value_low_usd: int
    value_point_usd: int
    value_high_usd: int
    self_funding_ratio_point: float   # value / plug cost (usually << 1)
    pencils_out: bool                 # value_high >= plug cost?
    buffer_pool: float = ACR_BUFFER_POOL
    crediting_period_years: int = CREDITING_PERIOD_YEARS
    label: str = "ACR orphan-well methodology, GWP-100; nascent two-tier market"

    def to_dict(self) -> dict:
        return asdict(self)


def carbon_kicker(t_co2e_gwp100_per_yr: float, plug_cost_usd: float) -> CarbonKicker:
    """Estimate lifetime credit value vs plug cost for one well."""
    tonnes = t_co2e_gwp100_per_yr * CREDITING_PERIOD_YEARS * (1 - ACR_BUFFER_POOL)
    v_lo = tonnes * PRICE_LOW
    v_pt = tonnes * PRICE_POINT
    v_hi = tonnes * PRICE_HIGH
    return CarbonKicker(
        creditable_tonnes=round(tonnes, 2),
        value_low_usd=int(round(v_lo)),
        value_point_usd=int(round(v_pt)),
        value_high_usd=int(round(v_hi)),
        self_funding_ratio_point=round(v_pt / plug_cost_usd, 4) if plug_cost_usd else 0.0,
        pencils_out=bool(v_hi >= plug_cost_usd),
    )
