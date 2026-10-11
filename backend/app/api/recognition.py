import os

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..config import settings
from ..deps import db_dep, require_approved_police
from ..schemas.recognition import RecognitionResponse
from ..services.recognition_service import MODELS, RecognitionService
from ..utils.images import ensure_dir, safe_filename, validate_image

router = APIRouter(prefix="/recognition", tags=["recognition"])


@router.get("/availability")
async def availability(user: dict = Depends(require_approved_police()),
                       db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Approved POLICE and ADMIN only: model availability discloses which
    protected identity indexes are searchable."""
    return RecognitionService(db).availability()


@router.post("/search", response_model=RecognitionResponse)
async def search(image: UploadFile, model: str = Form(default="all"),
                 user: dict = Depends(require_approved_police()),
                 db: AsyncIOMotorDatabase = Depends(db_dep)):
    choice = (model or "all").strip().lower()
    alias = {"mediapipe": "mediapipe_knn", "mp": "mediapipe_knn"}
    choice = alias.get(choice, choice)
    if choice not in (*MODELS, "all"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid model '{model}'. Use cnn, arcface, mediapipe_knn, or all.")
    content = await image.read()
    try:
        ext = validate_image(content, image.content_type, settings.max_image_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    dest_dir = ensure_dir(os.path.join(settings.storage_dir, "queries"))
    name = safe_filename(ext)
    with open(os.path.join(dest_dir, name), "wb") as fh:
        fh.write(content)
    query_url = f"/storage/queries/{name}"
    return await RecognitionService(db).recognize(content, choice, user["id"], query_url)
