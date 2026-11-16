"""Optional AI extraction of quote fields through the Vercel AI Gateway (OpenAI-compatible API).

The AI only reads the document. It never calculates; every field is shown to the user to confirm.
"""
from __future__ import annotations

import base64
import json
import re

import httpx
from pydantic import ValidationError

from ..config import settings
from ..models import QuoteFields

SYSTEM = """You read Philippine rooftop solar installer quotations and copy facts from them into JSON.
Rules:
- Copy only what the document states. Use null for anything not stated. Never guess, estimate or calculate.
- Prices in PHP as plain numbers (no commas or currency signs). total_price_php is the final total the customer pays.
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


class ExtractionUnavailable(RuntimeError):
    pass


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


def to_fields(d: dict, label: str) -> QuoteFields:
    d = _clean(d)
    try:
        return QuoteFields(label=label, **d)
    except ValidationError as e:
        bad = {err["loc"][0] for err in e.errors()}
        return QuoteFields(label=label, **{k: v for k, v in d.items() if k not in bad})


def extract(kind: str, data: bytes, text: str, label: str, client: httpx.Client | None = None) -> QuoteFields:
    if not settings.ai_enabled:
        raise ExtractionUnavailable("AI extraction is switched off.")
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
    headers = {"Authorization": f"Bearer {settings.ai_key}"}
    own = client is None
    client = client or httpx.Client(timeout=45)
    try:
        last_err = None
        for _ in range(2):   # one retry on unreadable JSON
            try:
                r = client.post(f"{settings.ai_base_url}/chat/completions", json=body, headers=headers)
            except httpx.HTTPError as e:
                raise ExtractionUnavailable(f"AI service not reachable: {e.__class__.__name__}") from e
            if r.status_code != 200:
                raise ExtractionUnavailable(f"AI service returned {r.status_code}")
            try:
                reply = r.json()["choices"][0]["message"]["content"]
                if isinstance(reply, list):
                    reply = "".join(p.get("text", "") for p in reply)
                return to_fields(_parse_json(reply), label)
            except (KeyError, ValueError, TypeError) as e:
                last_err = e
        raise ExtractionUnavailable(f"AI reply could not be read: {last_err}")
    finally:
        if own:
            client.close()
