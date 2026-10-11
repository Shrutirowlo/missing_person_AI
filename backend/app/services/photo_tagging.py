"""Reference-photo tagging with the ORIGINAL models.

When a reference photo is uploaded for a missing person, each ORIGINAL
model is asked for its own predicted label and the answers are stored
verbatim on the photo document (`ai_labels`). No new algorithm: later
searches link a query to a person when the *same original model*
predicts the *same label* for both. Nulls are stored as nulls — a model
that detects no face tags nothing, it never blocks the others.
"""
import asyncio

from ..ai import registry
from ..ai.result import AIMissingDependency


async def tag_photo(image_bytes: bytes) -> dict:
    tags: dict[str, str | None] = {"cnn": None, "arcface": None, "mediapipe_knn": None}

    def _cnn_label() -> str | None:
        try:
            return registry.get_cnn().recognize(image_bytes).get("predicted_label")
        except (AIMissingDependency, ValueError):
            return None

    def _arcface_label() -> str | None:
        try:
            raw = registry.get_arcface().recognize(image_bytes)
        except (AIMissingDependency, ValueError):
            return None
        # NO_FACE_DETECTED carries no identity claim; only tag real predictions.
        if raw.get("status") == "NO_FACE_DETECTED" or not raw.get("predicted_label"):
            return None
        return raw["predicted_label"]

    tags["cnn"], tags["arcface"] = await asyncio.gather(
        asyncio.to_thread(_cnn_label), asyncio.to_thread(_arcface_label)
    )
    # mediapipe_knn stays untagged until face_landmarker.task exists (never substituted).
    return tags
