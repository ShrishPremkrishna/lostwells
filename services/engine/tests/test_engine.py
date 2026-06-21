"""Unit tests for the Lost Wells ranking engine + ingest normalizers."""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))  # services/engine
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(_HERE)), "ingest"))

from methane import estimate_methane, GWP100_FOSSIL, GWP20_FOSSIL  # noqa: E402
from plugcost import estimate_plug_cost, BASE_RECLAMATION  # noqa: E402
from carbon import carbon_kicker  # noqa: E402
import scoring  # noqa: E402
import normalize as N  # noqa: E402


# --- methane --------------------------------------------------------------
def test_unplugged_emits_far_more_than_plugged():
    up = estimate_methane(plugged=False)
    pl = estimate_methane(plugged=True)
    assert up.g_per_hr_point > pl.g_per_hr_point * 50
    assert up.t_co2e_gwp100_point > pl.t_co2e_gwp100_point


def test_methane_conversion_and_gwp():
    # §2B re-pin: legacy 31 g/hr was the old single unplugged constant. Pin to an
    # explicit cell — rest_us (CA) / unplugged / unknown = 10.02 g/hr.
    m = estimate_methane(plugged=False, state_abbr="CA", well_type="unknown")
    # 10.02 g/hr * 8760 / 1e6 ~= 0.0878 t CH4/yr
    assert m.t_ch4_per_yr_point == pytest.approx(0.0878, abs=1e-3)
    assert m.t_co2e_gwp100_point == pytest.approx(m.t_ch4_per_yr_point * GWP100_FOSSIL, abs=0.01)
    assert m.t_co2e_gwp20_point > m.t_co2e_gwp100_point          # 20-yr urgency higher
    assert GWP20_FOSSIL > GWP100_FOSSIL


def test_methane_band_ordering():
    m = estimate_methane(plugged=False)
    assert m.g_per_hr_low < m.g_per_hr_point < m.g_per_hr_high


# --- §2B region × status × type differentiation ---------------------------
def test_region_differentiation_appalachia_higher_than_rest_us():
    pa = estimate_methane(plugged=False, state_abbr="PA", well_type="unknown")
    ca = estimate_methane(plugged=False, state_abbr="CA", well_type="unknown")
    assert pa.g_per_hr_point == pytest.approx(30.57)
    assert ca.g_per_hr_point == pytest.approx(10.02)
    assert pa.g_per_hr_point > ca.g_per_hr_point
    assert pa.region == "appalachia" and ca.region == "rest_us"


def test_type_differentiation_gas_higher_than_oil():
    gas = estimate_methane(plugged=False, state_abbr="CA", well_type="gas")
    oil = estimate_methane(plugged=False, state_abbr="CA", well_type="oil")
    assert gas.g_per_hr_point == pytest.approx(75.0)
    assert oil.g_per_hr_point == pytest.approx(0.30)
    assert gas.g_per_hr_point > oil.g_per_hr_point


def test_unknown_status_blends_between_plugged_and_unplugged():
    up = estimate_methane(plugged=False, state_abbr="CA", well_type="unknown")
    pl = estimate_methane(plugged=True, state_abbr="CA", well_type="unknown")
    blend = estimate_methane(plugged=None, state_abbr="CA", well_type="unknown")
    assert pl.g_per_hr_point < blend.g_per_hr_point < up.g_per_hr_point
    assert blend.status_known is False
    # 0.69*10.02 + 0.31*0.002 = 6.9144 g/hr -> ~1.82 t CO2e/yr
    assert blend.g_per_hr_point == pytest.approx(6.9144, abs=1e-3)
    assert blend.t_co2e_gwp100_point == pytest.approx(1.817, abs=0.02)


def test_differentiated_flag():
    # CA / status-unknown / type-unknown -> undifferentiated
    undiff = estimate_methane(plugged=None, state_abbr="CA", well_type="unknown")
    assert undiff.differentiated is False
    # PA / unplugged / gas -> differentiated
    diff = estimate_methane(plugged=False, state_abbr="PA", well_type="gas")
    assert diff.differentiated is True
    # known status but unknown type is still differentiated (status is a signal)
    known_status = estimate_methane(plugged=False, state_abbr="CA", well_type="unknown")
    assert known_status.differentiated is True


def test_band_ordering_over_all_cells():
    from methane import EF_POINT
    seen_regions = {r for (r, _s, _t) in EF_POINT}
    for region in seen_regions:
        for type_key in ("gas", "oil", "unknown"):
            for plugged in (False, True, None):
                m = estimate_methane(plugged=plugged, region=region, well_type=type_key)
                assert m.g_per_hr_low < m.g_per_hr_point < m.g_per_hr_high
                assert m.t_co2e_gwp100_low < m.t_co2e_gwp100_point < m.t_co2e_gwp100_high


def test_legacy_positional_call_still_works():
    up = estimate_methane(False)
    pl = estimate_methane(True)
    assert up.g_per_hr_point > pl.g_per_hr_point


