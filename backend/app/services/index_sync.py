"""Incremental index synchronization for the ORIGINAL model indexes.

When a person is added via the API their photos are embedded with the
ORIGINAL adapters' own extraction pipeline and appended to the extension
overlay (app.ai.index_ext). Adapters merge those rows at load/reload, so
subsequent recognition searches see the new person WITHOUT modifying any
original artifact (weights and original index files stay read-only).

reindex_all() rebuilds the extension stores deterministically from the
registered dataset on disk: every photo not covered by the ORIGINAL index
is embedded, and the extension store is rewritten to exactly the
successfully-embedded set. Stale rows (photos deleted from disk) drop
out; photos that fail embedding stay uncovered and are retried next run.
Covered set = original index keys ∪ extension keys, so re-running is
idempotent.
"""
import asyncio
import os
import time

import numpy as np

from ..ai import gallery, index_ext, registry

_MODELS = ("cnn", "arcface", "mediapipe_knn")

_ADAPTERS = {
    "cnn": registry.get_cnn,
    "arcface": registry.get_arcface,
    "mediapipe_knn": registry.get_mediapipe_knn,
}


def _disk_photos() -> list[tuple[str, str, str]]:
    """(identity, filename, absolute path) for every registered dataset photo."""
    root = gallery.gallery_dir()
    out = []
    try:
        identities = sorted(os.listdir(root))
    except OSError:
        return out
    for identity in identities:
        folder = os.path.join(root, identity)
        if not os.path.isdir(folder):
            continue
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            continue
        for name in names:
            full = os.path.join(folder, name)
            if os.path.isfile(full) and os.path.splitext(name)[1].lower() in gallery.SUPPORTED_PHOTO_EXTS:
                out.append((identity, name, full))
    return out


def _covered_keys(model: str) -> set[str]:
    """Photos already indexed: original index keys + extension keys."""
    keys: set[str] = set()
    orig = index_ext.original_photo_keys(model)
    if orig:
        keys |= orig
    ext = index_ext.load_ext(model)
    if ext is not None:
        keys |= {index_ext.rel_key(p) for p in ext["paths"]}
    return keys


def _candidates(model: str) -> list[tuple[str, str, str]]:
    """Dataset photos not yet indexed by this model.

    CNN originals have no per-photo provenance, so the original CNN index
    is treated as covering exactly its 22 label identities; photos of any
    other identity are candidates. ArcFace/MediaPipe have per-photo
    provenance (paths.npy), so coverage is per photo — including extra
    photos of original identities that were never indexed."""
    photos = _disk_photos()
    if model == "cnn":
        orig_labels = index_ext.original_label_set("cnn") or set()
        ext = index_ext.load_ext("cnn")
        ext_paths = set(ext["paths"].tolist()) if ext is not None else set()
        return [
            (identity, name, path)
            for identity, name, path in photos
            if identity not in orig_labels and path not in ext_paths
        ]
    covered = _covered_keys(model)
    return [
        (identity, name, path)
        for identity, name, path in photos
        if index_ext.rel_key(path) not in covered
    ]


def _embed_files(model: str, paths: list[str]) -> dict:
    """Embed photos with the ORIGINAL adapter pipeline (runs in a worker thread).

    Returns {"embeddings": [...], "labels": [...], "paths": [...],
    "failed": [{file, error}...]}. Raises AIMissingDependency when the
    model is unavailable on this machine."""
    adapter = _ADAPTERS[model]()
    if not adapter.load():
        from ..ai.result import AIMissingDependency

        raise AIMissingDependency(adapter._error or f"{model} unavailable")
    embeddings, labels, out_paths, failed = [], [], [], []
    for path in paths:
        try:
            vec = adapter.embed_image_file(path)
        except Exception as exc:  # corrupt file, runtime hiccup — report, continue
            failed.append({"file": os.path.basename(path), "error": str(exc)})
            continue
        if vec is None:
            failed.append({"file": os.path.basename(path), "error": "no face detected"})
            continue
        embeddings.append(np.asarray(vec, dtype=np.float32))
        labels.append(os.path.basename(os.path.dirname(path)))
        out_paths.append(path)
    return {"embeddings": embeddings, "labels": labels, "paths": out_paths,
            "failed": failed}


async def _embed_files_threaded(model: str, paths: list[str]) -> dict:
    return await asyncio.to_thread(_embed_files, model, paths)


async def _append_and_reload(model: str, embedded: dict) -> int:
    if not embedded["embeddings"]:
        return 0
    added = await asyncio.to_thread(
        index_ext.append_ext,
        model,
        np.vstack(embedded["embeddings"]),
        embedded["labels"],
        embedded["paths"],
    )
    if added:
        await asyncio.to_thread(_ADAPTERS[model]().reload_index)
    return added


