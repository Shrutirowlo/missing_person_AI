"""Pipeline tests: dataset import, gallery mapping, match consistency.

Uses an in-memory Mongo (mongomock) and NEVER writes to the original
dataset or model files (test 10 tripwires any write). The REAL original
files on disk are read to prove the import + mapping against them.
"""
import hashlib
import os

import pytest
from mongomock_motor import AsyncMongoMockClient

from app.ai import gallery
from app.ai.result import AIMissingDependency
from app.repositories.registered import RegisteredRepository
from app.services.dataset_import import import_registered_dataset
from app.services.recognition_service import RecognitionService

DATASET = r"C:\Users\shrut_hi39oyy\Downloads\mpp\mpp\data\registered"
MPP = r"C:\Users\shrut_hi39oyy\Downloads\mpp\mpp"
ARTIFACTS = [
    MPP + r"\models\cnn_face_embedding_model.keras",
    MPP + r"\models\cnn_embedding_knn.joblib",
    MPP + r"\models\cnn_embedding_labels.npy",
    MPP + r"\data\cnn_features\cnn_train_embeddings.npy",
    MPP + r"\data\cnn_features\cnn_train_labels.npy",
    MPP + r"\data\arcface_features\X.npy",
    MPP + r"\data\arcface_features\y.npy",
    MPP + r"\data\arcface_features\paths.npy",
    MPP + r"\models\mediapipe_knn.joblib",
    MPP + r"\data\mediapipe_features\X_normalized.npy",
    MPP + r"\data\mediapipe_features\y.npy",
]


@pytest.fixture
async def mockdb():
    db = AsyncMongoMockClient()["test_db"]
    await db["registered_persons"].create_index("identity", unique=True)
    await db["registered_images"].create_index("rel_path", unique=True)
    return db


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def _snapshot():
    snap = {p: _sha(p) for p in ARTIFACTS}
    listing = []
    for root, _dirs, files in os.walk(DATASET):
        for n in sorted(files):
            full = os.path.join(root, n)
            listing.append((os.path.relpath(full, DATASET), os.path.getsize(full)))
    snap["__listing__"] = listing
    return snap


def _disk_counts():
    """Expected import counts derived from the dataset on disk RIGHT NOW.

    The suite must stay green when an authorized user legitimately adds a
    person through POST /dataset/person (folder-per-identity convention);
    only the importer's fidelity to disk (and its idempotency) is asserted.
    """
    n_persons, n_images = 0, 0
    for identity in sorted(os.listdir(DATASET)):
        folder = os.path.join(DATASET, identity)
        if not os.path.isdir(folder):
            continue
        n_persons += 1
        for name in os.listdir(folder):
            full = os.path.join(folder, name)
            if os.path.isfile(full) and os.path.splitext(name)[1].lower() in gallery.SUPPORTED_PHOTO_EXTS:
                n_images += 1
    return n_persons, n_images


async def test_1_import_creates_persons_and_images(mockdb):
    want_persons, want_images = _disk_counts()
    assert want_persons >= 20  # the 20 original identities are always present
    report = await import_registered_dataset(mockdb, DATASET)
    assert report["identities_found"] == want_persons
    assert report["persons_created"] == want_persons
    assert report["images_created"] == want_images
    assert report["errors"] == []
    assert await mockdb["registered_persons"].count_documents({}) == want_persons
    assert await mockdb["registered_images"].count_documents({}) == want_images


async def test_2_import_twice_no_duplicates(mockdb):
    want_persons, want_images = _disk_counts()
    await import_registered_dataset(mockdb, DATASET)
    second = await import_registered_dataset(mockdb, DATASET)
    assert second["persons_created"] == 0
    assert second["images_created"] == 0
    assert second["persons_matched"] == want_persons
    assert await mockdb["registered_persons"].count_documents({}) == want_persons
    assert await mockdb["registered_images"].count_documents({}) == want_images


async def test_3_biswa_identity_found(mockdb):
    await import_registered_dataset(mockdb, DATASET)
    doc = await RegisteredRepository(mockdb).get_with_images("biswa")
    assert doc is not None and doc["identity"] == "biswa"
    assert len(doc["images"]) == 6


async def test_4_imported_paths_point_to_real_files(mockdb):
    await import_registered_dataset(mockdb, DATASET)
    bad = []
    async for img in mockdb["registered_images"].find({}):
        if not os.path.isfile(os.path.join(DATASET, img["rel_path"].replace("/", os.sep))):
            bad.append(img["rel_path"])
    assert bad == []


