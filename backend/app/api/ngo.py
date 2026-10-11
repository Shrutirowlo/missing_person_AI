"""NGO router — shared cases, sightings, and activity."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..deps import db_dep, require_ngo_or_above
from ..repositories.persons import PersonRepository
from ..schemas.persons import SightingIn, SightingOut

router = APIRouter(prefix="/ngo", tags=["ngo"])


def _ngo_case_out(doc: dict) -> dict:
    """Strip AI labels and sensitive recognition fields from NGO responses."""
    images = [
        {
            "id": img["id"],
            "url": f"/storage/{img['path']}",
            "is_primary": img.get("is_primary", False),
            "created_at": img.get("created_at"),
        }
        for img in doc.get("images", [])
    ]
    return {
        "id": doc["id"],
        "full_name": doc["full_name"],
        "age": doc.get("age"),
        "gender": doc.get("gender"),
        "last_seen_location": doc.get("last_seen_location", ""),
        "last_seen_city": doc.get("last_seen_city", ""),
        "last_seen_state": doc.get("last_seen_state", ""),
        "date_last_seen": str(doc["date_last_seen"]) if doc.get("date_last_seen") else None,
        "description": doc.get("description", ""),
        "status": doc.get("status"),
        "images": images,
        "created_at": doc.get("created_at"),
        "ngo_notes": doc.get("ngo_notes", ""),
    }


@router.get("/cases")
async def ngo_cases(
    user: dict = Depends(require_ngo_or_above()),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    """NGO workers see cases shared with their NGO; police/admin see all."""
    repo = PersonRepository(db)
    role = user.get("role")
    if role == "NGO_WORKER":
        ngo_org = user.get("ngo_org") or ""
        docs = await repo.list_persons_for_ngo(ngo_org)
    else:
        docs = await repo.list_persons()
    return [_ngo_case_out(d) for d in docs]


@router.post("/sightings", response_model=SightingOut, status_code=201)
async def submit_sighting(
    payload: SightingIn,
    user: dict = Depends(require_ngo_or_above()),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    repo = PersonRepository(db)
    person = await repo.get_by_id(payload.person_id)
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    role = user.get("role")
    if role == "NGO_WORKER":
        ngo_org = user.get("ngo_org") or ""
        if ngo_org not in (person.get("shared_with_ngo") or []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Case not shared with your NGO")
    doc = {
        "person_id": payload.person_id,
        "submitted_by": user["id"],
        "ngo_org": user.get("ngo_org"),
        "location": payload.location,
        "description": payload.description,
        "photo_urls": payload.photo_urls,
        "created_at": datetime.now(timezone.utc),
    }
    res = await db["ngo_sightings"].insert_one(doc)
    doc["id"] = str(res.inserted_id)
    doc.pop("_id", None)
    return doc


@router.get("/activity")
async def my_activity(
    user: dict = Depends(require_ngo_or_above()),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    """Returns sightings submitted by the current user."""
    cursor = db["ngo_sightings"].find({"submitted_by": user["id"]}).sort("created_at", -1).limit(100)
    out = []
    async for d in cursor:
        d["id"] = str(d.pop("_id"))
        out.append(d)
    return out
