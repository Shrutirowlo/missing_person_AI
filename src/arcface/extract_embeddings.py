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

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "data",
    "arcface_features"
)

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)


# ============================================================
# LOAD ARCFACE RECOGNITION MODEL
# ============================================================

MODEL_PATH = os.path.expanduser(
    r"~\.insightface\models\buffalo_l\w600k_r50.onnx"
)

print("=" * 60)
print("LOADING ARCFACE RECOGNITION MODEL")
print("=" * 60)

print("Model:", MODEL_PATH)

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(
        f"ArcFace model not found:\n{MODEL_PATH}"
    )

recognition_model = get_model(
    MODEL_PATH
)

recognition_model.prepare(
    ctx_id=0
)

print("ArcFace recognition model loaded!")
print()


# ============================================================
# PREPROCESSING
# ============================================================

def prepare_face(image):
    """
    LFW images are already face-cropped images.

    We preserve their aspect ratio and place the face crop
    into a square canvas before resizing to 112x112.

    This avoids stretching a 94x125 image directly into
    112x112.
    """

    h, w = image.shape[:2]

    # Make square canvas
    size = max(h, w)

    canvas = np.zeros(
        (size, size, 3),
        dtype=np.uint8
    )

    # Center image
    y_offset = (size - h) // 2
    x_offset = (size - w) // 2

    canvas[
        y_offset:y_offset + h,
        x_offset:x_offset + w
    ] = image

    # ArcFace recognition input
    face = cv2.resize(
        canvas,
        (112, 112),
        interpolation=cv2.INTER_CUBIC
    )

    return face


# ============================================================
# EMBEDDING FUNCTION
# ============================================================

def generate_embedding(image):

    face = prepare_face(image)

    embedding = recognition_model.get_feat(
        face
    )

    embedding = embedding.flatten()

    # L2 normalization
    norm = np.linalg.norm(
        embedding
    )

    if norm > 0:
        embedding = embedding / norm

    return embedding.astype(
        np.float32
    )


# ============================================================
# STORAGE
# ============================================================

embeddings = []
labels = []
image_paths = []

successful = 0
failed = 0


# ============================================================
# FIND PEOPLE
# ============================================================

people = sorted(
    [
        folder
        for folder in os.listdir(
            DATASET_DIR
        )
        if os.path.isdir(
            os.path.join(
                DATASET_DIR,
                folder
            )
        )
    ]
)

print(
    "Number of people:",
    len(people)
)

print()


# ============================================================
# PROCESS DATASET
# ============================================================

for person in people:

    person_dir = os.path.join(
        DATASET_DIR,
        person
    )

    print(
        f"Processing: {person}"
    )

    files = sorted(
        os.listdir(
            person_dir
        )
    )

    person_success = 0
    person_failed = 0

    for filename in files:

        image_path = os.path.join(
            person_dir,
            filename
        )

        # Only image files
        if not filename.lower().endswith(
            (".jpg", ".jpeg", ".png", ".bmp")
        ):
            continue

        image = cv2.imread(
            image_path
        )

        if image is None:

            print(
                f"  FAILED: {filename} "
                "(could not read)"
            )

            failed += 1
            person_failed += 1
            continue

        try:

            embedding = generate_embedding(
                image
            )

            embeddings.append(
                embedding
            )

            labels.append(
                person
            )

            image_paths.append(
                image_path
            )

            successful += 1
            person_success += 1

        except Exception as e:

            print(
                f"  FAILED: {filename} "
                f"({e})"
            )

            failed += 1
            person_failed += 1

    print(
        f"  Successful: {person_success}"
    )

    if person_failed > 0:

        print(
            f"  Failed: {person_failed}"
        )

    print()


# ============================================================
# CONVERT TO NUMPY
# ============================================================

X = np.array(
    embeddings,
    dtype=np.float32
)

y = np.array(
    labels
)

paths = np.array(
    image_paths
)


# ============================================================
# SAVE
# ============================================================

np.save(
    os.path.join(
        OUTPUT_DIR,
        "X.npy"
    ),
    X
)

np.save(
    os.path.join(
        OUTPUT_DIR,
        "y.npy"
    ),
    y
)

np.save(
    os.path.join(
        OUTPUT_DIR,
        "paths.npy"
    ),
    paths
)


# ============================================================
# SUMMARY
# ============================================================

print("=" * 60)
print("ARCFACE EMBEDDING EXTRACTION COMPLETE")
print("=" * 60)

print(
    "Successful images:",
    successful
)

print(
    "Failed images:",
    failed
)

print(
    "X shape:",
    X.shape
)

print(
    "y shape:",
    y.shape
)

print(
    "Number of people:",
    len(
        np.unique(y)
    )
)

if len(X) > 0:

    print(
        "Embedding dimensions:",
        X.shape[1]
    )

print()

print(
    "Saved to:",
    OUTPUT_DIR
)