"""Field-report photo matching (staff-only orchestration).

Recognition against the REGISTERED dataset is closed-set: a person unknown
to the original models can never be returned as a registered identity. To
close the loop for citizen/staff field reports, this module compares the
query embedding against the ORIGINAL-pipeline embeddings stored with each
report photo (person_images.vectors) and surfaces the closest stored photo
above a conservative floor — always with its raw similarity and a
"verify visually" note, never as a proven identity.

Only CNN and ArcFace participate: both emit L2-normalized embeddings, so
cosine similarity is meaningful. MediaPipe landmarks are raw x,y,z
(no normalization in the original pipeline), so cosine over them would be
misleading and the model is excluded here (its own result card is
unaffected).
"""
import asyncio
import os

import numpy as np
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..ai import registry

# Cosine floor for claiming a stored report photo resembles the query.
# Same-file searches score 1.0; same-person photos typically land well
# above this. Anything below is reported as no report match.
REPORT_MATCH_MIN_SIM = 0.55

_MODELS = ("cnn", "arcface")


def cosine_best(query: np.ndarray, rows: list[dict], min_sim: float = REPORT_MATCH_MIN_SIM) -> dict | None:
    """Pure helper: best {row, similarity} with similarity >= min_sim.

    Each row: {"person_id", "person_name", "photo_path", "vector",
    "model"}. Returns None when nothing clears the floor.
    """
    q = np.asarray(query, dtype=np.float32)
    n = float(np.linalg.norm(q))
    if n < 1e-12 or not rows:
        return None
    q = q / n
    best = None
    for row in rows:
        try:
            v = np.asarray(row["vector"], dtype=np.float32)
            v = v / max(float(np.linalg.norm(v)), 1e-12)
            sim = float(np.dot(q, v))
        except Exception:
            continue
        if sim >= min_sim and (best is None or sim > best["similarity"]):
            best = {"row": row, "similarity": round(sim, 4)}
    return best


def _query_vector(model: str, image_bytes: bytes) -> np.ndarray | None:
    """Original-pipeline query embedding, or None when unavailable."""
    adapter = registry.get_cnn() if model == "cnn" else registry.get_arcface()
    try:
        return adapter.embed_query(image_bytes)
    except Exception:
        return None


async def _query_vector_threaded(model: str, image_bytes: bytes):
    return await asyncio.to_thread(_query_vector, model, image_bytes)


async def query_vector(model: str, image_bytes: bytes):
    """Public wrapper: ORIGINAL-pipeline query embedding for one model.

    Returns the embedding array, or None when the model is unavailable,
    the bytes are undecodable, or no face is detected. Never raises.
    """
    return await _query_vector_threaded(model, image_bytes)


async def match_reports(db: AsyncIOMotorDatabase, image_bytes: bytes) -> dict | None:
    """Best stored-report-photo match across CNN + ArcFace, or None.

    Returned match: {"person_id", "person_name", "photo_url",
    "similarity", "model", "note"}. Staff-only callers only.
    """
    persons = db["missing_persons"]
    archived_ids: set[str] = set()
    async for doc in persons.find({"archived": True}, {"_id": 1}):
        archived_ids.add(str(doc["_id"]))

    candidates: list[dict] = []
    async for img in db["person_images"].find(
        {"$or": [{"vectors.cnn": {"$exists": True}}, {"vectors.arcface": {"$exists": True}}]}
    ):
        pid = img.get("person_id")
        if pid in archived_ids:
            continue
        vectors = img.get("vectors") or {}
        for model in _MODELS:
            vec = vectors.get(model)
            if vec:
                candidates.append(
                    {
                        "person_id": pid,
                        "photo_path": img.get("path"),
                        "vector": vec,
                        "model": model,
                    }
                )
    if not candidates:
        return None

    best_overall = None
    for model in _MODELS:
        model_rows = [c for c in candidates if c["model"] == model]
        if not model_rows:
            continue
        query = await _query_vector_threaded(model, image_bytes)
        if query is None:
            continue
        hit = cosine_best(query, model_rows)
        if hit and (best_overall is None or hit["similarity"] > best_overall["similarity"]):
            best_overall = {**hit, "model": model}

    if best_overall is None:
        return None
    row = best_overall["row"]
    person = None
    try:
        from bson import ObjectId

        person = await persons.find_one({"_id": ObjectId(row["person_id"])})
    except Exception:
        person = None
    name = person.get("full_name") if person else row["person_id"]
    return {
        "person_id": row["person_id"],
        "person_name": name,
        "photo_url": f"/storage/{row['photo_path']}" if row.get("photo_path") else None,
        "similarity": best_overall["similarity"],
        "model": best_overall["model"],
        "note": ("Closest stored field-report photo by original-pipeline "
                 "embedding similarity — verify visually, not a proven identity."),
    }


async def backfill_report_vectors(db: AsyncIOMotorDatabase, storage_dir: str) -> dict:
    """Embed every report photo missing vectors with the ORIGINAL pipelines.

    Additive and idempotent: photos that already have vectors are skipped;
    failures (no face, unavailable model) are reported per photo and left
    for a later run. Original model artifacts are only read.
    """
    from ..ai.result import AIMissingDependency

    report: dict = {"photos_seen": 0, "photos_updated": 0, "failed": [], "models": {}}
    for model in _MODELS:
        adapter = registry.get_cnn() if model == "cnn" else registry.get_arcface()
        try:
            ok = await asyncio.to_thread(adapter.load)
            report["models"][model] = {"available": bool(ok)}
            if not ok:
                report["models"][model]["error"] = adapter._error
        except Exception as exc:
            report["models"][model] = {"available": False, "error": str(exc)}

    async for img in db["person_images"].find({}):
        vectors = img.get("vectors") or {}
        missing = [m for m in _MODELS if not vectors.get(m)]
        if not missing:
            continue
        report["photos_seen"] += 1
        rel = img.get("path") or ""
        full = os.path.join(storage_dir, rel.replace("/", os.sep))
        if not os.path.isfile(full):
            report["failed"].append({"photo": rel, "error": "file not found on disk"})
            continue
        try:
            with open(full, "rb") as fh:
                content = fh.read()
        except OSError as exc:
            report["failed"].append({"photo": rel, "error": str(exc)})
            continue
        new_vectors = dict(vectors)
        photo_failed = []
        for model in missing:
            if not report["models"][model].get("available"):
                photo_failed.append({"model": model, "error": "model unavailable"})
                continue
            try:
                vec = await _query_vector_threaded(model, content)
            except AIMissingDependency as exc:
                photo_failed.append({"model": model, "error": str(exc)})
                continue
            except Exception as exc:
                photo_failed.append({"model": model, "error": str(exc)})
                continue
            if vec is None:
                photo_failed.append({"model": model, "error": "no face detected"})
            else:
                new_vectors[model] = np.asarray(vec, dtype=np.float32).tolist()
        if len(new_vectors) > len(vectors):
            await db["person_images"].update_one(
                {"_id": img["_id"]}, {"$set": {"vectors": new_vectors}}
            )
            report["photos_updated"] += 1
        if photo_failed:
            report["failed"].append({"photo": rel, "models": photo_failed})
    return report
