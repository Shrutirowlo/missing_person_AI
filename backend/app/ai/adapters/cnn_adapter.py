"""CNN adapter — calls the ORIGINAL authoritative embedding pipeline.

Original implementation: <mpp>/src/cnn/predict.py
Authoritative artifacts (read-only, never modified):
    models/cnn_face_embedding_model.keras
    models/cnn_embedding_knn.joblib
    models/cnn_embedding_labels.npy          (22-class, authoritative)
    data/cnn_features/cnn_train_embeddings.npy
    data/cnn_features/cnn_train_labels.npy

Pipeline mirrored exactly from the original script:
    bytes -> tf decode/resize(160,160)/cast/expand -> normalized_embedding
    layer output -> L2 normalize -> knn.predict / predict_proba ->
    cosine similarities vs train embeddings -> class score = mean of
    strongest 3 per class.

Legacy files (cnn_face_model.keras, cnn_labels.npy) are NOT used.
"""
import os
import threading

import joblib
import numpy as np

from ...config import settings
from .. import index_ext
from ..result import AIMissingDependency

IMG_SIZE = (160, 160)


class CNNAdapter:
    name = "cnn"

    def __init__(self):
        self._lock = threading.Lock()
        self._infer_lock = threading.Lock()
        self._loaded = False
        self._error: str | None = None
        self._model = None
        self._embedding_model = None
        self._knn = None
        self._labels = None
        self._train_embeddings = None
        self._train_labels = None
        # Extension overlay (people added via the API): merged rows + a
        # RE-FIT of the derived KNN only when extensions exist. The original
        # joblib/weights are never rewritten.
        self._ext_rows = 0
        self._merged_embeddings = None
        self._merged_labels = None
        self._merged_paths = None

    # ---- lifecycle ----
    def required_paths(self) -> dict:
        return {
            "model": settings.cnn_model_path,
            "knn": settings.cnn_knn_path,
            "labels": settings.cnn_labels_path,
            "train_embeddings": settings.cnn_train_embeddings_path,
            "train_labels": settings.cnn_train_labels_path,
        }

    def missing_paths(self) -> dict:
        return {k: p for k, p in self.required_paths().items() if not os.path.exists(p)}

    def is_available(self) -> bool:
        return self.load() and self._error is None

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
        # Loads ONLY the ORIGINAL artifacts. There is deliberately no
        # fallback network (no ImageNet backbone, no histogram stand-in):
        # if the originals are absent the adapter stays unavailable.
        with self._lock:
            if self._loaded:
                return self._error is None
            self._loaded = True
            missing = self.missing_paths()
            if missing:
                self._error = "Missing ORIGINAL CNN artifacts: " + ", ".join(missing.values())
                return False
            try:
                self._load_index_data()
            except Exception as exc:  # never invent results; report init failure
                self._error = f"CNN init failed: {exc}"
                return False
            return True

    def _load_index_data(self) -> None:
        import tensorflow as tf

        self._model = tf.keras.models.load_model(settings.cnn_model_path)
        self._embedding_model = tf.keras.Model(
            self._model.input,
            self._model.get_layer("normalized_embedding").output,
        )
        self._knn = joblib.load(settings.cnn_knn_path)
        self._labels = np.load(settings.cnn_labels_path, allow_pickle=True)
        self._train_embeddings = np.load(settings.cnn_train_embeddings_path)
        self._train_labels = np.load(settings.cnn_train_labels_path)
        self._merge_extensions()

    def _merge_extensions(self) -> None:
        """Merge API-added photos AFTER the original rows and refit the
        DERIVED KNN (fit = store training rows; no weights change). With no
        extension rows the original objects are used untouched."""
        self._ext_rows = 0
        self._merged_embeddings = None
        self._merged_labels = None
        self._merged_paths = None
        ext = index_ext.load_ext("cnn")
        if not ext or len(ext["labels"]) == 0:
            return
        from sklearn.base import clone

        orig_row_labels = self._labels[self._train_labels].astype(str)
        embeddings = np.vstack([self._train_embeddings, ext["embeddings"]]).astype(np.float32)
        row_labels = np.concatenate([orig_row_labels, ext["labels"].astype(str)])
        refit = clone(self._knn)
        refit.fit(embeddings, row_labels)
        self._knn = refit
        self._merged_embeddings = embeddings
        self._merged_labels = row_labels
        self._merged_paths = np.concatenate(
            [np.array([""] * len(orig_row_labels)), ext["paths"].astype(str)]
        )
        self._ext_rows = int(len(ext["labels"]))

    def reload_index(self) -> None:
        """Re-read original + extension index data (models stay in memory)."""
        with self._lock:
            if not self._loaded or self._error is not None:
                return
            try:
                self._knn = joblib.load(settings.cnn_knn_path)
                self._labels = np.load(settings.cnn_labels_path, allow_pickle=True)
                self._train_embeddings = np.load(settings.cnn_train_embeddings_path)
                self._train_labels = np.load(settings.cnn_train_labels_path)
                self._merge_extensions()
            except Exception as exc:
                self._error = f"CNN index reload failed: {exc}"

    def embed_image_file(self, path: str) -> np.ndarray:
        """Original embedding pipeline for one dataset photo file."""
        if not self.load():
            raise AIMissingDependency(self._error or "CNN unavailable")
        with open(path, "rb") as fh:
            return self._embed(fh.read())

    # ---- inference (original pipeline) ----
    def _embed(self, image_bytes: bytes) -> np.ndarray:
        import tensorflow as tf

        image = tf.image.decode_image(tf.constant(image_bytes), channels=3, expand_animations=False)
        image.set_shape([None, None, 3])
        image = tf.image.resize(image, IMG_SIZE)
        image = tf.cast(image, tf.float32)
        image = tf.expand_dims(image, axis=0)
        with self._infer_lock:  # TF runtimes are not guaranteed thread-safe
            embedding = self._embedding_model.predict(image, verbose=0)[0]
        embedding = np.asarray(embedding, dtype=np.float32)
        embedding /= max(np.linalg.norm(embedding), 1e-12)
        return embedding

    def embed_query(self, image_bytes: bytes) -> np.ndarray:
        """L2-normalized query embedding via the ORIGINAL CNN pipeline.

        Same decode gate + _embed() that recognize() uses; provided so the
        orchestration layer can compare a query against stored field-report
        photos. Raises ValueError on undecodable bytes, AIMissingDependency
        when the model is unavailable."""
        import cv2

        if not self.load():
            raise AIMissingDependency(self._error or "CNN unavailable")
        if cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR) is None:
            raise ValueError("Could not decode image bytes")
        return self._embed(image_bytes)

    def recognize(self, image_bytes: bytes, top_k: int = 10) -> dict:
        """Returns only values produced by the ORIGINAL pipeline."""
        if not self.load():
            raise AIMissingDependency(self._error or "CNN unavailable")
        # Same decodability gate as the ArcFace / MediaPipe adapters: reject
        # non-photograph bytes as ValueError BEFORE the original TF pipeline
        # runs (TF raises its own InvalidArgumentError otherwise). The
        # inference pipeline below is unchanged.
        import cv2

        if cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR) is None:
            raise ValueError("Could not decode image bytes")
        embedding = self._embed(image_bytes)
        if self._merged_embeddings is not None:
            return self._recognize_merged(embedding, top_k)
        vector = embedding.reshape(1, -1)

        predicted_index = int(self._knn.predict(vector)[0])
        predicted_person = str(self._labels[predicted_index])

        try:
            confidence = float(np.max(self._knn.predict_proba(vector)[0]))
        except Exception:
            confidence = None  # model produced no probability; never invent one

        similarities = np.dot(self._train_embeddings, embedding)
        order = np.argsort(similarities)[::-1]

        class_scores: dict[int, float] = {}
        for class_id in range(len(self._labels)):
            values = similarities[self._train_labels == class_id]
            if len(values) == 0:
                continue
            class_scores[class_id] = float(np.mean(np.sort(values)[-3:]))

        ranked = sorted(class_scores, key=class_scores.get, reverse=True)
        top_classes = [
            {"label": str(self._labels[c]), "score": round(class_scores[c], 4)}
            for c in ranked[:top_k]
        ]
        # Mirrors the original script's "TOP 10 CLOSEST TRAINING IMAGES" list:
        # per-photo ranking (label + cosine similarity). The ORIGINAL CNN
        # index stores no source file per embedding, so no photo is attached
        # here — nothing is guessed or reconstructed.
        top_images = [
            {"rank": rank, "label": str(self._labels[int(self._train_labels[i])]),
             "similarity": round(float(similarities[i]), 4)}
            for rank, i in enumerate(order[:top_k], start=1)
        ]
        return {
            "model": self.name,
            "predicted_label": predicted_person,
            "confidence": confidence,
            "best_similarity": round(float(similarities[order[0]]), 4),
            "best_class_similarity": round(class_scores.get(predicted_index, 0.0), 4),
            "top_classes": top_classes,
            "top_images": top_images,
            "status": "PREDICTED",
        }

    def _recognize_merged(self, embedding: np.ndarray, top_k: int) -> dict:
        """Same original scoring, computed over original + API-added rows.

        Per-person class score is still the mean of the strongest 3 cosine
        similarities; the only difference is that rows carry string identity
        labels and extension rows know their source photo."""
        vector = embedding.reshape(1, -1)
        predicted_person = str(self._knn.predict(vector)[0])
        try:
            confidence = float(np.max(self._knn.predict_proba(vector)[0]))
        except Exception:
            confidence = None

        embeddings = self._merged_embeddings
        row_labels = self._merged_labels
        paths = self._merged_paths
        similarities = np.dot(embeddings, embedding)
        order = np.argsort(similarities)[::-1]

        class_scores: dict[str, float] = {}
        for person in sorted(set(row_labels.tolist())):
            values = similarities[row_labels == person]
            class_scores[person] = float(np.mean(np.sort(values)[-3:]))
        ranked = sorted(class_scores, key=class_scores.get, reverse=True)
        top_classes = [
            {"label": p, "score": round(class_scores[p], 4)} for p in ranked[:top_k]
        ]
        top_images = []
        for rank, i in enumerate(order[:top_k], start=1):
            entry = {"rank": rank, "label": str(row_labels[i]),
                     "similarity": round(float(similarities[i]), 4)}
            if paths is not None and paths[i]:
                entry["source"] = paths[i]
            top_images.append(entry)
        return {
            "model": self.name,
            "predicted_label": predicted_person,
            "confidence": confidence,
            "best_similarity": round(float(similarities[order[0]]), 4),
            "best_class_similarity": round(class_scores.get(predicted_person, 0.0), 4),
            "top_classes": top_classes,
            "top_images": top_images,
            "status": "PREDICTED",
        }
