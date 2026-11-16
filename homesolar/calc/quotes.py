"""Quote normalization and neutral flags. Never ranks quotes."""
from __future__ import annotations

from ..config import defaults, region_map
from ..models import CompareRequest, CompareResult, EstimateColumn, Flag, QuoteFields, QuoteResult
from .solar import estimate, monthly_yield, payback

INCLUSION_LABELS = {
    "net_metering": ("net-metering application", "Will you handle the net-metering application with the utility, and is it included in the price?"),
    "permits": ("permits", "Which permits (building, electrical) are included, and who files them?"),
    "electrical_upgrade": ("electrical upgrades", "Does my panel board or wiring need upgrades, and is that included?"),
    "monitoring": ("monitoring app", "Is a monitoring app or device included so I can see what the system produces?"),
    "installation": ("delivery and installation", "Are delivery, mounting and installation labour all included?"),
    "after_sales": ("after-sales visits", "What after-sales visits or cleaning are included, and for how long?"),
}


def price_incl_vat(q: QuoteFields) -> float | None:
    if q.total_price_php is None:
        return None
    if q.vat_included is False:
        return q.total_price_php * (1 + defaults()["quote_flags"]["vat_rate"])
    return q.total_price_php


def analyse(q: QuoteFields, yearly_yield: float, solar_ctx: dict | None) -> QuoteResult:
    d = defaults()
    qf = d["quote_flags"]
    flags: list[Flag] = []
    kwp_panels = round(q.panel_watt * q.panel_qty / 1000, 2) if q.panel_watt and q.panel_qty else None
    kwp = q.kwp or kwp_panels
    if q.kwp and kwp_panels and abs(kwp_panels - q.kwp) / q.kwp > qf["size_mismatch_tolerance"]:
        flags.append(Flag(code="size_mismatch", level="check",
                          text=f"Panels listed add up to {kwp_panels} kWp, but the quote states {q.kwp} kWp.",
                          question="Can you confirm the exact number and wattage of panels, and the total system size?"))
    price = price_incl_vat(q)
    if q.total_price_php is not None and q.vat_included is None:
        flags.append(Flag(code="vat_unclear", level="check", text="The quote does not say whether VAT is included.",
                          question="Is the total price inclusive of 12% VAT?"))
    ppw = round(price / (kwp * 1000), 2) if price and kwp else None
    gen = round(kwp * yearly_yield) if kwp else None
    stype = q.system_type if q.system_type != "unknown" else "grid_tie"
    lo, hi = d["cost_per_kwp_php"]["by_type"][stype]
    if ppw is not None:
        if ppw * 1000 > hi:
            flags.append(Flag(code="high_price", level="check",
                              text=f"PHP {ppw:.0f} per watt is above the typical range this app uses for this system type (PHP {lo/1000:.0f}-{hi/1000:.0f} per watt).",
                              question="What makes this price higher than typical: equipment brand, mounting, roof work or extra services?"))
        elif ppw * 1000 < lo * (1 - qf["low_price_margin"]):
            flags.append(Flag(code="low_price", level="check",
                              text=f"PHP {ppw:.0f} per watt is well below the typical range (PHP {lo/1000:.0f}-{hi/1000:.0f} per watt).",
                              question="What is not included in this price, and what brands and warranties come with it?"))
    if q.system_type == "unknown":
        flags.append(Flag(code="type_unclear", level="info", text="System type (grid-tie, hybrid or off-grid) is not stated.",
                          question="Is this a grid-tie, hybrid or off-grid system?"))
    for key, (label, question) in INCLUSION_LABELS.items():
        if getattr(q.inclusions, key) is not True:
            state = "not listed" if getattr(q.inclusions, key) is None else "not included"
            flags.append(Flag(code=f"missing_{key}", level="check" if key in ("net_metering", "permits", "installation") else "info",
                              text=f"{label.capitalize()}: {state}.", question=question))
    w = q.warranty_years
    if w.workmanship is None:
        flags.append(Flag(code="workmanship_unclear", level="check", text="No workmanship (installation) warranty stated.",
                          question="What warranty do you give on the installation work itself, and how are claims handled?"))
    elif w.workmanship < qf["min_workmanship_years"]:
        flags.append(Flag(code="short_workmanship", level="check", text=f"Workmanship warranty is only {w.workmanship} year(s).",
                          question="Can the workmanship warranty be extended, and what does it cover?"))
    if w.inverter is None:
        flags.append(Flag(code="inverter_warranty_unclear", level="info", text="Inverter warranty not stated.",
                          question="How many years is the inverter warranty, and is it handled locally?"))
    if q.deposit_pct is not None and q.deposit_pct > qf["max_deposit_pct"]:
        flags.append(Flag(code="high_deposit", level="check", text=f"Deposit of {q.deposit_pct:.0f}% is high.",
                          question="Can payments be split into milestones, with a larger share due after installation and inspection?"))

    sav_lo = sav_hi = pb_lo = pb_hi = None
    if solar_ctx and kwp:
        if kwp > qf["oversize_ratio"] * solar_ctx["s_full"]:
            flags.append(Flag(code="oversized", level="check",
                              text=f"{kwp} kWp is much larger than your usage needs (about {solar_ctx['s_full']:.1f} kWp covers all your yearly use).",
                              question="Why do you recommend this size for my usage, and what would a smaller system cost?"))
        if (q.battery_kwh or q.system_type == "hybrid") and solar_ctx["net"] and solar_ctx["daytime"] == "daytime":
            flags.append(Flag(code="battery_need", level="info",
                              text="A battery is quoted, but you use most power in the daytime and plan net metering.",
                              question="What would the battery do for me, and how much would the system cost without it?"))
        ests = [estimate(solar_ctx["input"].model_copy(update={"overrides": solar_ctx["input"].overrides.model_copy(update={"size_kwp": kwp})}))]
        e = ests[0]
        sav_lo, sav_hi = e.conservative.yearly_savings_php, e.optimistic.yearly_savings_php
        if price:
            inv = d["inverter_replacement"]["share_of_cost"]
            esc = d["tariff_escalation"]
            pb_lo = payback(price, sav_hi, esc["high"], price * inv)[0]
            pb_hi = payback(price, sav_lo, esc["low"], price * inv)[0]
    warr = [x for x in (w.panel_product, w.inverter, w.workmanship) if x is not None]
    return QuoteResult(
        label=q.label, installer_name=q.installer_name, kwp=kwp, kwp_from_panels=kwp_panels,
        price_incl_vat_php=round(price) if price else None, price_per_wp=ppw, yearly_gen_kwh=gen,
        price_per_yearly_kwh=round(price / gen, 2) if price and gen else None,
        yearly_savings_low=sav_lo, yearly_savings_high=sav_hi, payback_low=pb_lo, payback_high=pb_hi,
        warranty_total_years=sum(warr) if warr else None, flags=flags,
    )


