"""MongoDB connection (motor, async). Fail fast with a clear error if unreachable."""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .config import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_url, serverSelectionTimeoutMS=5000)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    return get_client()[settings.mongodb_db]


async def ping_db() -> None:
    await get_client().admin.command("ping")


async def ensure_indexes() -> None:
    db = get_db()
    await db["users"].create_index("username", unique=True)
    await db["users"].create_index("email", unique=True, sparse=True)
    await db["users"].create_index("role")
    await db["users"].create_index("approved")
    await db["missing_persons"].create_index("created_at")
    await db["missing_persons"].create_index("status")
    await db["missing_persons"].create_index("created_by")
    await db["missing_persons"].create_index("shared_with_ngo")
    await db["person_images"].create_index("person_id")
    await db["recognition_searches"].create_index("created_at")
    await db["recognition_searches"].create_index("searched_by")
    await db["recognition_results"].create_index("search_id")
    await db["registered_persons"].create_index("identity", unique=True)
    await db["registered_images"].create_index("rel_path", unique=True)
    await db["registered_images"].create_index("identity")
    await db["import_runs"].create_index("started_at")
    await db["ngo_sightings"].create_index("person_id")
    await db["ngo_sightings"].create_index("submitted_by")
    await db["ngo_sightings"].create_index("created_at")
