# HomeSolarPH: Product Requirements Document

**Status:** Draft v0.1 for review · **Date:** 16 Nov 2026 · **Stage:** Test app (Stage 1)

Companion documents: [specs.md](specs.md) (technical detail) and [Build Plan.md](Build%20Plan.md) (build sequence). This PRD describes *what* the product is and does; it does not cover how or when it is built.

---

## 1. Purpose

HomeSolarPH is a free, neutral resource for Philippine homeowners deciding whether to install rooftop solar. It turns a few details from the homeowner's electricity bill and roof into an indicative system size, a savings and payback range, and a checklist of questions for installers. It also helps homeowners compare installer quotes side by side.

The app does not sell systems, recommend specific installers or brands, or replace a professional site survey. Its job is to help the homeowner make a better-informed decision and have a better conversation with installers.

## 2. Problem

Homeowners considering solar face three recurring problems (from the pain-point research done before this PRD):

1. **They can't tell whether solar pays off for them.** Installer payback figures are best-case single numbers; homeowners can't check them against their own bill and usage.
2. **They can't tell whether a quote is fair.** Quotes differ in size, brands, inclusions and warranty, so prices can't be compared directly. Trust in installers is the largest single concern.
3. **They don't know what to ask or what the process involves:** net-metering application, permits, warranties, payment terms.

Interest is high but commitment is low: in one Meralco-area survey, 82% said they would probably or definitely adopt rooftop solar, but only about 20% said definitely. Doubt, not lack of interest, holds the decision back.

## 3. Goals and non-goals

### Goals (Stage 1)
- G1. A homeowner can get an indicative system size and savings/payback **range** in under 5 minutes, using only figures from their bill.
- G2. Every result shows its assumptions, and the user can change them.
- G3. A homeowner can upload 1–4 installer quotes and see them normalized side by side, with neutral flags and questions to ask.
- G4. A homeowner leaves with a practical guide: questions for installers, red flags, and the process steps.
- G5. Nothing is stored unless the user opts in; opted-in data is anonymous and limited to region-level location.
- G6. Runs at zero or near-zero running cost on Vercel.

### Non-goals (Stage 1)
- Recommending, ranking or listing installers, brands or products.
- Selling leads or taking commissions.
- User accounts or saved history.
- Detailed battery/hybrid modelling, financing calculators, satellite roof analysis (see staging, section 9).
- Commercial or industrial systems, off-grid systems, renters.

## 4. Target users

**Primary (Stage 1):** owners of houses or townhouses in the Philippines, with monthly electricity bills of roughly PHP 3,000 or more, who are researching solar or already hold one or more quotes. Initial focus is the Meralco franchise area; the app works for all regions.

**Personas**
| Persona | Situation | What they need from the app |
|---|---|---|
| Bill-shocked researcher | PHP 6–15k bill after rate increases; reading Reddit/Facebook | "Does solar make sense for me, roughly?" |
| Quote holder | Has 2–3 quotes that look very different | "Which quote is reasonable and what's missing?" |
| Buying for family | Adult child or OFW paying for parents' system remotely | A trustworthy check without being on site |
| Daytime user | Work-from-home or retirees, high daytime use | Correct credit for self-consumption |

**Later:** lower-income households (needs financing features), installers, suppliers and lenders (see section 9).

## 5. Product principles

1. **Neutral.** No installer or brand is promoted. No revenue depends on what the user buys.
2. **Ranges, not promises.** Results are indicative estimates, shown as low–high ranges, never as a quotation.
3. **Visible assumptions.** Every number can be traced to an input or a stated, editable assumption.
4. **Numbers come from calculation, not AI.** AI may extract data from documents and explain results in plain language; it never produces or alters the figures.
5. **Private by default.** No account, no names, no addresses. Data is stored only on explicit opt-in.
6. **Plain English.** Short sentences, local terms (kWh from your Meralco bill, net metering), no jargon without explanation.

## 6. Stage 1 features

### F1. Solar check: sizing and savings tool

