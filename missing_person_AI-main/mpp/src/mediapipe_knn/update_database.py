import os
import json
import cv2
import numpy as np
import mediapipe as mp
import joblib
from sklearn.neighbors import KNeighborsClassifier


# ============================================================
# MEDIAPIPE INCREMENTAL DATABASE UPDATER
# ============================================================
# Add a new folder:
#
# data/registered/<person_name>/
#
# Then run:
#
# py .\src\mediapipe_knn\update_database.py
#
# IMPORTANT:
# - Existing images are NOT run through MediaPipe again.
# - Only NEW person folders are processed.
# - The existing X.npy/y.npy database is loaded and the new
#   features are appended.
# - KNN is rebuilt from the already-saved features + new
#   features. This is fast compared with re-extracting faces.
# ============================================================


# ------------------------------------------------------------
# PROJECT PATHS
# ------------------------------------------------------------

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

FEATURE_DIR = os.path.join(
    BASE_DIR,
    "data",
    "mediapipe_features"
)

MODEL_DIR = os.path.join(
    BASE_DIR,
    "models"
)

X_PATH = os.path.join(
    FEATURE_DIR,
    "X.npy"
)

Y_PATH = os.path.join(
    FEATURE_DIR,
    "y.npy"
)

PATHS_PATH = os.path.join(
    FEATURE_DIR,
    "paths.npy"
)

MODEL_PATH = os.path.join(
    MODEL_DIR,
    "face_landmarker.task"
)

KNN_PATH = os.path.join(
    MODEL_DIR,
    "mediapipe_knn.joblib"
)

MANIFEST_PATH = os.path.join(
    FEATURE_DIR,
    "mediapipe_database_manifest.json"
)

os.makedirs(
    FEATURE_DIR,
    exist_ok=True
)

os.makedirs(
    MODEL_DIR,
    exist_ok=True
)


# ------------------------------------------------------------
# HEADER
# ------------------------------------------------------------

print("=" * 60)
print("MEDIAPIPE INCREMENTAL DATABASE UPDATE")
print("=" * 60)


# ------------------------------------------------------------
# CHECK REQUIRED FILES
# ------------------------------------------------------------

for path in [
    MODEL_PATH,
    X_PATH,
    Y_PATH,
    PATHS_PATH
]:

    if not os.path.exists(path):

        raise FileNotFoundError(
            f"\nRequired file not found:\n{path}\n\n"
            "Run your existing MediaPipe feature preparation "
            "pipeline once before using the incremental updater."
        )


if not os.path.exists(
    REGISTERED_DIR
):

    raise FileNotFoundError(
        f"\nRegistered directory not found:\n"
        f"{REGISTERED_DIR}"
    )


# ------------------------------------------------------------
# LOAD EXISTING DATABASE
# ------------------------------------------------------------

print("\nLoading existing MediaPipe database...")

X_existing = np.load(
    X_PATH
).astype(
    np.float32
)

y_existing = np.load(
    Y_PATH,
    allow_pickle=True
).astype(str)

paths_existing = np.load(
    PATHS_PATH,
    allow_pickle=True
).astype(str)


print(
    "Existing features:",
    X_existing.shape
)

print(
    "Existing labels:",
    y_existing.shape
)

print(
    "Existing images:",
    paths_existing.shape
)


# ------------------------------------------------------------
# LOAD MANIFEST
# ------------------------------------------------------------

if os.path.exists(
    MANIFEST_PATH
):

    with open(
        MANIFEST_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        manifest = json.load(f)

    registered_people = set(
        manifest.get(
            "registered_people",
            []
        )
    )

else:

    # First updater run.
    # Build the list from the labels already present in the
    # existing database. This prevents reprocessing the
    # existing 20 people.
    registered_people = set(
        np.unique(
            y_existing
        ).tolist()
    )

    print(
        "\nNo manifest found."
    )

    print(
        "Using existing y.npy labels to initialize it."
    )


# ------------------------------------------------------------
# FIND CURRENT PERSON FOLDERS
# ------------------------------------------------------------

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


new_people = [
    person
    for person in current_people
    if person not in registered_people
]


print(
    "\nCurrent registered folders:",
    len(current_people)
)

print(
    "Already in database:",
    len(registered_people)
)

print(
    "NEW folders:",
    len(new_people)
)


# ------------------------------------------------------------
# NOTHING NEW
# ------------------------------------------------------------

if not new_people:

    print(
        "\nNo new folders found."
    )

    print(
        "MediaPipe database is already up to date."
    )

    print("=" * 60)

    raise SystemExit(0)


print(
    "\nOnly these folders will be processed:"
)

for person in new_people:

    print(
        " ->",
        person
    )


# ------------------------------------------------------------
# CREATE MEDIAPIPE LANDMARKER ONCE
# ------------------------------------------------------------

def create_landmarker():

    BaseOptions = mp.tasks.BaseOptions

    FaceLandmarker = (
        mp.tasks.vision.FaceLandmarker
    )

    FaceLandmarkerOptions = (
        mp.tasks.vision.FaceLandmarkerOptions
    )

    RunningMode = (
        mp.tasks.vision.RunningMode
    )

    options = FaceLandmarkerOptions(
        base_options=BaseOptions(
            model_asset_path=MODEL_PATH
        ),
        running_mode=RunningMode.IMAGE,
        num_faces=1
    )

    return FaceLandmarker.create_from_options(
        options
    )


# ------------------------------------------------------------
# EXTRACT FEATURES
# ------------------------------------------------------------

def extract_features(
    image_path,
    landmarker
):

    image = cv2.imread(
        image_path
    )

    if image is None:

        return None

    image_rgb = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2RGB
    )

    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=image_rgb
    )

    result = landmarker.detect(
        mp_image
    )

    if not result.face_landmarks:

        return None

    face_landmarks = result.face_landmarks[0]

    features = []

    for landmark in face_landmarks:

        features.extend([
            landmark.x,
            landmark.y,
            landmark.z
        ])

    return np.array(
        features,
        dtype=np.float32
    )


