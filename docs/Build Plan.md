# HomeSolarPH: Build Plan

**Status:** Steps 1-7 code done locally (16 Nov 2026); Step 0 accounts and Step 8 test launch pending · **Date:** 16 Nov 2026 · **Scope:** Stage 1 (test app)

What to build is in the [PRD](PRD.md); how it works is in [specs.md](specs.md). This plan sets the order of work. Each step ends with tests passing, a commit, and a Vercel preview for the owner to check.

---

## Progress (16 Nov 2026)
- Done: skeleton, data files (PVGIS table for 18 regions), calculation engine, solar check pages, installer guide, quote comparison (manual + AI extraction), opt-in sharing, feedback, about page; 57 automated tests pass; checked in a local browser including phone width.
- CI/CD: GitHub Actions workflow (lint, tests, requirements check, smoke test; Vercel preview and production deploys after checks pass) and Dependabot set up.
- To do: Vercel project, the four GitHub secrets/variables for deploys, Neon database, AI Gateway check, review of all values marked verify, engineer review of guide content, test users.

## Step 0 – Accounts and checks (no code)
- Create the Vercel project linked to the private `HomeSolarPH` repo (Hobby plan).
- Register a free NREL developer API key (for the offline yield tool only).
- Confirm on the live services:
  - PVWatts v8 returns data for Philippine coordinates, and which dataset answers; otherwise use PVGIS.
  - Vercel AI Gateway free credit is active on the account, and which free-tier models can read images and PDFs.
  - Neon free tier is available from the Vercel Marketplace.
- Gather current default values for `defaults.json` (rates by provider type, net-metering export credit, installed cost per kWp) with sources and dates.

**Done when:** every **(verify)** item in specs.md has a value and a source, or a decision to leave it out.

## Step 1 – Skeleton and deployment
- `pyproject.toml`, FastAPI app with `/` and `/api/health`, base template and CSS, pytest set up.
- Deploy to Vercel; confirm the FastAPI function and `public/` static files work.
- GitHub Actions running pytest.

**Done when:** the preview URL shows the home page on a phone and `/api/health` responds.

## Step 2 – Data files
- Write `tools/build_yield_table.py`; generate `data/regions.json` for all regions and directions.
- Create `data/defaults.json` from Step 0 values.
- Sanity check: yearly yield per kWp per region within a plausible band, shown in a small report.

**Done when:** both files are committed with source and `as_of` fields; a test checks their structure.

## Step 3 – Calculation engine
- `app/calc/solar.py`: inputs normalization, sizing with caps, monthly energy, savings, cost, payback, low/high cases, verdict band.
- Golden test cases checked by hand in a spreadsheet; property tests.

**Done when:** all tests pass and the golden cases match the spreadsheet within 1%.

## Step 4 – Solar check pages (F1)
- Form page with validation and plain-English help text; results page with ranges, chart, assumptions panel (live recalculation through `/api/solar/estimate`), template explanation, verdict band, disclaimer, copy/print summary.
- Mobile layout check on a small Android screen size.

**Done when:** a first-time user can go from home to results in under 5 minutes without help (test with 2–3 people).

## Step 5 – Installer guide (F2)
- Write guide content in Markdown: questions by topic, red flags, process steps, glossary.
- Render guide pages; show the most relevant questions on the results page; printable checklist.
- Content review by someone with installation or engineering experience.

**Done when:** guide pages render, link from results, and print cleanly.

## Step 6 – Quote comparison (F3)
1. Manual entry form and `/api/quotes/compare` with normalization and flags (works with no AI).
2. File intake: browser image downsizing, PDF text extraction.
3. AI extraction through the AI Gateway, with schema validation, retry and fallback; daily cap.
4. Review screen where users confirm or correct each field; comparison table and flags linked to guide questions.
- Test with dummy quotes only (made-up installers and figures); no real quotes in the repo.

**Done when:** a 3-quote comparison works with AI on and with AI off; extraction errors can always be corrected.

## Step 7 – Opt-in sharing and feedback (F4)
- Add Neon Postgres; apply `db/schema.sql`.
- Consent checkbox (off by default), `/api/share` with reference code, `/api/share/delete`, feedback widget.
- Privacy test: stored rows contain only allowed fields.
- `/about` page: how the app works, neutrality, data rules, privacy notice.

**Done when:** sharing works end to end, deletion works, and the app still runs with the database switched off.

## Step 8 – Hardening and test launch
- Security headers, input limits, error pages, honeypot.
- Check free-tier usage settings and caps (Vercel, AI Gateway, Neon).
- README with setup and deployment notes.
- Small test group (friends and family, then a few r/SolarPH users if appropriate); collect "Was this useful?" feedback.

**Done when:** test users complete both flows; issues logged for the next round.

## Order and dependencies

```
0 ─► 1 ─► 2 ─► 3 ─► 4 ─► 5
                 └──► 6 (needs 3; AI part needs 0)
                        └──► 7 ─► 8
```

Steps 5 (content writing) and 6.1–6.2 can run alongside Step 4 once Step 3 is done.

## Out of scope for this plan
Everything in PRD section 9 Stages 2–4 (batteries, financing, Filipino language, installer directory, accounts, data products, other countries).
