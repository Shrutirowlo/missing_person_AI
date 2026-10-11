import os
import numpy as np
import tensorflow as tf

from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score
)


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

MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "cnn_face_model.keras"
)

LABELS_PATH = os.path.join(
    BASE_DIR,
    "models",
    "cnn_labels.npy"
)

TEST_DIR = os.path.join(
    BASE_DIR,
    "data",
    "cnn_features"
)

X_TEST_PATH = os.path.join(
    TEST_DIR,
    "X_test.npy"
)

Y_TEST_PATH = os.path.join(
    TEST_DIR,
    "y_test.npy"
)


# ============================================================
# CONFIG
# ============================================================

IMG_SIZE = (160, 160)
BATCH_SIZE = 16


# ============================================================
# HEADER
# ============================================================

print("=" * 60)
print("CNN FINAL EVALUATION")
print("=" * 60)


# ============================================================
# CHECK FILES
# ============================================================

required_files = [
    MODEL_PATH,
    LABELS_PATH,
    X_TEST_PATH,
    Y_TEST_PATH
]

for path in required_files:

    if not os.path.exists(path):

        raise FileNotFoundError(
            f"\nRequired file not found:\n{path}"
        )


# ============================================================
# LOAD MODEL
# ============================================================

print("\nLoading CNN model...")

model = tf.keras.models.load_model(
    MODEL_PATH
)

print("CNN model loaded!")


# ============================================================
# LOAD LABELS
# ============================================================

labels = np.load(
    LABELS_PATH,
    allow_pickle=True
)

print(
    "Number of classes:",
    len(labels)
)


# ============================================================
# LOAD TEST DATA
# ============================================================

X_test = np.load(
    X_TEST_PATH,
    allow_pickle=True
)

y_test = np.load(
    Y_TEST_PATH
)

print(
    "\nTest images:",
    len(X_test)
)

print(
    "Test labels:",
    len(y_test)
)


# ============================================================
# IMAGE LOADING
# ============================================================

def load_image(path):

    image = tf.io.read_file(
        path
    )

    image = tf.image.decode_image(
        image,
        channels=3,
        expand_animations=False
    )

    image.set_shape(
        [None, None, 3]
    )

    image = tf.image.resize(
        image,
        IMG_SIZE
    )

    image = tf.cast(
        image,
        tf.float32
    )

    return image


# ============================================================
# PREDICT
# ============================================================

print("\nRunning predictions...")

predicted_classes = []

total = len(X_test)

for start in range(
    0,
    total,
    BATCH_SIZE
):

    batch_paths = X_test[
        start:start + BATCH_SIZE
    ]

    batch_images = tf.stack(
        [
            load_image(path)
            for path in batch_paths
        ]
    )

    predictions = model.predict(
        batch_images,
        verbose=0
    )

    batch_classes = np.argmax(
        predictions,
        axis=1
    )

    predicted_classes.extend(
        batch_classes
    )


predicted_classes = np.array(
    predicted_classes
)


# ============================================================
# ACCURACY
# ============================================================

accuracy = accuracy_score(
    y_test,
    predicted_classes
)


# ============================================================
# CLASSIFICATION REPORT
# ============================================================

print("\n" + "=" * 60)
print("CNN RESULTS")
print("=" * 60)

print(
    f"\nAccuracy: {accuracy * 100:.2f}%"
)

print("\nClassification Report:")

print(
    classification_report(
        y_test,
        predicted_classes,
        labels=np.arange(len(labels)),
        target_names=labels,
        zero_division=0
    )
)


# ============================================================
# CONFUSION MATRIX
# ============================================================

cm = confusion_matrix(
    y_test,
    predicted_classes,
    labels=np.arange(len(labels))
)


print("\n" + "=" * 60)
print("CONFUSION MATRIX")
print("=" * 60)

print("\nClasses:")

for index, label in enumerate(labels):

    print(
        f"{index:2d} -> {label}"
    )

print("\nMatrix:")

print(cm)


# ============================================================
# SAVE RESULTS
# ============================================================

RESULTS_DIR = os.path.join(
    BASE_DIR,
    "data",
    "cnn_results"
)

os.makedirs(
    RESULTS_DIR,
    exist_ok=True
)

np.save(
    os.path.join(
        RESULTS_DIR,
        "confusion_matrix.npy"
    ),
    cm
)

np.save(
    os.path.join(
        RESULTS_DIR,
        "predictions.npy"
    ),
    predicted_classes
)


# ============================================================
# FINAL
# ============================================================

print("\n" + "=" * 60)
print("CNN EVALUATION COMPLETE")
print("=" * 60)

print(
    f"Final Test Accuracy: "
    f"{accuracy * 100:.2f}%"
)

print(
    "\nResults saved to:"
)

print(
    RESULTS_DIR
)