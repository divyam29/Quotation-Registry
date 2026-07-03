# Tender & Quotation Registry

FastAPI-backed PWA scaffold for managing tender entries and generating quotations.

## What is in the repo

- FastAPI app serving the web shell and JSON API
- Vanilla HTML/CSS/JS frontend
- Draft endpoints for entries, quotations, assets, and settings
- Basic PWA files: `manifest.json` and `sw.js`
- Local JSON persistence for the current scaffold

## Run locally

Requirements:

- Python 3.11+
- MongoDB running locally or reachable via `MONGODB_URI`
- A Python runtime built with modern TLS/OpenSSL support for Atlas connections

Create the local environment file:

```bash
cp .env.example .env
```

Create a virtual environment and install dependencies:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Start the app:

```bash
python -m uvicorn app.main:app --reload
```

Open:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/health`

## Current status

The repo is a scaffold, not yet the full production PWA described in the plan.

What works now:

- Static shell loads from FastAPI
- API route structure exists
- Draft storage uses local JSON files

What is still missing:

- MongoDB/Motor persistence
- Complete registry UI
- Full quotation builder UI and preview
- Asset upload/remove UI
- Dashboard stats rendering
- Offline caching strategy for app shell and API fallback
- Production-grade PWA install assets and icons

## Next steps

1. Replace the JSON store with MongoDB via Motor.
2. Build the registry tab UI:
   - dashboard cards
   - search/filter toolbar
   - entries table
   - create/edit/delete modal
3. Build the quotation generator UI:
   - form sections
   - line items
   - live preview
   - print/PDF layout
4. Add upload controls for logo and signature assets.
5. Wire autosave for quotation drafts and org settings.
6. Make the PWA installable with proper icons and metadata.
7. Improve the service worker for reliable offline shell caching.
8. Add validation and tests for the API and business logic.

## Project layout

```text
app/
  main.py
  models.py
  store.py
  routers/
  static/
```

## Notes

- The app is MongoDB-backed now. Set `MONGODB_URI` if you are not using `mongodb://localhost:27017`.
- Store local secrets in `.env`. The repo includes `.env.example` as the template.
- The plan in `tender_quotation_registry_plan.md` describes the intended end state.

## Deploying to Vercel

This repository is configured for Vercel deployment with a Python serverless entrypoint.

1. Ensure your project has `MONGODB_URI` and `MONGODB_DB` configured in Vercel Environment Variables.
2. Use the Vercel dashboard or CLI to deploy the repo.
3. `api/index.py` exports the FastAPI `app` from `app.main`.
4. `vercel.json` rewrites all incoming traffic to the Python function.
5. `runtime.txt` pins Python 3.11 for deployment compatibility.

If you want to deploy locally for testing, run:

```bash
python -m uvicorn app.main:app --reload
```
