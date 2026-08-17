import os
import numpy as np
import tensorflow as tf
import joblib


# ============================================================
# CNN FACE EMBEDDING PREDICTOR
# ============================================================

IMG_SIZE = (160, 160)
BATCH_SIZE = 1

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
    "cnn_face_embedding_model.keras"
)

KNN_PATH = os.path.join(
    BASE_DIR,
    "models",
    "cnn_embedding_knn.joblib"
)

LABELS_PATH = os.path.join(
    BASE_DIR,
    "models",
    "cnn_embedding_labels.npy"
)

TRAIN_EMBEDDINGS_PATH = os.path.join(
    BASE_DIR,
    "data",
    "cnn_features",
    "cnn_train_embeddings.npy"
)

TRAIN_LABELS_PATH = os.path.join(
    BASE_DIR,
    "data",
    "cnn_features",
    "cnn_train_labels.npy"
)


# ============================================================
# HEADER
# ============================================================

print("=" * 60)
print("CNN FACE EMBEDDING PREDICTOR")
print("=" * 60)


# ============================================================
# CHECK FILES
# ============================================================

required_files = [
    MODEL_PATH,
    KNN_PATH,
    LABELS_PATH,
    TRAIN_EMBEDDINGS_PATH,
    TRAIN_LABELS_PATH
]

for path in required_files:

    if not os.path.exists(path):

        raise FileNotFoundError(
            f"\nRequired file not found:\n{path}"
        )


# ============================================================
# LOAD CNN
# ============================================================

print("\nLoading CNN...")

model = tf.keras.models.load_model(
    MODEL_PATH
)

print("CNN loaded!")


# ============================================================
# LOAD KNN
# ============================================================

print("\nLoading KNN...")

knn = joblib.load(
    KNN_PATH
)

print("KNN loaded!")


# ============================================================
# LOAD LABELS
# ============================================================

labels = np.load(
    LABELS_PATH,
    allow_pickle=True
)

print(
    "Number of people:",
    len(labels)
)


# ============================================================
# LOAD TRAIN EMBEDDINGS
# ============================================================

train_embeddings = np.load(
    TRAIN_EMBEDDINGS_PATH
)

train_labels = np.load(
    TRAIN_LABELS_PATH
)

print(
    "Training embeddings:",
    train_embeddings.shape
)


# ============================================================
# BUILD EMBEDDING MODEL
# ============================================================

embedding_model = tf.keras.Model(
    model.input,
    model.get_layer(
        "normalized_embedding"
    ).output
)


# ============================================================
# GET IMAGE
# ============================================================

image_path = input(
    "\nEnter image path: "
).strip().strip('"')


if not os.path.isabs(image_path):

    image_path = os.path.join(
        BASE_DIR,
        image_path
    )


if not os.path.exists(image_path):

    raise FileNotFoundError(
        f"\nImage not found:\n{image_path}"
    )


print(
    "\nImage:",
    image_path
)


# ============================================================
# LOAD IMAGE
# ============================================================

image = tf.io.read_file(
    image_path
)

image = tf.image.decode_image(
    image,
    channels=3,
    expand_animations=False
)

image.set_shape(
    [None, None, 3]
)

original_height = int(
    image.shape[0]
)

original_width = int(
    image.shape[1]
)

print(
    "Original image:",
    f"{original_width} x {original_height}"
)

image = tf.image.resize(
    image,
    IMG_SIZE
)

image = tf.cast(
    image,
    tf.float32
)

image = tf.expand_dims(
    image,
    axis=0
)


# ============================================================
# EXTRACT EMBEDDING
# ============================================================

print(
    "\nExtracting face embedding..."
)

test_embedding = embedding_model.predict(
    image,
    verbose=0
)[0]

test_embedding = np.asarray(
    test_embedding,
    dtype=np.float32
)

test_embedding /= max(
    np.linalg.norm(test_embedding),
    1e-12
)

print(
    "Embedding shape:",
    test_embedding.shape
)


# ============================================================
# KNN PREDICTION
# ============================================================

test_vector = test_embedding.reshape(
    1,
    -1
)

predicted_index = int(
    knn.predict(test_vector)[0]
)

predicted_person = labels[
    predicted_index
]


# ============================================================
# KNN PROBABILITY
# ============================================================

try:

    probabilities = knn.predict_proba(
        test_vector
    )[0]

    confidence = float(
        np.max(probabilities)
    )

except Exception:

    confidence = 0.0


# ============================================================
# COSINE SIMILARITY
# ============================================================

similarities = np.dot(
    train_embeddings,
    test_embedding
)

top_indices = np.argsort(
    similarities
)[::-1]


# ============================================================
# CLASS-LEVEL SIMILARITY
# ============================================================

class_scores = {}

for class_id, label in enumerate(
    labels
):

    class_values = similarities[
        train_labels == class_id
    ]

    if len(class_values) == 0:
        continue

    # Average of the strongest 3 matches
    strongest = np.sort(
        class_values
    )[-3:]

    class_scores[
        class_id
    ] = float(
        np.mean(strongest)
    )


sorted_classes = sorted(
    class_scores,
    key=class_scores.get,
    reverse=True
)


# ============================================================
# RESULT
# ============================================================

print(
    "\n" + "=" * 60
)

print(
    "CNN FACE RECOGNITION RESULT"
)

print(
    "=" * 60
)

print(
    "\nPredicted person:",
    predicted_person
)

if confidence > 0:

    print(
        f"KNN confidence: "
        f"{confidence * 100:.2f}%"
    )

print(
    f"Best similarity: "
    f"{similarities[top_indices[0]] * 100:.2f}%"
)


# ============================================================
# TOP 10 INDIVIDUAL MATCHES
# ============================================================

print(
    "\n" + "=" * 60
)

print(
    "TOP 10 CLOSEST TRAINING IMAGES"
)

print(
    "=" * 60
)

for rank, index in enumerate(
    top_indices[:10],
    start=1
):

    class_id = int(
        train_labels[index]
    )

    person = labels[
        class_id
    ]

    similarity = similarities[
        index
    ]

    print(
        f"{rank:2d}. "
        f"{person:30s} "
        f"similarity = "
        f"{similarity:.4f}"
    )


# ============================================================
# TOP 10 CLASS RESULTS
# ============================================================

print(
    "\n" + "=" * 60
)

print(
    "TOP 10 CLASS-LEVEL RESULTS"
)

print(
    "=" * 60
)

for rank, class_id in enumerate(
    sorted_classes[:10],
    start=1
):

    print(
        f"{rank:2d}. "
        f"{labels[class_id]:30s} "
        f"score = "
        f"{class_scores[class_id]:.4f}"
    )


# ============================================================
# FINAL
# ============================================================

print(
    "\n" + "=" * 60
)

print(
    "FINAL CNN PREDICTION"
)

print(
    "=" * 60
)

print(
    "Predicted person:",
    predicted_person
)

print(
    f"Best class similarity: "
    f"{class_scores[predicted_index]:.4f}"
)

print(
    f"Closest image similarity: "
    f"{similarities[top_indices[0]]:.4f}"
)

print(
    "=" * 60
)