# HomeSolarPH

A free, neutral resource for Philippine homeowners deciding whether to go rooftop solar.

Live test version: https://home-solar-ph.vercel.app

- **Solar check:** system size, savings and payback ranges from a few bill and roof details.
- **Installer guide:** questions to ask, red flags and the steps to net metering.
- **Compare quotes:** upload installer quotes and see them side by side with the app's estimate.

## Run locally

Needs [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run uvicorn index:app --reload --port 8040
```

Then open http://localhost:8040. Optional settings are listed in `.env.example`; the app runs without them.

## Tests

```bash
uv run pytest -q
```

## Privacy

No accounts, names, addresses or contact details. Uploaded files are never stored. Anonymous figures are saved only if the user agrees.
