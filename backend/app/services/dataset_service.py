"""Read-only access to the ORIGINAL mpp/data dataset.

The dataset that the ORIGINAL models search is the photo collection under
MPP_ORIGINAL_ROOT/data (indexed by the ORIGINAL feature files). This
service only *reads* those original files to (a) describe the dataset and
(b) serve an individual dataset photo by its feature-row index. No file
is ever written, moved, or modified; user input is only ever an integer
index — never a path — and served files must resolve inside the dataset
root (containment enforced).
"""
import mimetypes
import os

from ..ai import gallery, registry
from ..config import settings


def dataset_root() -> str:
    return os.path.join(
        os.getenv("MPP_ORIGINAL_ROOT", r"C:/Users/shrut_hi39oyy/Downloads/mpp/mpp"), "data"
    )


def info() -> dict:
    cnn = registry.get_cnn()
    cnn.load()
    arc = registry.get_arcface()
    arc.load()
    mp_knn = registry.get_mediapipe_knn()
    mp_status = mp_knn.status()
    return {
        "root": dataset_root(),
        "gallery": {
            "identities": sorted(gallery.identities()),
            "counts": {name: gallery.image_count(name) for name in sorted(gallery.identities())},
        },
        "cnn": {
            "train_embeddings": int(cnn._train_embeddings.shape[0]) if cnn._train_embeddings is not None else 0,
            "people": int(len(cnn._labels)) if cnn._labels is not None else 0,
            "per_photo_sources": False,
            "note": "Original CNN index stores label+similarity per training photo, no source file per row.",
        },
        "arcface": {
            "train_embeddings": int(arc._X.shape[0]) if arc._X is not None else 0,
            "people": int(len(set(str(p) for p in arc._y))) if arc._y is not None else 0,
            "per_photo_sources": arc._paths is not None,
        },
        "mediapipe_knn": {
            "available": bool(mp_status.get("available")),
            "per_photo_sources": mp_knn._paths is not None,
            "error": mp_status.get("error"),
        },
    }


def resolve_arcface_photo(index: int) -> str:
    """Returns the verified absolute path of dataset photo `index`.

    Raises LookupError/ValueError on any problem — callers map to 404/400.
    """
    arc = registry.get_arcface()
    if not arc.load():
        raise LookupError("ArcFace artifacts unavailable")
    paths = arc._paths
    if paths is None:
        raise LookupError("Original ArcFace paths.npy not present")
    return _verified_dataset_photo(paths, index)


def resolve_mediapipe_photo(index: int) -> str:
    """Returns the verified absolute path of dataset photo `index` for the
    MediaPipe + KNN training rows (original y.npy row order, with the API
    extension rows appended after the original ones). Reads paths directly
    — independent of the mediapipe runtime, which can be unavailable on some
    machines. Raises LookupError on any problem — callers map to 404/400."""
    import numpy as np

    from ..ai import index_ext

    paths_file = os.path.join(dataset_root(), "mediapipe_features", "paths.npy")
    paths: list[str] = []
    if os.path.isfile(paths_file):
        try:
            paths = [str(p) for p in np.load(paths_file, allow_pickle=True)]
        except Exception as exc:
            raise LookupError(f"Original MediaPipe paths.npy unreadable: {exc}")
    ext = index_ext.load_ext("mediapipe_knn")
    if ext is not None:
        paths = paths + [str(p) for p in ext["paths"]]
    if not paths:
        raise LookupError("Original MediaPipe paths.npy not present")
    return _verified_dataset_photo(paths, index)


def _verified_dataset_photo(paths: list[str], index: int) -> str:
    if not isinstance(index, int) or index < 0 or index >= len(paths):
        raise LookupError("Dataset photo index out of range")
    candidate = os.path.realpath(paths[index])
    root = os.path.realpath(dataset_root())
    if os.path.commonpath([candidate, root]) != root or not os.path.isfile(candidate):
        raise LookupError("Dataset photo not found inside the dataset root")
    return candidate


def guess_media_type(path: str) -> str:
    return mimetypes.guess_type(path)[0] or "application/octet-stream"
