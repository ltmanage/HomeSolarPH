"""Optional AI extraction of quote fields through an OpenAI-compatible API (Gemini or the Vercel AI Gateway).

The AI only reads the document. It never calculates; every field is shown to the user to confirm.
"""
from __future__ import annotations

import base64
import json
import re
import time

import httpx
from pydantic import ValidationError

from ..config import settings
from ..models import QuoteFields

SYSTEM = """You read Philippine rooftop solar installer quotations and copy facts from them into JSON.
Rules:
- Copy only what the document states. Use null for anything not stated. Never guess, estimate or calculate.
- Prices in PHP as plain numbers (no commas or currency signs). total_price_php is the final total the customer pays.
- If only a price before VAT is given (e.g. "PHP 385,000 + 12% VAT"), put that price in total_price_php and set vat_included to false; the app adds the VAT.
- vat_included: true if the total says VAT inclusive, false if VAT is added separately or excluded, null if not stated.
- system_type: "grid_tie", "hybrid" (has a battery and hybrid inverter), "off_grid", or "unknown".
- inclusions values: true if clearly included, false if clearly excluded, null if not mentioned.
- warranty_years: whole years; null if not stated.
- deposit_pct: percent of the price due before installation, if stated.
- Reply with a single JSON object only, no other text."""

SCHEMA_HINT = json.dumps({
    "installer_name": None, "system_type": "unknown", "kwp": None, "total_price_php": None, "vat_included": None,
    "panel_brand": None, "panel_model": None, "panel_watt": None, "panel_qty": None,
    "inverter_brand": None, "inverter_type": None, "inverter_kw": None, "battery_brand": None, "battery_kwh": None,
    "mounting": None,
    "inclusions": {"net_metering": None, "permits": None, "electrical_upgrade": None, "monitoring": None,
                   "installation": None, "after_sales": None},
    "warranty_years": {"panel_product": None, "panel_performance": None, "inverter": None, "battery": None, "workmanship": None},
    "deposit_pct": None, "timeline_weeks": None, "validity_days": None, "notes": None,
})


RETRY_STATUS = {429, 500, 502, 503, 504}   # free tiers often answer "busy" or "too many requests per minute"
ATTEMPTS = 3
REQUEST_TIMEOUT = 50   # seconds per try
BUDGET = 100           # seconds for all tries together
MAX_WAIT = 20          # longest pause between tries


class ExtractionUnavailable(RuntimeError):
    def __init__(self, msg: str, busy: bool = False):
        super().__init__(msg)
        self.busy = busy   # the service was busy or slow: trying again later may work


def _retry_wait(r: httpx.Response | None, attempt: int) -> float:
    """Seconds to wait before the next try: the service's own hint if it gives one, else a short backoff."""
    hint = None
    if r is not None:
        ra = r.headers.get("retry-after", "")
        if ra.replace(".", "", 1).isdigit():
            hint = float(ra)
        else:
            m = re.search(r"retry(?:Delay)?\D{0,12}?(\d+(?:\.\d+)?)\s*s", r.text, re.I)
            hint = float(m.group(1)) if m else None
    return min(MAX_WAIT, hint if hint is not None else 4.0 * (2 ** attempt))


def _parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in reply")
    return json.loads(m.group(0))


def _clean(d: dict) -> dict:
    """Drop values the model returned in the wrong type, so validation keeps the rest."""
    out = {}
    for k, v in d.items():
        if k not in QuoteFields.model_fields or k == "label":
            continue
        out[k] = v
    for sub in ("inclusions", "warranty_years"):
        if not isinstance(out.get(sub), dict):
            out.pop(sub, None)
    return out


def _error_detail(r: httpx.Response) -> str:
    """Best-effort error message. Providers differ: {"error": {...}}, [{"error": {...}}], or plain text."""
    try:
        body = r.json()
    except ValueError:
        return r.text[:150]
    if isinstance(body, list) and body:
        body = body[0]
    err = body.get("error", body) if isinstance(body, dict) else body
    if isinstance(err, dict):
        return str(err.get("message") or err.get("status") or err.get("type") or "")
    return str(err)


def to_fields(d: dict, label: str) -> QuoteFields:
    d = _clean(d)
    try:
        return QuoteFields(label=label, **d)
    except ValidationError as e:
        bad = {err["loc"][0] for err in e.errors()}
        return QuoteFields(label=label, **{k: v for k, v in d.items() if k not in bad})


def extract(kind: str, data: bytes, text: str, label: str, client: httpx.Client | None = None,
            token: str | None = None) -> QuoteFields:
    """token: per-request Vercel OIDC token (x-vercel-oidc-token header); falls back to AI_GATEWAY_API_KEY."""
    token = token or settings.ai_key
    if not settings.ai_enabled or not token:
        raise ExtractionUnavailable("AI extraction is switched off or has no credentials.")
    if text:
        content = [{"type": "text", "text": f"Quotation text:\n\n{text[:20000]}\n\nReturn JSON with these keys:\n{SCHEMA_HINT}"}]
    else:
        b64 = base64.b64encode(data).decode()
        if kind == "pdf":
            part = {"type": "file", "file": {"filename": "quote.pdf", "file_data": f"data:application/pdf;base64,{b64}"}}
        else:
            part = {"type": "image_url", "image_url": {"url": f"data:image/{kind};base64,{b64}"}}
        content = [part, {"type": "text", "text": f"Read this quotation. Return JSON with these keys:\n{SCHEMA_HINT}"}]
    body = {"model": settings.ai_model, "temperature": 0,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}]}
    if settings.ai_provider == "gemini":
        body["reasoning_effort"] = settings.ai_reasoning_effort   # copying figures needs little "thinking"; keeps replies fast
    headers = {"Authorization": f"Bearer {token}"}
    own = client is None
    client = client or httpx.Client(timeout=REQUEST_TIMEOUT)
    deadline = time.monotonic() + BUDGET
    try:
        last_err, bad_json = None, 0
        for attempt in range(ATTEMPTS):
            r = None
            try:
                r = client.post(f"{settings.ai_base_url}/chat/completions", json=body, headers=headers)
            except httpx.TimeoutException as e:
                last_err = ExtractionUnavailable(f"AI service timed out: {e.__class__.__name__}", busy=True)
            except httpx.HTTPError as e:
                raise ExtractionUnavailable(f"AI service not reachable: {e.__class__.__name__}") from e
            if r is not None and r.status_code in RETRY_STATUS:
                last_err = ExtractionUnavailable(f"AI service returned {r.status_code} {_error_detail(r)[:150]}".strip(), busy=True)
            elif r is not None and r.status_code != 200:
                raise ExtractionUnavailable(f"AI service returned {r.status_code} {_error_detail(r)[:150]}".strip())
            elif r is not None:
                try:
                    reply = r.json()["choices"][0]["message"]["content"]
                    if isinstance(reply, list):
                        reply = "".join(p.get("text", "") for p in reply)
                    return to_fields(_parse_json(reply), label)
                except (KeyError, ValueError, TypeError) as e:
                    bad_json += 1
                    last_err = ExtractionUnavailable(f"AI reply could not be read: {e}")
                    if bad_json >= 2:   # one retry on unreadable JSON
                        break
                    continue
            if attempt == ATTEMPTS - 1:
                break
            wait = _retry_wait(r, attempt)
            if time.monotonic() + wait + REQUEST_TIMEOUT > deadline:   # no time left for another full try
                break
            sleep(wait)
        raise last_err
    finally:
        if own:
            client.close()


sleep = time.sleep   # replaced in tests