# --- §2B super-emitter spatial join --------------------------------------
def test_super_emitter_join_sets_flag_by_distance():
    pytest.importorskip("geopandas")
    import geopandas as gpd  # noqa: E402
    import super_emitter as SE  # noqa: E402

    # One event; one well ~500 m away (True), one far away (False). Use a
    # local UTM-ish projection by working directly in the metric CRS via points.
    events = gpd.GeoDataFrame(
        {"emission_rate_kg_hr": [250.0], "operator": ["ACME"]},
        geometry=gpd.points_from_xy([-119.0], [35.0]), crs="EPSG:4326",
    ).to_crs(SE.METRIC_CRS)
    # Build wells in metric CRS: near = event + 500 m east; far = + 50 km.
    ex, ey = events.geometry.iloc[0].x, events.geometry.iloc[0].y
    from shapely.geometry import Point  # noqa: E402
    wells = gpd.GeoDataFrame(
        {"well_id": ["near", "far"]},
        geometry=[Point(ex + 500, ey), Point(ex + 50000, ey)],
        crs=SE.METRIC_CRS,
    )
    out = SE.match_wells(wells, events, radius_m=2000)
    assert out["near"]["super_emitter"] is True
    assert out["near"]["super_emitter_dist_m"] == pytest.approx(500, abs=1)
    assert out["far"]["super_emitter"] is False


def test_build_record_uses_high_anchor_when_super_emitter():
    import score_candidates as SC  # noqa: E402
    base = {
        "well_id": "w1", "state_abbr": "CA", "type_norm": "unknown",
        "status_norm": "undocumented", "is_plugged": False,
    }
    flagged = SC.build_record(base, None, {"super_emitter": True,
                                           "super_emitter_dist_m": 500.0})
    unflagged = SC.build_record(base, None, {"super_emitter": False})
    assert flagged["metrics"]["methane"] == flagged["methane"]["t_co2e_gwp100_high"]
    assert unflagged["metrics"]["methane"] == unflagged["methane"]["t_co2e_gwp100_point"]
    assert flagged["metrics"]["methane"] > unflagged["metrics"]["methane"]
    # undocumented candidate -> status-unknown blend -> undifferentiated badge
    assert unflagged["methane"]["differentiated"] is False
    assert unflagged["methane"]["status_known"] is False


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


def test_drinking_water_and_hospitals_become_present_when_supplied():
    # Two wells differing in drinking_water + hospitals; both should appear in
    # present_metrics once supplied (they were renormalized out before §2A).
    recs = [
        _rec(id="a", population=100, drinking_water=0.9, hospitals=3, methane=8.0,
             plug_cost=76000, program_match=1.0),
        _rec(id="b", population=10, drinking_water=0.1, hospitals=0, methane=8.0,
             plug_cost=76000, program_match=1.0),
    ]
    scoring.score_set(recs)
    for r in recs:
        assert "drinking_water" in r["score"]["present_metrics"]
        assert "hospitals" in r["score"]["present_metrics"]


# --- ingest: state-registry normalizers ----------------------------------
def test_normalize_api_handles_dashes_and_truncation():
    assert N.normalize_api("34-019-20162") == "3401920162"      # dashed -> 10
    assert N.normalize_api("3401920162") == "3401920162"        # already 10
    assert N.normalize_api("34019201620000") == "3401920162"    # API-14 -> 10
    assert N.normalize_api("4-019-20162") == "0401920162"       # zero-padded
    assert N.normalize_api("00-000-00000") is None              # bad state code
    assert N.normalize_api(None) is None
    assert N.normalize_api("n/a") is None


def test_normalize_operator_drops_placeholders():
    assert N.normalize_operator("  acme oil co ") == "ACME OIL CO"
    assert N.normalize_operator("unknown") is None
    assert N.normalize_operator("N/A") is None
    assert N.normalize_operator("") is None
    assert N.normalize_operator(None) is None


def test_normalize_depth_guards_sentinels():
    assert N.normalize_depth("4,200 ft") == 4200.0
    assert N.normalize_depth(3150) == 3150.0
    assert N.normalize_depth(0) is None
    assert N.normalize_depth(-999) is None
    assert N.normalize_depth(None) is None
    assert N.normalize_depth("garbage") is None


def test_state_status_vocab_extensions():
    assert N.classify_status("DV") == N.STATUS_ABANDONED       # dry & abandoned
    assert N.classify_status("TA") == N.STATUS_IDLE            # temp abandoned
    assert N.classify_status("Inactive") == N.STATUS_IDLE
    # plugged still wins ordering
    assert N.classify_status("Plugged & Abandoned") == N.STATUS_PLUGGED


# --- ingest: tract PIP ----------------------------------------------------
def test_resolve_tracts_assigns_geoid_via_pip():
    pytest.importorskip("geopandas")
    import geopandas as gpd  # noqa: E402
    from shapely.geometry import Polygon  # noqa: E402
    import pandas as pd  # noqa: E402
    import tracts as T  # noqa: E402

    # One unit square tract; one point inside, one outside.
    poly = gpd.GeoDataFrame(
        {"GEOID": ["39000000100"]},
        geometry=[Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])],
        crs="EPSG:4326",
    )
    monkey = T.load_polygons
    T.load_polygons = lambda states, kind="tract": poly  # type: ignore
    try:
        wells = pd.DataFrame({
            "well_id": ["in", "out"],
            "lat": [0.5, 5.0], "lon": [0.5, 5.0],
            "state_abbr": ["OH", "OH"],
        })
        res = T.resolve_tracts(wells, ["OH"], kind="tract")
    finally:
        T.load_polygons = monkey
    got = dict(zip(res["well_id"], res["tract_geoid"]))
    assert got["in"] == "39000000100"
    assert got["out"] is None or pd.isna(got["out"])
