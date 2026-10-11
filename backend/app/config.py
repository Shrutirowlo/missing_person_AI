"""Central configuration. Everything comes from environment variables.

The ORIGINAL AI artifacts are referenced read-only via paths below.
The application never writes to, retrains, or regenerates them.
"""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Automatically load backend/.env or repo .env if present
_app_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.dirname(_app_dir)
_root_dir = os.path.dirname(_backend_dir)
for _env_candidate in [
    os.path.join(_backend_dir, ".env"),
    os.path.join(_root_dir, ".env"),
    os.path.join(os.getcwd(), ".env"),
    os.path.join(os.getcwd(), "backend", ".env"),
]:
    if os.path.isfile(_env_candidate):
        load_dotenv(_env_candidate, override=False)


def _orig(*parts: str) -> str:
    root = os.getenv("MPP_ORIGINAL_ROOT", r"C:/Users/shrut_hi39oyy/Downloads/mpp/mpp")
    return os.path.join(root, *parts)


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "missing-person-api")
    api_prefix: str = os.getenv("API_PREFIX", "/api")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    mongodb_url: str = os.getenv("MONGODB_URL", "mongodb://127.0.0.1:27017")
    mongodb_db: str = os.getenv("MONGODB_DB", "missing_person_ai")

    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "change-me-to-a-long-random-secret")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))

    storage_dir: str = os.getenv("STORAGE_DIR", "./storage")
    max_image_bytes: int = int(os.getenv("MAX_IMAGE_BYTES", str(8 * 1024 * 1024)))
    cors_origins: tuple = field(
        default_factory=lambda: tuple(
            o.strip()
            for o in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
            if o.strip()
        )
    )

    # ---- ORIGINAL CNN artifacts (authoritative embedding pipeline) ----
    cnn_model_path: str = os.getenv("CNN_MODEL_PATH", _orig("models", "cnn_face_embedding_model.keras"))
    cnn_knn_path: str = os.getenv("CNN_KNN_PATH", _orig("models", "cnn_embedding_knn.joblib"))
    cnn_labels_path: str = os.getenv("CNN_LABELS_PATH", _orig("models", "cnn_embedding_labels.npy"))
    cnn_train_embeddings_path: str = os.getenv(
        "CNN_TRAIN_EMBEDDINGS_PATH", _orig("data", "cnn_features", "cnn_train_embeddings.npy")
    )
    cnn_train_labels_path: str = os.getenv(
        "CNN_TRAIN_LABELS_PATH", _orig("data", "cnn_features", "cnn_train_labels.npy")
    )

    # ---- ORIGINAL ArcFace artifacts ----
    arcface_x_path: str = os.getenv("ARCFACE_X_PATH", _orig("data", "arcface_features", "X.npy"))
    arcface_y_path: str = os.getenv("ARCFACE_Y_PATH", _orig("data", "arcface_features", "y.npy"))
    arcface_model_path: str = os.getenv(
        "ARCFACE_MODEL_PATH",
        os.path.expanduser(r"~/.insightface/models/buffalo_l/w600k_r50.onnx"),
    )

    # ---- ORIGINAL MediaPipe + KNN artifacts ----
    mediapipe_knn_path: str = os.getenv("MEDIAPIPE_KNN_PATH", _orig("models", "mediapipe_knn.joblib"))
    mediapipe_y_path: str = os.getenv(
        "MEDIAPIPE_Y_PATH", _orig("data", "mediapipe_features", "y.npy")
    )
    mediapipe_task_path: str = os.getenv(
        "MEDIAPIPE_TASK_PATH", _orig("models", "face_landmarker.task")
    )


settings = Settings()
