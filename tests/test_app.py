"""Routes and privacy rules."""
import pytest
from fastapi.testclient import TestClient

from homesolar import store
from homesolar.main import app
from homesolar.models import QuoteFields, ShareRequest, SolarInput


@pytest.fixture(autouse=True)
def no_services(monkeypatch):
    for k in ("AI_GATEWAY_API_KEY", "VERCEL_OIDC_TOKEN", "DATABASE_URL", "POSTGRES_URL"):
        monkeypatch.delenv(k, raising=False)


client = TestClient(app)
FORM = {"region": "NCR", "provider": "meralco", "bill_php": "9,000", "kwh_month": "600", "daytime": "mixed",
        "net_metering": "yes", "direction": "south", "shading": "none", "website": ""}


@pytest.mark.parametrize("path", ["/", "/check", "/quotes", "/guide", "/guide/questions", "/guide/red-flags",
                                  "/guide/process", "/guide/glossary", "/about", "/static/style.css"])
def test_pages_ok(path):
    r = client.get(path)
    assert r.status_code == 200


def test_security_headers():
    r = client.get("/")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"


def test_404_page():
    assert client.get("/nope").status_code == 404
    assert client.get("/guide/nope").status_code == 404


def test_check_flow():
    r = client.post("/check", data=FORM)
    assert r.status_code == 200 and "Your solar estimate" in r.text and "kWp" in r.text


def test_check_validation_error():
    r = client.post("/check", data={**FORM, "bill_php": "-5"})
    assert "Please check" in r.text


def test_api_estimate_with_override():
    body = {k: v for k, v in FORM.items() if k != "website"}
    body.update(bill_php=9000, kwh_month=600, overrides={"size_kwp": 3})
    r = client.post("/api/solar/estimate", json=body)
    assert r.status_code == 200 and r.json()["estimate"]["size_kwp"] == 3


def test_extract_without_ai_falls_back_to_manual():
    r = client.post("/api/quotes/extract", files={"file": ("q.pdf", b"%PDF-1.4 dummy", "application/pdf")},
                    data={"label": "Quote A"})
    assert r.status_code == 200 and r.json()["source"] == "manual"


def test_extract_rejects_other_files():
    r = client.post("/api/quotes/extract", files={"file": ("q.exe", b"MZ\x90\x00", "application/octet-stream")})
    assert r.status_code == 400


def test_compare_api():
    q = {"label": "Quote A", "kwp": 5, "total_price_php": 250000, "vat_included": True}
    r = client.post("/api/quotes/compare", json={"quotes": [q], "region": "NCR"})
    assert r.status_code == 200 and r.json()["quotes"][0]["price_per_wp"] == 50


def test_share_disabled_without_database():
    r = client.post("/api/share", json={"consent": True, "kind": "check"})
    assert r.status_code == 503


def test_health():
    j = client.get("/api/health").json()
    assert j["status"] == "ok" and j["ai_enabled"] is False and j["sharing_enabled"] is False


def test_stored_rows_contain_only_allowed_fields():
    solar = SolarInput(region="NCR", provider="meralco", bill_php=9000, kwh_month=600, roof_area_m2=45, budget_php=250000)
    q = QuoteFields(label="Quote A", installer_name="Sample Solar Co.", notes="call Ana at 0917...", kwp=5, total_price_php=250000)
    req = ShareRequest(consent=True, kind="quotes", solar=solar, quotes=[q], fields_corrected=[2], extraction_source=["ai_text"])
    crow, qrows = store.check_row(req), store.quote_rows(req)
    assert set(crow) == set(store.CHECK_FIELDS)
    assert set(qrows[0]) == set(store.QUOTE_FIELDS)
    flat = str(crow) + str(qrows)
    assert "Sample Solar" not in flat and "0917" not in flat
    assert crow["roof_area_band"] == "40-60 m2" and crow["budget_band"] == "200000-300000 PHP"


def test_home_privacy_text_and_installer_prompt():
    home = client.get("/").text
    assert "unless you request a referral to our accredited installers" in home
    assert "only if you agree specifically" in home
    r = client.post("/check", data=FORM)
    assert "data-installers" in r.text
