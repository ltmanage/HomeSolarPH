"""Solar check: sizing, generation, savings and payback. Pure functions, no I/O beyond data files."""
from __future__ import annotations

from ..config import defaults, region_map
from ..models import Assumption, Case, SolarEstimate, SolarInput

YEARS = 25


def round_half(x: float) -> float:
    """Round down to the nearest 0.5 kWp, minimum 1."""
    return max(1.0, int(x * 2) / 2)


def monthly_yield(region: str, direction: str, shading: str) -> list[float]:
    """kWh per kWp for each month, after shading."""
    regions = region_map()
    if region not in regions:
        raise ValueError(f"Unknown region: {region}")
    y = regions[region]["yield_kwh_per_kwp"]
    if direction == "unsure":
        dirs = ["south", "east", "west", "flat"]
        base = [sum(y[d][m] for d in dirs) / len(dirs) for m in range(12)]
    else:
        base = y[direction]
    f = defaults()["shading_factor"]["values"][shading]
    return [v * f for v in base]


def payback(cost: float, first_year_saving: float, escalation: float, inverter_cost: float) -> tuple[float | None, float]:
    """Return (payback years, interpolated; None if beyond 25 years) and 25-year net savings."""
    d = defaults()
    deg = d["degradation"]["value"]
    inv_year = d["inverter_replacement"]["year"]
    cum, pb = -cost, None
    for y in range(1, YEARS + 1):
        s = first_year_saving * (1 + escalation) ** (y - 1) * (1 - deg) ** (y - 1)
        if y == inv_year:
            s -= inverter_cost
        prev = cum
        cum += s
        if pb is None and cum >= 0 and s > 0:
            pb = round(y - 1 + (-prev) / s, 1)
    return pb, round(cum)


