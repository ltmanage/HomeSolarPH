# HomeSolarPH: Technical Specification

**Status:** v0.1, Stage 1 implemented · **Date:** 16 Nov 2026 · **Scope:** Stage 1 (test app)

This document gives the technical detail behind the [PRD](PRD.md). The build sequence is in [Build Plan.md](Build%20Plan.md). Values marked **(verify)** are placeholders to confirm before public testing.

---

## 1. Architecture

```
Browser (mobile-first HTML + light JS + Chart.js)
   │  form posts / fetch JSON
   ▼
Vercel ── FastAPI app (one Python serverless function)
   ├── pages (Jinja2 templates)           ── static files: public/
   ├── calc/      sizing, savings, payback, quote normalization (pure Python)
   ├── quotes/    file intake, PDF text extraction, optional AI extraction
   ├── content/   installer guide (Markdown), defaults and regions (JSON)
   └── store/     opt-in records, feedback  ──►  Postgres (Neon, Vercel Marketplace free tier)
                       │
                       └── optional AI calls ──►  Vercel AI Gateway (free monthly credits)

Offline (developer machine, not at runtime):
   tools/build_yield_table.py ──► EU JRC PVGIS 5.3 (cross-check: NREL/NLR PVWatts v8) ──► data/regions.json
```

Design choices:
- **One FastAPI function** serves pages and JSON. No separate frontend build.
- **No runtime solar API call.** Regional yields are pre-computed and stored in the repo, so the app never sends a location anywhere and has no API-key or rate-limit dependency at runtime.
- **Stateless server.** Form inputs and results live in the browser (`sessionStorage`) and in the request; nothing is kept server-side unless the user opts in.
- **Graceful degradation.** `AI_ENABLED=false` → manual quote entry and template text. `DATABASE_URL` missing → the sharing option is hidden.

## 2. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.12 | Pinned in `.python-version`; supported by Vercel's Python runtime |
| Web framework | FastAPI + Jinja2 | Vercel detects FastAPI and runs it as a Python function |
| Validation | Pydantic v2 | All inputs and outputs typed |
| Frontend | Server-rendered HTML, vanilla JS, Chart.js (CDN, pinned version) | No build step; small CSS file, mobile-first |
| PDF text | `pypdf` | Text-based PDFs parsed without AI |
| AI (optional) | Vercel AI Gateway (OpenAI-compatible endpoint) via `httpx` | Free-tier vision-capable model; model name in env var |
| Database | Postgres (Neon via Vercel Marketplace, free tier) via `psycopg` | Opt-in records and feedback only |
| Tests | `pytest`, FastAPI `TestClient` | No network calls in tests |
| Packaging | `uv` + `pyproject.toml`; `requirements.txt` exported for Vercel if needed | |
| Hosting | Vercel Hobby plan | Test/non-commercial use only |

## 3. Repository layout

```
HomeSolarPH/
├── index.py                 Vercel entry point (imports the FastAPI app)
├── homesolar/
│   ├── main.py              FastAPI app, routes, template setup
│   ├── config.py            env vars, feature flags
│   ├── models.py            Pydantic request/response models
│   ├── calc/
│   │   ├── solar.py         sizing, generation, savings, payback
│   │   └── quotes.py        normalization and flag rules
│   ├── quotes/
│   │   ├── intake.py        file checks, PDF text extraction
│   │   └── ai_extract.py    AI Gateway call, JSON schema, parsing
│   ├── explain.py           template explanations (+ optional AI rewording)
│   ├── store.py             DB access (opt-in records, feedback)
│   └── templates/           Jinja2 pages
├── content/guide/           installer guide Markdown files
├── data/
│   ├── regions.json         region list + monthly yield per kWp
│   └── defaults.json        rates, costs, factors, thresholds, "as_of" dates
├── public/                  CSS, JS, icons (served by Vercel)
├── tools/build_yield_table.py
├── db/schema.sql
├── tests/
├── docs/  PRD.md · specs.md · Build Plan.md
├── pyproject.toml · vercel.json (only if needed) · README.md · .env.example
```

## 4. Data files

