"""Opt-in anonymous records and feedback (Postgres). Only the fields listed here are ever stored."""
from __future__ import annotations

import datetime
import secrets
import string
import threading

from . import __version__
from .calc.quotes import price_incl_vat
from .calc.solar import estimate
from .config import region_map, settings
from .models import FeedbackRequest, ShareRequest

CONSENT_VERSION = "2026-11-v1"
ALPHABET = string.ascii_uppercase.replace("O", "").replace("I", "") + "23456789"

CHECK_FIELDS = ["region", "provider_type", "bill_php", "kwh_month", "kwh_estimated", "daytime_band", "home_type",
                "roof_type", "roof_area_band", "direction", "shading", "net_metering", "budget_band",
                "size_low", "size_high", "payback_low", "payback_high"]
QUOTE_FIELDS = ["region", "system_type", "kwp", "total_price_php", "vat_included", "price_per_wp", "panel_brand",
                "panel_watt", "panel_qty", "inverter_brand", "inverter_type", "inverter_kw", "battery_brand",
                "battery_kwh", "mounting", "incl_net_metering", "incl_permits", "incl_electrical", "incl_monitoring",
                "incl_installation", "incl_after_sales", "w_panel_product", "w_panel_perf", "w_inverter", "w_battery",
                "w_workmanship", "deposit_pct", "timeline_weeks", "extraction_source", "fields_corrected"]

_mem_ai = {"day": None, "calls": 0}
_lock = threading.Lock()


def band(x: float | None, edges: list[float], unit: str) -> str | None:
    if x is None:
        return None
    for lo, hi in zip(edges, edges[1:], strict=False):
        if x < hi:
            return f"{lo:g}-{hi:g} {unit}"
    return f"{edges[-1]:g}+ {unit}"


ROOF_EDGES = [0, 20, 40, 60, 100, 200]
BUDGET_EDGES = [0, 100000, 200000, 300000, 500000, 1000000]


def check_row(req: ShareRequest) -> dict | None:
    s = req.solar
    if not s:
        return None
    e = estimate(s)
    return {
        "region": s.region, "provider_type": s.provider, "bill_php": round(s.bill_php), "kwh_month": e.kwh_month,
        "kwh_estimated": e.kwh_estimated, "daytime_band": s.daytime, "home_type": s.home_type, "roof_type": s.roof_type,
        "roof_area_band": band(s.roof_area_m2, ROOF_EDGES, "m2"), "direction": s.direction, "shading": s.shading,
        "net_metering": s.net_metering, "budget_band": band(s.budget_php, BUDGET_EDGES, "PHP"),
        "size_low": e.size_low_kwp, "size_high": e.size_high_kwp,
        "payback_low": e.optimistic.payback_years, "payback_high": e.conservative.payback_years,
    }


def quote_rows(req: ShareRequest) -> list[dict]:
    rows = []
    region = req.solar.region if req.solar else (req.region if req.region in region_map() else None)
    for i, q in enumerate(req.quotes):
        price = price_incl_vat(q)
        kwp = q.kwp or (q.panel_watt * q.panel_qty / 1000 if q.panel_watt and q.panel_qty else None)
        inc, w = q.inclusions, q.warranty_years
        rows.append({   # installer_name and notes are deliberately not stored
            "region": region, "system_type": q.system_type, "kwp": kwp, "total_price_php": q.total_price_php,
            "vat_included": q.vat_included, "price_per_wp": round(price / (kwp * 1000), 2) if price and kwp else None,
            "panel_brand": q.panel_brand, "panel_watt": q.panel_watt, "panel_qty": q.panel_qty,
            "inverter_brand": q.inverter_brand, "inverter_type": q.inverter_type, "inverter_kw": q.inverter_kw,
            "battery_brand": q.battery_brand, "battery_kwh": q.battery_kwh, "mounting": q.mounting,
            "incl_net_metering": inc.net_metering, "incl_permits": inc.permits, "incl_electrical": inc.electrical_upgrade,
            "incl_monitoring": inc.monitoring, "incl_installation": inc.installation, "incl_after_sales": inc.after_sales,
            "w_panel_product": w.panel_product, "w_panel_perf": w.panel_performance, "w_inverter": w.inverter,
            "w_battery": w.battery, "w_workmanship": w.workmanship, "deposit_pct": q.deposit_pct,
            "timeline_weeks": q.timeline_weeks,
            "extraction_source": req.extraction_source[i] if i < len(req.extraction_source) else None,
            "fields_corrected": req.fields_corrected[i] if i < len(req.fields_corrected) else None,
        })
    return rows


def _connect():
    import psycopg
    return psycopg.connect(settings.database_url, connect_timeout=8)


def _insert(cur, table: str, row: dict, allowed: list[str]):
    cols = [c for c in allowed if c in row]
    assert set(row) <= set(allowed) | {"submission_id"}, "unexpected field"
    cols = (["submission_id"] if "submission_id" in row else []) + cols
    cur.execute(f"insert into {table} ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))})",
                [row[c] for c in cols])


def new_ref() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(10))


def ym() -> str:
    return datetime.date.today().strftime("%Y-%m")


def save_share(req: ShareRequest) -> str:
    if not req.consent:
        raise ValueError("Consent is required.")
    ref = new_ref()
    crow, qrows = check_row(req), quote_rows(req)
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("insert into submission (ref_code, kind, submitted_ym, consent_ver, app_ver) values (%s,%s,%s,%s,%s) returning id",
                    (ref, req.kind, ym(), CONSENT_VERSION, __version__))
        sid = cur.fetchone()[0]
        if crow:
            _insert(cur, "check_record", {"submission_id": sid, **crow}, CHECK_FIELDS)
        for r in qrows:
            _insert(cur, "quote_record", {"submission_id": sid, **r}, QUOTE_FIELDS)
    return ref


def delete_share(ref: str) -> bool:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("delete from submission where ref_code = %s", (ref.strip().upper(),))
        return cur.rowcount > 0


def save_feedback(fb: FeedbackRequest) -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("insert into feedback (page, useful, comment, submitted_ym) values (%s,%s,%s,%s)",
                    (fb.page, fb.useful, (fb.comment or "")[:500] or None, ym()))


def ai_call_allowed() -> bool:
    """Count today's AI calls against the daily cap (database if available, else per-instance memory)."""
    cap, today = settings.ai_daily_cap, datetime.date.today()
    if settings.database_url:
        try:
            with _connect() as conn, conn.cursor() as cur:
                cur.execute("insert into ai_usage (day, calls) values (%s, 1) on conflict (day) do update "
                            "set calls = ai_usage.calls + 1 returning calls", (today,))
                return cur.fetchone()[0] <= cap
        except Exception:
            pass
    with _lock:
        if _mem_ai["day"] != today:
            _mem_ai.update(day=today, calls=0)
        _mem_ai["calls"] += 1
        return _mem_ai["calls"] <= cap
