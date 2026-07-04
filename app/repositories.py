from __future__ import annotations

import base64
import asyncio
import re
from datetime import date, datetime, timedelta
from typing import Any, Optional, Union

from bson import ObjectId
from pymongo import ReturnDocument

from .db import (
    assets_collection,
    entries_collection,
    now_utc,
    quotations_collection,
    reminders_collection,
    settings_collection,
)
from .notifications import (
    build_quote_reminder_body,
    build_quote_reminder_subject,
    get_admin_emails,
    send_email,
)
from .models import QuotationDraft, RegistryEntryBase


def _ensure_object_id(value: Union[str, ObjectId]) -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    return ObjectId(value)


def _serialize_doc(doc: dict[str, Any]) -> dict[str, Any]:
    doc["_id"] = str(doc["_id"])
    for key in ("created_at", "updated_at"):
        if isinstance(doc.get(key), datetime):
            doc[key] = doc[key].isoformat()
    for key in ("date_applied", "deadline", "last_follow_up"):
        if isinstance(doc.get(key), date):
            doc[key] = doc[key].isoformat()
    return doc


def _coerce_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _search_filter(q: Optional[str], entry_type: Optional[str], status: Optional[str]) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    clauses: list[dict[str, Any]] = []
    if entry_type:
        filters["type"] = entry_type
    if status:
        filters["status"] = status
    if q:
        clauses.append({"$text": {"$search": q}})
        regex = re.escape(q)
        clauses.append(
            {
                "$or": [
                    {"title": {"$regex": regex, "$options": "i"}},
                    {"ref_number": {"$regex": regex, "$options": "i"}},
                    {"department": {"$regex": regex, "$options": "i"}},
                ]
            }
        )
    if clauses:
        if len(clauses) == 1:
            filters.update(clauses[0])
        else:
            filters["$or"] = clauses
    return filters


def _entry_payload(entry: RegistryEntryBase) -> dict[str, Any]:
    payload = entry.model_dump(mode="json")
    payload["date_applied"] = payload.get("date_applied")
    payload["deadline"] = payload.get("deadline")
    payload["last_follow_up"] = payload.get("last_follow_up")
    return payload


async def list_entries(
    q: Optional[str] = None,
    entry_type: Optional[str] = None,
    status: Optional[str] = None,
) -> list[dict[str, Any]]:
    cursor = entries_collection().find(_search_filter(q, entry_type, status)).sort("updated_at", -1)
    return [_serialize_doc(doc) async for doc in cursor]


async def create_entry(entry: RegistryEntryBase) -> dict[str, Any]:
    now = now_utc()
    payload = _entry_payload(entry)
    record = {"_id": ObjectId(), **payload, "created_at": now, "updated_at": now}
    await entries_collection().insert_one(record)
    return _serialize_doc(record)


async def update_entry(entry_id: str, entry: RegistryEntryBase) -> dict[str, Any]:
    now = now_utc()
    payload = _entry_payload(entry)
    payload["updated_at"] = now
    result = await entries_collection().find_one_and_update(
        {"_id": _ensure_object_id(entry_id)},
        {"$set": payload},
        return_document=ReturnDocument.AFTER,
    )
    if result is None:
        raise KeyError("Entry not found")
    return _serialize_doc(result)


async def delete_entry(entry_id: str) -> bool:
    result = await entries_collection().delete_one({"_id": _ensure_object_id(entry_id)})
    return result.deleted_count > 0


async def entry_stats() -> dict[str, Any]:
    entries = await list_entries()
    today = date.today()
    awaiting = [e for e in entries if e.get("status") not in {"Won", "Lost"}]
    urgent = [e for e in awaiting if e.get("deadline") and (date.fromisoformat(e["deadline"]) - today).days <= 3]
    won = [e for e in entries if e.get("status") == "Won"]
    total_value = sum(float(e.get("amount") or 0) for e in entries)
    win_rate = round((len(won) / len(entries) * 100) if entries else 0, 1)
    return {
        "total": len(entries),
        "awaiting_result": len(awaiting),
        "due_for_follow_up": len(urgent),
        "won": len(won),
        "win_rate": win_rate,
        "total_quoted_value": total_value,
    }


async def get_draft() -> dict[str, Any]:
    doc = await quotations_collection().find_one({"_id": "draft"})
    if doc is None:
        draft = QuotationDraft().model_dump(mode="json")
        draft["_id"] = "draft"
        draft["updated_at"] = now_utc()
        return draft
    doc["_id"] = str(doc["_id"])
    return doc


async def save_draft(payload: dict[str, Any]) -> dict[str, Any]:
    record = {**payload, "_id": "draft", "updated_at": now_utc()}
    await quotations_collection().update_one({"_id": "draft"}, {"$set": record}, upsert=True)
    return record


async def save_entry_from_draft(draft: dict[str, Any]) -> dict[str, Any]:
    meta = draft.get("meta", {})
    terms = draft.get("terms", {})
    deadline = None
    if meta.get("date") and terms.get("validity_days"):
        deadline = (datetime.fromisoformat(meta["date"]).date() + timedelta(days=int(terms["validity_days"]))).isoformat()
    entry = RegistryEntryBase(
        title=meta.get("subject") or "Quotation",
        ref_number=meta.get("ref_number") or "",
        department=meta.get("party_name") or "",
        type="Quotation",
        status="Pending",
        date_applied=date.fromisoformat(meta["date"]) if meta.get("date") else None,
        deadline=date.fromisoformat(deadline) if deadline else None,
        amount=sum(float(item.get("amount") or 0) for item in draft.get("line_items", [])),
        currency=meta.get("currency") or "INR",
        contact_person=meta.get("attention") or "",
        notes=terms.get("tax_note") or "",
        follow_up_cadence="none",
        last_follow_up=None,
    )
    result = await create_entry(entry)
    await schedule_quote_reminder(result)
    return result