### 4.1 `data/regions.json`
One entry per administrative region (NCR, CAR, I, II, III, IV-A, MIMAROPA, V, VI, NIR, VII, VIII, IX, X, XI, XII, Caraga, BARMM). Each entry has a representative coordinate (a main population centre, used only offline), and monthly AC yield in kWh per kWp for each roof direction:

```json
{
  "source": "EU JRC PVGIS 5.3 (ERA5 weather data), tilt 10°, losses 14%",
  "generated": "2026-11-xx",
  "regions": [
    { "code": "NCR", "name": "National Capital Region",
      "yield_kwh_per_kwp": { "south": [12 monthly values], "east": [...], "west": [...],
                             "north": [...], "flat": [...] } }
  ]
}
```

`tools/build_yield_table.py` calls the PVGIS 5.3 `PVcalc` API (ERA5 weather data, no key needed) with 1 kWp, losses 14%, the region coordinate, tilt 10° and aspects south/east/west/north (flat: tilt 0), and writes 12 monthly values per direction. Cross-check (16 Nov 2026): NREL PVWatts v8, now served at `developer.nlr.gov` after NREL became the National Laboratory of the Rockies, covers the Philippines with NSRDB Himawari data and gives about 5% less for Metro Manila (1,264 vs 1,328 kWh/kWp/yr); the conservative case (0.9x output) covers this. `--source pvwatts` rebuilds the table from PVWatts; this needs a free personal key in `NREL_API_KEY` (the shared DEMO_KEY is rate-limited after a few calls). The key is used only by this tool, never by the deployed app.

### 4.2 `data/defaults.json`
All assumptions live here, each with a value, a short label shown to users, and an `as_of` date. Users can override most of them in the assumptions panel.

| Key | Meaning | Initial value |
|---|---|---|
| `rate_per_kwh.meralco` / `.private_du` / `.coop` | Default all-in rate if kWh not given | (verify from current rate notices) |
| `avoidable_share` | Share of the per-kWh rate saved by self-consumed solar | 0.95 (verify) |
| `export_credit_per_kwh` | Net-metering credit for exported kWh, by provider type | (verify; generation-charge based) |
| `self_use_share` | Share of use during solar hours: evening / mixed / daytime | 0.30 / 0.50 / 0.70 |
| `shading_factor` | none / light / moderate / heavy / not sure | 1.00 / 0.95 / 0.85 / 0.70 / 0.90 |
| `m2_per_kwp` | Roof area needed per kWp incl. spacing | 6.5 (verify) |
| `cost_per_kwp_php` | Installed grid-tie cost range, low–high | 40,000–60,000 (verify) |
| `tariff_escalation` | Yearly rate increase, low–high | 0%–4% |
| `degradation` | Panel output loss per year | 0.5% |
| `inverter_replacement` | Year and cost share | year 12, 15% of system cost (verify) |
| `verdict_bands` | Payback (high end) for strong / reasonable | ≤ 6 yr / ≤ 9 yr |
| `quote_flags` | Thresholds for F3 flags (section 6.3) | see section 6.3 |

## 5. Calculation model (F1)

All functions live in `homesolar/calc/solar.py`, take Pydantic models, return Pydantic models, and are deterministic.

**Inputs normalized**
- `kwh_month` = user kWh, else `bill / rate_default[provider]` (flag "estimated from bill").
- `rate` = `bill / kwh_month` when both given (effective rate), else default.
- Monthly use is treated as flat across the year in Stage 1 (seasonal profile is a Stage 2 option).

**Yield**
- `Y[m]` = `regions[region].yield[direction][m] × shading_factor` (kWh per kWp in month m).
- `Y_year` = Σ `Y[m]`.

**Sizing (kWp)**
- `S_day` = `self_use_share × kwh_month × 12 / Y_year` (covers daytime use only).
- `S_full` = `kwh_month × 12 / Y_year` (offsets all yearly use).
- Suggested range: with net metering → `[S_day, S_full]`; without → `[0.8 × S_day, S_day]`.
- Caps: roof `area / m2_per_kwp`; budget `budget / cost_high`. Apply the lowest cap; report which limit applied.
- Round to 0.5 kWp; minimum 1 kWp. The point estimate used for charts is the range midpoint.

