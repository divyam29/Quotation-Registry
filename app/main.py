from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .db import close_mongo, connect_to_mongo, ensure_indexes
from .routers import assets, entries, quotations, settings


app = FastAPI(title="Tender & Quotation Registry")
app.include_router(entries.router, prefix="/api")
app.include_router(quotations.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")


@app.on_event("startup")
async def startup():
    await connect_to_mongo()
    await ensure_indexes()


@app.on_event("shutdown")
async def shutdown():
    await close_mongo()


@app.get("/health")
async def health():
    return {"ok": True}
