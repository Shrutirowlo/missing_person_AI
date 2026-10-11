import os
import cv2
import numpy as np
from insightface.model_zoo import get_model


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

DATASET_DIR = os.path.join(
    BASE_DIR,
    "data",
    "registered"
)

FEATURE_DIR = os.path.join(
    BASE_DIR,
    "data",
    "arcface_features"
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

MODEL_PATH = os.path.expanduser(
    r"~\.insightface\models\buffalo_l\w600k_r50.onnx"
)


# ============================================================
# CREATE OUTPUT DIRECTORY
# ============================================================

os.makedirs(
    FEATURE_DIR,
    exist_ok=True
)


# ============================================================
# LOAD EXISTING DATABASE
# ============================================================

print("=" * 60)
print("ARCFACE INCREMENTAL DATABASE UPDATE")
print("=" * 60)


if (
    os.path.exists(X_PATH)
    and os.path.exists(Y_PATH)
    and os.path.exists(PATHS_PATH)
):

    X_existing = np.load(
        X_PATH,
        allow_pickle=True
    )

    y_existing = np.load(
        Y_PATH,
        allow_pickle=True
    )

    paths_existing = np.load(
        PATHS_PATH,
        allow_pickle=True
    )

else:

    print("\nNo existing database found.")
    print("Starting a new database.\n")

    X_existing = np.empty(
        (0, 512),
        dtype=np.float32
    )

    y_existing = np.array(
        [],
        dtype=str
    )

    paths_existing = np.array(
        [],
        dtype=str
    )


print(
    "\nExisting embeddings:",
    len(X_existing)
)

print(
    "Existing people:",
    len(np.unique(y_existing))
)


# ============================================================
# NORMALIZE EXISTING PATHS
# ============================================================

def normalize_path(path):
    """
    Convert a path into a consistent absolute Windows path.
    This prevents the same image from being added twice.
    """

    return os.path.normcase(
        os.path.abspath(
            os.path.normpath(path)
        )
    )


processed_paths = {
    normalize_path(path)
    for path in paths_existing
}


# ============================================================
# LOAD ARCFACE RECOGNITION MODEL
# ============================================================

print("\n" + "=" * 60)
print("LOADING ARCFACE")
print("=" * 60)

print(
    "Model:",
    MODEL_PATH
)

recognition_model = get_model(
    MODEL_PATH,
    providers=["CPUExecutionProvider"]
)

recognition_model.prepare(
    ctx_id=0
)

print(
    "ArcFace recognition model loaded!"
)


# ============================================================
# FIND PEOPLE
# ============================================================

people = sorted(
    [
        folder
        for folder in os.listdir(DATASET_DIR)
        if os.path.isdir(
            os.path.join(
                DATASET_DIR,
                folder
            )
        )
    ]
)

print(
    "\nRegistered people:",
    len(people)
)


# ============================================================
# STORAGE FOR NEW DATA
# ============================================================

new_embeddings = []
new_labels = []
new_paths = []

skipped = 0
successful = 0
failed = 0


# ============================================================
# PROCESS ONLY NEW IMAGES
# ============================================================

print("\n" + "=" * 60)
print("SCANNING FOR NEW IMAGES")
print("=" * 60)


for person in people:

    person_dir = os.path.join(
        DATASET_DIR,
        person
    )

    files = sorted(
        os.listdir(person_dir)
    )

    print(
        f"\n{person}: {len(files)} files"
    )

    for filename in files:

        image_path = os.path.join(
            person_dir,
            filename
        )

        normalized = normalize_path(
            image_path
        )

        # ----------------------------------------------------
        # SKIP ALREADY PROCESSED IMAGE
        # ----------------------------------------------------

        if normalized in processed_paths:

            skipped += 1
            continue


        # ----------------------------------------------------
        # READ IMAGE
        # ----------------------------------------------------

        image = cv2.imread(
            image_path
        )

        if image is None:

            print(
                f"  FAILED: {filename} "
                "(could not read)"
            )

            failed += 1
            continue


        # ----------------------------------------------------
        # GENERATE EMBEDDING
        #
        # IMPORTANT:
        # These registered images are already face crops
        # (LFW-style images), so we directly resize them
        # to ArcFace's expected 112x112 input.
        # ----------------------------------------------------

        try:

            resized = cv2.resize(
                image,
                (112, 112),
                interpolation=cv2.INTER_CUBIC
            )

            embedding = recognition_model.get_feat(
                resized
            )[0]

            embedding = np.asarray(
                embedding,
                dtype=np.float32
            )

            # ------------------------------------------------
            # SAVE NEW RESULT
            # ------------------------------------------------

            new_embeddings.append(
                embedding
            )

            new_labels.append(
                person
            )

            new_paths.append(
                os.path.abspath(
                    image_path
                )
            )

            successful += 1

            print(
                f"  NEW: {filename}"
            )

        except Exception as e:

            print(
                f"  FAILED: {filename} "
                f"({e})"
            )

            failed += 1


# ============================================================
# NOTHING NEW
# ============================================================

if len(new_embeddings) == 0:

    print("\n" + "=" * 60)
    print("NO NEW IMAGES FOUND")
    print("=" * 60)

    print(
        "\nDatabase is already up to date."
    )

    print(
        "Existing embeddings:",
        len(X_existing)
    )

    print(
        "Skipped existing images:",
        skipped
    )

    print(
        "Failed:",
        failed
    )

    exit()


# ============================================================
# CONVERT NEW DATA
# ============================================================

X_new = np.array(
    new_embeddings,
    dtype=np.float32
)

y_new = np.array(
    new_labels
)

paths_new = np.array(
    new_paths
)


# ============================================================
# APPEND TO EXISTING DATABASE
# ============================================================

X_updated = np.vstack(
    [
        X_existing,
        X_new
    ]
)

y_updated = np.concatenate(
    [
        y_existing,
        y_new
    ]
)

paths_updated = np.concatenate(
    [
        paths_existing,
        paths_new
    ]
)


# ============================================================
# SAVE UPDATED DATABASE
# ============================================================

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


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n" + "=" * 60)
print("DATABASE UPDATE COMPLETE")
print("=" * 60)

print(
    "New images added:",
    successful
)

print(
    "Existing images skipped:",
    skipped
)

print(
    "Failed images:",
    failed
)

print(
    "Previous embeddings:",
    len(X_existing)
)

print(
    "New embeddings:",
    len(X_new)
)

print(
    "Total embeddings:",
    len(X_updated)
)

print(
    "Total people:",
    len(np.unique(y_updated))
)

print(
    "Embedding dimensions:",
    X_updated.shape[1]
)

print(
    "\nDatabase saved to:"
)

print(
    FEATURE_DIR
)