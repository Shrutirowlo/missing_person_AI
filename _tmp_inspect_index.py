"""Temporary: inspect ORIGINAL index file formats (read-only)."""
import os

import numpy as np

ROOT = os.getenv("MPP_ORIGINAL_ROOT", r"C:/Users/shrut_hi39oyy/Downloads/mpp/mpp")


def show(name, path, n=3):
    print(f"--- {name}: {path}")
    print("    exists:", os.path.exists(path))
    if not os.path.exists(path):
        return
    arr = np.load(path, allow_pickle=True)
    print("    shape:", arr.shape, "dtype:", arr.dtype)
    for row in arr[:n]:
        print("    sample:", repr(row)[:160])


show("arcface y", os.path.join(ROOT, "data", "arcface_features", "y.npy"))
show("arcface paths", os.path.join(ROOT, "data", "arcface_features", "paths.npy"))
show("mediapipe y", os.path.join(ROOT, "data", "mediapipe_features", "y.npy"))
show("mediapipe paths", os.path.join(ROOT, "data", "mediapipe_features", "paths.npy"))
show("cnn labels", os.path.join(ROOT, "models", "cnn_embedding_labels.npy"))
show("cnn train_labels", os.path.join(ROOT, "data", "cnn_features", "cnn_train_labels.npy"))
show("cnn train_emb", os.path.join(ROOT, "data", "cnn_features", "cnn_train_embeddings.npy"))

reg = os.path.join(ROOT, "data", "registered")
folders = [d for d in os.listdir(reg) if os.path.isdir(os.path.join(reg, d))]
total = 0
for d in folders:
    total += sum(
        1 for f in os.listdir(os.path.join(reg, d))
        if os.path.isfile(os.path.join(reg, d, f)) and f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    )
print("registered folders:", len(folders), "photos:", total)
print("first 5 folders:", folders[:5])
