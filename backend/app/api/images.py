import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..config import settings
from ..deps import current_user_dep, db_dep
from ..repositories.persons import PersonRepository
from ..schemas.persons import PersonImageOut
from ..services.photo_tagging import tag_photo
from ..services.report_matching import query_vector as _report_query_vector
from ..utils.images import ensure_dir, safe_filename, validate_image

router = APIRouter(prefix="/images", tags=["images"])


@router.post("/persons/{person_id}", response_model=list[PersonImageOut],
             status_code=status.HTTP_201_CREATED)
async def upload_reference_images(person_id: str, files: list[UploadFile],
                                  user: dict = Depends(current_user_dep),
                                  db: AsyncIOMotorDatabase = Depends(db_dep)):
    repo = PersonRepository(db)
    person = await repo.get_by_id(person_id)
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")

    role = user.get("role")
    # Ownership checks
    if role == "CITIZEN":
        if person.get("created_by") != user["id"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Not your report")
    elif role == "NGO_WORKER":
        ngo_org = user.get("ngo_org") or ""
        if ngo_org not in (person.get("shared_with_ngo") or []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Case not shared with your NGO")

    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files uploaded")
    dest_dir = ensure_dir(os.path.join(settings.storage_dir, "persons", person_id))
    saved = []
    restricted = role in ("CITIZEN", "NGO_WORKER")
    for upload in files:
        content = await upload.read()
        try:
            ext = validate_image(content, upload.content_type, settings.max_image_bytes)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        name = safe_filename(ext)
        with open(os.path.join(dest_dir, name), "wb") as fh:
            fh.write(content)
        rel = f"persons/{person_id}/{name}"
        # Tag with the ORIGINAL models (stored verbatim; failures tag null).
        tags = await tag_photo(content)
        # Store ORIGINAL-pipeline embeddings for staff-only report matching:
        # lets a later recognition search surface this field photo as a
        # visually-similar candidate (never as a proven identity).
        vectors: dict = {}
        for _model in ("cnn", "arcface"):
            try:
                _vec = await _report_query_vector(_model, content)
            except Exception:
                _vec = None
            if _vec is not None:
                import numpy as _np

                vectors[_model] = _np.asarray(_vec, dtype=_np.float32).tolist()
        doc = await repo.add_image(person_id, rel, ai_labels=tags, vectors=vectors or None)
        saved.append({
            "id": doc["id"],
            "url": f"/storage/{rel}",
            "is_primary": doc["is_primary"],
            "created_at": doc.get("created_at"),
            "ai_labels": {} if restricted else doc.get("ai_labels", {}),
        })
    return saved
