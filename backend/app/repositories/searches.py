"""Data-access layer for recognition_searches + recognition_results."""
from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


def _out(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


class SearchRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.searches = db["recognition_searches"]
        self.results = db["recognition_results"]

    async def create_search(self, data: dict) -> dict:
        data["created_at"] = datetime.now(timezone.utc)
        res = await self.searches.insert_one(data)
        doc = await self.searches.find_one({"_id": res.inserted_id})
        return _out(doc)

    async def add_result(self, search_id: str, model: str, payload: dict) -> dict:
        doc = {"search_id": search_id, "model": model, "payload": payload,
               "created_at": datetime.now(timezone.utc)}
        res = await self.results.insert_one(doc)
        doc["_id"] = res.inserted_id
        return _out(doc)

    async def set_report_match(self, search_id: str, match: dict | None) -> None:
        """Attach the staff-only field-report match to a search record."""
        try:
            oid = ObjectId(search_id)
        except Exception:
            return
        await self.searches.update_one({"_id": oid}, {"$set": {"report_match": match}})

    async def list_searches(self, user_id: str | None = None, limit: int = 50) -> list[dict]:
        query = {"searched_by": user_id} if user_id else {}
        cursor = self.searches.find(query).sort("created_at", -1).limit(limit)
        return [_out(d) async for d in cursor]

    async def list_searches_with_results(self, user_id: str | None = None,
                                         limit: int = 50) -> list[dict]:
        """History page: newest-first searches with their per-model result
        cards attached (one batched results query, not N+1)."""
        docs = await self.list_searches(user_id, limit)
        if not docs:
            return docs
        grouped: dict[str, list[dict]] = {d["id"]: [] for d in docs}
        cursor = self.results.find({"search_id": {"$in": list(grouped)}})
        async for r in cursor:
            grouped.setdefault(str(r.get("search_id")), []).append(_out(r))
        for d in docs:
            d["results"] = grouped.get(d["id"], [])
        return docs

    async def get_search(self, search_id: str) -> dict | None:
        try:
            oid = ObjectId(search_id)
        except Exception:
            return None
        doc = await self.searches.find_one({"_id": oid})
        if doc is None:
            return None
        out = _out(doc)
        out["results"] = [
            _out(r) async for r in self.results.find({"search_id": search_id})
        ]
        return out