**User inputs** (basic form, one screen; optional "more details" section):
| Input | Required | Notes |
|---|---|---|
| Region | Yes | Dropdown of Philippine administrative regions. No city, barangay or address. |
| Electricity provider type | Yes | Meralco / other private utility / electric cooperative. Sets default rates. |
| Monthly bill (PHP) | Yes | Average of recent months, or one month. |
| Monthly use (kWh) | Recommended | From the bill. If missing, estimated from the bill and default rate. |
| Daytime use | Yes | Mostly evening / mixed / mostly daytime (sets the self-consumption share). |
| Home and roof type | Yes | House or townhouse; roof material (e.g. metal, concrete, tile). |
| Usable roof area | Optional | Approximate m², or "not sure". Caps the system size. |
| Roof direction and shading | Optional | Simple choices; defaults to "not sure / some shading". |
| Net metering | Yes | Plan to apply / not sure / no. |
| Budget | Optional | Caps the suggested size. |

**Outputs**
- Suggested system size (kWp) as a range, with the reason (usage-limited, roof-limited or budget-limited).
- Estimated monthly and yearly generation.
- Estimated monthly bill before and after, and yearly savings (low–high).
- Indicative installed cost range (from editable PHP-per-kW assumptions).
- Simple payback range in years, and 25-year savings range.
- A monthly generation vs use chart.
- An **assumptions panel**: every default (rates, yield, losses, cost per kW, rate increase, degradation) shown and editable; results update instantly.
- A plain-language explanation of what drives the result and what could change it.
- A verdict band, worded neutrally: e.g. "Strong case", "Reasonable case", "Weak case: check these factors first".
- Disclaimer: indicative only; a site survey and formal quote are required.

### F2. Installer guide

Static, well-structured content linked from the results:
- **Questions to ask an installer**, grouped (system design, equipment, price and inclusions, warranty, net metering and permits, payment and timeline, after-sales). Results pages surface the most relevant questions for the user's case (e.g. shading questions when shading was selected).
- **Red flags** (e.g. very large upfront payment, no itemized quote, no net-metering handling, unclear warranty owner).
- **Process steps:** survey → quote → contract → permits → installation → inspection → net-metering application → meter change, with what the homeowner does at each step.
- **Glossary** (kWp, kWh, inverter, hybrid, net metering, payback).
- Printable/copyable checklist.

### F3. Quote comparison

**Flow:** upload up to 4 quotes (PDF or photo) → the app extracts key fields → **user reviews and corrects every field** → side-by-side comparison. Manual entry is always available, and is the fallback if extraction is unavailable or fails.

**Fields captured per quote**
- System size (kWp), system type (grid-tie / hybrid / off-grid), total price, VAT included or not.
- Panels: brand, model, wattage, quantity.
- Inverter: brand, type, capacity. Battery: brand, kWh (if any).
- Mounting/racking type.
- Inclusions checklist: net-metering application, permits, electrical upgrades, monitoring app, delivery/installation, after-sales visits.
- Warranties: panel product, panel performance, inverter, battery, workmanship (years).
- Payment terms (deposit %, milestones), installation timeline, quote validity.

**Comparison outputs**
- Normalized table: price per Wp, price per kWh of yearly generation, warranty totals, inclusions side by side.
- Each quote's estimated savings and payback, using the user's own F1 inputs if available.
- Neutral flags, e.g.: "price per Wp is above the typical range used in this app", "size is much larger than your usage needs", "net-metering application not listed", "workmanship warranty under 2 years", "deposit above 50%". Each flag links to a question to ask.
- No overall "winner". The app never recommends a quote or installer; it highlights differences and gaps.
- Installer names on uploaded quotes are shown to the user but are **not** stored.

**File handling:** uploaded files are processed in memory and discarded immediately. They are never stored.

### F4. Opt-in anonymous data sharing

At the end of F1 and F3, the user may tick "Share my anonymous figures to help build fair price benchmarks for other homeowners." Default is **off**.

- **Stored if opted in:** region, provider type, bill and kWh, daytime-use band, home/roof type, roof area band, direction, shading, net-metering intent, sizing results; and for quotes, all F3 fields except installer name and contact details; the month and year submitted.
- **Never stored:** names, addresses, city/barangay, phone, email, IP address, account numbers, uploaded files, installer names.
- The user receives a random reference code to request deletion.
- Aggregates are shown only when a group has at least 5 records (from Stage 2).

### Cross-cutting
- Mobile-first, works on low-end Android phones and slow connections.
- Copy/print summary of results and comparison.
- Simple feedback link on each page ("Was this useful?").
- "How this app works and who pays for it" page stating neutrality and data rules.

## 7. Key user flows

