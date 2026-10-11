"""MediaPipe + KNN adapter — calls the ORIGINAL landmark pipeline.

Original implementation: <mpp>/src/mediapipe_knn/predict.py
Authoritative artifacts (read-only, never modified):
    models/face_landmarker.task          (via mp.tasks.vision.FaceLandmarker)
    models/mediapipe_knn.joblib          (trained KNN, loaded as-is)
    data/mediapipe_features/y.npy        (per-row identity labels)

Pipeline mirrored exactly from the original script:
    bytes -> cv2 decode -> BGR->RGB -> mp.Image -> FaceLandmarker.detect ->
    x,y,z per landmark (478*3 floats) -> knn.predict ->
    kneighbors distances -> similarity = 1/(1+distance),
    relative confidence = mean(similarities).

No substitute landmark model (e.g. solutions.face_mesh) and no retraining
is used anywhere: if the ORIGINAL asset is absent the adapter reports
unavailable and raises AIMissingDependency on recognize().
"""
import os
import threading

import cv2
import numpy as np

from ...config import settings
from .. import index_ext
from ..result import AIMissingDependency


class MediaPipeKNNAdapter:
    name = "mediapipe_knn"

    def __init__(self):
        self._lock = threading.Lock()
        self._infer_lock = threading.Lock()  # a FaceLandmarker is not thread-safe
        self._loaded = False
        self._error: str | None = None
        self._landmarker = None
        self._knn = None
        self._labels = None
        self._knn_info: dict | None = None
        # Optional provenance: original paths.npy aligns 1:1 with y.npy rows.
        # Recognition never depends on it; used only to point at the exact
        # ORIGINAL training photo behind a nearest-neighbour row.
        self._paths = None
        # Extension overlay (people added via the API): the DERIVED KNN is
        # re-fit with identical construction params over original + added
        # rows; the original joblib file is never rewritten.
        self._ext_rows = 0

    def required_paths(self) -> dict:
        return {
            "landmarker_task": settings.mediapipe_task_path,
            "knn": settings.mediapipe_knn_path,
            "labels": settings.mediapipe_y_path,
        }

    def missing_paths(self) -> dict:
        return {k: p for k, p in self.required_paths().items() if not os.path.exists(p)}

    def knn_compatibility(self) -> dict:
        """Read-only check that the ORIGINAL KNN/labels/dims are mutually
        compatible (landmarker asset still required separately to run)."""
        if self._knn_info is None:
            try:
                import joblib
                import numpy as np

                knn = joblib.load(settings.mediapipe_knn_path)
                y = np.load(settings.mediapipe_y_path, allow_pickle=True)
                self._knn_info = {
                    "knn_type": type(knn).__name__,
                    "n_neighbors": int(knn.n_neighbors),
                    "metric": str(knn.metric),
                    "n_features_in": int(knn.n_features_in_),
                    "n_classes": int(len(knn.classes_)),
                    "labels_file_rows": int(len(y)),
                    "expects_478_landmarks_x3": int(knn.n_features_in_) == 478 * 3,
                }
            except Exception as exc:
                self._knn_info = {"error": str(exc)}
        return self._knn_info

    def is_available(self) -> bool:
        return self.load() and self._error is None

    def status(self) -> dict:
        self.load()
        return {
            "model": self.name,
            "available": self._error is None,
            "error": self._error,
            "missing_paths": self.missing_paths(),
            "knn_compatibility": self.knn_compatibility(),
            "extension_rows": self._ext_rows,
        }

    def load(self) -> bool:
        # Loads ONLY the ORIGINAL artifacts with the ORIGINAL construction
        # parameters from predict.py (IMAGE running mode, num_faces=1).
        with self._lock:
            if self._loaded:
                return self._error is None
            self._loaded = True
            missing = self.missing_paths()
            if missing:
                self._error = (
                    "Missing ORIGINAL MediaPipe asset(s): " + ", ".join(missing.values())
                    + ". The original pipeline requires models/face_landmarker.task; "
                    "no substitute landmark model is used."
                )
                return False
            try:
                import joblib
                import mediapipe as mp

                self._load_index_data()

                BaseOptions = mp.tasks.BaseOptions
                options = mp.tasks.vision.FaceLandmarkerOptions(
                    base_options=BaseOptions(model_asset_path=settings.mediapipe_task_path),
                    running_mode=mp.tasks.vision.RunningMode.IMAGE,
                    num_faces=1,
                )
                self._landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)
            except Exception as exc:  # never invent results; report init failure
                detail = str(exc)
                if "4551" in detail or "Application Control" in detail:
                    detail += (
                        " — Windows (Smart App Control / WDAC) blocked mediapipe's "
                        "native runtime libmediapipe.dll, so the ORIGINAL MediaPipe "
                        "pipeline cannot load on this machine; no substitute is used."
                    )
                self._error = f"MediaPipe + KNN init failed: {detail}"
                return False
            return True

    def _load_index_data(self) -> None:
        import joblib

        self._knn = joblib.load(settings.mediapipe_knn_path)
        self._labels = np.load(settings.mediapipe_y_path, allow_pickle=True).astype(str)

        # Read-only provenance (optional): original paths.npy rows
        # align 1:1 with the y.npy training rows.
        _pp = os.path.join(os.path.dirname(settings.mediapipe_y_path), "paths.npy")
        if os.path.exists(_pp):
            try:
                self._paths = [str(p) for p in np.load(_pp, allow_pickle=True)]
            except Exception:
                self._paths = None
        self._merge_extensions()

    def _merge_extensions(self) -> None:
        """Re-fit the DERIVED KNN over original + API-added rows.

        sklearn KNeighborsClassifier.get_params() captures the original
        construction exactly; fit() only stores the training rows."""
        self._ext_rows = 0
        ext = index_ext.load_ext("mediapipe_knn")
        if not ext or len(ext["labels"]) == 0:
            return
        from sklearn.base import clone

        fit_X = getattr(self._knn, "_fit_X", None)
        if fit_X is None or len(fit_X) != len(self._labels):
            return  # unexpected original layout: never risk misalignment
        merged_X = np.vstack([fit_X, ext["embeddings"]]).astype(np.float32)
        merged_y = np.concatenate([self._labels, ext["labels"].astype(str)])
        refit = clone(self._knn)
        refit.fit(merged_X, merged_y)
        self._knn = refit
        self._labels = merged_y
        orig_len = len(fit_X)
        if self._paths is not None and len(self._paths) == orig_len:
            self._paths = self._paths + [str(p) for p in ext["paths"]]
        else:
            self._paths = None
        self._ext_rows = int(len(ext["labels"]))

    def reload_index(self) -> None:
        """Re-read original + extension index data (landmarker stays in memory)."""
        with self._lock:
            if not self._loaded or self._error is not None:
                return
            try:
                self._load_index_data()
            except Exception as exc:
                self._error = f"MediaPipe + KNN index reload failed: {exc}"

    def embed_image_file(self, path: str) -> np.ndarray | None:
        """Original landmark pipeline for one dataset photo file
        (None when no face is detected)."""
        if not self.load():
            raise AIMissingDependency(self._error or "MediaPipe + KNN unavailable")
        with open(path, "rb") as fh:
            return self._features(fh.read())

    # ---- inference (original pipeline) ----
    def _features(self, image_bytes: bytes) -> np.ndarray | None:
        """Raw x,y,z per landmark — the exact feature layout of the original
        extract_landmarks.py (no extra normalization is applied)."""
        import mediapipe as mp

        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Could not decode image bytes")
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        with self._infer_lock:
            result = self._landmarker.detect(mp_image)
        if not result.face_landmarks:
            return None
        features: list[float] = []
        for landmark in result.face_landmarks[0]:
            features.extend([landmark.x, landmark.y, landmark.z])
        return np.array(features, dtype=np.float32)

    def recognize(self, image_bytes: bytes, top_k: int = 10) -> dict:
        """Returns only values produced by the ORIGINAL pipeline."""
        if not self.load():
            raise AIMissingDependency(self._error or "MediaPipe + KNN unavailable")
        features = self._features(image_bytes)
        if features is None:
            return {"model": self.name, "predicted_label": None,
                    "status": "NO_FACE_DETECTED", "similarity": None, "confidence": None,
                    "top_matches": [], "neighbor_votes": []}
        X = features.reshape(1, -1)

        predicted_person = str(self._knn.predict(X)[0])

        n_neighbors = int(self._knn.n_neighbors)
        distances, indices = self._knn.kneighbors(X, n_neighbors=n_neighbors)
        distances = distances[0]
        indices = indices[0]
        neighbor_labels = self._labels[indices]

        # Original relative score (NOT a calibrated probability):
        # similarity = 1 / (1 + distance); confidence = mean(similarities)
        similarities = 1.0 / (1.0 + distances)
        confidence_score = float(np.mean(similarities))

        top_matches = []
        for rank, i in enumerate(indices, start=1):
            d = distances[rank - 1]
            entry = {"rank": rank, "photo_id": int(i),
                     "label": str(neighbor_labels[rank - 1]),
                     "distance": round(float(d), 6),
                     "similarity": round(float(1.0 / (1.0 + d)), 4)}
            # Source photo from the ORIGINAL paths.npy (same row order as y).
            if self._paths is not None and 0 <= int(i) < len(self._paths):
                entry["source"] = self._paths[int(i)]
            top_matches.append(entry)
        top_matches = top_matches[:top_k]

        people, counts = np.unique(neighbor_labels, return_counts=True)
        vote_order = np.argsort(counts)[::-1]
        neighbor_votes = [
            {"label": str(people[i]), "votes": int(counts[i]),
             "of": int(len(neighbor_labels))}
            for i in vote_order
        ]

        return {
            "model": self.name,
            "predicted_label": predicted_person,
            "similarity": round(confidence_score, 4),
            "confidence": None,  # original prints a relative score, not a probability
            "n_neighbors": n_neighbors,
            "status": "PREDICTED",
            "top_matches": top_matches,
            "neighbor_votes": neighbor_votes,
        }
