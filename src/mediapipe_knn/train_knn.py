import os

import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib


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

MODEL_DIR = os.path.join(
    BASE_DIR,
    "models"
)

os.makedirs(MODEL_DIR, exist_ok=True)


# --------------------------------------------------
# LOAD FEATURES
# --------------------------------------------------

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


print("Dataset loaded")
print("X shape:", X.shape)
print("y shape:", y.shape)


# --------------------------------------------------
# TRAIN / TEST SPLIT
# --------------------------------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)


print("\nTrain samples:", len(X_train))
print("Test samples:", len(X_test))


# --------------------------------------------------
# CREATE KNN
# --------------------------------------------------

knn = KNeighborsClassifier(
    n_neighbors=5,
    metric="euclidean"
)


# --------------------------------------------------
# TRAIN KNN
# --------------------------------------------------

print("\nTraining KNN...")

knn.fit(
    X_train,
    y_train
)

print("KNN training complete!")


# --------------------------------------------------
# TEST KNN
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

print(
    f"\nAccuracy: {accuracy * 100:.2f}%"
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
# SAVE MODEL
# --------------------------------------------------

model_path = os.path.join(
    MODEL_DIR,
    "mediapipe_knn.joblib"
)

joblib.dump(
    knn,
    model_path
)

print(
    "\nModel saved to:",
    model_path
)