from __future__ import annotations

from pathlib import Path
import asyncio
import contextlib

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .db import ensure_indexes
from .repositories import send_due_reminders
from .routers import assets, entries, quotations, settings


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Tender & Quotation Registry")
app.include_router(entries.router, prefix="/api")
app.include_router(quotations.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.mount("/", StaticFiles(directory=str(BASE_DIR / "static"), html=True), name="static")


async def _reminder_worker() -> None:
    while True:
        try:
            await send_due_reminders()
        except Exception:
            pass
        await asyncio.sleep(3600)


@app.on_event("startup")
async def startup_event() -> None:
    await ensure_indexes()
    await send_due_reminders()
    app.state.reminder_task = asyncio.create_task(_reminder_worker())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    reminder_task = getattr(app.state, "reminder_task", None)
    if reminder_task is not None:
        reminder_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reminder_task


@app.get("/health")
async def health():
    return {"ok": True}
