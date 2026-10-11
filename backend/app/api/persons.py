from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..deps import current_user_dep, db_dep, require_police_or_admin
from ..repositories.persons import PersonRepository
from ..schemas.persons import NgoShareIn, PersonIn, PersonOut, PersonUpdateIn

router = APIRouter(prefix="/persons", tags=["persons"])


def _person_out(doc: dict, base_url: str = "", role: str = "ADMIN") -> dict:
    restricted = role in ("CITIZEN", "NGO_WORKER")
    images = [
        {
            "id": img["id"],
            "url": f"{base_url}/storage/{img['path']}" if base_url else f"/storage/{img['path']}",
            "is_primary": img.get("is_primary", False),
            "ai_labels": {} if restricted else img.get("ai_labels", {}),
            "created_at": img.get("created_at"),
        }
        for img in doc.get("images", [])
    ]
    return {
        **{k: v for k, v in doc.items() if k != "images"},
        "date_last_seen": str(doc.get("date_last_seen")) if doc.get("date_last_seen") else None,
        "images": images,
    }


@router.post("", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
async def create_person(payload: PersonIn, user: dict = Depends(current_user_dep),
                        db: AsyncIOMotorDatabase = Depends(db_dep)):
    data = payload.model_dump()
    if data.get("date_last_seen"):
        data["date_last_seen"] = str(data["date_last_seen"])
    data["created_by"] = user["id"]
    return _person_out(await PersonRepository(db).create(data), role=user.get("role", "CITIZEN"))


@router.get("", response_model=list[PersonOut])
async def list_persons(status: str | None = Query(default=None),
                       q: str | None = Query(default=None),
                       limit: int = Query(default=50, le=200), skip: int = 0,
                       user: dict = Depends(current_user_dep),
                       db: AsyncIOMotorDatabase = Depends(db_dep)):
    role = user.get("role")
    repo = PersonRepository(db)
    if role == "CITIZEN":
        docs = await repo.list_persons_by_creator(user["id"], status=status, q=q, limit=limit, skip=skip)
    elif role == "NGO_WORKER":
        ngo_org = user.get("ngo_org") or ""
        docs = await repo.list_persons_for_ngo(ngo_org, status=status, q=q, limit=limit, skip=skip)
    else:
        docs = await repo.list_persons(status=status, q=q, limit=limit, skip=skip)
    return [_person_out(d, role=role) for d in docs]


@router.get("/{person_id}", response_model=PersonOut)
async def get_person(person_id: str, user: dict = Depends(current_user_dep),
                     db: AsyncIOMotorDatabase = Depends(db_dep)):
    doc = await PersonRepository(db).get_by_id(person_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    role = user.get("role")
    if role == "CITIZEN" and doc.get("created_by") != user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your report")
    elif role == "NGO_WORKER":
        ngo_org = user.get("ngo_org") or ""
        if ngo_org not in (doc.get("shared_with_ngo") or []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Case not shared with your NGO")
    return _person_out(doc, role=role)


@router.put("/{person_id}", response_model=PersonOut)
async def update_person(person_id: str, payload: PersonUpdateIn,
                        user: dict = Depends(current_user_dep),
                        db: AsyncIOMotorDatabase = Depends(db_dep)):
    role = user.get("role")
    if role == "NGO_WORKER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="NGO workers cannot edit person records directly")
    repo = PersonRepository(db)
    doc = await repo.get_by_id(person_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    if role == "CITIZEN" and doc.get("created_by") != user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your report")
    patch = {k: (str(v) if k == "date_last_seen" and v is not None else v)
             for k, v in payload.model_dump().items() if v is not None}
    updated = await repo.update(person_id, patch)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return _person_out(updated, role=role)


@router.delete("/{person_id}", status_code=status.HTTP_200_OK)
async def delete_person(person_id: str, user: dict = Depends(current_user_dep),
                        db: AsyncIOMotorDatabase = Depends(db_dep)):
    role = user.get("role")
    if role == "NGO_WORKER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="NGO workers cannot archive person records")
    repo = PersonRepository(db)
    if role == "CITIZEN":
        doc = await repo.get_by_id(person_id)
        if doc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
        if doc.get("created_by") != user["id"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your report")
    ok = await repo.archive(person_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return {"status": "archived", "id": person_id}


@router.patch("/{person_id}/share-ngo", response_model=PersonOut)
async def share_with_ngo(
    person_id: str,
    payload: NgoShareIn,
    user: dict = Depends(require_police_or_admin()),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    """Police and admins can share a case with a specific NGO."""
    repo = PersonRepository(db)
    doc = await repo.get_by_id(person_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    shared = doc.get("shared_with_ngo") or []
    if payload.ngo_org not in shared:
        shared.append(payload.ngo_org)
    patch: dict = {"shared_with_ngo": shared}
    if payload.ngo_notes:
        patch["ngo_notes"] = payload.ngo_notes
    updated = await repo.update(person_id, patch)
    return _person_out(updated, role=user["role"])