# ------------------------------------------------------------
# PROCESS ONLY NEW FOLDERS
# ------------------------------------------------------------

new_features = []
new_labels = []
new_paths = []

processed = 0
failed = 0

print(
    "\nStarting MediaPipe processing..."
)

with create_landmarker() as landmarker:

    for person in new_people:

        person_dir = os.path.join(
            REGISTERED_DIR,
            person
        )

        image_files = sorted(
            filename
            for filename in os.listdir(
                person_dir
            )
            if filename.lower().endswith(
                (".jpg", ".jpeg", ".png", ".bmp")
            )
        )

        print(
            f"\nProcessing NEW person: {person}"
        )

        print(
            f"Images found: {len(image_files)}"
        )

        for filename in image_files:

            image_path = os.path.join(
                person_dir,
                filename
            )

            features = extract_features(
                image_path,
                landmarker
            )

            if features is None:

                print(
                    f"  FAILED: {filename}"
                )

                failed += 1

                continue

            new_features.append(
                features
            )

            new_labels.append(
                person
            )

            new_paths.append(
                image_path
            )

            processed += 1

            print(
                f"  Processed: {filename}"
            )


# ------------------------------------------------------------
# CHECK NEW DATA
# ------------------------------------------------------------

if not new_features:

    print(
        "\nNo usable new faces were found."
    )

    print(
        "Nothing was added to the database."
    )

    raise SystemExit(0)


X_new = np.array(
    new_features,
    dtype=np.float32
)

y_new = np.array(
    new_labels,
    dtype=str
)

paths_new = np.array(
    new_paths,
    dtype=str
)


# ------------------------------------------------------------
# APPEND WITHOUT REPROCESSING OLD IMAGES
# ------------------------------------------------------------

X_updated = np.vstack(
    [
        X_existing,
        X_new
    ]
).astype(
    np.float32
)

y_updated = np.concatenate(
    [
        y_existing,
        y_new
    ]
).astype(str)

paths_updated = np.concatenate(
    [
        paths_existing,
        paths_new
    ]
).astype(str)


# ------------------------------------------------------------
# SAVE FEATURE DATABASE
# ------------------------------------------------------------

print(
    "\nSaving updated feature database..."
)

np.save(
    X_PATH,
    X_updated
)

np.save(
    Y_PATH,
    y_updated
)

np.save(
    PATHS_PATH,
    paths_updated
)


# ------------------------------------------------------------
# REBUILD KNN
# ------------------------------------------------------------
# KNN itself does not support adding samples with .fit()
# incrementally. However, we do NOT extract the old images
# again. We simply fit KNN on the already-saved feature
# vectors plus the new feature vectors.

print(
    "\nRebuilding KNN from saved features..."
)

knn = KNeighborsClassifier(
    n_neighbors=5,
    metric="euclidean"
)

knn.fit(
    X_updated,
    y_updated
)

joblib.dump(
    knn,
    KNN_PATH
)


# ------------------------------------------------------------
# UPDATE MANIFEST
# ------------------------------------------------------------

registered_people.update(
    new_people
)

manifest = {
    "registered_people": sorted(
        registered_people
    ),
    "total_people": len(
        registered_people
    ),
    "total_images": int(
        len(X_updated)
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


# ------------------------------------------------------------
# FINAL SUMMARY
# ------------------------------------------------------------

print(
    "\n" + "=" * 60
)

print(
    "MEDIAPIPE DATABASE UPDATE COMPLETE"
)

print(
    "=" * 60
)

print(
    "\nNEW people processed:",
    len(new_people)
)

print(
    "NEW images processed:",
    processed
)

print(
    "Failed new images:",
    failed
)

print(
    "Total people:",
    len(
        np.unique(y_updated)
    )
)

print(
    "Total images:",
    len(X_updated)
)

print(
    "\nExisting images were NOT reprocessed."
)

print(
    "Only NEW folders were sent through MediaPipe."
)

print(
    "\nUpdated KNN:",
    KNN_PATH
)

print(
    "\nManifest:",
    MANIFEST_PATH
)

print(
    "=" * 60
)