from __future__ import annotations

from fastapi import APIRouter

from ..repositories import get_settings as repo_get_settings, save_settings as repo_save_settings

router = APIRouter(tags=["settings"])


@router.get("/settings")
async def get_settings():
    return await repo_get_settings()


@router.put("/settings")
async def put_settings(payload: dict):
    return await repo_save_settings(payload)