def estimate(inp: SolarInput) -> SolarEstimate:
    d = defaults()
    o = inp.overrides
    warnings: list[str] = []
    region = region_map()[inp.region] if inp.region in region_map() else None
    if region is None:
        raise ValueError(f"Unknown region: {inp.region}")

    # --- usage and rate ---
    default_rate = d["rate_per_kwh"]["values"][inp.provider]
    if inp.kwh_month:
        kwh, kwh_est = inp.kwh_month, False
        rate = inp.bill_php / inp.kwh_month
        if not 5 <= rate <= 40:
            warnings.append(f"Your bill and kWh give PHP {rate:.2f} per kWh, which is unusual. Please check both figures.")
    else:
        rate, kwh_est = default_rate, True
        kwh = inp.bill_php / rate
        warnings.append(f"Monthly kWh was estimated from your bill at PHP {rate:.2f} per kWh. Enter the kWh from your bill for a better estimate.")
    if o.rate_per_kwh:
        rate = o.rate_per_kwh
    share = o.self_use_share or d["self_use_share"]["values"][inp.daytime]
    net = inp.net_metering != "no"
    credit = (o.export_credit_per_kwh if o.export_credit_per_kwh is not None
              else d["export_credit_per_kwh"]["values"][inp.provider]) if net else 0.0
    if inp.net_metering == "unsure":
        warnings.append("Figures assume you apply for net metering, so extra solar power sent to the grid earns bill credits.")
    cost_lo = o.cost_low or d["cost_per_kwp_php"]["low"]
    cost_hi = o.cost_high or d["cost_per_kwp_php"]["high"]
    if cost_lo > cost_hi:
        cost_lo, cost_hi = cost_hi, cost_lo
    esc_lo = d["tariff_escalation"]["low"] if o.escalation_low is None else o.escalation_low
    esc_hi = d["tariff_escalation"]["high"] if o.escalation_high is None else o.escalation_high

    # --- sizing ---
    Y = monthly_yield(inp.region, inp.direction, inp.shading)
    y_year = sum(Y)
    s_full = kwh * 12 / y_year
    s_day = share * kwh * 12 / y_year
    lo, hi = (s_day, s_full) if net else (0.8 * s_day, s_day)
    limited_by = "usage"
    caps = {}
    if inp.roof_area_m2:
        caps["roof"] = inp.roof_area_m2 / d["m2_per_kwp"]["value"]
    if inp.budget_php:
        caps["budget"] = inp.budget_php / cost_hi
    if caps:
        which = min(caps, key=caps.get)
        if caps[which] < hi:
            hi, limited_by = caps[which], which
            lo = min(lo, hi)
    size_lo, size_hi = round_half(lo), round_half(hi)
    size_lo = min(size_lo, size_hi)
    size = round_half((size_lo + size_hi) / 2 + 0.25)   # midpoint, rounded to nearest 0.5
    size = min(max(size, size_lo), size_hi)
    if o.size_kwp:
        size, limited_by = o.size_kwp, "user"
    if limited_by == "roof":
        warnings.append("Your roof area limits the system size below what your usage could support.")
    if limited_by == "budget":
        warnings.append("Your budget limits the system size below what your usage could support.")
    if inp.shading == "heavy":
        warnings.append("Heavy shading greatly reduces output. Ask installers for a shading assessment before deciding.")
    if inp.direction == "north":
        warnings.append("North-facing roofs produce a little less in the Philippines; the estimate allows for this.")

    # --- energy and savings ---
    avoid = d["avoidable_share"]["value"]
    fixed = d["fixed_charges_php"]["value"]
    bill_before = kwh * rate

    def year_one(yield_factor: float):
        gen = [size * v * yield_factor for v in Y]
        self_ = [min(g, share * kwh) for g in gen]
        exp = [g - s for g, s in zip(gen, self_, strict=True)]
        saving = sum(s * rate * avoid + e * credit for s, e in zip(self_, exp, strict=True))
        cap = max(0.0, 12 * (bill_before - fixed))
        return gen, self_, exp, min(saving, cap)

    gen, self_, exp, base_saving = year_one(1.0)
    inv_share = d["inverter_replacement"]["share_of_cost"]

    def case(yield_factor, cost_per_kw, esc) -> Case:
        sav = year_one(yield_factor)[3]
        cost = size * cost_per_kw
        pb, net25 = payback(cost, sav, esc, cost * inv_share)
        return Case(cost_php=round(cost), yearly_savings_php=round(sav), payback_years=pb, net_25y_php=net25)

    yc = d["yield_case"]
    opt = case(yc["optimistic"], cost_lo, esc_hi)
    con = case(yc["conservative"], cost_hi, esc_lo)
    vb = d["verdict_bands"]
    if con.payback_years is not None and con.payback_years <= vb["strong"]:
        verdict = "strong"
    elif con.payback_years is not None and con.payback_years <= vb["reasonable"]:
        verdict = "reasonable"
    else:
        verdict = "weak"

    def pct(x): return f"{x * 100:.0f}%"
    assumptions = [
        Assumption(key="rate_per_kwh", label="Electricity rate (PHP per kWh)", value=f"{rate:.2f}",
                   source="From your bill and kWh" if not kwh_est and not o.rate_per_kwh else d["rate_per_kwh"]["source"], editable=True),
        Assumption(key="self_use_share", label=d["self_use_share"]["label"], value=f"{share:.2f}",
                   source=d["self_use_share"]["source"], editable=True),
        Assumption(key="export_credit_per_kwh", label=d["export_credit_per_kwh"]["label"], value=f"{credit:.2f}",
                   source=d["export_credit_per_kwh"]["source"] if net else "No net metering selected", editable=net),
        Assumption(key="cost_low", label="Installed cost per kW, low (PHP)", value=f"{cost_lo:.0f}",
                   source=d["cost_per_kwp_php"]["source"], editable=True),
        Assumption(key="cost_high", label="Installed cost per kW, high (PHP)", value=f"{cost_hi:.0f}",
                   source=d["cost_per_kwp_php"]["source"], editable=True),
        Assumption(key="escalation_low", label="Yearly rate increase, conservative", value=f"{esc_lo:.3f}",
                   source=d["tariff_escalation"]["source"], editable=True),
        Assumption(key="escalation_high", label="Yearly rate increase, optimistic", value=f"{esc_hi:.3f}",
                   source=d["tariff_escalation"]["source"], editable=True),
        Assumption(key="yield", label="Solar output per kW per year (kWh)", value=f"{y_year:.0f}",
                   source=f"{region['name']}, roof direction {inp.direction}, shading {inp.shading}. {_regions_source()}"),
        Assumption(key="avoidable_share", label=d["avoidable_share"]["label"], value=pct(avoid), source=d["avoidable_share"]["source"]),
        Assumption(key="degradation", label=d["degradation"]["label"], value=pct(d["degradation"]["value"]) if d["degradation"]["value"] >= 0.01 else "0.5%",
                   source=d["degradation"]["source"]),
        Assumption(key="inverter", label="Inverter replacement", value=f"Year {d['inverter_replacement']['year']}, {pct(inv_share)} of system cost",
                   source=d["inverter_replacement"]["source"]),
        Assumption(key="yield_case", label="Output range used", value=f"{yc['conservative']:.2f}x to {yc['optimistic']:.2f}x of modelled output",
                   source="Allows for weather and installation differences."),
    ]

    return SolarEstimate(
        region_name=region["name"], kwh_month=round(kwh, 1), kwh_estimated=kwh_est, rate_per_kwh=round(rate, 2),
        size_low_kwp=size_lo, size_high_kwp=size_hi, size_kwp=size, limited_by=limited_by,
        monthly_use_kwh=[round(kwh, 1)] * 12, monthly_gen_kwh=[round(g, 1) for g in gen],
        monthly_self_kwh=[round(s, 1) for s in self_], monthly_export_kwh=[round(e, 1) for e in exp],
        yearly_gen_kwh=round(sum(gen)), bill_before_php=round(bill_before),
        bill_after_php=round(max(fixed, bill_before - base_saving / 12)),
        optimistic=opt, conservative=con, verdict=verdict, assumptions=assumptions, warnings=warnings,
    )


def _regions_source() -> str:
    from ..config import regions
    return "Source: " + regions()["source"]
