"""Clean data-access layer for the users collection."""
from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


def _out(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


class UserRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db["users"]

    async def get_by_username(self, username: str) -> dict | None:
        doc = await self.col.find_one({"username": username})
        return _out(doc) if doc else None

    async def get_by_email(self, email: str) -> dict | None:
        doc = await self.col.find_one({"email": email})
        return _out(doc) if doc else None

    async def get_by_id(self, user_id: str) -> dict | None:
        try:
            oid = ObjectId(user_id)
        except Exception:
            return None
        doc = await self.col.find_one({"_id": oid})
        return _out(doc) if doc else None

    async def create(self, data: dict) -> dict:
        data["created_at"] = datetime.now(timezone.utc)
        res = await self.col.insert_one(data)
        return await self.get_by_id(str(res.inserted_id))

    async def update(self, user_id: str, patch: dict) -> dict | None:
        try:
            oid = ObjectId(user_id)
        except Exception:
            return None
        await self.col.update_one({"_id": oid}, {"$set": patch})
        return await self.get_by_id(user_id)

    async def list_all(self, limit: int = 100) -> list[dict]:
        return [_out(d) async for d in self.col.find().limit(limit)]
