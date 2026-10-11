"""ArcFace adapter — calls the ORIGINAL ArcFace pipeline.

Original implementation: <mpp>/src/arcface/predict.py
Authoritative artifacts (read-only, never modified):
    data/arcface_features/X.npy
    data/arcface_features/y.npy
    ~/.insightface/models/buffalo_l/w600k_r50.onnx  (InsightFace cache)

Pipeline mirrored from the original script:
    small image (min side < 200) -> resize 112x112 -> get_feat -> 512-D
    normal photo -> FaceAnalysis detect -> largest face embedding
    cosine similarities -> class score = mean of top-5 per class
    decision: MATCH (>=0.60 with margin >=0.10), POSSIBLE (>=0.50),
              else NO RELIABLE MATCH.
"""
import os
import threading

import cv2
import numpy as np

from ...config import settings
from .. import index_ext
from ..result import AIMissingDependency


def _normalize(vec) -> np.ndarray:
    vec = np.asarray(vec, dtype=np.float32)
    norm = np.linalg.norm(vec)
    return vec if norm == 0 else vec / norm


class ArcFaceAdapter:
    name = "arcface"

    def __init__(self):
        self._lock = threading.Lock()
        self._infer_lock = threading.Lock()
        self._loaded = False
        self._error: str | None = None
        self._app = None
        self._recognition_model = None
        self._X = None
        self._y = None
        # Extension overlay (people added via the API), merged AFTER the
        # original rows; original X.npy/y.npy/paths.npy stay untouched.
        self._ext_rows = 0

    def required_paths(self) -> dict:
        return {
            "train_embeddings": settings.arcface_x_path,
            "train_labels": settings.arcface_y_path,
            "onnx": settings.arcface_model_path,
        }

    def missing_paths(self) -> dict:
        return {k: p for k, p in self.required_paths().items() if not os.path.exists(p)}

    def status(self) -> dict:
        self.load()
        return {
            "model": self.name,
            "available": self._error is None,
            "error": self._error,
            "missing_paths": self.missing_paths(),
            "extension_rows": self._ext_rows,
        }

    def load(self) -> bool:
        with self._lock:
            if self._loaded:
                return self._error is None
            self._loaded = True
            missing = self.missing_paths()
            if missing:
                self._error = "Missing ORIGINAL ArcFace artifacts: " + ", ".join(missing.values())
                return False
            try:
                self._load_index_data()
                from insightface.app import FaceAnalysis
                from insightface.model_zoo import get_model

                self._app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
                self._app.prepare(ctx_id=0, det_size=(640, 640))
                self._recognition_model = get_model(settings.arcface_model_path)
                self._recognition_model.prepare(ctx_id=0)
            except Exception as exc:
                self._error = f"ArcFace init failed: {exc}"
                return False
            return True

    def _load_index_data(self) -> None:
        self._X = np.load(settings.arcface_x_path)
        self._y = np.load(settings.arcface_y_path)
        # Provenance: original paths.npy aligns 1:1 with X/y rows.
        # Optional — recognition never depends on it.
        self._paths = None
        _pp = os.path.join(os.path.dirname(settings.arcface_x_path), "paths.npy")
        if os.path.exists(_pp):
            try:
                self._paths = [str(p) for p in np.load(_pp, allow_pickle=True)]
            except Exception:
                self._paths = None
        self._merge_extensions()

    def _merge_extensions(self) -> None:
        """Append API-added rows after the original rows (none → untouched)."""
        self._ext_rows = 0
        ext = index_ext.load_ext("arcface")
        if not ext or len(ext["labels"]) == 0:
            return
        orig_len = len(self._X)
        self._X = np.vstack([self._X, ext["embeddings"]]).astype(np.float32)
        self._y = np.concatenate([self._y.astype(str), ext["labels"].astype(str)])
        ext_paths = [str(p) for p in ext["paths"]]
        # Only merge paths when the original provenance is present and
        # row-aligned — otherwise drop provenance rather than misalign it.
        if self._paths is not None and len(self._paths) == orig_len:
            self._paths = self._paths + ext_paths
        else:
            self._paths = None
        self._ext_rows = int(len(ext_paths))

    def reload_index(self) -> None:
        """Re-read original + extension index data (models stay in memory)."""
        with self._lock:
            if not self._loaded or self._error is not None:
                return
            try:
                self._load_index_data()
            except Exception as exc:
                self._error = f"ArcFace index reload failed: {exc}"

    def embed_image_file(self, path: str) -> np.ndarray | None:
        """Original embedding pipeline for one dataset photo file
        (None when no face is detected — mirroring the query-image rules)."""
        if not self.load():
            raise AIMissingDependency(self._error or "ArcFace unavailable")
        image = cv2.imread(path, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Could not decode dataset photo: {path}")
        h, w = image.shape[:2]
        if min(h, w) <= 200:
            return self._crop_embedding(image)
        embedding, _count = self._photo_embedding(image)
        if embedding is None and min(h, w) <= 300 and 0.75 <= (w / h) <= 1.33:
            return self._crop_embedding(image)
        return embedding

    # ---- original pipeline ----
    def _crop_embedding(self, image):
        resized = cv2.resize(image, (112, 112), interpolation=cv2.INTER_CUBIC)
        with self._infer_lock:  # insightface sessions are not thread-safe
            feat = self._recognition_model.get_feat(resized)[0]
        return _normalize(feat)

    def _photo_embedding(self, image):
        with self._infer_lock:
            faces = self._app.get(image)
        if len(faces) == 0:
            h, w = image.shape[:2]
            if max(h, w) < 640:
                pad_top = (640 - h) // 2
                pad_bottom = 640 - h - pad_top
                pad_left = (640 - w) // 2
                pad_right = 640 - w - pad_left
                padded = cv2.copyMakeBorder(image, pad_top, pad_bottom, pad_left, pad_right, cv2.BORDER_REPLICATE)
                with self._infer_lock:
                    faces = self._app.get(padded)
        if len(faces) == 0:
            return None, 0
        faces = sorted(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
        return _normalize(faces[0].embedding), len(faces)

    def embed_query(self, image_bytes: bytes) -> np.ndarray | None:
        """L2-normalized query embedding via the ORIGINAL ArcFace pipeline.

        Same decode + crop/photo branch that recognize() uses (None when no
        face is detected). Provided so the orchestration layer can compare a
        query against stored field-report photos. Raises ValueError on
        undecodable bytes, AIMissingDependency when unavailable."""
        if not self.load():
            raise AIMissingDependency(self._error or "ArcFace unavailable")
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Could not decode image bytes")
        h, w = image.shape[:2]
        if min(h, w) <= 200:
            return self._crop_embedding(image)
        embedding, _count = self._photo_embedding(image)
        if embedding is None and min(h, w) <= 300 and 0.75 <= (w / h) <= 1.33:
            return self._crop_embedding(image)
        return embedding

    def recognize(self, image_bytes: bytes, top_k: int = 10) -> dict:
        """Returns only values produced by the ORIGINAL pipeline."""
        if not self.load():
            raise AIMissingDependency(self._error or "ArcFace unavailable")
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Could not decode image bytes")
        h, w = image.shape[:2]
        if min(h, w) <= 200:
            test_embedding = self._crop_embedding(image)
            input_type = "LFW_CROP"
        else:
            test_embedding, _count = self._photo_embedding(image)
            if test_embedding is None and min(h, w) <= 300 and 0.75 <= (w / h) <= 1.33:
                test_embedding = self._crop_embedding(image)
                input_type = "FACE_CROP"
            elif test_embedding is None:
                return {"model": self.name, "predicted_label": None,
                        "status": "NO_FACE_DETECTED", "similarity": None, "confidence": None,
                        "top_classes": [], "top_matches": []}
            else:
                input_type = "NORMAL_PHOTO"

        targets = np.array([_normalize(x) for x in self._X])
        similarities = np.dot(targets, test_embedding)

        per_person: dict[str, list[float]] = {}
        for idx, person in enumerate(self._y):
            per_person.setdefault(str(person), []).append(float(similarities[idx]))
        class_results = []
        for person, scores in per_person.items():
            top = sorted(scores)[-min(5, len(scores)):]
            class_results.append((person, float(np.mean(top)), float(np.max(scores))))
        class_results.sort(key=lambda r: r[1], reverse=True)

        best_person, best_class, best_single = class_results[0]
        second = class_results[1][1] if len(class_results) > 1 else 0.0
        margin = best_class - second
        if best_class >= 0.60 and margin >= 0.10:
            decision = "MATCH_FOUND"
        elif best_class >= 0.50:
            decision = "POSSIBLE_MATCH"
        else:
            decision = "NO_RELIABLE_MATCH"

        order = np.argsort(similarities)[::-1][:top_k]
        top_matches = []
        for rank, i in enumerate(order, start=1):
            entry = {"rank": rank, "photo_id": int(i),
                     "label": str(self._y[i]),
                     "similarity": round(float(similarities[i]), 4)}
            # Source photo from the ORIGINAL paths.npy (same row order as X/y).
            if self._paths is not None and 0 <= int(i) < len(self._paths):
                entry["source"] = self._paths[int(i)]
            top_matches.append(entry)
        return {
            "model": self.name,
            "predicted_label": best_person,
            "similarity": round(best_class, 4),
            "confidence": None,  # original pipeline emits similarities, not probabilities
            "best_individual_similarity": round(best_single, 4),
            "margin": round(margin, 4),
            "input_type": input_type,
            "status": decision,
            "top_classes": [
                {"label": p, "score": round(s, 4), "best": round(b, 4)}
                for p, s, b in class_results[:top_k]
            ],
            "top_matches": top_matches,
        }
