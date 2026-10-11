import os
import json
import numpy as np
import tensorflow as tf
import joblib


# ============================================================
# CNN INCREMENTAL DATABASE UPDATER
# ============================================================
# Add a new folder inside:
#
# data/registered/<new_person>/
#
# Then run:
#
# .\.venv_cnn\Scripts\python.exe .\src\cnn\update_database.py
#
# This script:
#   1. Loads the already-trained CNN embedding model.
#   2. Checks the saved database manifest.
#   3. Processes ONLY folders that are not already registered.
#   4. Adds their embeddings to the existing database.
#   5. Rebuilds the KNN using the combined embeddings.
#
# It does NOT retrain the CNN.
# It does NOT process all existing folders again.
# ============================================================


IMG_SIZE = (160, 160)
BATCH_SIZE = 16

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

REGISTERED_DIR = os.path.join(
    BASE_DIR,
    "data",
    "registered"
)

MODEL_DIR = os.path.join(
    BASE_DIR,
    "models"
)

FEATURE_DIR = os.path.join(
    BASE_DIR,
    "data",
    "cnn_features"
)

MODEL_PATH = os.path.join(
    MODEL_DIR,
    "cnn_face_embedding_model.keras"
)

LABELS_PATH = os.path.join(
    MODEL_DIR,
    "cnn_embedding_labels.npy"
)

KNN_PATH = os.path.join(
    MODEL_DIR,
    "cnn_embedding_knn.joblib"
)

TRAIN_EMBEDDINGS_PATH = os.path.join(
    FEATURE_DIR,
    "cnn_train_embeddings.npy"
)

TRAIN_LABELS_PATH = os.path.join(
    FEATURE_DIR,
    "cnn_train_labels.npy"
)

MANIFEST_PATH = os.path.join(
    FEATURE_DIR,
    "cnn_database_manifest.json"
)

os.makedirs(
    FEATURE_DIR,
    exist_ok=True
)


# ============================================================
# HEADER
# ============================================================

print("=" * 60)
print("CNN INCREMENTAL DATABASE UPDATE")
print("=" * 60)


# ============================================================
# CHECK REQUIRED FILES
# ============================================================

required_files = [
    MODEL_PATH,
    LABELS_PATH,
    KNN_PATH,
    TRAIN_EMBEDDINGS_PATH,
    TRAIN_LABELS_PATH
]

for path in required_files:

    if not os.path.exists(path):

        raise FileNotFoundError(
            f"\nRequired file not found:\n{path}\n\n"
            "Make sure the CNN training has completed first."
        )


if not os.path.exists(
    REGISTERED_DIR
):

    raise FileNotFoundError(
        f"\nRegistered directory not found:\n"
        f"{REGISTERED_DIR}"
    )


# ============================================================
# LOAD EXISTING DATABASE
# ============================================================

print("\nLoading existing CNN database...")

train_embeddings = np.load(
    TRAIN_EMBEDDINGS_PATH
).astype(
    np.float32
)

train_labels = np.load(
    TRAIN_LABELS_PATH
).astype(
    np.int32
)

labels = np.load(
    LABELS_PATH,
    allow_pickle=True
).astype(str)


print(
    "Existing embeddings:",
    train_embeddings.shape
)

print(
    "Existing people:",
    len(labels)
)


# ============================================================
# LOAD MANIFEST
# ============================================================

if os.path.exists(
    MANIFEST_PATH
):

    with open(
        MANIFEST_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        manifest = json.load(f)

else:

    # First updater run.
    # Treat the currently existing database labels as already
    # registered so we don't process those folders again.
    manifest = {
        "registered_people": labels.tolist()
    }


registered_people = set(
    manifest.get(
        "registered_people",
        []
    )
)


# ============================================================
# FIND CURRENT FOLDERS
# ============================================================

current_people = sorted(
    folder
    for folder in os.listdir(
        REGISTERED_DIR
    )
    if os.path.isdir(
        os.path.join(
            REGISTERED_DIR,
            folder
        )
    )
)


# Only folders not already in the database
new_people = [
    person
    for person in current_people
    if person not in registered_people
]


print(
    "\nFolders found:",
    len(current_people)
)

print(
    "Already registered:",
    len(registered_people)
)

print(
    "New folders:",
    len(new_people)
)


# ============================================================
# NOTHING NEW
# ============================================================

if not new_people:

    print(
        "\nNo new registered people found."
    )

    print(
        "Database is already up to date."
    )

    print("=" * 60)

    raise SystemExit(0)


print("\nNew people to process:")

for person in new_people:

    print(
        " ->",
        person
    )


# ============================================================
# LOAD CNN
# ============================================================

print(
    "\nLoading CNN embedding model..."
)

model = tf.keras.models.load_model(
    MODEL_PATH
)

embedding_model = tf.keras.Model(
    model.input,
    model.get_layer(
        "normalized_embedding"
    ).output
)

print(
    "CNN embedding model loaded!"
)


# ============================================================
# IMAGE HELPERS
# ============================================================

valid_extensions = (
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp"
)


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

    return tf.cast(
        image,
        tf.float32
    )


# ============================================================
# GET NEW IMAGES
# ============================================================

new_image_paths = []
new_image_people = []

print(
    "\nCollecting NEW images..."
)

for person in new_people:

    person_dir = os.path.join(
        REGISTERED_DIR,
        person
    )

    person_images = []

    for filename in sorted(
        os.listdir(person_dir)
    ):

        if not filename.lower().endswith(
            valid_extensions
        ):
            continue

        person_images.append(
            os.path.join(
                person_dir,
                filename
            )
        )

    print(
        f"{person:30s}: "
        f"{len(person_images)} images"
    )

    for path in person_images:

        new_image_paths.append(
            path
        )

        new_image_people.append(
            person
        )


if not new_image_paths:

    print(
        "\nNew folders contain no supported images."
    )

    raise SystemExit(0)


# ============================================================
# ASSIGN NEW CLASS IDs
# ============================================================

label_list = labels.tolist()

new_label_ids = {}

next_label_id = len(
    label_list
)

for person in new_people:

    new_label_ids[
        person
    ] = next_label_id

    label_list.append(
        person
    )

    next_label_id += 1


# ============================================================
# EXTRACT NEW EMBEDDINGS
# ============================================================

print(
    "\nExtracting embeddings ONLY for new images..."
)

new_embeddings = []

for start in range(
    0,
    len(new_image_paths),
    BATCH_SIZE
):

    batch_paths = new_image_paths[
        start:start + BATCH_SIZE
    ]

    batch_images = tf.stack(
        [
            load_image(path)
            for path in batch_paths
        ]
    )

    batch_embeddings = embedding_model.predict(
        batch_images,
        verbose=0
    )

    batch_embeddings = np.asarray(
        batch_embeddings,
        dtype=np.float32
    )

    batch_embeddings /= np.maximum(
        np.linalg.norm(
            batch_embeddings,
            axis=1,
            keepdims=True
        ),
        1e-12
    )

    new_embeddings.append(
        batch_embeddings
    )

    print(
        f"Processed "
        f"{min(start + BATCH_SIZE, len(new_image_paths))}"
        f"/{len(new_image_paths)}"
    )


new_embeddings = np.vstack(
    new_embeddings
).astype(
    np.float32
)


# ============================================================
# CREATE NEW LABEL ARRAY
# ============================================================

new_labels = np.array(
    [
        new_label_ids[person]
        for person in new_image_people
    ],
    dtype=np.int32
)


# ============================================================
# MERGE DATABASE
# ============================================================

updated_embeddings = np.vstack(
    [
        train_embeddings,
        new_embeddings
    ]
).astype(
    np.float32
)

updated_labels = np.concatenate(
    [
        train_labels,
        new_labels
    ]
).astype(
    np.int32
)

updated_labels_list = np.array(
    label_list,
    dtype=str
)


# ============================================================
# SAVE DATABASE
# ============================================================

print(
    "\nSaving updated CNN database..."
)

np.save(
    TRAIN_EMBEDDINGS_PATH,
    updated_embeddings
)

np.save(
    TRAIN_LABELS_PATH,
    updated_labels
)

np.save(
    LABELS_PATH,
    updated_labels_list
)


# ============================================================
# REBUILD KNN
# ============================================================

print(
    "\nRebuilding CNN KNN..."
)

knn = __import__(
    "sklearn.neighbors",
    fromlist=["KNeighborsClassifier"]
).KNeighborsClassifier(
    n_neighbors=5,
    metric="cosine",
    weights="distance"
)

knn.fit(
    updated_embeddings,
    updated_labels
)

joblib.dump(
    knn,
    KNN_PATH
)


# ============================================================
# UPDATE MANIFEST
# ============================================================

for person in new_people:

    registered_people.add(
        person
    )

manifest = {
    "registered_people": sorted(
        registered_people
    ),

    "total_people": len(
        registered_people
    ),

    "total_embeddings": int(
        len(updated_embeddings)
    )
}

with open(
    MANIFEST_PATH,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        manifest,
        f,
        indent=2
    )


# ============================================================
# FINAL RESULT
# ============================================================

print(
    "\n" + "=" * 60
)

print(
    "CNN DATABASE UPDATE COMPLETE"
)

print(
    "=" * 60
)

print(
    "\nNew people added:",
    len(new_people)
)

print(
    "New images processed:",
    len(new_image_paths)
)

print(
    "Total people now:",
    len(updated_labels_list)
)

print(
    "Total embeddings now:",
    len(updated_embeddings)
)

print(
    "\nUpdated KNN:"
)

print(
    KNN_PATH
)

print(
    "\nDatabase manifest:"
)

print(
    MANIFEST_PATH
)

print(
    "\nIMPORTANT:"
)

print(
    "Existing folders were NOT reprocessed."
)

print(
    "CNN was NOT retrained."
)

print(
    "=" * 60
)