**Monthly energy and savings** (for a size S)
- `gen[m]` = `S × Y[m]`.
- `self[m]` = `min(gen[m], self_use_share × kwh_month)`.
- `export[m]` = `gen[m] − self[m]`.
- `saving[m]` = `self[m] × rate × avoidable_share + export[m] × export_credit` (export credit = 0 without net metering).
- Yearly saving is capped so the bill cannot fall below the provider's fixed charges (verify typical minimum).

**Cost and payback**
- `cost_low/high` = `S × cost_per_kwp_low/high`.
- Year-by-year for 25 years: savings × `(1 + escalation)^(y−1)` × `(1 − degradation)^(y−1)`; subtract inverter replacement in its year.
- Payback = first year cumulative savings ≥ cost (interpolated to 0.1 year).
- **Low/high case:** optimistic = cost low, escalation high, yield +5%; conservative = cost high, escalation low, yield −10%.
- Verdict band from the conservative payback.

**Outputs** (`SolarEstimate`): size range and limiting factor, monthly gen/use/self/export arrays, yearly generation, bill before/after, yearly savings low–high, cost low–high, payback low–high, 25-year net savings low–high, verdict band, list of assumptions used (key, label, value, source, as_of), list of warnings (e.g. "kWh estimated from bill").

## 6. Quote comparison (F3)

### 6.1 Intake (`homesolar/quotes/intake.py`)
- Accept PDF, JPG, PNG, HEIC→JPG (browser converts); max 4 files per comparison, one file per request.
- Vercel request bodies are limited (about 4.5 MB), so the browser downsizes images to ~1600 px longest side, JPEG quality 0.8, before upload; server rejects > 4 MB.
- Files are read into memory, never written to disk or storage, and dropped after the response.
- PDF with a text layer → extract text with `pypdf`, then send **text only** to AI (cheaper). Scanned PDF or photo → send the image to AI (first 3 pages max).

### 6.2 Extraction (`homesolar/quotes/ai_extract.py`)
- Calls the Vercel AI Gateway OpenAI-compatible chat endpoint (`https://ai-gateway.vercel.sh/v1`) with a vision-capable model from the free tier (`AI_MODEL`, chosen at build time). On Vercel the function authenticates with the project's OIDC token; locally with `AI_GATEWAY_API_KEY`.
- Prompt asks for JSON matching the `QuoteFields` schema, `null` for anything not stated, and never to guess or calculate. Response validated with Pydantic; invalid JSON → one retry, then manual entry.
- Installer name is extracted only for display on the user's screen; it is excluded from anything stored.
- If AI is disabled, out of credit or fails, the user gets the empty manual form with a short message. The text layer (if any) is shown beside the form to help typing.
- A global daily cap (`AI_DAILY_CAP`, counted in the database when available) protects the free credit.

`QuoteFields`: label (user-editable, e.g. "Quote A"), installer_name (display only), system_type, kwp, total_price_php, vat_included, panel_brand, panel_model, panel_watt, panel_qty, inverter_brand, inverter_type, inverter_kw, battery_brand, battery_kwh, mounting, inclusions{net_metering, permits, electrical_upgrade, monitoring, installation, after_sales}, warranty_years{panel_product, panel_performance, inverter, battery, workmanship}, deposit_pct, timeline_weeks, validity_days, notes.

### 6.3 Normalization and flags (`homesolar/calc/quotes.py`)
- Consistency checks: `panel_watt × panel_qty / 1000` vs stated kWp (> 5% difference → flag).
- `price_per_wp` = total incl. VAT / (kWp × 1000). VAT-exclusive prices are grossed up at 12% and labelled.
- Expected yearly generation from the user's region/direction (or region default) → `price_per_annual_kwh`, savings and payback using section 5.
- Flags (thresholds in `defaults.json`, each linked to a guide question):
  | Flag | Rule |
  |---|---|
  | High price per Wp | above `cost_per_kwp` high for its system type (verify per type) |
  | Unusually low price | below `cost_per_kwp` low by > 20% — ask what is excluded |
  | Oversized | kWp > 1.3 × user's `S_full` (when F1 inputs exist) |
  | Missing inclusion | any inclusion not stated |
  | Short workmanship warranty | < 2 years (verify) |
  | High deposit | deposit > 50% |
  | Size mismatch | panel maths ≠ stated kWp |
  | Battery without need | battery quoted, user chose net metering and mostly daytime use — ask why |
