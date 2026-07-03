from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from ..models import RegistryEntryCreate, RegistryEntryOut, RegistryEntryUpdate, StatsOut
from ..repositories import (
    build_followup_ics,
    create_entry as repo_create_entry,
    delete_entry as repo_delete_entry,
    entry_stats,
    list_entries as repo_list_entries,
    update_entry as repo_update_entry,
    send_due_reminders,
    send_reminder_for_entry,
)

router = APIRouter(tags=["entries"])


@router.get("/entries")
async def list_entries_endpoint(
    q: Optional[str] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
):
    return await repo_list_entries(q=q, entry_type=type, status=status)


@router.post("/entries", response_model=RegistryEntryOut)
async def create_entry(entry: RegistryEntryCreate):
    return await repo_create_entry(entry)


@router.put("/entries/{entry_id}", response_model=RegistryEntryOut)
async def update_entry(entry_id: str, entry: RegistryEntryUpdate):
    try:
        return await repo_update_entry(entry_id, entry)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Entry not found") from exc


@router.delete("/entries/{entry_id}")
async def delete_entry(entry_id: str):
    return {"deleted": await repo_delete_entry(entry_id)}


@router.get("/entries/stats", response_model=StatsOut)
async def stats():
    return await entry_stats()


@router.post("/reminders/send")
async def trigger_reminders():
    sent_count = await send_due_reminders()
    return {"sent": sent_count}


@router.post("/entries/{entry_id}/send-reminder")
async def send_reminder_entry(entry_id: str):
    try:
        result = await send_reminder_for_entry(entry_id)
        return {"sent": True, "reminder": result}
    except KeyError:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Entry not found")
    except Exception as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/entries/{entry_id}/followup-ics")
async def followup_ics(entry_id: str):
    entries = await repo_list_entries()
    for entry in entries:
        if entry["_id"] == entry_id:
            return PlainTextResponse(build_followup_ics(entry), media_type="text/calendar")
    raise HTTPException(status_code=404, detail="Entry not found")
