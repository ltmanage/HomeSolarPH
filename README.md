# HomeSolarPH

A free, neutral resource for Philippine homeowners deciding whether to go rooftop solar.

Live test version: https://home-solar-ph.vercel.app

- **Solar check:** system size, savings and payback ranges from a few bill and roof details.
- **Installer guide:** questions to ask, red flags and the steps to net metering.
- **Compare quotes:** upload up to 2 installer quotes and see them side by side with the app's own estimate.

The app never ranks quotes or recommends an installer. It shows ranges, differences and the questions to ask.

## How it works

```
Browser (HTML pages, light JavaScript, Chart.js on the results page)
   │
   ▼
FastAPI app (one Python serverless function on Vercel)
   ├── pages ............ Jinja2 templates; static files served from public/
   ├── calc/ ............ sizing, savings, payback, quote comparison (pure Python)
   ├── quotes/ .......... file checks, PDF text, optional AI reading of quotes
   ├── store.py ......... opt-in anonymous records and feedback ──► Postgres (optional)
   └── ai_extract.py .... quote reading only ──► OpenAI-compatible AI API (optional)

Offline, not at runtime:
   tools/build_yield_table.py ──► PVGIS (EU JRC) ──► data/regions.json
```

- **One app, no frontend build.** Server-rendered pages plus a small JSON API.
- **No solar API at runtime.** Monthly output per kWp is pre-computed for 18 regions and 5 roof directions and kept in `data/regions.json`. No location ever leaves the app.
- **Every assumption in one file.** `data/defaults.json` holds electricity rates, costs per kWp, losses, net-metering credit and flag thresholds, each with a source and date. Most are editable by the user on the results page.
- **Optional services.** Without an AI key, quotes are typed in. Without a database, the sharing option is hidden. The app runs fully without either.

## Main flows

**Solar check.** The form posts to `/check`; inputs are validated and `calc/solar.py` returns a size range, monthly self-use and export, savings, cost and payback as an optimistic and a conservative case. Changing an assumption on the results page calls `/api/solar/estimate` and updates the page in place. Nothing is stored.

**Quote reading.** Photos are downsized in the browser before upload. The server checks the file type by its content (PDF, JPG, PNG or WEBP, up to 4 MB). If the PDF has a text layer, only the text is sent to the AI; otherwise the file itself is. The AI only copies figures into a fixed set of fields; each field is validated, and the user checks and corrects every one. If the AI service is busy, the app retries a few times, then offers **Try reading again**. Typing the figures in always works. Files are never stored.

**Comparison.** Up to 2 quotes, shown as columns next to an **App estimate** column (from the user's solar check, or typical regional prices without one). Figures are normalised (price per watt, price per yearly kWh, warranty totals) and neutral flags list what to check, each with a question to ask. Quotes with no size or price are left out, with a note.

**Leaving a page.** On the results and quote pages, the app asks once about a list of accredited installers (a planned feature), asks before saving any anonymous quote data, and warns before clearing quotes on screen.

## Project layout

| Path | What it holds |
|---|---|
| `index.py` | Entry point for Vercel and local runs |
| `homesolar/main.py` | Routes, security headers, JSON API |
| `homesolar/models.py` | Pydantic request and response models |
| `homesolar/calc/` | Solar estimate and quote comparison (pure functions) |
| `homesolar/quotes/` | File intake, PDF text, AI reading |
| `homesolar/store.py` | Opt-in records, deletion by reference code, feedback, AI daily cap |
| `homesolar/templates/` | Pages |
| `public/static/` | CSS, JavaScript, icon |
| `content/guide/` | Installer guide pages (Markdown) |
| `data/` | `regions.json` (solar output) and `defaults.json` (assumptions) |
| `db/schema.sql` | Tables for the optional database |
| `tools/` | Solar-table builder and a requirements check |
| `tests/` | Automated tests |

## Routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/`, `/check`, `/quotes`, `/guide`, `/guide/{page}`, `/about` | Pages |
| POST | `/check` | Solar check form → results page |
| POST | `/api/solar/estimate` | Recalculate with changed assumptions |
| POST | `/api/quotes/extract` | One file → quote fields to confirm |
| POST | `/api/quotes/compare` | 1–2 confirmed quotes → comparison |
| POST | `/api/share`, `/api/share/delete` | Opt-in anonymous sharing; delete by reference code |
| POST | `/api/feedback` | "Was this useful?" |
| GET | `/api/health` | Version and which optional services are on |

## Privacy and security

- No accounts, cookies or tracking. No names, addresses or contact details are asked for.
- Uploaded files are read in memory and never stored. Installer names stay on the user's screen.
- Anonymous figures are saved only if the user agrees, with region-level location only, and can be deleted with the reference code given at the time.
- Before uploading, users are asked to cover their own name, address and phone number, since the AI service is a third party.
- Strict Content Security Policy (no inline scripts), `no-referrer`, no framing; inputs validated; file types checked by content; a daily cap on AI calls.

## Run locally

Needs [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run uvicorn index:app --reload --port 8040
```

Then open http://localhost:8040.

## Configuration

All optional. Copy `.env.example` to `.env` locally, or set them as environment variables on the host.

| Variable | Effect |
|---|---|
| `GEMINI_API_KEY` | Turns on automatic quote reading |
| `AI_MODEL` | Overrides the default model |
| `AI_DAILY_CAP` | Most AI calls per day (default 50; counted in the database if there is one, otherwise per server instance) |
| `AI_ENABLED` | `false` switches quote reading off |
| `DATABASE_URL` | Postgres connection string for opt-in sharing and feedback (tables in `db/schema.sql`) |
| `SHARING_ENABLED` | `false` hides sharing even with a database |

## Tests and deployment

```bash
uv run pytest -q
uv run ruff check .
```

GitHub Actions (`.github/workflows/ci-cd.yml`) runs on every push and pull request: lint, tests, a check that `requirements.txt` matches `uv.lock`, and a smoke test that starts the app and loads every page. Only after these pass does it deploy to Vercel (pull requests to a preview, `main` to production) and check `/api/health` on the live site. Vercel's own Git deploys are switched off in `vercel.json`. Dependabot proposes dependency updates weekly.

After changing dependencies, regenerate `requirements.txt` (Vercel installs from it), then remove the `-e .` line:

```bash
uv export --no-dev --no-hashes --format requirements-txt -o requirements.txt
```

## Updating the solar data

```bash
uv run python tools/build_yield_table.py
```

This queries PVGIS (no key needed) for each region and roof direction and rewrites `data/regions.json`. Commit the result; the app never calls PVGIS at runtime.

## Known limitations

- Estimates are indicative. Some defaults (net-metering credit, rates outside Meralco, hybrid costs) should be checked against current rate notices and installer prices.
- Monthly use is treated as flat across the year, and self-use is a simple monthly share rather than an hourly model.
- On a free AI tier, reading can be slow (photos about 20 s) or busy, needing "Try reading again".
- The leave-page questions run only when following links in the app, not when closing the tab.
- English only.
