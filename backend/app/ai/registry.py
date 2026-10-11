"""Process-wide singleton AI adapters.

Models are heavy (TF graph, ONNX sessions). Without this, every API
request would reload them. Singletons are read-only after load and
inference is serialized per adapter via its own lock. No AI logic lives
here — pure lifecycle.
"""
import threading

_singletons: dict = {}
_singleton_lock = threading.Lock()


def get_cnn():
    from .adapters.cnn_adapter import CNNAdapter

    with _singleton_lock:
        return _singletons.setdefault("cnn", CNNAdapter())


def get_arcface():
    from .adapters.arcface_adapter import ArcFaceAdapter

    with _singleton_lock:
        return _singletons.setdefault("arcface", ArcFaceAdapter())


def get_mediapipe_knn():
    from .adapters.mediapipe_knn_adapter import MediaPipeKNNAdapter

    with _singleton_lock:
        return _singletons.setdefault("mediapipe_knn", MediaPipeKNNAdapter())
