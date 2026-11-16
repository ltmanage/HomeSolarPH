"""Typed inputs and outputs (Pydantic)."""
from typing import Literal, Optional
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
    rate_per_kwh: Optional[float] = Field(None, gt=0, le=60)
    export_credit_per_kwh: Optional[float] = Field(None, ge=0, le=60)
    self_use_share: Optional[float] = Field(None, ge=0.05, le=1)
    cost_low: Optional[float] = Field(None, gt=0, le=300000)
    cost_high: Optional[float] = Field(None, gt=0, le=300000)
    escalation_low: Optional[float] = Field(None, ge=-0.05, le=0.2)
    escalation_high: Optional[float] = Field(None, ge=-0.05, le=0.2)
    size_kwp: Optional[float] = Field(None, ge=0.5, le=50)


class SolarInput(BaseModel):
    region: str = Field(max_length=12)
    provider: Provider
    bill_php: float = Field(gt=0, le=500000)
    kwh_month: Optional[float] = Field(None, gt=0, le=20000)
    daytime: Daytime = "mixed"
    home_type: HomeType = "house"
    roof_type: RoofType = "unsure"
    roof_area_m2: Optional[float] = Field(None, gt=0, le=2000)
    direction: Direction = "unsure"
    shading: Shading = "unsure"
    net_metering: NetMetering = "yes"
    budget_php: Optional[float] = Field(None, gt=0, le=20000000)
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
    payback_years: Optional[float]   # None = not within 25 years
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
    net_metering: Optional[bool] = None
    permits: Optional[bool] = None
    electrical_upgrade: Optional[bool] = None
    monitoring: Optional[bool] = None
    installation: Optional[bool] = None
    after_sales: Optional[bool] = None


class Warranties(BaseModel):
    panel_product: Optional[int] = Field(None, ge=0, le=50)
    panel_performance: Optional[int] = Field(None, ge=0, le=50)
    inverter: Optional[int] = Field(None, ge=0, le=50)
    battery: Optional[int] = Field(None, ge=0, le=50)
    workmanship: Optional[int] = Field(None, ge=0, le=50)


class QuoteFields(BaseModel):
    label: str = Field("Quote", max_length=40)
    installer_name: Optional[str] = Field(None, max_length=120)   # display only, never stored
    system_type: SystemType = "unknown"
    kwp: Optional[float] = Field(None, gt=0, le=100)
    total_price_php: Optional[float] = Field(None, gt=0, le=50000000)
    vat_included: Optional[bool] = None
    panel_brand: Optional[str] = Field(None, max_length=60)
    panel_model: Optional[str] = Field(None, max_length=80)
    panel_watt: Optional[int] = Field(None, gt=0, le=1000)
    panel_qty: Optional[int] = Field(None, gt=0, le=500)
    inverter_brand: Optional[str] = Field(None, max_length=60)
    inverter_type: Optional[str] = Field(None, max_length=60)
    inverter_kw: Optional[float] = Field(None, gt=0, le=200)
    battery_brand: Optional[str] = Field(None, max_length=60)
    battery_kwh: Optional[float] = Field(None, ge=0, le=500)
    mounting: Optional[str] = Field(None, max_length=80)
    inclusions: Inclusions = Inclusions()
    warranty_years: Warranties = Warranties()
    deposit_pct: Optional[float] = Field(None, ge=0, le=100)
    timeline_weeks: Optional[float] = Field(None, ge=0, le=104)
    validity_days: Optional[int] = Field(None, ge=0, le=365)
    notes: Optional[str] = Field(None, max_length=1000)              # display only, never stored


class CompareRequest(BaseModel):
    quotes: list[QuoteFields] = Field(min_length=1, max_length=4)
    solar: Optional[SolarInput] = None
    region: Optional[str] = Field(None, max_length=12)


class Flag(BaseModel):
    code: str
    level: Literal["info", "check"]
    text: str
    question: str


class QuoteResult(BaseModel):
    label: str
    installer_name: Optional[str]
    kwp: Optional[float]
    kwp_from_panels: Optional[float]
    price_incl_vat_php: Optional[float]
    price_per_wp: Optional[float]
    yearly_gen_kwh: Optional[float]
    price_per_yearly_kwh: Optional[float]
    yearly_savings_low: Optional[float]
    yearly_savings_high: Optional[float]
    payback_low: Optional[float]
    payback_high: Optional[float]
    warranty_total_years: Optional[int]
    flags: list[Flag]


class CompareResult(BaseModel):
    region_name: str
    quotes: list[QuoteResult]
    notes: list[str]


class ShareRequest(BaseModel):
    consent: bool
    kind: Literal["check", "quotes"]
    solar: Optional[SolarInput] = None
    region: Optional[str] = Field(None, max_length=12)
    quotes: list[QuoteFields] = Field(default_factory=list, max_length=4)
    fields_corrected: list[int] = Field(default_factory=list, max_length=4)
    extraction_source: list[str] = Field(default_factory=list, max_length=4)


class FeedbackRequest(BaseModel):
    page: str = Field(max_length=40)
    useful: bool
    comment: Optional[str] = Field(None, max_length=500)
    website: Optional[str] = None   # honeypot: must be empty
