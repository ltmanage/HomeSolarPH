# HomeSolarPH

A free, neutral resource for Philippine homeowners deciding whether to go rooftop solar.

**Status:** Stage 1 test app (v0.1). Runs locally; Vercel deployment pending.

Stage 1 features:
- **Solar check:** sizing, savings and payback ranges from a few bill and roof details, with editable assumptions.
- **Installer guide:** questions to ask, red flags, process steps, glossary.
- **Quote comparison:** upload installer quotes (PDF or photo), confirm the extracted figures, compare side by side with neutral flags.
- **Opt-in anonymous sharing** of figures (region-level only), plus feedback.

Documents: [PRD](docs/PRD.md) · [Technical specification](docs/specs.md) · [Build plan](docs/Build%20Plan.md)

## Run locally

Needs [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run uvicorn index:app --reload --port 8040
```

Open http://localhost:8040. Without AI or database settings the app still works: quotes are typed in, and sharing is hidden.

Tests (57):

```bash
uv run pytest -q
```

## Deploy to Vercel (free Hobby plan)

1. In Vercel, **Add New → Project**, import the `HomeSolarPH` GitHub repository. Framework preset: FastAPI (detected). No build command needed.
2. **AI Gateway (optional, for reading quotes):** enable AI Gateway for the team. The function authenticates with its OIDC token automatically. Optionally set `AI_MODEL` (default `google/gemini-2.5-flash`) and `AI_DAILY_CAP` (default 50).
3. **Database (optional, for sharing and feedback):** add **Neon** from the Vercel Marketplace (free plan) and connect it to the project; it sets `DATABASE_URL`. Run `db/schema.sql` once in the Neon SQL editor.
4. Redeploy. Check `/api/health` shows `ai_enabled` and `sharing_enabled` as expected.

## Data

- `data/regions.json`: monthly solar output per kWp for 18 regions and 5 roof directions, built with `uv run python tools/build_yield_table.py` (PVGIS, no key). `--source pvwatts` uses NREL PVWatts with `NREL_API_KEY`.
- `data/defaults.json`: every assumption with its source and date. Values marked `verify` must be checked before public testing.
- `content/guide/*.md`: installer guide text.

## Privacy

No accounts, names, addresses or contact details. Uploaded files are processed in memory and never stored. Nothing is saved unless the user opts in; opted-in records hold region-level, anonymous figures only (see `homesolar/store.py` and `db/schema.sql`).
