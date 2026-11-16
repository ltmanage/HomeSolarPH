"""Calculation engine tests. The golden case is worked out by hand in the comments."""
import pytest

from homesolar.calc.solar import estimate, monthly_yield, payback, round_half
from homesolar.config import defaults, region_map, regions
from homesolar.models import Overrides, SolarInput


def base(**kw) -> SolarInput:
    d = dict(region="NCR", provider="meralco", bill_php=9000, kwh_month=600, daytime="mixed",
             direction="south", shading="none", net_metering="yes")
    d.update(kw)
    return SolarInput(**d)


def test_data_files_structure():
    r = regions()
    assert len(r["regions"]) == 18 and r["source"] and r["generated"]
    for reg in r["regions"]:
        for d in ("south", "east", "west", "north", "flat"):
            vals = reg["yield_kwh_per_kwp"][d]
            assert len(vals) == 12
            assert 1000 < sum(vals) < 1800, (reg["code"], d)
    d = defaults()
    assert d["as_of"] and d["cost_per_kwp_php"]["low"] < d["cost_per_kwp_php"]["high"]


def test_golden_case():
    # NCR south, 600 kWh at PHP 15/kWh, mixed use (50% daytime), net metering.
    y = sum(monthly_yield("NCR", "south", "none"))
    e = estimate(base())
    assert e.rate_per_kwh == 15.0
    # size range: daytime 0.5*7200/y .. full 7200/y, rounded down to 0.5
    assert e.size_low_kwp == round_half(0.5 * 7200 / y)
    assert e.size_high_kwp == round_half(7200 / y)
    assert e.size_kwp == 4.0
    # every month 4 kWp produces more than the 300 kWh daytime use, so self-use = 300 x 12
    assert sum(e.monthly_self_kwh) == pytest.approx(3600, abs=1)
    exported = 4 * y - 3600
    expected = 3600 * 15 * 0.95 + exported * 8.0
    first_year = estimate(base(overrides=Overrides(size_kwp=4)))
    # optimistic case uses 1.05x output; conservative 0.9x output
    assert e.yearly_gen_kwh == pytest.approx(4 * y, abs=1)
    assert first_year.optimistic.cost_php == 4 * 44000
    assert first_year.conservative.cost_php == 4 * 60000
    # base-case saving lies between the two cases
    assert e.conservative.yearly_savings_php <= expected <= e.optimistic.yearly_savings_php
    assert e.verdict == "strong"


def test_payback_simple():
    pb, net = payback(100000, 25000, 0.0, 0)
    assert 4.0 <= pb <= 4.1   # degradation adds a little
    assert net > 0
    assert payback(100000, 1000, 0.0, 0)[0] is None


def test_kwh_estimated_from_bill():
    e = estimate(base(kwh_month=None))
    assert e.kwh_estimated and e.kwh_month == pytest.approx(9000 / 15.06, abs=0.1)
    assert any("estimated" in w for w in e.warnings)


def test_no_net_metering_smaller_and_no_export_value():
    with_nm, without = estimate(base()), estimate(base(net_metering="no"))
    assert without.size_high_kwp <= with_nm.size_high_kwp
    assert without.optimistic.yearly_savings_php < with_nm.optimistic.yearly_savings_php


def test_roof_and_budget_caps():
    e = estimate(base(roof_area_m2=13))   # 13 / 6.5 = 2 kWp
    assert e.size_high_kwp == 2.0 and e.limited_by == "roof"
    e = estimate(base(budget_php=120000))  # 120000 / 60000 = 2 kWp
    assert e.size_high_kwp == 2.0 and e.limited_by == "budget"


@pytest.mark.parametrize("region", list(region_map()))
def test_properties_all_regions(region):
    for daytime in ("evening", "mixed", "daytime"):
        e = estimate(base(region=region, daytime=daytime, direction="unsure", shading="unsure"))
        assert e.conservative.yearly_savings_php >= 0
        assert e.optimistic.yearly_savings_php >= e.conservative.yearly_savings_php
        if e.conservative.payback_years is not None:
            assert e.optimistic.payback_years <= e.conservative.payback_years
        assert e.size_low_kwp <= e.size_kwp <= e.size_high_kwp
        assert e.bill_after_php <= e.bill_before_php


def test_bigger_system_more_generation():
    small = estimate(base(overrides=Overrides(size_kwp=3)))
    big = estimate(base(overrides=Overrides(size_kwp=6)))
    assert big.yearly_gen_kwh > small.yearly_gen_kwh
    assert big.limited_by == "user"


def test_shading_reduces_output():
    assert estimate(base(shading="heavy")).yearly_gen_kwh < estimate(base(shading="none")).yearly_gen_kwh


def test_unknown_region_rejected():
    with pytest.raises(ValueError):
        estimate(base(region="ZZ"))
