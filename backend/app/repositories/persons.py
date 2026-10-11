"""Data-access layer for missing_persons + person_images collections."""
import re
from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


def _oid(value: str) -> ObjectId:
    return ObjectId(value)


def _out(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


class PersonRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.persons = db["missing_persons"]
        self.images = db["person_images"]

    # ---- persons ----
    async def create(self, data: dict) -> dict:
        now = datetime.now(timezone.utc)
        data.update({
            "status": data.get("status", "ACTIVE"),
            "archived": False,
            "created_at": now,
            "updated_at": now,
            "shared_with_ngo": data.get("shared_with_ngo", []),
            "ngo_notes": data.get("ngo_notes", ""),
        })
        res = await self.persons.insert_one(data)
        return await self.get_by_id(str(res.inserted_id))

    async def get_by_id(self, person_id: str, include_archived: bool = False) -> dict | None:
        try:
            oid = _oid(person_id)
        except Exception:
            return None
        query: dict = {"_id": oid}
        if not include_archived:
            query["archived"] = False
        doc = await self.persons.find_one(query)
        if doc is None:
            return None
        out = _out(doc)
        out["images"] = await self.list_images(person_id)
        return out

    async def list_persons(self, *, status: str | None = None, q: str | None = None,
                   include_archived: bool = False, limit: int = 50, skip: int = 0) -> list[dict]:
        query: dict = {}
        if not include_archived:
            query["archived"] = False
        if status:
            query["status"] = status
        if q:
            query["full_name"] = {"$regex": q, "$options": "i"}
        cursor = self.persons.find(query).sort("created_at", -1).skip(skip).limit(limit)
        out = []
        async for doc in cursor:
            item = _out(doc)
            item["images"] = await self.list_images(item["id"])
            out.append(item)
        return out

    async def list_persons_by_creator(self, creator_id: str, *, status: str | None = None,
                                      q: str | None = None, limit: int = 50, skip: int = 0) -> list[dict]:
        """Returns only persons created by the given user (for CITIZEN role)."""
        query: dict = {"archived": False, "created_by": creator_id}
        if status:
            query["status"] = status
        if q:
            query["full_name"] = {"$regex": q, "$options": "i"}
        cursor = self.persons.find(query).sort("created_at", -1).skip(skip).limit(limit)
        out = []
        async for doc in cursor:
            item = _out(doc)
            item["images"] = await self.list_images(item["id"])
            out.append(item)
        return out

    async def list_persons_for_ngo(self, ngo_org: str, *, status: str | None = None,
                                   q: str | None = None, limit: int = 50, skip: int = 0) -> list[dict]:
        """Returns only persons shared with the given NGO organisation."""
        query: dict = {"archived": False, "shared_with_ngo": ngo_org}
        if status:
            query["status"] = status
        if q:
            query["full_name"] = {"$regex": q, "$options": "i"}
        cursor = self.persons.find(query).sort("created_at", -1).skip(skip).limit(limit)
        out = []
        async for doc in cursor:
            item = _out(doc)
            item["images"] = await self.list_images(item["id"])
            out.append(item)
        return out

    async def update(self, person_id: str, patch: dict) -> dict | None:
        try:
            oid = _oid(person_id)
        except Exception:
            return None
        patch["updated_at"] = datetime.now(timezone.utc)
        res = await self.persons.update_one({"_id": oid, "archived": False}, {"$set": patch})
        if res.matched_count == 0:
            return None
        return await self.get_by_id(person_id)

    async def archive(self, person_id: str) -> bool:
        """Soft delete: records are archived, never hard-deleted."""
        try:
            oid = _oid(person_id)
        except Exception:
            return False
        res = await self.persons.update_one(
            {"_id": oid}, {"$set": {"archived": True, "updated_at": datetime.now(timezone.utc)}}
        )
        return res.matched_count == 1

    async def find_by_name(self, full_name: str) -> dict | None:
        doc = await self.persons.find_one(
            {"full_name": {"$regex": f"^{re.escape(full_name)}$", "$options": "i"}, "archived": False}
        )
        if doc is None:
            return None
        out = _out(doc)
        out["images"] = await self.list_images(out["id"])
        return out

    async def find_by_photo_label(self, model: str, label: str) -> tuple[dict | None, dict | None]:
        """Finds the person whose reference photo the SAME original model
        tagged with the SAME label. Returns (person, photo)."""
        if not label or model not in ("cnn", "arcface", "mediapipe_knn"):
            return None, None
        img = await self.images.find_one(
            {f"ai_labels.{model}": {"$regex": f"^{re.escape(label)}$", "$options": "i"}}
        )
        if img is None:
            return None, None
        person = await self.get_by_id(img["person_id"])
        if person is None:  # archived or removed
            return None, None
        return person, _out(img)

    # ---- images ----
    async def add_image(self, person_id: str, rel_path: str, is_primary: bool = False,
                      ai_labels: dict | None = None, vectors: dict | None = None) -> dict:
        if is_primary:
            await self.images.update_many({"person_id": person_id}, {"$set": {"is_primary": False}})
        else:
            existing = await self.images.count_documents({"person_id": person_id})
            is_primary = existing == 0
        doc = {"person_id": person_id, "path": rel_path, "is_primary": is_primary,
               "ai_labels": ai_labels or {},
               "created_at": datetime.now(timezone.utc)}
        if vectors:
            doc["vectors"] = vectors
        res = await self.images.insert_one(doc)
        doc["_id"] = res.inserted_id
        return _out(doc)

    async def list_images(self, person_id: str) -> list[dict]:
        return [_out(d) async for d in self.images.find({"person_id": person_id})]