- No ranking or "best quote" output.

## 7. Routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Home: what the app does, two entry buttons |
| GET | `/check` | Solar check form |
| POST | `/check` | Validates form, renders results page |
| POST | `/api/solar/estimate` | JSON: recompute when assumptions change (debounced 300 ms) |
| GET | `/guide`, `/guide/{section}` | Installer guide pages (rendered Markdown) |
| GET | `/quotes` | Quote comparison page |
| POST | `/api/quotes/extract` | Multipart, one file → `QuoteFields` (+ `source: ai|text|manual`) |
| POST | `/api/quotes/compare` | JSON list of confirmed `QuoteFields` (+ optional F1 inputs) → comparison |
| POST | `/api/share` | Opt-in anonymous record → reference code |
| POST | `/api/share/delete` | Reference code → deletes the record |
| POST | `/api/feedback` | Useful yes/no + optional comment (comment length-limited, no contact fields) |
| GET | `/about` | How the app works, data rules, who pays |
| GET | `/api/health` | Status, data `as_of` dates, flags for AI and DB |

## 8. Database (opt-in only)

`db/schema.sql` (Postgres):

```sql
create table submission (
  id            uuid primary key default gen_random_uuid(),
  ref_code      text unique not null,          -- random 10-char code shown to user
  kind          text not null check (kind in ('check','quotes')),
  submitted_ym  char(7) not null,              -- 'YYYY-MM' only, no timestamp
  consent_ver   text not null,
  app_ver       text not null
);
create table check_record (
  submission_id uuid primary key references submission(id) on delete cascade,
  region text, provider_type text, bill_php numeric, kwh_month numeric, kwh_estimated boolean,
  daytime_band text, home_type text, roof_type text, roof_area_band text,
  direction text, shading text, net_metering text, budget_band text,
  size_low numeric, size_high numeric, payback_low numeric, payback_high numeric
);
create table quote_record (
  id uuid primary key default gen_random_uuid(),
  submission_id uuid references submission(id) on delete cascade,
  region text, system_type text, kwp numeric, total_price_php numeric, vat_included boolean,
  price_per_wp numeric, panel_brand text, panel_watt int, panel_qty int,
  inverter_brand text, inverter_type text, inverter_kw numeric,
  battery_brand text, battery_kwh numeric, mounting text,
  incl_net_metering boolean, incl_permits boolean, incl_electrical boolean,
  incl_monitoring boolean, incl_installation boolean, incl_after_sales boolean,
  w_panel_product int, w_panel_perf int, w_inverter int, w_battery int, w_workmanship int,
  deposit_pct numeric, timeline_weeks numeric, extraction_source text, fields_corrected int
);
create table feedback (
  id uuid primary key default gen_random_uuid(),
  page text, useful boolean, comment text, submitted_ym char(7)
);
create table ai_usage (day date primary key, calls int not null default 0);
```

Rules: no names, addresses, city/barangay, contact details, IP addresses, installer names or files. Roof area and budget stored as bands. Free-text `notes` from quotes is never stored. Aggregates (Stage 2) shown only for groups of 5 or more.

## 9. Explanations and text

- `homesolar/explain.py` builds explanations from templates keyed on the result (limiting factor, verdict band, warnings, net-metering choice). This always works and costs nothing.
- Optional AI rewording (behind `AI_EXPLAIN_ENABLED`; **not implemented in v0.1**, template text only) would receive only the computed result object and is instructed not to change or add numbers; output is checked so every number in it appears in the result, otherwise the template text is used.

## 10. Configuration

`.env.example`:
```
AI_ENABLED=true
AI_EXPLAIN_ENABLED=false
AI_MODEL=<free-tier vision model id>
AI_GATEWAY_API_KEY=            # local only; on Vercel use OIDC
AI_DAILY_CAP=50
DATABASE_URL=                  # set by the Neon integration on Vercel
SHARING_ENABLED=true
NREL_API_KEY=                  # tools/ only, never deployed
```

