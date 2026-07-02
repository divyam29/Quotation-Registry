from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..models import QuotationDraft
from ..repositories import get_draft as repo_get_draft, save_draft as repo_save_draft, save_entry_from_draft

router = APIRouter(tags=["quotations"])


@router.get("/quotations/draft")
async def get_draft():
    return await repo_get_draft()


@router.put("/quotations/draft")
async def put_draft(draft: QuotationDraft):
    payload = draft.model_dump(mode="json")
    return await repo_save_draft(payload)


@router.post("/quotations/save-to-registry")
async def save_to_registry(draft: QuotationDraft):
    return await save_entry_from_draft(draft.model_dump(mode="json"))
