from __future__ import annotations

import base64
import re
from datetime import date, datetime, timedelta
from typing import Any, Optional, Union

from bson import ObjectId
from pymongo import ReturnDocument

from .db import assets_collection, entries_collection, now_utc, quotations_collection, settings_collection
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
    return await create_entry(entry)


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
