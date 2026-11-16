"""HomeSolarPH web app: pages and JSON API."""
from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from . import __version__, guide, store
from .calc.quotes import compare
from .calc.solar import estimate
from .config import ROOT, defaults, regions, settings
from .explain import explain, relevant_questions
from .models import CompareRequest, FeedbackRequest, QuoteFields, ShareRequest, SolarInput
from .quotes import ai_extract, intake

app = FastAPI(title="HomeSolarPH", version=__version__, docs_url=None, redoc_url=None)
# On Vercel, public/ is served by the CDN and is not inside the Python function, so only mount it when present (local runs).
STATIC_DIR = ROOT / "public" / "static"
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=ROOT / "homesolar" / "templates")
templates.env.globals.update(version=__version__, as_of=lambda: defaults()["as_of"])
templates.env.filters["php"] = lambda x: "-" if x is None else f"PHP {x:,.0f}"
templates.env.filters["num"] = lambda x, d=1: "-" if x is None else f"{x:,.{d}f}"

CSP = ("default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; style-src 'self'; img-src 'self' data:; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["Content-Security-Policy"] = CSP
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "DENY"
    return resp


def region_options():
    return [(r["code"], r["name"]) for r in regions()["regions"]]


def page(request: Request, name: str, **ctx):
    return templates.TemplateResponse(request, name, {"regions": region_options(), "settings": settings, **ctx})


# ---------- pages ----------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return page(request, "home.html")


@app.get("/check", response_class=HTMLResponse)
def check_form(request: Request):
    return page(request, "check.html", values={}, errors=[])


def form_to_input(form) -> dict:
    data = {k: v for k, v in form.items() if k != "website" and str(v).strip() != ""}
    for k in ("bill_php", "kwh_month", "roof_area_m2", "budget_php"):
        if k in data:
            data[k] = str(data[k]).replace(",", "")
    return data


@app.post("/check", response_class=HTMLResponse)
async def check_submit(request: Request):
    form = await request.form()
    data = form_to_input(form)
    try:
        inp = SolarInput(**data)
        e = estimate(inp)
    except (ValidationError, ValueError) as err:
        msgs = ([f"{x['loc'][-1]}: {x['msg']}" for x in err.errors()] if isinstance(err, ValidationError) else [str(err)])
        return page(request, "check.html", values=data, errors=msgs)
    return page(request, "results.html", inp=inp, e=e, ex=explain(inp, e), questions=relevant_questions(inp),
                inp_json=inp.model_dump_json(), e_json=e.model_dump_json())


@app.get("/guide", response_class=HTMLResponse)
def guide_index(request: Request):
    return page(request, "guide_index.html", pages=guide.pages())


@app.get("/guide/{slug}", response_class=HTMLResponse)
def guide_page(request: Request, slug: str):
    p = guide.page(slug)
    if not p:
        raise HTTPException(404)
    return page(request, "guide_page.html", p=p, pages=guide.pages())


@app.get("/quotes", response_class=HTMLResponse)
def quotes_page(request: Request):
    return page(request, "quotes.html")


@app.get("/about", response_class=HTMLResponse)
def about(request: Request):
    return page(request, "about.html", d=defaults(), yield_source=regions()["source"])


# ---------- API ----------
@app.post("/api/solar/estimate")
def api_estimate(inp: SolarInput):
    try:
        e = estimate(inp)
    except ValueError as err:
        raise HTTPException(422, str(err)) from err
    return {"estimate": e.model_dump(), "explain": explain(inp, e)}


@app.post("/api/quotes/extract")
async def api_extract(request: Request, file: UploadFile = File(...), label: str = Form("Quote")):
    data = await file.read(intake.MAX_BYTES + 1)
    await file.close()
    try:
        kind = intake.check(data)
    except intake.IntakeError as err:
        raise HTTPException(400, str(err)) from err
    text = intake.pdf_text(data) if kind == "pdf" else ""
    label = label[:40] or "Quote"
    if not settings.ai_enabled:
        return {"source": "manual", "fields": QuoteFields(label=label).model_dump(), "text": text[:6000],
                "message": "Automatic reading is not available. Please type the key figures from your quote."}
    if not store.ai_call_allowed():
        return {"source": "manual", "fields": QuoteFields(label=label).model_dump(), "text": text[:6000],
                "message": "Automatic reading has reached today's limit. Please type the key figures from your quote."}
    try:
        oidc = request.headers.get("x-vercel-oidc-token") if settings.ai_provider == "gateway" else None
        fields = ai_extract.extract(kind, data, text, label, token=oidc)
    except ai_extract.ExtractionUnavailable as err:
        print(f"AI extraction unavailable: {err}")   # visible in Vercel function logs
        return {"source": "manual", "fields": QuoteFields(label=label).model_dump(), "text": text[:6000],
                "message": ("The free reading service is busy right now. Wait a minute and press “Try reading again”, "
                            "or type the key figures from your quote." if err.busy else
                            "We could not read this file automatically. Please type the key figures from your quote."),
                "retry": err.busy, "reason": str(err)[:200]}
    finally:
        del data   # the file is never stored
    return {"source": "ai_text" if text else "ai_image", "fields": fields.model_dump(), "text": "",
            "message": "Please check every field against your quote and correct anything that is wrong or missing."}


@app.post("/api/quotes/compare")
def api_compare(req: CompareRequest):
    try:
        return compare(req).model_dump()
    except ValueError as err:
        raise HTTPException(422, str(err)) from err


@app.post("/api/share")
def api_share(req: ShareRequest):
    if not settings.sharing_enabled:
        raise HTTPException(503, "Sharing is not available at the moment.")
    if not req.consent:
        raise HTTPException(400, "Consent is required.")
    try:
        ref = store.save_share(req)
    except Exception:
        raise HTTPException(503, "Could not save right now. Nothing was stored.") from None
    return {"ref_code": ref}


@app.post("/api/share/delete")
def api_share_delete(payload: dict):
    ref = str(payload.get("ref_code", ""))[:20]
    if not settings.sharing_enabled or not ref:
        raise HTTPException(400, "Reference code required.")
    try:
        ok = store.delete_share(ref)
    except Exception:
        raise HTTPException(503, "Could not delete right now. Please try again later.") from None
    return {"deleted": ok}


@app.post("/api/feedback")
def api_feedback(fb: FeedbackRequest):
    if fb.website:   # honeypot filled: silently ignore
        return {"ok": True}
    if settings.database_url:
        try:
            store.save_feedback(fb)
        except Exception:
            pass
    return {"ok": True}


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__, "defaults_as_of": defaults()["as_of"],
            "yield_table": regions().get("generated"), "ai_enabled": settings.ai_enabled, "ai_provider": settings.ai_provider, "ai_model": settings.ai_model,
            "sharing_enabled": settings.sharing_enabled}


@app.exception_handler(404)
async def not_found(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    resp = page(request, "error.html", message="Page not found.")
    resp.status_code = 404
    return resp
