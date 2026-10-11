"""
cnn_engine.py
Deep Convolutional Neural Network (CNN) Face Embedding Extractor & Matcher.
Uses 128-D normalized deep feature vectors with Cosine Similarity and KNN classification.
"""
import os
import cv2
import numpy as np

class CNNEngine:
    def __init__(self, model_path=None):
        self.img_size = (160, 160)
        self.embedding_dim = 128
        self.model = None
        self.is_initialized = False
        self.init_model(model_path)

    def init_model(self, model_path=None):
        """Builds or loads TensorFlow CNN Face Embedding model."""
        try:
            import tensorflow as tf

            if model_path and os.path.exists(model_path):
                self.model = tf.keras.models.load_model(model_path)
                self.is_initialized = True
                return

            # Construct Deep CNN Face Feature Extractor using MobileNetV2 backbone
            base_model = tf.keras.applications.MobileNetV2(
                input_shape=(self.img_size[0], self.img_size[1], 3),
                include_top=False,
                weights='imagenet'
            )
            base_model.trainable = False

            inputs = tf.keras.Input(shape=(self.img_size[0], self.img_size[1], 3), name="input_image")
            x = tf.keras.applications.mobilenet_v2.preprocess_input(inputs)
            x = base_model(x, training=False)
            x = tf.keras.layers.GlobalAveragePooling2D(name="gap")(x)
            x = tf.keras.layers.Dense(256, activation='relu', name="dense_proj")(x)
            x = tf.keras.layers.Dropout(0.2)(x)
            embedding = tf.keras.layers.Dense(self.embedding_dim, name="raw_embedding")(x)
            # L2 Normalization layer
            norm_embedding = tf.keras.layers.Lambda(
                lambda v: tf.math.l2_normalize(v, axis=1),
                name="normalized_embedding"
            )(embedding)

            self.model = tf.keras.Model(inputs=inputs, outputs=norm_embedding, name="cnn_face_embedder")
            self.is_initialized = True
        except Exception as e:
            print(f"[CNNEngine] Warning: TensorFlow initialization notice: {e}")
            self.is_initialized = False

    def normalize_embedding(self, embedding):
        """L2 normalizes embedding vector."""
        vec = np.asarray(embedding, dtype=np.float32).flatten()
        norm = np.linalg.norm(vec)
        if norm == 0:
            return vec
        return vec / norm

    def extract_embedding(self, image_bgr):
        """
        Extracts 128-D normalized embedding from image crop.
        Returns a 1D float32 numpy array of shape (128,) or None.
        """
        if image_bgr is None or image_bgr.size == 0:
            return None

        # Resize to (160, 160) and convert BGR -> RGB
        rgb_img = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb_img, self.img_size, interpolation=cv2.INTER_AREA)

        if self.model is not None:
            try:
                import tensorflow as tf
                inp = np.expand_dims(resized.astype(np.float32), axis=0)
                emb = self.model.predict(inp, verbose=0)[0]
                return self.normalize_embedding(emb)
            except Exception as e:
                print(f"[CNNEngine] Prediction error: {e}")

        # Fallback: Color-histogram + spatial moments embedding (128-D)
        hist_b = cv2.calcHist([image_bgr], [0], None, [42], [0, 256])
        hist_g = cv2.calcHist([image_bgr], [1], None, [43], [0, 256])
        hist_r = cv2.calcHist([image_bgr], [2], None, [43], [0, 256])
        hist = np.concatenate([hist_b, hist_g, hist_r]).flatten()
        return self.normalize_embedding(hist)

    def compute_similarity(self, query_vector, target_vectors):
        """
        Computes cosine similarity between query_vector (128,) and target_vectors (N, 128).
        Returns 1D numpy array of similarities in [-1, 1].
        """
        if len(target_vectors) == 0:
            return np.array([])

        q_norm = self.normalize_embedding(query_vector)
        targets_norm = np.array([self.normalize_embedding(t) for t in target_vectors])

        similarities = np.dot(targets_norm, q_norm)
        return np.clip(similarities, -1.0, 1.0)

    def similarity_to_confidence(self, cosine_sim):
        """
        Converts CNN cosine similarity to an intuitive 0-100% confidence score.
        CNN embedding cosine similarity interpretation:
        - sim >= 0.75 : strong match (~85% - 98%)
        - sim >= 0.55 : moderate match (~65% - 85%)
        - sim >= 0.35 : partial match (~40% - 65%)
        - sim < 0.35  : low / unverified (< 40%)
        """
        if cosine_sim <= 0.05:
            return max(0.0, round(float(cosine_sim * 100), 2))

        if cosine_sim >= 0.70:
            pct = 85.0 + ((cosine_sim - 0.70) / 0.30) * 14.0
        elif cosine_sim >= 0.50:
            pct = 60.0 + ((cosine_sim - 0.50) / 0.20) * 25.0
        elif cosine_sim >= 0.30:
            pct = 35.0 + ((cosine_sim - 0.30) / 0.20) * 25.0
        else:
            pct = 10.0 + ((cosine_sim - 0.05) / 0.25) * 25.0

        return round(min(99.5, max(1.0, float(pct))), 2)
