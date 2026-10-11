"""Unit tests that need no MongoDB and never touch the ORIGINAL AI files."""
import os

import pytest

from app.ai.adapters.arcface_adapter import ArcFaceAdapter
from app.ai.adapters.cnn_adapter import CNNAdapter
from app.ai.adapters.mediapipe_knn_adapter import MediaPipeKNNAdapter
from app.ai.result import AIMissingDependency
from app.config import settings
from app.security import create_access_token, decode_token, hash_password, verify_password
from app.utils.images import validate_image


def test_password_hash_and_verify():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_jwt_roundtrip():
    token = create_access_token("user123", {"role": "CITIZEN"})
    payload = decode_token(token)
    assert payload["sub"] == "user123"
    assert payload["role"] == "CITIZEN"


def test_image_validation_rejects_non_image():
    with pytest.raises(ValueError):
        validate_image(b"not an image at all", "image/jpeg", settings.max_image_bytes)


def test_image_validation_rejects_oversize():
    jpeg = b"\xff\xd8\xff" + b"\x00" * 10
    with pytest.raises(ValueError):
        validate_image(jpeg, "image/jpeg", 5)


def test_image_validation_accepts_minimal_jpeg():
    jpeg = b"\xff\xd8\xff" + b"\x00" * 100
    assert validate_image(jpeg, "image/jpeg", settings.max_image_bytes) == ".jpg"


def test_ai_paths_point_at_original_readonly_roots():
    assert "mpp" in settings.cnn_model_path.replace("\\", "/")
    assert "mpp" in settings.arcface_x_path.replace("\\", "/")
    assert "mpp" in settings.mediapipe_knn_path.replace("\\", "/")
    # backends must read from storage/, never write into the AI roots
    assert "storage" in settings.storage_dir


def test_mediapipe_adapter_never_substitutes():
    adapter = MediaPipeKNNAdapter()
    status = adapter.status()
    assert status["model"] == "mediapipe_knn"
    if not os.path.exists(settings.mediapipe_task_path):
        assert status["available"] is False
        assert "face_landmarker.task" in (status["error"] or "")
        with pytest.raises(AIMissingDependency):
            adapter.recognize(b"\xff\xd8\xff" + b"\x00" * 10)
    else:
        # Asset present: available, or a real runtime failure (e.g. the OS
        # blocked mediapipe's native DLL) — either way never a substitute.
        assert isinstance(status["available"], bool)


def test_cnn_and_arcface_status_report_without_crashing():
    for adapter in (CNNAdapter(), ArcFaceAdapter()):
        status = adapter.status()
        # Required shape; adapters may add extra transparency keys
        # (e.g. extension_rows) without breaking this contract.
        assert {"model", "available", "error", "missing_paths"} <= set(status)
        assert isinstance(status["available"], bool)


def test_gallery_authority_maps_only_data_registered():
    import pytest as _pytest
    from app.ai import gallery

    ids = gallery.identities()
    if not ids:
        _pytest.skip("original data/registered/ not present here")
    assert "biswa" in ids
    assert gallery.registered_match("biswa") == ("biswa", None)
    match, reason = gallery.registered_match("shruti")
    assert match is None and "data/registered" in (reason or "")
    assert gallery.registered_match(None)[0] is None

def test_cnn_adapter_contains_no_substitute_implementation():
    import inspect
    from app.ai.adapters import cnn_adapter

    src = inspect.getsource(cnn_adapter)
    # Detect real substitute *usage* (imports/calls), not docstring mentions.
    for banned in ("keras.applications", "MobileNetV2(", "calcHist", ".FaceMesh(",
                   "solutions.face_mesh", "get_model("):
        assert banned not in src, f"substitute usage {banned!r} found in CNN adapter"


def test_report_cosine_best_honors_floor():
    import numpy as np

    from app.services.report_matching import REPORT_MATCH_MIN_SIM, cosine_best

    assert 0 < REPORT_MATCH_MIN_SIM < 1
    rows = [
        {"person_id": "a", "vector": [1.0, 0.0]},
        {"person_id": "b", "vector": [0.0, 1.0]},
    ]
    hit = cosine_best(np.array([1.0, 0.0], dtype=np.float32), rows)
    assert hit is not None and hit["row"]["person_id"] == "a"
    assert hit["similarity"] == 1.0
    # A query far from every row stays below the floor -> None, never forced.
    assert cosine_best(np.array([-1.0, 0.0], dtype=np.float32), rows) is None
    assert cosine_best(np.array([1.0, 0.0], dtype=np.float32), []) is None
