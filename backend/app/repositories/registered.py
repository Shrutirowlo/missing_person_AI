"""Data-access layer for registered_persons (imported gallery identities)."""
from motor.motor_asyncio import AsyncIOMotorDatabase


def _out(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


class RegisteredRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db["registered_persons"]
        self.images = db["registered_images"]

    async def get_by_identity(self, identity: str) -> dict | None:
        doc = await self.col.find_one({"identity": identity})
        return _out(doc) if doc else None

    async def list_identities(self, limit: int = 100) -> list[dict]:
        return [_out(d) async for d in self.col.find().sort("identity", 1).limit(limit)]

    async def get_with_images(self, identity: str) -> dict | None:
        person = await self.get_by_identity(identity)
        if person is None:
            return None
        person["images"] = [
            {**img, "id": str(img.pop("_id"))}
            async for img in self.images.find({"identity": identity}).sort("filename", 1)
        ]
        return person