def compare(req: CompareRequest) -> CompareResult:
    notes = []
    ctx = None
    if req.solar:
        region = req.solar.region
        Y = monthly_yield(region, req.solar.direction, req.solar.shading)
        base = estimate(req.solar.model_copy(update={"overrides": req.solar.overrides.model_copy(update={"size_kwp": None})}))
        ctx = {"input": req.solar, "s_full": base.kwh_month * 12 / sum(Y), "net": req.solar.net_metering != "no",
               "daytime": req.solar.daytime}
    else:
        region = req.region or "NCR"
        Y = monthly_yield(region, "unsure", "unsure")
        notes.append("Savings and payback per quote need your bill details. Run the solar check first, or add them on this page.")
    if region not in region_map():
        raise ValueError(f"Unknown region: {region}")
    results = [analyse(q, sum(Y), ctx) for q in req.quotes]
    notes.append("This comparison highlights differences and gaps. It does not rank quotes or recommend an installer.")
    return CompareResult(region_name=region_map()[region]["name"], estimate=app_estimate(req, sum(Y)), quotes=results, notes=notes)


def app_estimate(req: CompareRequest, yearly_yield: float) -> EstimateColumn:
    """The app's own figures, shown as the first column next to the quotes."""
    lo, hi = defaults()["cost_per_kwp_php"]["by_type"]["grid_tie"]
    if not req.solar:
        return EstimateColumn(
            basis="Typical grid-tie prices used by this app. Run the solar check for size, savings and payback.",
            price_per_wp_low=lo / 1000, price_per_wp_high=hi / 1000,
            price_per_yearly_kwh_low=round(lo / yearly_yield, 1), price_per_yearly_kwh_high=round(hi / yearly_yield, 1))
    e = estimate(req.solar)
    gen = e.yearly_gen_kwh
    return EstimateColumn(
        has_solar_check=True,
        basis=f"From your solar check: {e.size_kwp:g} kWp in {e.region_name}, cost range PHP {lo/1000:.0f}-{hi/1000:.0f} per watt.",
        size_low_kwp=e.size_low_kwp, size_high_kwp=e.size_high_kwp, size_kwp=e.size_kwp,
        cost_low_php=e.optimistic.cost_php, cost_high_php=e.conservative.cost_php,
        price_per_wp_low=round(e.optimistic.cost_php / (e.size_kwp * 1000), 1),
        price_per_wp_high=round(e.conservative.cost_php / (e.size_kwp * 1000), 1),
        yearly_gen_kwh=gen,
        price_per_yearly_kwh_low=round(e.optimistic.cost_php / gen, 1) if gen else None,
        price_per_yearly_kwh_high=round(e.conservative.cost_php / gen, 1) if gen else None,
        yearly_savings_low=e.conservative.yearly_savings_php, yearly_savings_high=e.optimistic.yearly_savings_php,
        payback_low=e.optimistic.payback_years, payback_high=e.conservative.payback_years)
