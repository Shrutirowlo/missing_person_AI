from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..deps import current_user_dep, db_dep
from ..repositories.searches import SearchRepository
from ..schemas.recognition import SearchDetail, SearchHistoryItem

router = APIRouter(prefix="/search-history", tags=["search-history"])

_RESTRICTED_ROLES = ("CITIZEN", "NGO_WORKER")


@router.get("", response_model=list[SearchHistoryItem])
async def history(mine: bool = Query(default=True), limit: int = Query(default=50, le=200),
                  user: dict = Depends(current_user_dep),
                  db: AsyncIOMotorDatabase = Depends(db_dep)):
    scope = user["id"] if (mine or user.get("role") != "ADMIN") else None
    docs = await SearchRepository(db).list_searches_with_results(scope, limit)
    role = user.get("role")
    restricted = role in _RESTRICTED_ROLES
    items = []
    for doc in docs:
        results = doc.get("results") if isinstance(doc.get("results"), list) else []
        payloads = [r.get("payload") or {} for r in results]
        first = payloads[0] if payloads else {}
        ran = [p for p in payloads]
        matched = [p for p in ran
                   if p.get("available") and p.get("match_found")]
        unavailable = [p for p in ran if not p.get("available")]
        errored = [p for p in ran if p.get("available") and p.get("error")]
        best = None
        if not restricted:
            for p in matched:
                label = p.get("registered_match") or p.get("predicted_label")
                if label:
                    best = {"label": label,
                            "person_id": p.get("registered_person_id") or p.get("person_id"),
                            "model": p.get("model")}
                    break
        item = {
            "id": doc["id"],
            "model": doc.get("model", "all"),
            "predicted_label": None if restricted else first.get("predicted_label"),
            "person_id": None if restricted else first.get("person_id"),
            "status": first.get("status", doc.get("model", "")),
            "created_at": doc.get("created_at"),
            "query_image_url": doc.get("query_image_url"),
            "models_run": len(ran),
            "models_matched": len(matched),
            "models_unavailable": len(unavailable),
            "models_errored": len(errored),
            "best_match": best,
        }
        items.append(item)
    return items


@router.get("/{search_id}", response_model=SearchDetail)
async def search_detail(search_id: str, user: dict = Depends(current_user_dep),
                        db: AsyncIOMotorDatabase = Depends(db_dep)):
    doc = await SearchRepository(db).get_search(search_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found")
    if user.get("role") != "ADMIN" and doc.get("searched_by") != user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your search")

    role = user.get("role")
    restricted = role in _RESTRICTED_ROLES

    if restricted:
        # Strip all sensitive identity/recognition fields for citizens and NGO workers
        # (report_match is omitted entirely — staff-only).
        safe_results = {}
        for r in doc.get("results", []):
            safe_results[r["model"]] = {
                "available": r.get("payload", {}).get("available", False),
                "status": r.get("payload", {}).get("status", ""),
                "explanation": "Your report has been submitted. Authorized personnel can review it.",
                "match_found": False,
                "predicted_label": None,
                "registered_match": None,
                "registered_person_id": None,
                "source_photo_url": None,
                "detail": {},
            }
        return {
            "id": doc["id"],
            "model": doc.get("model", "all"),
            "results": safe_results,
            "query_image_url": doc.get("query_image_url"),
            "searched_by": doc.get("searched_by"),
            "created_at": doc.get("created_at"),
            "report_match": None,
        }

    results = {r["model"]: r["payload"] for r in doc.get("results", [])}
    return {"id": doc["id"], "model": doc.get("model", "all"), "results": results,
            "query_image_url": doc.get("query_image_url"), "searched_by": doc.get("searched_by"),
            "created_at": doc.get("created_at"),
            "report_match": doc.get("report_match")}
