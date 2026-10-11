import os
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..ai import gallery
from ..config import settings
from ..deps import current_user_dep, db_dep, require_admin, require_approved_police, require_police_or_admin
from ..repositories.registered import RegisteredRepository
from ..services import dataset_service, index_sync
from ..services.dataset_import import import_registered_dataset
from ..utils.images import ensure_dir, validate_image

router = APIRouter(prefix="/dataset", tags=["dataset"])


def _slug_identity(name: str) -> str:
    """'John Doe' -> 'john_doe' — matches the original folder naming style."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:80]


def _decodable(content: bytes) -> bool:
    """True only if the bytes are a real, decodable photograph."""
    import cv2
    import numpy as np

    return cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR) is not None


@router.get("/info")
async def dataset_info(user: dict = Depends(require_approved_police()),
                       db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Describes the ORIGINAL mpp/data dataset the models search."""
    return dataset_service.info()


@router.get("/photo")
async def dataset_photo(model: str = Query(default="arcface"),
                        index: int = Query(ge=0),
                        user: dict = Depends(current_user_dep),
                        db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Serves one ORIGINAL dataset photo (read-only) by feature-row index.

    Open to any signed-in role so recognition-result thumbnails render for
    whoever runs the search; the identity record listings stay restricted."""
    if model == "arcface":
        resolver = dataset_service.resolve_arcface_photo
    elif model == "mediapipe_knn":
        resolver = dataset_service.resolve_mediapipe_photo
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Per-photo sources exist only for ArcFace and MediaPipe + KNN "
                   "(original paths.npy). The original CNN index carries "
                   "label+similarity without a source file per row.",
        )
    try:
        path = resolver(index)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return FileResponse(path, media_type=dataset_service.guess_media_type(path))


@router.post("/import")
async def import_dataset(user: dict = Depends(require_admin()),
                         db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Idempotent import of data/registered/ into MongoDB (additive-only). Admin only."""
    return await import_registered_dataset(db)


@router.post("/reindex")
async def reindex_dataset(user: dict = Depends(require_approved_police()),
                          db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Synchronize the API extension indexes with data/registered/ on disk.

    Embeds never-indexed photos with the ORIGINAL pipelines, evicts rows for
    deleted photos, never touches original artifacts. Idempotent."""
    return await index_sync.reindex_all()


@router.get("/index-status")
async def index_status(user: dict = Depends(current_user_dep),
                       db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Per-model index coverage: original rows, extension rows, pending photos."""
    return index_sync.status_report()


@router.post("/reports/backfill-vectors")
async def backfill_report_vectors(user: dict = Depends(require_admin()),
                                  db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Embed stored field-report photos missing vectors (admin only).

    Additive and idempotent: photos that already carry CNN/ArcFace vectors
    are skipped; per-photo failures are reported, never hidden. Enables
    staff-only report-photo matching in recognition searches."""
    from ..services import report_matching

    return await report_matching.backfill_report_vectors(db, settings.storage_dir)


@router.get("/registered")
async def registered_identities(user: dict = Depends(require_approved_police()),
                                db: AsyncIOMotorDatabase = Depends(db_dep)):
    """MongoDB registered-person records imported from data/registered/."""
    repo = RegisteredRepository(db)
    items = await repo.list_identities(limit=1000)
    return {"imported": len(items) > 0, "count": len(items), "identities": items}


@router.get("/registered/{identity}")
async def registered_identity(identity: str, user: dict = Depends(require_approved_police()),
                               db: AsyncIOMotorDatabase = Depends(db_dep)):
    repo = RegisteredRepository(db)
    doc = await repo.get_with_images(identity)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No imported record for '{identity}'. Run the dataset import.")
    for img in doc.get("images", []):
        img["url"] = f"/api/dataset/gallery/{identity}/{img['filename']}"
    return doc


@router.get("/gallery/{identity}/{filename}")
async def gallery_photo(identity: str, filename: str,
                        user: dict = Depends(current_user_dep),
                        db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Serves one ORIGINAL data/registered/ photo (read-only, contained).

    Open to any signed-in role so recognition-result thumbnails render for
    whoever runs the search; the identity record listings stay restricted."""
    if identity not in gallery.identities():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"'{identity}' is not a data/registered/ identity")
    if os.path.basename(filename) != filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename")
    if os.path.splitext(filename)[1].lower() not in gallery.SUPPORTED_PHOTO_EXTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")
    path = os.path.realpath(os.path.join(gallery.gallery_dir(), identity, filename))
    root = os.path.realpath(gallery.gallery_dir())
    if os.path.commonpath([path, root]) != root or not os.path.isfile(path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    return FileResponse(path, media_type=dataset_service.guess_media_type(path))


@router.post("/person", status_code=status.HTTP_201_CREATED)
async def add_person_photos(name: str = Form(...),
                            files: list[UploadFile] = File(...),
                            user: dict = Depends(require_police_or_admin()),
                            db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Stores one or more photos for a person in the ORIGINAL registered dataset.

    POLICE and ADMIN only: writing to the registered identity gallery is a
    privileged operation (citizens/NGO use missing-person reports instead).

    Files are written to <MPP_ORIGINAL_ROOT>/data/registered/<identity>/ using the
    original one-folder-per-identity layout (never overwriting existing photos),
    and the matching registered_persons / registered_images records are upserted
    with exactly the shapes import_registered_dataset uses. The photos are then
    embedded with each ORIGINAL model's own extraction pipeline and appended to
    that model's extension index, so the person is searchable immediately; the
    original artifacts are never modified (see index_report in the response)."""
    display_name = (name or "").strip()
    if not 1 <= len(display_name) <= 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Person name must be 1-100 characters.")
    identity = _slug_identity(display_name)
    if not identity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Person name must contain letters or digits.")
    if not files or len(files) > 50:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Attach between 1 and 50 photos.")

    folder = ensure_dir(os.path.join(gallery.gallery_dir(), identity))
    existing = set(os.listdir(folder))
    saved: list[str] = []
    rejected: list[dict] = []
    counter = 1
    for f in files:
        content = await f.read()
        try:
            ext = validate_image(content, f.content_type, settings.max_image_bytes)
            if not _decodable(content):
                raise ValueError("File content could not be decoded as a photograph")
        except ValueError as exc:
            rejected.append({"filename": f.filename, "error": str(exc)})
            continue
        while f"{identity}_{counter}{ext}" in existing:
            counter += 1
        filename = f"{identity}_{counter}{ext}"
        with open(os.path.join(folder, filename), "wb") as fh:
            fh.write(content)
        existing.add(filename)
        counter += 1
        saved.append(filename)

    if not saved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"message": "None of the files could be stored.",
                                    "rejected": rejected})

    gallery.invalidate(identity)

    # Per-identity upserts mirroring import_registered_dataset (additive only).
    now = datetime.now(timezone.utc)
    valid = sorted(n for n in os.listdir(folder)
                   if os.path.isfile(os.path.join(folder, n))
                   and os.path.splitext(n)[1].lower() in gallery.SUPPORTED_PHOTO_EXTS)
    sample = valid[0] if valid else None
    persons = db["registered_persons"]
    res = await persons.update_one(
        {"identity": identity},
        {"$set": {"identity": identity, "name": display_name,
                  "source_folder": identity, "dataset_root": gallery.gallery_dir(),
                  "image_count": len(valid),
                  "sample_image": sample,
                  "sample_image_path": f"{identity}/{sample}" if sample else None,
                  "sample_image_url": f"/api/dataset/gallery/{identity}/{sample}" if sample else None,
                  "updated_at": now},
         "$setOnInsert": {"created_at": now}},
        upsert=True)
    person_id = res.upserted_id
    if person_id is None:
        person_id = (await persons.find_one({"identity": identity}, {"_id": 1}))["_id"]
    images = db["registered_images"]
    for filename in saved:
        size = os.path.getsize(os.path.join(folder, filename))
        await images.update_one(
            {"rel_path": f"{identity}/{filename}"},
            {"$set": {"rel_path": f"{identity}/{filename}", "identity": identity,
                      "filename": filename,
                      "extension": os.path.splitext(filename)[1].lower(),
                      "size_bytes": size, "registered_person_id": person_id,
                      "url": f"/api/dataset/gallery/{identity}/{filename}",
                      "updated_at": now},
             "$setOnInsert": {"created_at": now}},
            upsert=True)

    # Embed the new photos into each model's extension index (original
    # pipeline, original artifacts untouched). Per-model outcomes — including
    # real unavailability errors — are reported, never hidden.
    index_report = await index_sync.index_photos(identity, saved)

    return {"identity": identity, "name": display_name,
            "saved_count": len(saved), "saved_files": saved,
            "rejected": rejected, "folder_photo_count": len(valid),
            "gallery_url": f"/api/dataset/registered/{identity}",
            "index_report": index_report,
            "note": ("Stored in the ORIGINAL data/registered dataset and the database. "
                     "Recognition gallery validation and the extension feature "
                     "indexes (see index_report) include these photos now; original "
                     "model artifacts were not modified.")}