1. **Quick check:** Home → Solar check form → Results (adjust assumptions) → Installer guide → optional share.
2. **Quote check:** Home → Compare quotes → upload → review fields → comparison → questions to ask → optional share.
3. **Combined:** Results page → "Got quotes? Compare them against this estimate".

## 8. Technical outline (detail in specs.md)

- **Hosting:** Vercel (Hobby plan) only, during the test stage.
- **Backend:** Python FastAPI running as a Vercel serverless function; server-rendered pages with light JavaScript; Chart.js for charts.
- **Solar yield:** NREL PVWatts used offline to build a regional yield table (monthly kWh per kWp by region); the app reads this table, so no address is ever sent to an outside service. PVGIS is the fallback data source.
- **Calculations:** pure Python module (sizing, savings, payback, quote normalization), fully unit-tested.
- **AI (optional):** Vercel AI Gateway free monthly credits for quote extraction and plain-language text. No paid API in Stage 1. The app works fully without AI (manual quote entry, template explanations).
- **Database:** free-tier Postgres via the Vercel Marketplace, used only for opt-in anonymous records and feedback.
- **Content:** installer guide and rate defaults kept as editable data files (Markdown/JSON) in the repo.
- **Privacy:** no accounts, no cookies beyond essentials, no analytics that track individuals.

## 9. Future features and suggested staging

| Stage | Theme | Features | Pre-condition |
|---|---|---|---|
| **1 – Test app** (this PRD) | Decide and compare | Solar check, installer guide, quote comparison, opt-in data | — |
| **2 – Better answers** | Depth for homeowners | Hybrid/battery estimate (clearly separate, higher uncertainty); financing view (cash vs bank vs Pag-IBIG/SSS/GSIS loans); downloadable one-page PDF for installer meetings; Filipino/Taglish wording; bill photo reading; regional price benchmarks from opt-in data (n ≥ 5) | Stage 1 used by real homeowners; enough opt-in quotes |
| **3 – Trust layer** | Installers and verification | Verified-installer directory with published criteria and flat fee (never ranked by payment); installer track record from user feedback; paid independent engineer quote review; net-metering/permit step tracker; optional accounts to save results | Neutrality charter and advisory input in place; legal review |
| **4 – Platform** | Supply side and scale | Standard quote format/tool for installers; anonymized market data reports for lenders, suppliers, researchers; utility and LGU partnerships; roof analysis from satellite imagery; other countries | Sustainable funding; data volume |

Staging rule: a stage starts only when the previous one shows real use, and each new revenue feature must pass the neutrality ground rules (flat, disclosed fees; no commissions; no paid ranking).

## 10. Success measures (test stage)

- Completion rate of the solar check (form start → results) ≥ 60%.
- Share of users who open the installer guide after results.
- Number of quotes compared; share of extracted fields the user had to correct.
- Opt-in rate for anonymous sharing.
- "Was this useful?" yes-rate ≥ 70%.
- Running cost stays at PHP 0 (within free tiers).

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| A wrong estimate harms trust | Ranges; visible, editable assumptions; engineer review of defaults; clear disclaimers |
| Rate and policy changes (tariffs, net-metering credits) | Defaults kept in one data file with an "as of" date shown in the app |
| AI extraction errors | Mandatory user review; manual entry; AI never sets figures without confirmation |
| Free-tier limits (Vercel, AI credits, database) | App degrades gracefully: AI off → manual entry; database off → sharing hidden |
| Users share personal data in uploads | Files never stored; only confirmed structured fields saved, installer name excluded |

## 12. Decisions made (16 Nov 2026)

- Stack: FastAPI with a simple web UI, deployed on Vercel only.
- Quote input: upload with AI extraction, user confirms; manual entry fallback.
- Data: nothing stored by default; opt-in anonymous records with region-level location only.
- Language: plain English at launch.
- AI: no paid API in the test stage; use what Vercel provides free.
- Repo: private GitHub repository `HomeSolarPH`; research files kept outside the repo.

## 13. Open questions

1. Who reviews the default assumptions (rates, cost per kW, yields) before public testing, e.g. a licensed electrical engineer?
2. Should regional price benchmarks be shown in Stage 1 using published figures, or only from Stage 2 when opt-in data exists?
3. Should installer names be stored in a later stage (for track records), and under what consent?
4. What wording should the neutral verdict bands use?
5. Who are the first test users (friends and family, r/SolarPH, a homeowners' association)?