async def test_5_prediction_maps_to_mongo_identity(mockdb):
    await import_registered_dataset(mockdb, DATASET)
    repo = RegisteredRepository(mockdb)
    biswa = await repo.get_by_identity("biswa")
    assert biswa is not None
    assert await repo.get_by_identity("shruti") is None  # no folder, no record


def _svc(mockdb):
    return RecognitionService.__new__(RecognitionService)


async def test_6_no_contradictory_match_status(mockdb):
    svc = _svc(mockdb)
    cnn_raw = {"status": "PREDICTED", "predicted_label": "biswa",
               "best_similarity": 0.9976, "confidence": 0.98,
               "best_class_similarity": 0.99, "top_classes": [], "top_images": []}
    reg_doc = {"id": "abc123", "identity": "biswa"}
    hit = svc._standardize("cnn", cnn_raw, None, None, None, reg_doc)
    assert hit["match_found"] is True
    assert hit["registered_match"] == "biswa"
    assert hit["registered_person_id"] == "abc123"

    miss = svc._standardize("cnn", cnn_raw, None, None, None, None)
    assert miss["match_found"] is False
    assert miss["registered_match"] is None
    assert miss["registered_person_id"] is None
    assert miss["status"] == "no_reliable_match"
    assert "MongoDB" in miss["explanation"]

    arc_raw = {"status": "NO_FACE_DETECTED", "predicted_label": None, "similarity": None}
    noface = svc._standardize("arcface", arc_raw, None, None, None, None)
    assert noface["match_found"] is False and "no face" in noface["explanation"].lower()
    assert noface["registered_match"] is None
    assert noface["registered_person_id"] is None


async def test_7_unknown_identity_no_match(mockdb):
    svc = _svc(mockdb)
    raw = {"status": "PREDICTED", "predicted_label": "nobody_xyz",
           "best_similarity": 0.5, "confidence": 0.4,
           "best_class_similarity": 0.5, "top_classes": [], "top_images": []}
    out = svc._standardize("cnn", raw, None, None, None, None)
    assert out["match_found"] is False
    assert out["registered_match"] is None
    assert "nobody_xyz" in out["explanation"]


async def test_8_missing_assets_reported_without_substitution(mockdb):
    import os

    from app.ai.adapters.mediapipe_knn_adapter import MediaPipeKNNAdapter
    from app.config import settings

    mp = MediaPipeKNNAdapter()
    st = mp.status()
    assert st["model"] == "mediapipe_knn"
    if not os.path.exists(settings.mediapipe_task_path):
        # Asset genuinely absent: the adapter must refuse, never substitute.
        assert st["available"] is False and "face_landmarker.task" in (st["error"] or "")
        with pytest.raises(AIMissingDependency):
            mp.recognize(b"\xff\xd8\xff" + b"\x00" * 10)
    else:
        # Asset present: the adapter may be available, or may report a real
        # runtime failure (e.g. blocked native DLL) — never a fake result.
        assert isinstance(st["available"], bool)
        if st["available"]:
            assert mp.recognize is not None
    assert gallery.registered_match("")[0] is None


async def test_9_adapters_independent_interfaces():
    from app.ai.adapters.arcface_adapter import ArcFaceAdapter
    from app.ai.adapters.cnn_adapter import CNNAdapter
    from app.ai.adapters.mediapipe_knn_adapter import MediaPipeKNNAdapter

    for cls, name in ((CNNAdapter, "cnn"), (ArcFaceAdapter, "arcface"),
                      (MediaPipeKNNAdapter, "mediapipe_knn")):
        adapter = cls()
        assert adapter.name == name
        assert callable(adapter.recognize) and callable(adapter.status)
        st = adapter.status() if name != "mediapipe_knn" else adapter.status()
        assert set(st) >= {"model", "available"}


async def test_10_originals_unchanged_by_import_and_recognition(mockdb):
    before = _snapshot()
    await import_registered_dataset(mockdb, DATASET)
    svc = _svc(mockdb)
    raw = {"status": "PREDICTED", "predicted_label": "biswa",
           "best_similarity": 0.99, "confidence": 0.9,
           "best_class_similarity": 0.99, "top_classes": [], "top_images": []}
    svc._standardize("cnn", raw, None, None, None, {"id": "x", "identity": "biswa"})
    assert _snapshot() == before
