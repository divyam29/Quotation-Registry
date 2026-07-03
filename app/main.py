from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .db import ensure_indexes
from .routers import assets, entries, quotations, settings


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Tender & Quotation Registry")
app.include_router(entries.router, prefix="/api")
app.include_router(quotations.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.mount("/", StaticFiles(directory=str(BASE_DIR / "static"), html=True), name="static")


@app.get("/health")
async def health():
    return {"ok": True}