## 11. Security and privacy

- Secrets only in Vercel environment variables; nothing secret in the frontend.
- Input validation on every field (ranges, enums, string lengths). Upload type checked by content, not extension.
- No cookies are needed; no third-party analytics. Vercel Web Analytics (cookie-less, aggregate) is acceptable if wanted.
- Security headers: CSP limited to self and the pinned Chart.js CDN, `X-Content-Type-Options`, `Referrer-Policy: no-referrer`.
- Abuse: file size/count limits, AI daily cap, simple honeypot field on forms. Vercel Firewall rules if needed.
- Data Privacy Act of 2012: consent text versioned (`consent_ver`); deletion by reference code; privacy notice on `/about`.

## 12. Testing

- **Unit:** `calc/solar.py` and `calc/quotes.py` with golden cases (e.g. NCR, PHP 8,000 bill, mixed use, net metering) whose expected values are hand-checked in a spreadsheet.
- **Property checks:** savings never negative; bigger system never lowers generation; payback low ≤ high.
- **API:** every route via `TestClient`; extraction tested with stubbed AI responses and sample dummy quotes (no real quotes in the repo).
- **Privacy test:** assert that stored records contain no fields outside the allowed list.
- CI: GitHub Actions (see section 15).

## 13. Performance and limits

- Pages < 200 KB excluding the chart library; first result under 1 s server time (no external calls).
- AI extraction target under 20 s; the UI shows progress and allows manual entry meanwhile.
- Free-tier limits to watch: Vercel Hobby function invocations and duration, AI Gateway monthly credit, Neon storage/compute hours.

## 14. Deployment

- Vercel project linked to the GitHub `HomeSolarPH` repository (private). Vercel's own Git auto-deploys are switched off in `vercel.json` (`git.deploymentEnabled: false`); **GitHub Actions does all deploying** (section 15), so nothing reaches production without passing the checks.
- Neon Postgres added from the Vercel Marketplace; `db/schema.sql` applied once.
- AI Gateway enabled for the Vercel team; OIDC used by the function.
- Vercel only during the test stage; no other hosts.

## 15. CI/CD (GitHub Actions)

Workflow: `.github/workflows/ci-cd.yml`.

| Job | Runs on | What it does |
|---|---|---|
| `checks` | every push, pull request, manual run | `uv sync --locked`; ruff lint; pytest; `tools/check_requirements.sh` (Vercel's `requirements.txt` must match `uv.lock`); smoke test that starts the app, loads every page and runs one solar check |
| `deploy-preview` | pull requests, after `checks` passes | Vercel CLI (pinned version) deploys a preview; URL written to the run summary |
| `deploy-production` | push to `main`, after `checks` passes | Vercel CLI deploys to production (GitHub environment `production`, one deploy at a time); then calls `PRODUCTION_URL/api/health` and fails if it is not `ok` |

Deploy jobs skip themselves (with a notice) until these are set in GitHub → Settings → Secrets and variables → Actions:

| Name | Type | Where to get it |
|---|---|---|
| `VERCEL_TOKEN` | secret | Vercel → Account Settings → Tokens (scope: the team that owns the project) |
| `VERCEL_ORG_ID` | secret | Vercel project → Settings → General ("Team ID"), or `.vercel/project.json` after `vercel link` |
| `VERCEL_PROJECT_ID` | secret | Vercel project → Settings → General ("Project ID") |
| `PRODUCTION_URL` | variable | The production address, e.g. `https://<project>.vercel.app` |

Other rules:
- **Dependabot** (`.github/dependabot.yml`) opens weekly grouped pull requests for Python packages (`uv`) and GitHub Actions. Dependabot pull requests get no secrets, so they run checks only. When a Python update changes `uv.lock`, regenerate `requirements.txt` on that branch (the check prints the command).
- Pull requests from forks get no secrets either, so they never deploy.
- Branch protection (require `checks` before merging to `main`) needs a paid GitHub plan for private repositories; it can be switched on free once the repository is public.
- Actions minutes: a full run takes about 1–2 minutes, well inside the free monthly allowance for private repositories.
