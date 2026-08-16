import os
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report
)


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

FEATURE_DIR = os.path.join(
    BASE_DIR,
    "data",
    "mediapipe_features"
)


# --------------------------------------------------
# LOAD NORMALIZED FEATURES
# --------------------------------------------------

X = np.load(
    os.path.join(
        FEATURE_DIR,
        "X_normalized.npy"
    )
)

y = np.load(
    os.path.join(
        FEATURE_DIR,
        "y.npy"
    )
)


print("Normalized dataset loaded")
print("X shape:", X.shape)
print("y shape:", y.shape)


# --------------------------------------------------
# SAME 70 / 15 / 15 SPLIT
# --------------------------------------------------

X_train, X_temp, y_train, y_temp = train_test_split(
    X,
    y,
    test_size=0.30,
    random_state=42,
    stratify=y
)

X_val, X_test, y_val, y_test = train_test_split(
    X_temp,
    y_temp,
    test_size=0.50,
    random_state=42,
    stratify=y_temp
)


print("\nData split:")
print("Training:", len(X_train))
print("Validation:", len(X_val))
print("Test:", len(X_test))


# --------------------------------------------------
# KNN
# --------------------------------------------------

knn = KNeighborsClassifier(
    n_neighbors=5,
    metric="euclidean"
)


# --------------------------------------------------
# TRAIN
# --------------------------------------------------

print("\nTraining KNN on normalized features...")

knn.fit(
    X_train,
    y_train
)

print("Training complete.")


# --------------------------------------------------
# TEST
# --------------------------------------------------

print("\nTesting...")

y_pred = knn.predict(
    X_test
)


# --------------------------------------------------
# ACCURACY
# --------------------------------------------------

accuracy = accuracy_score(
    y_test,
    y_pred
)


print("\n" + "=" * 55)
print("NORMALIZED FEATURES RESULT")
print("=" * 55)

print(
    f"Test Accuracy: {accuracy * 100:.2f}%"
)


# --------------------------------------------------
# CLASSIFICATION REPORT
# --------------------------------------------------

print("\nClassification Report:")

print(
    classification_report(
        y_test,
        y_pred,
        zero_division=0
    )
)


# --------------------------------------------------
# COMPARISON
# --------------------------------------------------

print("\n" + "=" * 55)
print("COMPARISON")
print("=" * 55)

print("Raw landmarks:        37.99%")
print(
    f"Normalized landmarks: {accuracy * 100:.2f}%"
)

print(
    f"Change: "
    f"{(accuracy * 100) - 37.99:+.2f} percentage points"
)