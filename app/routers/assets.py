from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from ..repositories import delete_asset as repo_delete_asset, upload_asset as repo_upload_asset

router = APIRouter(tags=["assets"])


@router.post("/assets")
async def upload_asset(kind: str = Form(...), file: UploadFile = File(...)):
    data = await file.read()
    record = await repo_upload_asset(kind=kind, content_type=file.content_type or "application/octet-stream", raw=data)
    return {"asset_id": record["_id"], "data_url": record["data_url"], "kind": record["kind"]}


@router.delete("/assets/{asset_id}")
async def delete_asset(asset_id: str):
    return {"deleted": await repo_delete_asset(asset_id)}
