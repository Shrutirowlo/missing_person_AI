"""Extension overlay for the ORIGINAL model feature indexes.

The original CNN / ArcFace / MediaPipe indexes are artifacts of the original
mpp training pipeline and are treated as READ-ONLY (never overwritten, never
retrained). To make people added through the API recognizable anyway, this
module maintains a small *extension* store per model:

    <storage_dir>/indexes/<model>/embeddings.npy   float32 rows, original pipeline
    <storage_dir>/indexes/<model>/labels.npy       identity string per row
    <storage_dir>/indexes/<model>/paths.npy        absolute dataset photo path

Adapters merge these rows AFTER the original index rows at load time, so
original row indices stay valid and the original artifacts are untouched.
Writes are atomic (tmp file + os.replace) and appends de-duplicate by path,
which keeps repeated uploads/reindex runs idempotent.
"""
import os

import numpy as np

from ..config import settings

_MODELS = ("cnn", "arcface", "mediapipe_knn")


def extension_root() -> str:
    """Directory that holds per-model extension stores (monkeypatchable in tests)."""
    return os.path.join(settings.storage_dir, "indexes")


def model_dir(model: str) -> str:
    return os.path.join(extension_root(), model)


def _file(model: str, kind: str) -> str:
    return os.path.join(model_dir(model), f"{kind}.npy")


def load_ext(model: str) -> dict | None:
    """Returns {'embeddings','labels','paths'} or None when no extension exists."""
    emb_path = _file(model, "embeddings")
    if not os.path.isfile(emb_path):
        return None
    try:
        return {
            "embeddings": np.load(emb_path),
            "labels": np.load(_file(model, "labels"), allow_pickle=True).astype(str),
            "paths": np.load(_file(model, "paths"), allow_pickle=True).astype(str),
        }
    except Exception:
        return None


def save_ext(model: str, embeddings: np.ndarray, labels, paths) -> None:
    """Atomically (re)write the extension store for a model."""
    os.makedirs(model_dir(model), exist_ok=True)
    arrays = {
        "embeddings": np.asarray(embeddings, dtype=np.float32),
        "labels": np.asarray([str(x) for x in labels]),
        "paths": np.asarray([str(x) for x in paths]),
    }
    for kind, arr in arrays.items():
        # NOTE: np.save appends ".npy" unless the name already ends with it,
        # so the tmp name must keep the .npy suffix or os.replace below
        # fails with FileNotFoundError.
        tmp = _file(model, kind) + ".tmp.npy"
        np.save(tmp, arr)
        os.replace(tmp, _file(model, kind))


def append_ext(model: str, embeddings: np.ndarray, labels, paths) -> int:
    """Append rows, skipping any photo path already present. Returns rows added."""
    incoming_paths = [str(p) for p in paths]
    existing = load_ext(model)
    if existing is not None:
        have = set(existing["paths"].tolist())
        keep = [i for i, p in enumerate(incoming_paths) if p not in have]
        if not keep:
            return 0
        embeddings = np.asarray(embeddings, dtype=np.float32)[keep]
        labels = [str(labels[i]) for i in keep]
        paths = [incoming_paths[i] for i in keep]
        embeddings = np.vstack([existing["embeddings"], embeddings])
        labels = list(existing["labels"]) + labels
        paths = list(existing["paths"]) + paths
    save_ext(model, embeddings, labels, paths)
    return len(paths) if existing is None else len(keep)


def clear_ext(model: str) -> None:
    for kind in ("embeddings", "labels", "paths"):
        try:
            os.remove(_file(model, kind))
        except OSError:
            pass


def ext_row_count(model: str) -> int:
    ext = load_ext(model)
    return int(len(ext["labels"])) if ext is not None else 0


# ---- coverage vs the ORIGINAL indexes (drives reindex candidates) ----


def registered_root() -> str:
    from . import gallery

    return gallery.gallery_dir()


def rel_key(abs_path: str) -> str:
    """'C:/.../data/registered/<identity>/<file>' -> '<identity>/<file>'."""
    try:
        return os.path.relpath(abs_path, registered_root()).replace("\\", "/")
    except ValueError:
        return os.path.basename(abs_path)


def original_photo_keys(model: str) -> set[str] | None:
    """Relative photo keys already covered by the ORIGINAL index.

    None for models whose original index carries no per-photo provenance
    (the original CNN index is class-level only)."""
    if model == "arcface":
        path = os.path.join(os.path.dirname(settings.arcface_x_path), "paths.npy")
    elif model == "mediapipe_knn":
        path = os.path.join(os.path.dirname(settings.mediapipe_y_path), "paths.npy")
    else:
        return None
    if not os.path.isfile(path):
        return set()
    try:
        return {rel_key(str(p)) for p in np.load(path, allow_pickle=True)}
    except Exception:
        return set()


def original_label_set(model: str) -> set[str] | None:
    """Identities the ORIGINAL index knows (None when not applicable)."""
    if model == "cnn":
        if not os.path.isfile(settings.cnn_labels_path):
            return set()
        try:
            return {str(x) for x in np.load(settings.cnn_labels_path, allow_pickle=True)}
        except Exception:
            return set()
    if model == "arcface":
        if not os.path.isfile(settings.arcface_y_path):
            return set()
        try:
            return {str(x) for x in np.load(settings.arcface_y_path, allow_pickle=True)}
        except Exception:
            return set()
    if model == "mediapipe_knn":
        if not os.path.isfile(settings.mediapipe_y_path):
            return set()
        try:
            return {str(x) for x in np.load(settings.mediapipe_y_path, allow_pickle=True)}
        except Exception:
            return set()
    return None
