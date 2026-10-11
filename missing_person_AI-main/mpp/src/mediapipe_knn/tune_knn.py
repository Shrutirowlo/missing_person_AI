import os

import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import accuracy_score


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
# LOAD DATA
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


print("Dataset:")
print("X shape:", X.shape)
print("y shape:", y.shape)


# --------------------------------------------------
# FIRST SPLIT
# 70% TRAIN
# 30% TEMPORARY
# --------------------------------------------------

X_train, X_temp, y_train, y_temp = train_test_split(
    X,
    y,
    test_size=0.30,
    random_state=42,
    stratify=y
)


# --------------------------------------------------
# SECOND SPLIT
# TEMPORARY → VALIDATION + TEST
#
# 50% / 50%
#
# Therefore:
# Train      = 70%
# Validation = 15%
# Test       = 15%
# --------------------------------------------------

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
# K VALUES TO TEST
# --------------------------------------------------

k_values = [1, 3, 5, 7, 9, 11]

results = []


# --------------------------------------------------
# TEST EACH K
# --------------------------------------------------

for k in k_values:

    print(f"\nTesting K = {k}")

    knn = KNeighborsClassifier(
        n_neighbors=k,
        metric="euclidean"
    )

    # Train
    knn.fit(
        X_train,
        y_train
    )

    # Validate
    y_val_pred = knn.predict(
        X_val
    )

    accuracy = accuracy_score(
        y_val,
        y_val_pred
    )

    results.append(
        (k, accuracy)
    )

    print(
        f"Validation accuracy: "
        f"{accuracy * 100:.2f}%"
    )


# --------------------------------------------------
# FIND BEST K
# --------------------------------------------------

best_k, best_accuracy = max(
    results,
    key=lambda item: item[1]
)


print("\n" + "=" * 50)

print("K-VALUE TUNING RESULTS")

print("=" * 50)


for k, accuracy in results:

    print(
        f"K = {k:2d}  →  "
        f"{accuracy * 100:.2f}%"
    )


print("\nBest K:", best_k)

print(
    f"Best validation accuracy: "
    f"{best_accuracy * 100:.2f}%"
)


print("\nThe test set was NOT used to choose K.")