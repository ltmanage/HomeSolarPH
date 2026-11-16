"""Typed inputs and outputs (Pydantic)."""
from typing import Literal

from pydantic import BaseModel, Field

Provider = Literal["meralco", "private_du", "coop"]
Daytime = Literal["evening", "mixed", "daytime"]
Direction = Literal["south", "east", "west", "north", "flat", "unsure"]
Shading = Literal["none", "light", "moderate", "heavy", "unsure"]
NetMetering = Literal["yes", "unsure", "no"]
HomeType = Literal["house", "townhouse", "other"]
RoofType = Literal["metal", "concrete", "tile", "other", "unsure"]
SystemType = Literal["grid_tie", "hybrid", "off_grid", "unknown"]


class Overrides(BaseModel):
    """Assumptions the user may change on the results page. None = use default."""
    rate_per_kwh: float | None = Field(None, gt=0, le=60)
    export_credit_per_kwh: float | None = Field(None, ge=0, le=60)
    self_use_share: float | None = Field(None, ge=0.05, le=1)
    cost_low: float | None = Field(None, gt=0, le=300000)
    cost_high: float | None = Field(None, gt=0, le=300000)
    escalation_low: float | None = Field(None, ge=-0.05, le=0.2)
    escalation_high: float | None = Field(None, ge=-0.05, le=0.2)
    size_kwp: float | None = Field(None, ge=0.5, le=50)


class SolarInput(BaseModel):
    region: str = Field(max_length=12)
    provider: Provider
    bill_php: float = Field(gt=0, le=500000)
    kwh_month: float | None = Field(None, gt=0, le=20000)
    daytime: Daytime = "mixed"
    home_type: HomeType = "house"
    roof_type: RoofType = "unsure"
    roof_area_m2: float | None = Field(None, gt=0, le=2000)
    direction: Direction = "unsure"
    shading: Shading = "unsure"
    net_metering: NetMetering = "yes"
    budget_php: float | None = Field(None, gt=0, le=20000000)
    overrides: Overrides = Overrides()


class Assumption(BaseModel):
    key: str
    label: str
    value: str
    source: str = ""
    editable: bool = False


class Case(BaseModel):
    cost_php: float
    yearly_savings_php: float
    payback_years: float | None   # None = not within 25 years
    net_25y_php: float


class SolarEstimate(BaseModel):
    region_name: str
    kwh_month: float
    kwh_estimated: bool
    rate_per_kwh: float
    size_low_kwp: float
    size_high_kwp: float
    size_kwp: float                   # size used for the figures below
    limited_by: Literal["usage", "roof", "budget", "user"]
    monthly_use_kwh: list[float]
    monthly_gen_kwh: list[float]
    monthly_self_kwh: list[float]
    monthly_export_kwh: list[float]
    yearly_gen_kwh: float
    bill_before_php: float
    bill_after_php: float
    optimistic: Case
    conservative: Case
    verdict: Literal["strong", "reasonable", "weak"]
    assumptions: list[Assumption]
    warnings: list[str]


class Inclusions(BaseModel):
    net_metering: bool | None = None
    permits: bool | None = None
    electrical_upgrade: bool | None = None
    monitoring: bool | None = None
    installation: bool | None = None
    after_sales: bool | None = None


class Warranties(BaseModel):
    panel_product: int | None = Field(None, ge=0, le=50)
    panel_performance: int | None = Field(None, ge=0, le=50)
    inverter: int | None = Field(None, ge=0, le=50)
    battery: int | None = Field(None, ge=0, le=50)
    workmanship: int | None = Field(None, ge=0, le=50)


class QuoteFields(BaseModel):
    label: str = Field("Quote", max_length=40)
    installer_name: str | None = Field(None, max_length=120)   # display only, never stored
    system_type: SystemType = "unknown"
    kwp: float | None = Field(None, gt=0, le=100)
    total_price_php: float | None = Field(None, gt=0, le=50000000)
    vat_included: bool | None = None
    panel_brand: str | None = Field(None, max_length=60)
    panel_model: str | None = Field(None, max_length=80)
    panel_watt: int | None = Field(None, gt=0, le=1000)
    panel_qty: int | None = Field(None, gt=0, le=500)
    inverter_brand: str | None = Field(None, max_length=60)
    inverter_type: str | None = Field(None, max_length=60)
    inverter_kw: float | None = Field(None, gt=0, le=200)
    battery_brand: str | None = Field(None, max_length=60)
    battery_kwh: float | None = Field(None, ge=0, le=500)
    mounting: str | None = Field(None, max_length=80)
    inclusions: Inclusions = Inclusions()
    warranty_years: Warranties = Warranties()
    deposit_pct: float | None = Field(None, ge=0, le=100)
    timeline_weeks: float | None = Field(None, ge=0, le=104)
    validity_days: int | None = Field(None, ge=0, le=365)
    notes: str | None = Field(None, max_length=1000)              # display only, never stored


class CompareRequest(BaseModel):
    quotes: list[QuoteFields] = Field(min_length=1, max_length=4)
    solar: SolarInput | None = None
    region: str | None = Field(None, max_length=12)


class Flag(BaseModel):
    code: str
    level: Literal["info", "check"]
    text: str
    question: str


class QuoteResult(BaseModel):
    label: str
    installer_name: str | None
    kwp: float | None
    kwp_from_panels: float | None
    price_incl_vat_php: float | None
    price_per_wp: float | None
    yearly_gen_kwh: float | None
    price_per_yearly_kwh: float | None
    yearly_savings_low: float | None
    yearly_savings_high: float | None
    payback_low: float | None
    payback_high: float | None
    warranty_total_years: int | None
    flags: list[Flag]


class EstimateColumn(BaseModel):
    """The app's own estimate, shown as the first column of the comparison."""
    has_solar_check: bool = False
    basis: str
    size_low_kwp: float | None = None
    size_high_kwp: float | None = None
    size_kwp: float | None = None
    cost_low_php: float | None = None
    cost_high_php: float | None = None
    price_per_wp_low: float | None = None
    price_per_wp_high: float | None = None
    yearly_gen_kwh: float | None = None
    price_per_yearly_kwh_low: float | None = None
    price_per_yearly_kwh_high: float | None = None
    yearly_savings_low: float | None = None
    yearly_savings_high: float | None = None
    payback_low: float | None = None
    payback_high: float | None = None


class CompareResult(BaseModel):
    region_name: str
    estimate: EstimateColumn
    quotes: list[QuoteResult]
    notes: list[str]


class ShareRequest(BaseModel):
    consent: bool
    kind: Literal["check", "quotes"]
    solar: SolarInput | None = None
    region: str | None = Field(None, max_length=12)
    quotes: list[QuoteFields] = Field(default_factory=list, max_length=4)
    fields_corrected: list[int] = Field(default_factory=list, max_length=4)
    extraction_source: list[str] = Field(default_factory=list, max_length=4)


class FeedbackRequest(BaseModel):
    page: str = Field(max_length=40)
    useful: bool
    comment: str | None = Field(None, max_length=500)
    website: str | None = None   # honeypot: must be empty
