"""Plain-language explanation built from templates. Uses only numbers already in the estimate."""
from .models import SolarEstimate, SolarInput

VERDICT = {
    "strong": ("Strong case", "Even with cautious assumptions, the system pays for itself in about {pb} years."),
    "reasonable": ("Reasonable case", "With cautious assumptions, payback is about {pb} years. Compare quotes carefully: price and size matter a lot here."),
    "weak": ("Weak case: check these factors first", "With cautious assumptions, payback is {pb}. Look at the factors below before asking for quotes."),
}

LIMIT = {
    "usage": "The size range is set by how much electricity you use.",
    "roof": "The size is limited by the roof area you entered.",
    "budget": "The size is limited by the budget you entered.",
    "user": "You set the system size yourself.",
}


def php(x: float) -> str:
    return f"PHP {x:,.0f}"


def explain(inp: SolarInput, e: SolarEstimate) -> dict:
    pb = e.conservative.payback_years
    pb_text = f"{pb:.1f}" if pb is not None else "longer than 25 years"
    title, line = VERDICT[e.verdict]
    paras = [line.format(pb=pb_text), LIMIT[e.limited_by]]
    self_total, gen_total = sum(e.monthly_self_kwh), sum(e.monthly_gen_kwh)
    if gen_total:
        share = self_total / gen_total
        if inp.net_metering == "no":
            paras.append(f"Without net metering, only the solar power you use as it is produced saves money: about {share:.0%} of output in this estimate. "
                         "That is why the suggested size is smaller.")
        else:
            paras.append(f"About {share:.0%} of the solar output is used directly in your home; the rest goes to the grid and earns net-metering credits, "
                         "which are worth less per kWh than the power you avoid buying.")
    if inp.daytime == "evening":
        paras.append("Most of your use is in the evening, when panels produce nothing. Shifting some use (laundry, ironing, aircon pre-cooling) to daytime improves savings.")
    tips = []
    if e.verdict != "strong":
        tips.append("Get at least three itemized quotes: installed price per watt has the largest effect on payback.")
        if inp.shading in ("moderate", "heavy"):
            tips.append("Ask for a shading assessment; shading lowers output for the whole day.")
        if e.kwh_month < 200:
            tips.append("With low usage, a small system or waiting may make more sense.")
    return {"title": title, "paragraphs": paras, "tips": tips,
            "summary": f"Suggested size {e.size_low_kwp:g}-{e.size_high_kwp:g} kWp. Estimated yearly savings "
                       f"{php(e.conservative.yearly_savings_php)}-{php(e.optimistic.yearly_savings_php)}."}


# Guide questions most relevant to the user's answers (section ids in content/guide)
def relevant_questions(inp: SolarInput) -> list[str]:
    q = ["What exactly is included in the price, item by item?",
         "Which panel and inverter brands and models are you proposing, and why?",
         "What warranties apply to panels, inverter and workmanship, and who handles claims?"]
    if inp.net_metering != "no":
        q.append("Will you handle the net-metering application, and how long does it usually take with my utility?")
    if inp.shading in ("light", "moderate", "heavy", "unsure"):
        q.append("How will you assess shading on my roof, and how does it change the expected output?")
    if inp.roof_type in ("metal", "tile", "unsure"):
        q.append("How will the panels be mounted, and how will you prevent roof leaks?")
    q.append("What payment schedule do you offer, and how much is due before installation?")
    return q
