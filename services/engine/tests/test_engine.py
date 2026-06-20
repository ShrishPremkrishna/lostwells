"""Unit tests for the Lost Wells ranking engine."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from methane import estimate_methane, GWP100_FOSSIL, GWP20_FOSSIL  # noqa: E402
from plugcost import estimate_plug_cost, BASE_RECLAMATION  # noqa: E402
from carbon import carbon_kicker  # noqa: E402
import scoring  # noqa: E402


# --- methane --------------------------------------------------------------
def test_unplugged_emits_far_more_than_plugged():
    up = estimate_methane(plugged=False)
    pl = estimate_methane(plugged=True)
    assert up.g_per_hr_point > pl.g_per_hr_point * 50
    assert up.t_co2e_gwp100_point > pl.t_co2e_gwp100_point


def test_methane_conversion_and_gwp():
    m = estimate_methane(plugged=False)
    # 31 g/hr * 8760 / 1e6 ~= 0.2716 t CH4/yr
    assert m.t_ch4_per_yr_point == pytest.approx(0.2716, abs=1e-3)
    assert m.t_co2e_gwp100_point == pytest.approx(m.t_ch4_per_yr_point * GWP100_FOSSIL, abs=0.01)
    assert m.t_co2e_gwp20_point > m.t_co2e_gwp100_point          # 20-yr urgency higher
    assert GWP20_FOSSIL > GWP100_FOSSIL


def test_methane_band_ordering():
    m = estimate_methane(plugged=False)
    assert m.g_per_hr_low < m.g_per_hr_point < m.g_per_hr_high


# --- plug cost ------------------------------------------------------------
def test_gas_costs_more_than_oil():
    gas = estimate_plug_cost(type_norm="gas")
    oil = estimate_plug_cost(type_norm="oil")
    assert gas.point_usd > oil.point_usd
    assert gas.point_usd == pytest.approx(oil.point_usd * 1.09, rel=1e-3)


def test_depth_increases_cost_and_sets_flag():
    shallow = estimate_plug_cost(type_norm="oil", depth_ft=None)
    deep = estimate_plug_cost(type_norm="oil", depth_ft=5000)
    assert deep.point_usd > shallow.point_usd
    assert deep.depth_known is True
    assert shallow.depth_known is False


def test_reclamation_exceeds_plug_only():
    c = estimate_plug_cost(type_norm="oil")
    assert c.reclamation_usd > c.plug_only_usd
    assert c.reclamation_usd == pytest.approx(BASE_RECLAMATION, rel=0.01)


# --- carbon ---------------------------------------------------------------
def test_carbon_rarely_pencils_for_typical_well():
    m = estimate_methane(plugged=False)
    plug = estimate_plug_cost(type_norm="oil")
    k = carbon_kicker(m.t_co2e_gwp100_point, plug.point_usd)
    assert k.self_funding_ratio_point < 0.5      # far below 1.0 for a typical well
    assert k.pencils_out is False
    assert k.creditable_tonnes > 0


# --- composite scoring ----------------------------------------------------
def _rec(**metrics):
    return {"well_id": metrics.pop("id", "w"), "metrics": metrics}


def test_breakdown_sums_to_composite():
    recs = [
        _rec(id="a", population=100, schools=2, hospitals=1, drinking_water=0.8,
             svi=0.9, ej=0.7, methane=8.0, plug_cost=76000, program_match=1.0),
        _rec(id="b", population=10, schools=0, hospitals=0, drinking_water=0.1,
             svi=0.2, ej=0.1, methane=8.0, plug_cost=76000, program_match=1.0),
    ]
    scoring.score_set(recs)
    for r in recs:
        assert 0 <= r["score"]["composite"] <= 100
        assert sum(r["score"]["breakdown"].values()) == pytest.approx(
            r["score"]["composite"], abs=0.1)


def test_higher_exposure_scores_higher():
    recs = [
        _rec(id="hi", population=1000, schools=5, hospitals=2, drinking_water=0.9,
             svi=0.95, ej=0.9, methane=8.0, plug_cost=76000, program_match=1.0),
        _rec(id="lo", population=1, schools=0, hospitals=0, drinking_water=0.0,
             svi=0.05, ej=0.05, methane=8.0, plug_cost=76000, program_match=1.0),
    ]
    scoring.score_set(recs)
    hi = next(r for r in recs if r["well_id"] == "hi")
    lo = next(r for r in recs if r["well_id"] == "lo")
    assert hi["score"]["composite"] > lo["score"]["composite"]


def test_lower_plug_cost_is_more_fundable():
    recs = [
        _rec(id="cheap", population=10, plug_cost=20000, program_match=1.0),
        _rec(id="pricey", population=10, plug_cost=500000, program_match=1.0),
    ]
    scoring.score_set(recs)
    cheap = next(r for r in recs if r["well_id"] == "cheap")
    pricey = next(r for r in recs if r["well_id"] == "pricey")
    assert cheap["score"]["normalized"]["fundability_cost"] > \
        pricey["score"]["normalized"]["fundability_cost"]


def test_missing_metrics_are_renormalized_not_zeroed():
    # only methane present -> composite should equal that metric's normalized*100
    recs = [_rec(id="x", methane=8.0), _rec(id="y", methane=4.0)]
    scoring.score_set(recs)
    for r in recs:
        assert r["score"]["present_metrics"] == ["methane"]
        assert set(r["score"]["missing_metrics"]) == set(scoring.DEFAULT_WEIGHTS) - {"methane"}
        assert 0 <= r["score"]["composite"] <= 100
