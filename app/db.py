from __future__ import annotations

import os
import ssl
from datetime import datetime, timezone
from typing import Any, Optional

import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from dotenv import load_dotenv


load_dotenv()


MONGO_URI = os.getenv("MONGODB_URI", os.getenv("MONGO_URL", "mongodb://localhost:27017"))
MONGO_DB = os.getenv("MONGODB_DB", "quotation_registry")

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def connect_to_mongo() -> None:
    global _client, _db
    if _client is not None:
        return
    _client = AsyncIOMotorClient(
        MONGO_URI,
        tls=True,
        tlsCAFile=certifi.where(),
        tlsAllowInvalidCertificates=False,
    )
    _db = _client[MONGO_DB]


async def close_mongo() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("MongoDB not connected")
    return _db


def entries_collection():
    return get_db()["registry_entries"]


def quotations_collection():
    return get_db()["quotations"]


def assets_collection():
    return get_db()["assets"]


def settings_collection():
    return get_db()["settings"]


async def ensure_indexes() -> None:
    await entries_collection().create_index([("title", "text"), ("ref_number", "text"), ("department", "text")])
    await entries_collection().create_index("deadline")
    await entries_collection().create_index("status")
    await assets_collection().create_index("kind")


def mongo_id(value: Any) -> str:
    return str(value)
