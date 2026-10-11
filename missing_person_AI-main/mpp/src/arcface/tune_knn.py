import os
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import accuracy_score


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
print("ARCFACE KNN TUNING")
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
# TRAIN / VALIDATION / TEST
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
# TEST DIFFERENT K VALUES
# ============================================================

k_values = [
    1,
    3,
    5,
    7,
    9,
    11,
    15
]

results = []


for k in k_values:

    print(
        f"Testing K = {k}"
    )

    model = KNeighborsClassifier(
        n_neighbors=k,
        metric="cosine",
        weights="distance",
        n_jobs=-1
    )

    model.fit(
        X_train,
        y_train
    )

    predictions = model.predict(
        X_val
    )

    accuracy = accuracy_score(
        y_val,
        predictions
    )

    results.append(
        (k, accuracy)
    )

    print(
        f"Validation accuracy: "
        f"{accuracy * 100:.2f}%"
    )

    print()


# ============================================================
# BEST K
# ============================================================

best_k, best_accuracy = max(
    results,
    key=lambda x: x[1]
)


print("=" * 60)
print("K-VALUE TUNING RESULTS")
print("=" * 60)

for k, accuracy in results:

    print(
        f"K = {k:2d} → "
        f"{accuracy * 100:.2f}%"
    )

print()

print(
    f"Best K: {best_k}"
)

print(
    f"Best validation accuracy: "
    f"{best_accuracy * 100:.2f}%"
)

print()

print(
    "IMPORTANT:"
)

print(
    "The test set was NOT used "
    "to choose K."
)