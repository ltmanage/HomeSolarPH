"""Quote normalization, flags and AI extraction parsing (no network). All quotes are dummy data."""
import httpx
import pytest

from homesolar.calc.quotes import compare
from homesolar.models import CompareRequest, QuoteFields, SolarInput
from homesolar.quotes import ai_extract, intake

SOLAR = SolarInput(region="NCR", provider="meralco", bill_php=9000, kwh_month=600, direction="south", shading="none")


def good_quote(**kw) -> QuoteFields:
    d = dict(label="Quote A", installer_name="Sample Solar Co.", system_type="grid_tie", kwp=5.0,
             total_price_php=250000, vat_included=True, panel_brand="BrandX", panel_watt=500, panel_qty=10,
             inverter_brand="InvY", inverter_kw=5,
             inclusions=dict(net_metering=True, permits=True, electrical_upgrade=True, monitoring=True,
                             installation=True, after_sales=True),
             warranty_years=dict(panel_product=12, panel_performance=25, inverter=10, workmanship=5),
             deposit_pct=30)
    d.update(kw)
    return QuoteFields(**d)


def codes(r):
    return {f.code for f in r.flags}


def test_clean_quote_has_no_check_flags():
    r = compare(CompareRequest(quotes=[good_quote()], solar=SOLAR)).quotes[0]
    assert r.price_per_wp == 50.0
    assert r.kwp_from_panels == 5.0
    assert not [f for f in r.flags if f.level == "check"]
    assert r.yearly_savings_low <= r.yearly_savings_high
    assert r.payback_low <= r.payback_high


def test_flags():
    q = good_quote(kwp=8.0, total_price_php=700000, vat_included=None, deposit_pct=70,
                   inclusions=dict(net_metering=None, permits=False, installation=True),
                   warranty_years=dict(workmanship=1))
    r = compare(CompareRequest(quotes=[q], solar=SOLAR)).quotes[0]
    c = codes(r)
    assert {"size_mismatch", "vat_unclear", "high_price", "high_deposit", "missing_net_metering",
            "missing_permits", "short_workmanship"} <= c


def test_vat_exclusive_grossed_up():
    r = compare(CompareRequest(quotes=[good_quote(vat_included=False)], region="NCR")).quotes[0]
    assert r.price_incl_vat_php == 280000


def test_oversized_and_low_price():
    r = compare(CompareRequest(quotes=[good_quote(kwp=10, panel_qty=20, total_price_php=300000)], solar=SOLAR)).quotes[0]
    assert {"oversized", "low_price"} <= codes(r)


def test_no_ranking_note_and_without_solar():
    res = compare(CompareRequest(quotes=[good_quote(), good_quote(label="Quote B")], region="VII"))
    assert any("does not rank" in n for n in res.notes)
    assert res.quotes[0].yearly_savings_low is None


def test_intake_sniff_and_limits():
    assert intake.check(b"%PDF-1.7 rest") == "pdf"
    assert intake.check(b"\xff\xd8\xff\xe0data") == "jpeg"
    with pytest.raises(intake.IntakeError):
        intake.check(b"MZ\x90\x00 not allowed")
    with pytest.raises(intake.IntakeError):
        intake.check(b"%PDF-" + b"0" * (intake.MAX_BYTES + 1))


def test_ai_reply_parsing_drops_bad_values():
    f = ai_extract.to_fields({"kwp": "five", "total_price_php": 250000, "label": "ignored",
                              "inclusions": {"permits": True}, "unknown_key": 1}, "Quote A")
    assert f.kwp is None and f.total_price_php == 250000 and f.inclusions.permits is True and f.label == "Quote A"


def test_ai_extract_with_stubbed_gateway(monkeypatch):
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-key")
    reply = '```json\n{"kwp": 5, "total_price_php": 250000, "system_type": "grid_tie"}\n```'

    def handler(request):
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(200, json={"choices": [{"message": {"content": reply}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    f = ai_extract.extract("pdf", b"", "Quotation text " * 30, "Quote A", client=client)
    assert f.kwp == 5 and f.system_type == "grid_tie"


def test_ai_extract_failure_is_unavailable(monkeypatch):
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-key")
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(402, json={})))
    with pytest.raises(ai_extract.ExtractionUnavailable):
        ai_extract.extract("jpeg", b"\xff\xd8\xff", "", "Quote A", client=client)


def test_ai_extract_uses_per_request_vercel_token(monkeypatch):
    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    monkeypatch.delenv("VERCEL_OIDC_TOKEN", raising=False)
    monkeypatch.setenv("VERCEL", "1")

    def handler(request):
        assert request.headers["Authorization"] == "Bearer oidc-from-header"
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"kwp": 6}'}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    f = ai_extract.extract("pdf", b"", "Quotation text " * 30, "Quote A", client=client, token="oidc-from-header")
    assert f.kwp == 6
    with pytest.raises(ai_extract.ExtractionUnavailable):   # on Vercel but no token in the request
        ai_extract.extract("pdf", b"", "text", "Quote A", client=client)


def test_gemini_provider_selected_by_key(monkeypatch):
    from homesolar.config import settings
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    assert settings.ai_provider == "gemini" and settings.ai_enabled
    assert settings.ai_base_url.startswith("https://generativelanguage.googleapis.com/")
    assert settings.ai_model == "gemini-3.8-flash"

    def handler(request):
        assert str(request.url) == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        assert request.headers["Authorization"] == "Bearer g-key"
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"kwp": 4.5}'}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert ai_extract.extract("pdf", b"", "Quotation text " * 30, "Quote A", client=client).kwp == 4.5


def test_gemini_without_key_is_off(monkeypatch):
    from homesolar.config import settings
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("VERCEL", "1")
    assert not settings.ai_enabled


@pytest.mark.parametrize("body", [
    [{"error": {"code": 400, "message": "API key not valid", "status": "INVALID_ARGUMENT"}}],
    {"error": {"message": "quota exceeded"}},
    "plain text error",
])
def test_ai_error_bodies_never_crash(monkeypatch, body):
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    resp = (lambda r: httpx.Response(400, json=body)) if not isinstance(body, str) else (lambda r: httpx.Response(400, text=body))
    client = httpx.Client(transport=httpx.MockTransport(resp))
    with pytest.raises(ai_extract.ExtractionUnavailable) as e:
        ai_extract.extract("pdf", b"", "Quotation text " * 30, "Quote A", client=client)
    assert "400" in str(e.value)