async def schedule_quote_reminder(entry: dict[str, Any]) -> dict[str, Any]:
    if not entry:
        raise ValueError("Entry data is required to schedule a reminder")

    applied_date = _coerce_date(entry.get("date_applied")) or date.today()
    reminder_due_date = applied_date + timedelta(days=7)
    reminder_payload = {
        "_id": ObjectId(),
        "entry_id": _ensure_object_id(entry["_id"] if isinstance(entry["_id"], str) else entry["_id"]),
        "title": entry.get("title", "Quotation"),
        "ref_number": entry.get("ref_number", ""),
        "department": entry.get("department", ""),
        "contact_person": entry.get("contact_person", ""),
        "date_applied": applied_date.isoformat(),
        "deadline": entry.get("deadline"),
        "amount": entry.get("amount"),
        "currency": entry.get("currency", "INR"),
        "created_at": now_utc(),
        "due_date": reminder_due_date.isoformat(),
        "sent_at": None,
    }
    await reminders_collection().insert_one(reminder_payload)
    return {
        **reminder_payload,
        "_id": str(reminder_payload["_id"]),
        "entry_id": str(reminder_payload["entry_id"]),
        "date_applied": reminder_payload["date_applied"],
        "due_date": reminder_payload["due_date"],
    }


async def get_due_reminders() -> list[dict[str, Any]]:
    today_iso = date.today().isoformat()
    cursor = reminders_collection().find({"sent_at": None, "due_date": {"$lte": today_iso}})
    reminders = []
    async for reminder in cursor:
        reminder["_id"] = str(reminder["_id"])
        reminder["entry_id"] = str(reminder["entry_id"])
        # date_applied and due_date are stored as ISO date strings
        reminders.append(reminder)
    return reminders


async def mark_reminder_sent(reminder_id: str) -> bool:
    result = await reminders_collection().update_one(
        {"_id": _ensure_object_id(reminder_id)},
        {"$set": {"sent_at": now_utc()}},
    )
    return result.modified_count > 0


async def send_due_reminders() -> int:
    recipients = get_admin_emails()
    if not recipients:
        return 0

    reminders = await get_due_reminders()
    sent_count = 0
    for reminder in reminders:
        subject = build_quote_reminder_subject(reminder)
        body = build_quote_reminder_body(reminder)
        try:
            await asyncio.to_thread(send_email, subject, body, recipients)
            await mark_reminder_sent(reminder["_id"])
            sent_count += 1
        except Exception:
            continue
    return sent_count


async def send_reminder_for_entry(entry_id: str) -> dict[str, Any]:
    entry = await entries_collection().find_one({"_id": _ensure_object_id(entry_id)})
    if not entry:
        raise KeyError("Entry not found")

    recipients = get_admin_emails()
    if not recipients:
        raise RuntimeError("No admin recipients configured")

    subject = build_quote_reminder_subject(entry)
    body = build_quote_reminder_body(entry)
    await asyncio.to_thread(send_email, subject, body, recipients)

    # record the reminder as sent
    reminder_payload = {
        "_id": ObjectId(),
        "entry_id": _ensure_object_id(entry_id),
        "title": entry.get("title", "Quotation"),
        "ref_number": entry.get("ref_number", ""),
        "department": entry.get("department", ""),
        "contact_person": entry.get("contact_person", ""),
        "date_applied": entry.get("date_applied") or date.today().isoformat(),
        "deadline": entry.get("deadline"),
        "amount": entry.get("amount"),
        "currency": entry.get("currency", "INR"),
        "created_at": now_utc(),
        "due_date": date.today().isoformat(),
        "sent_at": now_utc(),
    }
    await reminders_collection().insert_one(reminder_payload)
    reminder_payload["_id"] = str(reminder_payload["_id"])
    reminder_payload["entry_id"] = str(reminder_payload["entry_id"])
    return reminder_payload


async def upload_asset(kind: str, content_type: str, raw: bytes) -> dict[str, Any]:
    data_url = f"data:{content_type};base64,{base64.b64encode(raw).decode()}"
    record = {
        "_id": ObjectId(),
        "kind": kind,
        "content_type": content_type,
        "data_url": data_url,
        "created_at": now_utc(),
    }
    await assets_collection().insert_one(record)
    record["_id"] = str(record["_id"])
    return record


async def delete_asset(asset_id: str) -> bool:
    result = await assets_collection().delete_one({"_id": _ensure_object_id(asset_id)})
    return result.deleted_count > 0


async def get_settings() -> dict[str, Any]:
    doc = await settings_collection().find_one({"_id": "settings"})
    if doc is None:
        return {"_id": "settings", "org_name": "Quotation Registry"}
    doc["_id"] = str(doc["_id"])
    return doc


async def save_settings(payload: dict[str, Any]) -> dict[str, Any]:
    payload = {**payload, "_id": "settings", "updated_at": now_utc()}
    await settings_collection().update_one({"_id": "settings"}, {"$set": payload}, upsert=True)
    return payload


def build_followup_ics(entry: dict[str, Any]) -> str:
    summary = f"Follow up: {entry.get('title', '')}"
    ref = entry.get("ref_number", "")
    when = entry.get("deadline") or date.today().isoformat()
    event_date = date.fromisoformat(when) if isinstance(when, str) else when
    return "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Tender & Quotation Registry//EN",
            "BEGIN:VEVENT",
            f"UID:{entry.get('_id', '')}@quotation-registry",
            f"DTSTAMP:{now_utc().strftime('%Y%m%dT%H%M%SZ')}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:Reference {ref}",
            f"DTSTART;VALUE=DATE:{event_date.strftime('%Y%m%d')}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )
