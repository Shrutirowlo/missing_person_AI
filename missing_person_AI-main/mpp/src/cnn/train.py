import os
import json
import random
import numpy as np
import tensorflow as tf

from sklearn.utils.class_weight import compute_class_weight
from sklearn.neighbors import KNeighborsClassifier

# ============================================================
# CNN FACE EMBEDDING TRAINING
# ============================================================

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
tf.random.set_seed(SEED)

IMG_SIZE = (160, 160)
BATCH_SIZE = 16

HEAD_EPOCHS = 12
FINE_TUNE_EPOCHS = 12

EMBEDDING_DIM = 128

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

DATASET_DIR = os.path.join(
    BASE_DIR, "data", "registered"
)

MODEL_DIR = os.path.join(
    BASE_DIR, "models"
)

FEATURE_DIR = os.path.join(
    BASE_DIR, "data", "cnn_features"
)

os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(FEATURE_DIR, exist_ok=True)

MODEL_PATH = os.path.join(
    MODEL_DIR,
    "cnn_face_embedding_model.keras"
)

LABELS_PATH = os.path.join(
    MODEL_DIR,
    "cnn_embedding_labels.npy"
)

TRAIN_EMBEDDINGS_PATH = os.path.join(
    FEATURE_DIR,
    "cnn_train_embeddings.npy"
)

TRAIN_LABELS_PATH = os.path.join(
    FEATURE_DIR,
    "cnn_train_labels.npy"
)

TEST_EMBEDDINGS_PATH = os.path.join(
    FEATURE_DIR,
    "cnn_test_embeddings.npy"
)

TEST_LABELS_PATH = os.path.join(
    FEATURE_DIR,
    "cnn_test_labels.npy"
)

TEST_PATHS_PATH = os.path.join(
    FEATURE_DIR,
    "cnn_test_paths.npy"
)


# ============================================================
# HEADER
# ============================================================

print("=" * 60)
print("CNN FACE EMBEDDING TRAINING")
print("=" * 60)

print("TensorFlow:", tf.__version__)

if tf.config.list_physical_devices("GPU"):
    print("Using GPU")
else:
    print("Using CPU")


# ============================================================
# CLASSES
# ============================================================

people = sorted(
    folder
    for folder in os.listdir(DATASET_DIR)
    if os.path.isdir(
        os.path.join(DATASET_DIR, folder)
    )
)

if len(people) < 2:
    raise RuntimeError(
        "At least 2 people are required."
    )

label_to_index = {
    person: i
    for i, person in enumerate(people)
}

index_to_label = {
    i: person
    for person, i in label_to_index.items()
}

print("\nNumber of people:", len(people))

print("\nClasses:")

for i, person in index_to_label.items():
    print(f"{i:2d} -> {person}")


# ============================================================
# COLLECT IMAGES
# ============================================================

valid_extensions = (
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp"
)

image_paths = []
labels = []

print("\nCollecting images...")

for person in people:

    person_dir = os.path.join(
        DATASET_DIR,
        person
    )

    count = 0

    for filename in sorted(
        os.listdir(person_dir)
    ):

        if not filename.lower().endswith(
            valid_extensions
        ):
            continue

        image_paths.append(
            os.path.join(
                person_dir,
                filename
            )
        )

        labels.append(
            label_to_index[person]
        )

        count += 1

    print(
        f"{person:30s}: {count} images"
    )

image_paths = np.array(
    image_paths
)

labels = np.array(
    labels,
    dtype=np.int32
)

print(
    "\nTotal images:",
    len(image_paths)
)


# ============================================================
# PER-CLASS TRAIN / VALIDATION / TEST SPLIT
# ============================================================

print("\nCreating per-class split...")

rng = np.random.default_rng(SEED)

train_paths = []
train_labels = []

val_paths = []
val_labels = []

test_paths = []
test_labels = []

for class_id in sorted(
    np.unique(labels)
):

    indices = np.where(
        labels == class_id
    )[0]

    rng.shuffle(indices)

    n = len(indices)

    if n < 3:

        raise RuntimeError(
            f"{index_to_label[class_id]} has only {n} images. "
            "At least 3 images are required."
        )

    n_val = max(
        1,
        int(round(n * 0.20))
    )

    n_test = max(
        1,
        int(round(n * 0.20))
    )

    if n_val + n_test >= n:
        n_val = 1
        n_test = 1

    test_idx = indices[
        :n_test
    ]

    val_idx = indices[
        n_test:n_test + n_val
    ]

    train_idx = indices[
        n_test + n_val:
    ]

    for idx in train_idx:

        train_paths.append(
            image_paths[idx]
        )

        train_labels.append(
            labels[idx]
        )

    for idx in val_idx:

        val_paths.append(
            image_paths[idx]
        )

        val_labels.append(
            labels[idx]
        )

    for idx in test_idx:

        test_paths.append(
            image_paths[idx]
        )

        test_labels.append(
            labels[idx]
        )


X_train = np.array(
    train_paths
)

y_train = np.array(
    train_labels,
    dtype=np.int32
)

X_val = np.array(
    val_paths
)

y_val = np.array(
    val_labels,
    dtype=np.int32
)

X_test = np.array(
    test_paths
)

y_test = np.array(
    test_labels,
    dtype=np.int32
)


# Shuffle each split

for X, y in (
    (X_train, y_train),
    (X_val, y_val),
    (X_test, y_test)
):

    order = rng.permutation(
        len(X)
    )

    X[:] = X[order]
    y[:] = y[order]


print("\nData split:")

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

if "biswa" in label_to_index:

    biswa_id = label_to_index["biswa"]

    print("\nBiswa split:")

    print(
        "Training:",
        int(np.sum(y_train == biswa_id))
    )

    print(
        "Validation:",
        int(np.sum(y_val == biswa_id))
    )

    print(
        "Test:",
        int(np.sum(y_test == biswa_id))
    )


# ============================================================
# IMAGE PIPELINE
# ============================================================

def load_image(
    path,
    label
):

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

    return image, label


augmentation = tf.keras.Sequential(
    [
        tf.keras.layers.RandomFlip(
            "horizontal"
        ),

        tf.keras.layers.RandomRotation(
            0.08
        ),

        tf.keras.layers.RandomZoom(
            0.12
        ),

        tf.keras.layers.RandomContrast(
            0.12
        )
    ],
    name="augmentation"
)


def make_dataset(
    paths,
    labels_,
    training=False
):

    ds = tf.data.Dataset.from_tensor_slices(
        (
            paths,
            labels_
        )
    )

    if training:

        ds = ds.shuffle(
            len(paths),
            seed=SEED,
            reshuffle_each_iteration=True
        )

    ds = ds.map(
        load_image,
        num_parallel_calls=tf.data.AUTOTUNE
    )

    if training:

        ds = ds.map(
            lambda image, label: (
                augmentation(
                    image,
                    training=True
                ),
                label
            ),
            num_parallel_calls=tf.data.AUTOTUNE
        )

    ds = ds.batch(
        BATCH_SIZE
    )

    ds = ds.prefetch(
        tf.data.AUTOTUNE
    )

    return ds


train_ds = make_dataset(
    X_train,
    y_train,
    training=True
)

val_ds = make_dataset(
    X_val,
    y_val
)


# ============================================================
# CLASS WEIGHTS
# ============================================================

classes = np.unique(
    y_train
)

weights = compute_class_weight(
    class_weight="balanced",
    classes=classes,
    y=y_train
)

class_weights = {
    int(c): float(w)
    for c, w in zip(
        classes,
        weights
    )
}


# ============================================================
# MOBILE NET V2
# ============================================================

print(
    "\nLoading MobileNetV2..."
)

base_model = tf.keras.applications.MobileNetV2(
    input_shape=(
        IMG_SIZE[0],
        IMG_SIZE[1],
        3
    ),
    include_top=False,
    weights="imagenet"
)

base_model.trainable = False


# ============================================================
# CNN MODEL
# ============================================================

inputs = tf.keras.Input(
    shape=(
        IMG_SIZE[0],
        IMG_SIZE[1],
        3
    ),
    name="image"
)

x = tf.keras.applications.mobilenet_v2.preprocess_input(
    inputs
)

x = base_model(
    x,
    training=False
)

x = tf.keras.layers.GlobalAveragePooling2D()(
    x
)

x = tf.keras.layers.Dense(
    256,
    activation="relu"
)(
    x
)

x = tf.keras.layers.Dropout(
    0.35
)(
    x
)

embedding = tf.keras.layers.Dense(
    EMBEDDING_DIM,
    activation=None,
    name="face_embedding"
)(
    x
)

# IMPORTANT:
# UnitNormalization is used instead of a Lambda layer.
# This makes the saved Keras model load safely in Keras 2.21.

normalized_embedding = tf.keras.layers.UnitNormalization(
    axis=1,
    name="normalized_embedding"
)(
    embedding
)

outputs = tf.keras.layers.Dense(
    len(people),
    activation="softmax",
    name="identity_classifier"
)(
    normalized_embedding
)

model = tf.keras.Model(
    inputs,
    outputs,
    name="CNNFaceEmbeddingModel"
)


# ============================================================
# EMBEDDING MODEL
# ============================================================

embedding_model = tf.keras.Model(
    inputs,
    normalized_embedding,
    name="CNNEmbeddingExtractor"
)


# ============================================================
# COMPILE
# ============================================================

model.compile(
    optimizer=tf.keras.optimizers.Adam(
        learning_rate=1e-3
    ),

    loss="sparse_categorical_crossentropy",

    metrics=[
        "accuracy"
    ]
)


# ============================================================
# CALLBACKS
# ============================================================

callbacks = [

    tf.keras.callbacks.EarlyStopping(
        monitor="val_accuracy",
        mode="max",
        patience=4,
        restore_best_weights=True,
        verbose=1
    ),

    tf.keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss",
        factor=0.3,
        patience=2,
        min_lr=1e-7,
        verbose=1
    ),

    tf.keras.callbacks.ModelCheckpoint(
        MODEL_PATH,
        monitor="val_accuracy",
        mode="max",
        save_best_only=True,
        verbose=1
    )
]


# ============================================================
# PHASE 1
# ============================================================

print(
    "\n" + "=" * 60
)

print(
    "PHASE 1 — TRAINING CNN HEAD"
)

print(
    "=" * 60
)

model.fit(
    train_ds,
    validation_data=val_ds,
    epochs=HEAD_EPOCHS,
    class_weight=class_weights,
    callbacks=callbacks
)


# ============================================================
# PHASE 2
# ============================================================

print(
    "\n" + "=" * 60
)

print(
    "PHASE 2 — FINE TUNING CNN"
)

print(
    "=" * 60
)

base_model.trainable = True

for layer in base_model.layers[
    :100
]:

    layer.trainable = False


model.compile(
    optimizer=tf.keras.optimizers.Adam(
        learning_rate=1e-5
    ),

    loss="sparse_categorical_crossentropy",

    metrics=[
        "accuracy"
    ]
)

model.fit(
    train_ds,
    validation_data=val_ds,
    epochs=FINE_TUNE_EPOCHS,
    class_weight=class_weights,
    callbacks=callbacks
)


# ============================================================
# IMPORTANT:
# DO NOT LOAD THE MODEL AGAIN.
#
# EarlyStopping already restored the best weights and
# ModelCheckpoint saved them to disk.
#
# This avoids the Keras Lambda deserialization problem.
# ============================================================

print(
    "\nBest CNN weights are already loaded."
)


# ============================================================
# REBUILD EMBEDDING MODEL FROM BEST WEIGHTS
# ============================================================

embedding_model = tf.keras.Model(
    model.input,
    model.get_layer(
        "normalized_embedding"
    ).output
)


# ============================================================
# EMBEDDING DATASET
# ============================================================

def make_embedding_dataset(
    paths
):

    def load_only(
        path
    ):

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

    return (
        tf.data.Dataset
        .from_tensor_slices(
            paths
        )
        .map(
            load_only,
            num_parallel_calls=tf.data.AUTOTUNE
        )
        .batch(
            BATCH_SIZE
        )
        .prefetch(
            tf.data.AUTOTUNE
        )
    )


# ============================================================
# EXTRACT TRAIN EMBEDDINGS
# ============================================================

print(
    "\nExtracting training embeddings..."
)

train_embeddings = embedding_model.predict(
    make_embedding_dataset(
        X_train
    ),
    verbose=1
)

train_embeddings = np.asarray(
    train_embeddings,
    dtype=np.float32
)

train_embeddings /= np.maximum(
    np.linalg.norm(
        train_embeddings,
        axis=1,
        keepdims=True
    ),
    1e-12
)


# ============================================================
# EXTRACT TEST EMBEDDINGS
# ============================================================

print(
    "\nExtracting test embeddings..."
)

test_embeddings = embedding_model.predict(
    make_embedding_dataset(
        X_test
    ),
    verbose=1
)

test_embeddings = np.asarray(
    test_embeddings,
    dtype=np.float32
)

test_embeddings /= np.maximum(
    np.linalg.norm(
        test_embeddings,
        axis=1,
        keepdims=True
    ),
    1e-12
)


# ============================================================
# SAVE EMBEDDINGS
# ============================================================

np.save(
    TRAIN_EMBEDDINGS_PATH,
    train_embeddings
)

np.save(
    TRAIN_LABELS_PATH,
    y_train
)

np.save(
    TEST_EMBEDDINGS_PATH,
    test_embeddings
)

np.save(
    TEST_LABELS_PATH,
    y_test
)

np.save(
    TEST_PATHS_PATH,
    X_test
)

np.save(
    LABELS_PATH,
    np.array(
        people,
        dtype=str
    )
)


# ============================================================
# KNN EVALUATION
# ============================================================

print(
    "\nRunning embedding KNN test..."
)

knn = KNeighborsClassifier(
    n_neighbors=5,
    metric="cosine",
    weights="distance"
)

knn.fit(
    train_embeddings,
    y_train
)

test_predictions = knn.predict(
    test_embeddings
)

test_accuracy = np.mean(
    test_predictions == y_test
)


# ============================================================
# SAVE KNN
# ============================================================

knn_path = os.path.join(
    MODEL_DIR,
    "cnn_embedding_knn.joblib"
)

import joblib

joblib.dump(
    knn,
    knn_path
)


# ============================================================
# SAVE METADATA
# ============================================================

metadata = {

    "model":
        "MobileNetV2 CNN face embedding",

    "embedding_dimension":
        EMBEDDING_DIM,

    "image_size":
        list(IMG_SIZE),

    "classes":
        people,

    "train_images":
        int(len(X_train)),

    "validation_images":
        int(len(X_val)),

    "test_images":
        int(len(X_test)),

    "knn_k":
        5,

    "metric":
        "cosine",

    "test_accuracy":
        float(test_accuracy)
}

metadata_path = os.path.join(
    MODEL_DIR,
    "cnn_embedding_metadata.json"
)

with open(
    metadata_path,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        metadata,
        f,
        indent=2
    )


# ============================================================
# FINAL
# ============================================================

print(
    "\n" + "=" * 60
)

print(
    "CNN FACE EMBEDDING TRAINING COMPLETE"
)

print(
    "=" * 60
)

print(
    "Embedding dimension:",
    train_embeddings.shape[1]
)

print(
    "Training embeddings:",
    train_embeddings.shape
)

print(
    "Test embeddings:",
    test_embeddings.shape
)

print(
    f"\nEmbedding KNN Test Accuracy: "
    f"{test_accuracy * 100:.2f}%"
)

print(
    "\nSaved CNN model:"
)

print(
    MODEL_PATH
)

print(
    "\nSaved KNN model:"
)

print(
    knn_path
)

print(
    "\nSaved labels:"
)

print(
    LABELS_PATH
)

print(
    "\nCNN training complete."
)