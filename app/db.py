from __future__ import annotations

import os
import ssl
from datetime import datetime, timezone
from typing import Any, Optional

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from dotenv import load_dotenv


load_dotenv()


MONGO_URI = os.getenv("MONGODB_URI", os.getenv("MONGO_URL", "mongodb://localhost:27017"))
MONGO_DB = os.getenv("MONGODB_DB", "quotation_registry")

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def connect_to_mongo() -> None:
    global _client, _db
    if _client is not None:
        return

    client_kwargs = {
        "tls": True,
        "tlsAllowInvalidCertificates": False,
    }
    if certifi is not None:
        client_kwargs["tlsCAFile"] = certifi.where()

    _client = AsyncIOMotorClient(MONGO_URI, **client_kwargs)
    _db = _client[MONGO_DB]


def close_mongo() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        connect_to_mongo()
    return _db


def entries_collection():
    return get_db()["registry_entries"]


def quotations_collection():
    return get_db()["quotations"]
def reminders_collection():
    return get_db()["reminders"]


def assets_collection():
    return get_db()["assets"]


def settings_collection():
    return get_db()["settings"]


async def ensure_indexes() -> None:
    await entries_collection().create_index([("title", "text"), ("ref_number", "text"), ("department", "text")])
    await entries_collection().create_index("deadline")
    await entries_collection().create_index("status")
    await reminders_collection().create_index("due_date")
    await reminders_collection().create_index([("sent_at", 1), ("due_date", 1)])
    await assets_collection().create_index("kind")


def mongo_id(value: Any) -> str:
    return str(value)
