"""Methane emission proxy for orphaned/abandoned wells — region × status × type.

This is a MODELED ESTIMATE from EPA/literature emission factors — never a
measurement. Abandoned wells emit on the order of grams/hour, far below
satellite/aircraft detection floors (tens of kg/hr), so a per-well figure can
only be an estimate with a wide, right-skewed band.

§2B rebuilds the engine to differentiate by **region × plugging status × well
type** rather than collapsing every well to one of two constants:

  - Region: EPA GHG Inventory abandoned-well regional means (Appalachia runs far
    higher than the rest of the US because of the coal-vent pathway).
  - Type: Kang et al. 2016 PNAS category means (gas >> oil), substituted as
    *absolute* emission factors (not multiplied onto the GHGI base — that would
    double-count the gas signal).
  - Status: plugged << unplugged; genuinely *unknown* status blends the two
    (0.69 unplugged / 0.31 plugged, the GHGI abandoned-well split).

Heavy right tail: Williams et al. 2021 find the top ~10% of wells (>10 g/hr)
emit ~91% of the total; regional means run higher still (N. Louisiana mean
57.4 g/hr, range 0-1368; Driscoll et al. 2025). We therefore report a
low/point/high band, with the high anchored at ~90th-percentile (not the
absolute max), not a single false-precise number.

Honesty: wells whose type AND status are both unknown (e.g. attribute-less
undocumented topo detections) cannot be differentiated and carry
``differentiated=False`` so the UI can badge them "undifferentiated estimate".
The only per-well methane signal for such wells is a nearby EPA Super-Emitter
event, surfaced via ``super_emitter`` flags.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

HOURS_PER_YEAR = 8760
# CO2-equivalence (IPCC AR5/AR6). Use GWP-100=30 for any money/credit/inventory
# math; GWP-20=84 only as a labeled "20-year urgency" sidebar.
GWP100_FOSSIL = 30
GWP20_FOSSIL = 84

# g/hr -> t CO2e/yr (GWP-100) shorthand used in the plan's worked numbers:
#   g/hr * 8760 / 1e6 (t CH4/yr) * 30 (GWP100) = g/hr * 0.2628
_T_CO2E_PER_G_HR = HOURS_PER_YEAR / 1e6 * GWP100_FOSSIL  # = 0.2628

# Region routing. Appalachia carries the GHGI coal-vent pathway; everything else
# routes to the conservative low-EF "rest_us" default.
APPALACHIA_STATES = {"OH", "PA", "WV", "NY", "KY", "TN"}

# GHGI abandoned-well status split (used to blend when status is unknown).
DEFAULT_UNKNOWN_UNPLUGGED_FRAC = 0.69

# Emission-factor point table: (region, status, type) -> g CH4/hr.
# region in {appalachia, rest_us}; status in {unplugged, plugged};
# type in {gas, oil, unknown}. One provenance comment per cell.
EF_POINT: dict[tuple[str, str, str], float] = {
    # --- Appalachia ------------------------------------------------------
    ("appalachia", "unplugged", "unknown"): 30.57,  # GHGI Appalachia unplugged mean
    ("appalachia", "plugged", "unknown"): 0.36,     # GHGI Appalachia plugged mean
    ("appalachia", "unplugged", "gas"): 75.0,       # Kang gas-unplugged-noncoal abs mean
    ("appalachia", "plugged", "gas"): 47.0,         # Kang coal-area plugged-vented gas
    ("appalachia", "unplugged", "oil"): 0.30,       # Kang oil/combined (~0.2-0.4)
    ("appalachia", "plugged", "oil"): 0.30,         # Kang oil/combined (status-insensitive)
    # --- rest of US ------------------------------------------------------
    ("rest_us", "unplugged", "unknown"): 10.02,     # GHGI rest-US unplugged mean
    ("rest_us", "plugged", "unknown"): 0.002,       # GHGI rest-US plugged mean
    ("rest_us", "unplugged", "gas"): 75.0,          # Kang gas-unplugged (national) abs mean
    # modeling choice: no coal-vent pathway outside Appalachia, so plugged gas
    # falls to a near-plugged floor rather than Appalachia's 47 g/hr vented case.
    ("rest_us", "plugged", "gas"): 0.10,            # MODELING CHOICE (no coal-vent path)
    ("rest_us", "unplugged", "oil"): 0.30,          # Kang oil/combined
    ("rest_us", "plugged", "oil"): 0.002,           # GHGI rest-US plugged floor
}

# Band multipliers around the point (heavy right tail). Tuned so the rest_us
# unplugged-unknown cell (10.02 g/hr) reproduces today's (~1, 10, ~33) shape and
# the legacy (3, 31, 100) shape for the ~31 g/hr regime; documented as
# ~90th-percentile high, NOT the absolute max (cf. N. Louisiana mean 57.4 g/hr).
BAND_LOW_MULT = 0.10
BAND_HIGH_MULT = 3.25


def _norm_region(region: str | None, state_abbr: str | None) -> str:
    """Explicit region wins; else derive from state; else conservative rest_us."""
    if region in ("appalachia", "rest_us"):
        return region
    if state_abbr and state_abbr.upper() in APPALACHIA_STATES:
        return "appalachia"
    return "rest_us"


def _norm_type(well_type: str | None) -> str:
    """Collapse source type vocab to {gas, oil, unknown}."""
    if well_type:
        t = well_type.strip().lower()
        if t in ("gas", "oil_gas", "oilgas", "oil_and_gas"):
            return "gas"
        if t in ("oil",):
            return "oil"
    return "unknown"


def _cell(region: str, status: str, type_key: str) -> float:
    """Pick a g/hr point for a fully-specified cell.

    type unknown always uses the GHGI base (region, status, "unknown"); known
    types fall back to the base if a (region, status, type) cell is absent.
    """
    if type_key == "unknown":
        return EF_POINT[(region, status, "unknown")]
    return EF_POINT.get((region, status, type_key),
                        EF_POINT[(region, status, "unknown")])


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
    # --- §2B differentiation metadata (all defaulted; back-compatible) ----
    region: str = "rest_us"
    well_type: str = "unknown"
    status_known: bool = True
    differentiated: bool = True
    super_emitter: bool | None = None
    super_emitter_dist_m: float | None = None
    super_emitter_rate_kg_hr: float | None = None
    label: str = ("modeled estimate (EPA GHGI × Kang 2016 region/status/type); "
                  "heavy right tail")

    def to_dict(self) -> dict:
        return asdict(self)


def _t_ch4(g_hr: float) -> float:
    return g_hr * HOURS_PER_YEAR / 1e6


def estimate_methane(
    plugged: bool | None = False,
    *,
    region: str | None = None,
    state_abbr: str | None = None,
    well_type: str | None = None,
    super_emitter: bool | None = None,
    super_emitter_dist_m: float | None = None,
    super_emitter_rate_kg_hr: float | None = None,
    unknown_status_unplugged_frac: float = DEFAULT_UNKNOWN_UNPLUGGED_FRAC,
) -> MethaneEstimate:
    """Region × status × type methane estimate (low/point/high band).

    ``plugged`` is positional for back-compat: ``estimate_methane(False)`` and
    ``estimate_methane(True)`` keep working. ``plugged=None`` marks status
    genuinely unknown and triggers an element-wise unplugged/plugged blend.
    """
    reg = _norm_region(region, state_abbr)
    type_key = _norm_type(well_type)

    if plugged is None:
        # Unknown status -> element-wise blend of the unplugged & plugged cells,
        # so the point lies strictly between them.
        frac = unknown_status_unplugged_frac
        up = _cell(reg, "unplugged", type_key)
        pl = _cell(reg, "plugged", type_key)
        point = frac * up + (1.0 - frac) * pl
        status_known = False
    else:
        status = "plugged" if plugged else "unplugged"
        point = _cell(reg, status, type_key)
        status_known = True

    low = point * BAND_LOW_MULT
    high = point * BAND_HIGH_MULT

    ch4_lo, ch4_pt, ch4_hi = _t_ch4(low), _t_ch4(point), _t_ch4(high)

    # Wells with neither type nor status are intrinsically undifferentiated.
    differentiated = not (type_key == "unknown" and not status_known)

    label = ("modeled estimate (EPA GHGI × Kang 2016 region/status/type); "
             "heavy right tail")
    if not differentiated:
        label += " — undifferentiated (type+status unknown)"
    if super_emitter:
        label += " — EPA super-emitter nearby"

    return MethaneEstimate(
        g_per_hr_point=round(point, 4),
        g_per_hr_low=round(low, 4),
        g_per_hr_high=round(high, 4),
        t_ch4_per_yr_point=round(ch4_pt, 4),
        t_ch4_per_yr_low=round(ch4_lo, 4),
        t_ch4_per_yr_high=round(ch4_hi, 4),
        t_co2e_gwp100_point=round(ch4_pt * GWP100_FOSSIL, 3),
        t_co2e_gwp100_low=round(ch4_lo * GWP100_FOSSIL, 3),
        t_co2e_gwp100_high=round(ch4_hi * GWP100_FOSSIL, 3),
        t_co2e_gwp20_point=round(ch4_pt * GWP20_FOSSIL, 3),
        plugged=bool(plugged) if plugged is not None else False,
        region=reg,
        well_type=type_key,
        status_known=status_known,
        differentiated=differentiated,
        super_emitter=super_emitter,
        super_emitter_dist_m=(round(super_emitter_dist_m, 1)
                              if super_emitter_dist_m is not None else None),
        super_emitter_rate_kg_hr=super_emitter_rate_kg_hr,
        label=label,
    )
