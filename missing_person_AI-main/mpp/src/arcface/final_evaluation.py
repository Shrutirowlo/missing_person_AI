import os
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)


# ============================================================
# CONFIGURATION
# ============================================================

BEST_K = 5


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

FEATURE_DIR = os.path.join(
    BASE_DIR,
    "data",
    "arcface_features"
)


# ============================================================
# LOAD DATA
# ============================================================

X = np.load(
    os.path.join(
        FEATURE_DIR,
        "X.npy"
    )
)

y = np.load(
    os.path.join(
        FEATURE_DIR,
        "y.npy"
    )
)


print("=" * 60)
print("ARCFACE FINAL EVALUATION")
print("=" * 60)

print(
    "X shape:",
    X.shape
)

print(
    "y shape:",
    y.shape
)

print()


# ============================================================
# SAME SPLIT STRATEGY
# ============================================================

X_temp, X_test, y_temp, y_test = train_test_split(
    X,
    y,
    test_size=0.15,
    random_state=42,
    stratify=y
)

X_train, X_val, y_train, y_val = train_test_split(
    X_temp,
    y_temp,
    test_size=0.1765,
    random_state=42,
    stratify=y_temp
)


print("Data split:")
print(
    "Training:",
    len(X_train)
)

print(
    "Validation:",
    len(X_val)
)

print(
    "Test:",
    len(X_test)
)

print()


# ============================================================
# TRAIN FINAL MODEL
# ============================================================

print(
    f"Training KNN with K = {BEST_K}..."
)

model = KNeighborsClassifier(
    n_neighbors=BEST_K,
    metric="cosine",
    weights="distance",
    n_jobs=-1
)

model.fit(
    X_train,
    y_train
)

print(
    "Training complete."
)

print()


# ============================================================
# VALIDATION
# ============================================================

val_predictions = model.predict(
    X_val
)

val_accuracy = accuracy_score(
    y_val,
    val_predictions
)


# ============================================================
# FINAL TEST
# ============================================================

print(
    "Evaluating on untouched test set..."
)

test_predictions = model.predict(
    X_test
)

test_accuracy = accuracy_score(
    y_test,
    test_predictions
)


# ============================================================
# RESULTS
# ============================================================

print()

print("=" * 60)
print("FINAL ARCFACE RESULT")
print("=" * 60)

print(
    f"Validation Accuracy: "
    f"{val_accuracy * 100:.2f}%"
)

print(
    f"Test Accuracy: "
    f"{test_accuracy * 100:.2f}%"
)

print()

print("=" * 60)
print("CLASSIFICATION REPORT")
print("=" * 60)

print(
    classification_report(
        y_test,
        test_predictions,
        zero_division=0
    )
)


# ============================================================
# CONFUSION MATRIX
# ============================================================

print("=" * 60)
print("CONFUSION MATRIX")
print("=" * 60)

labels = sorted(
    np.unique(y)
)

cm = confusion_matrix(
    y_test,
    test_predictions,
    labels=labels
)

print(
    "Classes:"
)

for i, label in enumerate(labels):

    print(
        i,
        "→",
        label
    )

print()

print(cm)


# ============================================================
# SAVE MODEL
# ============================================================

import joblib

MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "arcface_knn.joblib"
)

os.makedirs(
    os.path.dirname(MODEL_PATH),
    exist_ok=True
)

joblib.dump(
    model,
    MODEL_PATH
)

print()

print(
    "Model saved to:"
)

print(
    MODEL_PATH
)
