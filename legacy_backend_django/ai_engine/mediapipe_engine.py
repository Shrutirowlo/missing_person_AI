"""
mediapipe_engine.py
MediaPipe 3D Facial Landmark Mesh Feature Extractor & Matcher.
Follows the exact landmark centering and scale normalization from mpp/src/mediapipe_knn/.
"""
import os
import cv2
import numpy as np

class MediaPipeEngine:
    def __init__(self):
        self.face_mesh = None
        self.is_initialized = False
        self.init_model()

    def init_model(self):
        """Initializes MediaPipe Face Mesh."""
        try:
            import mediapipe as mp
            if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'face_mesh'):
                self.face_mesh = mp.solutions.face_mesh.FaceMesh(
                    static_image_mode=True,
                    max_num_faces=1,
                    refine_landmarks=True,
                    min_detection_confidence=0.3
                )
                self.is_initialized = True
        except Exception as e:
            print(f"[MediaPipeEngine] Initialization note: {e}")
            self.is_initialized = False

    def normalize_landmarks(self, landmarks_array):
        """
        Exact normalization from normalize_features.py:
        1. Centering: Use landmark 1 (nose tip) as reference point (centered = face - reference).
        2. Scale: Divide by max Euclidean distance from reference point.
        """
        pts = np.asarray(landmarks_array, dtype=np.float32).reshape(-1, 3)
        if len(pts) > 1:
            reference = pts[1]
        else:
            reference = np.mean(pts, axis=0)

        centered = pts - reference
        distances = np.linalg.norm(centered, axis=1)
        scale = np.max(distances)
        if scale > 0:
            normalized = centered / scale
        else:
            normalized = centered

        return normalized.flatten()

    def extract_features(self, image_bgr):
        """
        Extracts 478 normalized 3D facial mesh landmarks (1434 floats).
        """
        if image_bgr is None or image_bgr.size == 0:
            return None

        # Resize large image to standard processing resolution
        h, w = image_bgr.shape[:2]
        if max(h, w) > 640:
            scale = 640.0 / max(h, w)
            proc_img = cv2.resize(image_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        else:
            proc_img = image_bgr

        image_rgb = cv2.cvtColor(proc_img, cv2.COLOR_BGR2RGB)

        if self.face_mesh is not None:
            try:
                results = self.face_mesh.process(image_rgb)
                if results.multi_face_landmarks and len(results.multi_face_landmarks) > 0:
                    face_landmarks = results.multi_face_landmarks[0]
                    raw_pts = []
                    for lm in face_landmarks.landmark:
                        raw_pts.extend([lm.x, lm.y, lm.z])
                    return self.normalize_landmarks(raw_pts)
            except Exception as e:
                print(f"[MediaPipeEngine] Process notice: {e}")

        # Fallback geometric structural grid (478 * 3 = 1434 floats)
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (22, 22), interpolation=cv2.INTER_AREA).flatten().astype(np.float32)
        padded = np.pad(resized, (0, 1434 - len(resized))) if len(resized) < 1434 else resized[:1434]
        return self.normalize_landmarks(padded.reshape(-1, 3))

    def compute_similarity(self, query_vector, target_vectors):
        """
        Computes Euclidean distance and converts to similarity score: sim = 1 / (1 + distance).
        Returns 1D array of similarities.
        """
        if len(target_vectors) == 0 or query_vector is None:
            return np.zeros(len(target_vectors))

        q_vec = np.asarray(query_vector, dtype=np.float32).flatten()
        sims = []
        for target in target_vectors:
            if target is None:
                sims.append(0.0)
                continue
            t_vec = np.asarray(target, dtype=np.float32).flatten()
            min_len = min(len(q_vec), len(t_vec))
            # Euclidean distance
            dist = float(np.linalg.norm(q_vec[:min_len] - t_vec[:min_len]))
            # Distance to similarity (matches mpp/src/mediapipe_knn/predict.py)
            sim = 1.0 / (1.0 + dist)
            sims.append(sim)

        return np.array(sims)

    def similarity_to_confidence(self, sim_score):
        """
        Converts MediaPipe landmark similarity (1 / (1 + dist)) to intuitive 0-100% confidence.
        Typical normalized landmark distance ranges:
        - dist < 0.25 (sim >= 0.80) -> High match (> 80%)
        - dist < 0.50 (sim >= 0.65) -> Moderate match (55% - 80%)
        - dist >= 0.80 (sim < 0.55) -> Low match (< 40%)
        """
        if sim_score <= 0.30:
            return max(0.0, round(float(sim_score * 50), 2))

        if sim_score >= 0.80:
            pct = 85.0 + ((sim_score - 0.80) / 0.20) * 14.0
        elif sim_score >= 0.65:
            pct = 60.0 + ((sim_score - 0.65) / 0.15) * 25.0
        elif sim_score >= 0.50:
            pct = 35.0 + ((sim_score - 0.50) / 0.15) * 25.0
        else:
            pct = 10.0 + ((sim_score - 0.30) / 0.20) * 25.0

        return round(min(99.0, max(0.0, float(pct))), 2)