async def index_photos(identity: str, filenames: list[str]) -> dict:
    """Incrementally index one person's newly stored photos across all models.

    Called after photos land in data/registered/<identity>/ so the person
    becomes recognizable by subsequent searches. Per-model outcomes are
    reported; a model that is unavailable or skips never blocks the rest."""
    root = gallery.gallery_dir()
    paths = [os.path.join(root, identity, name) for name in filenames]
    report: dict = {}
    for model in _MODELS:
        started = time.perf_counter()
        entry: dict = {"added": 0, "failed": []}
        # The original CNN index is class-level; photos added to an identity
        # it already knows cannot be merged safely (no per-row provenance).
        if model == "cnn" and identity in (index_ext.original_label_set("cnn") or set()):
            entry["status"] = "skipped"
            entry["reason"] = ("identity is already in the original CNN index; "
                               "the original CNN features carry no per-photo "
                               "provenance, so only new identities are extended")
        else:
            try:
                embedded = await _embed_files_threaded(model, paths)
            except Exception as exc:  # model unavailable on this machine
                entry["status"] = "unavailable"
                entry["error"] = str(exc)
            else:
                entry["added"] = await _append_and_reload(model, embedded)
                entry["failed"] = embedded["failed"]
                entry["status"] = "updated" if entry["added"] else "no_change"
        entry["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
        report[model] = entry
    return report


async def reindex_all() -> dict:
    """Synchronize the extension stores with the registered dataset on disk.

    Incremental and idempotent: photos already covered by the ORIGINAL index
    are never touched; extension rows whose file vanished from disk are
    evicted (reported as removed_stale); photos never indexed yet (new
    identities, or stored-but-never-indexed files) are embedded with the
    original pipeline and appended. Re-running changes nothing."""
    report: dict = {}
    for model in _MODELS:
        started = time.perf_counter()
        entry: dict = {"added": 0, "removed_stale": 0, "failed": []}
        old = index_ext.load_ext(model)

        # 1. Evict extension rows whose photo no longer exists on disk.
        keep_idx = []
        if old is not None:
            for i, path in enumerate(old["paths"]):
                if os.path.isfile(str(path)):
                    keep_idx.append(i)
                else:
                    entry["removed_stale"] += 1

        # 2. Embed photos not covered by the original index or the (valid)
        #    extension rows.
        try:
            candidates = _candidates(model)
            if candidates:
                embedded = await _embed_files_threaded(
                    model, [path for _identity, _name, path in candidates])
            else:
                embedded = {"embeddings": [], "labels": [], "paths": [], "failed": []}
        except Exception as exc:
            entry["status"] = "unavailable"
            entry["error"] = str(exc)
            entry["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
            report[model] = entry
            continue
        entry["failed"] = embedded["failed"]

        # 3. Persist kept + newly embedded rows.
        rows_emb = [old["embeddings"][i] for i in keep_idx] if old is not None else []
        rows_lab = [str(old["labels"][i]) for i in keep_idx] if old is not None else []
        rows_path = [str(old["paths"][i]) for i in keep_idx] if old is not None else []
        rows_emb.extend(embedded["embeddings"])
        rows_lab.extend(embedded["labels"])
        rows_path.extend(embedded["paths"])
        entry["added"] = len(embedded["paths"])
        if rows_emb:
            await asyncio.to_thread(
                index_ext.save_ext, model,
                np.vstack(rows_emb).astype(np.float32), rows_lab, rows_path,
            )
        else:
            await asyncio.to_thread(index_ext.clear_ext, model)
        entry["status"] = "updated" if (entry["added"] or entry["removed_stale"]) else "no_change"
        await asyncio.to_thread(_ADAPTERS[model]().reload_index)
        entry["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
        report[model] = entry
    return report


def status_report() -> dict:
    """Index coverage summary (no model loading — reads npy shapes only)."""
    import numpy as np

    from ..config import settings

    out: dict = {}
    for model in _MODELS:
        entry: dict = {"extension_rows": index_ext.ext_row_count(model)}
        try:
            if model == "cnn":
                entry["original_rows"] = int(len(np.load(settings.cnn_train_labels_path)))
            elif model == "arcface":
                entry["original_rows"] = int(len(np.load(settings.arcface_y_path)))
            else:
                entry["original_rows"] = int(len(np.load(settings.mediapipe_y_path)))
        except Exception:
            entry["original_rows"] = None
        try:
            entry["pending_candidates"] = len(_candidates(model))
        except Exception:
            entry["pending_candidates"] = None
        out[model] = entry
    return out
