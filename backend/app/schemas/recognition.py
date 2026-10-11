from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ModelName = Literal["cnn", "arcface", "mediapipe_knn", "all"]


class ModelResult(BaseModel):
    model: str
    available: bool
    match_found: bool = False
    predicted_label: str | None = None
    registered_match: str | None = None
    registered_person_id: str | None = None
    person_id: str | None = None
    source_photo_url: str | None = None
    source_photo_path: str | None = None
    similarity: float | None = None
    confidence: float | None = None
    status: str
    explanation: str = ""
    detail: dict = {}
    error: str | None = None


class RecognitionResponse(BaseModel):
    search_id: str
    models_evaluated: list[str]
    results: dict[str, ModelResult]
    query_image_url: str | None = None
    # Combined verdict over the per-model results: consistent / conflicting /
    # inconclusive (+ which models matched, and which could not run).
    summary: dict = {}
    # Closest stored field-report photo (staff-only): {person_id,
    # person_name, photo_url, similarity, model, note} or None.
    report_match: dict | None = None


class SearchHistoryItem(BaseModel):
    id: str
    model: str
    predicted_label: str | None = None
    person_id: str | None = None
    status: str
    created_at: datetime | None = None
    # Rich table rows for /history:
    query_image_url: str | None = None
    models_run: int = 0
    models_matched: int = 0
    models_unavailable: int = 0
    models_errored: int = 0
    best_match: dict | None = None  # {"label","person_id","model"} of first verified match


class SearchDetail(BaseModel):
    id: str
    model: str
    results: dict
    query_image_url: str | None = None
    searched_by: str | None = None
    created_at: datetime | None = None
    # Staff-only field-report match (stripped for CITIZEN/NGO_WORKER).
    report_match: dict | None = None
