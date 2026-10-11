import os
import cv2
import numpy as np

from insightface.app import FaceAnalysis
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

FEATURE_DIR = os.path.join(
    BASE_DIR,
    "data",
    "arcface_features"
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

ARCFACE_MODEL = os.path.expanduser(
    r"~\.insightface\models\buffalo_l\w600k_r50.onnx"
)


# ============================================================
# LOAD TRAINING EMBEDDINGS
# ============================================================

print("=" * 60)
print("LOADING ARCFACE PREDICTOR")
print("=" * 60)

X = np.load(X_PATH)
y = np.load(Y_PATH)

print("Training embeddings:", X.shape)
print("Training labels:", y.shape)


# ============================================================
# LOAD ARCFACE DETECTOR
# ============================================================

print("\nLoading ArcFace detector...")

app = FaceAnalysis(
    name="buffalo_l",
    providers=["CPUExecutionProvider"]
)

app.prepare(
    ctx_id=0,
    det_size=(640, 640)
)


# ============================================================
# LOAD RECOGNITION-ONLY ARCFACE MODEL
# ============================================================

print("Loading ArcFace recognition model...")

recognition_model = get_model(
    ARCFACE_MODEL
)

recognition_model.prepare(
    ctx_id=0
)

print("ArcFace models loaded!")


# ============================================================
# NORMALIZE EMBEDDING
# ============================================================

def normalize_embedding(embedding):

    embedding = np.asarray(
        embedding,
        dtype=np.float32
    )

    norm = np.linalg.norm(
        embedding
    )

    if norm == 0:
        return embedding

    return embedding / norm


# ============================================================
# GET EMBEDDING FROM SMALL LFW-STYLE IMAGE
# ============================================================

def get_crop_embedding(image):

    """
    LFW images are already cropped faces.

    Example:
        94 x 125 image

    We DO NOT run the face detector.

    Instead:
        image
          ↓
        resize 112x112
          ↓
        ArcFace recognition model
          ↓
        512-D embedding
    """

    resized = cv2.resize(
        image,
        (112, 112),
        interpolation=cv2.INTER_CUBIC
    )

    embedding = recognition_model.get_feat(
        resized
    )[0]

    return normalize_embedding(
        embedding
    )


# ============================================================
# GET EMBEDDING FROM NORMAL PHOTO
# ============================================================

def get_photo_embedding(image):

    """
    Normal photographs may contain the entire person/background.

    We detect the face first and then use the aligned
    ArcFace embedding.
    """

    faces = app.get(image)

    if len(faces) == 0:
        return None, 0

    if len(faces) > 1:

        # Use the largest detected face
        faces = sorted(
            faces,
            key=lambda f: (
                f.bbox[2] - f.bbox[0]
            ) * (
                f.bbox[3] - f.bbox[1]
            ),
            reverse=True
        )

    face = faces[0]

    embedding = face.embedding

    return normalize_embedding(
        embedding
    ), len(faces)


# ============================================================
# AUTOMATIC INPUT TYPE
# ============================================================

def get_test_embedding(image):

    h, w = image.shape[:2]

    print("\nImage shape:", image.shape)

    # --------------------------------------------------------
    # SMALL IMAGE = ALREADY CROPPED LFW-STYLE FACE
    # --------------------------------------------------------

    if min(h, w) < 200:

        print(
            "Small image detected."
        )

        print(
            "Treating image as an already-cropped face."
        )

        embedding = get_crop_embedding(
            image
        )

        return embedding, "LFW_CROP"

    # --------------------------------------------------------
    # LARGE IMAGE = NORMAL PHOTO
    # --------------------------------------------------------

    print(
        "Normal-size image detected."
    )

    print(
        "Running face detection..."
    )

    embedding, face_count = get_photo_embedding(
        image
    )

    if embedding is None:

        return None, "NO_FACE"

    print(
        "Faces detected:",
        face_count
    )

    return embedding, "NORMAL_PHOTO"


# ============================================================
# COSINE SIMILARITY
# ============================================================

def cosine_similarity(
    test_embedding,
    training_embeddings
):

    # Both are normalized, so dot product = cosine similarity

    similarities = np.dot(
        training_embeddings,
        test_embedding
    )

    return similarities


# ============================================================
# CLASS-LEVEL SIMILARITY
# ============================================================

def calculate_class_scores(
    similarities
):

    results = []

    people = np.unique(y)

    for person in people:

        scores = similarities[
            y == person
        ]

        # Best few images are more useful than
        # averaging hundreds of unrelated images.

        top_n = min(
            5,
            len(scores)
        )

        top_scores = np.sort(
            scores
        )[-top_n:]

        class_score = np.mean(
            top_scores
        )

        best_score = np.max(
            scores
        )

        results.append(
            (
                person,
                class_score,
                best_score
            )
        )

    results.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return results


# ============================================================
# MAIN
# ============================================================

print("\n" + "=" * 60)
print("ARCFACE READY")
print("=" * 60)

image_path = input(
    "\nEnter image path: "
).strip().strip('"')


# ------------------------------------------------------------
# READ IMAGE
# ------------------------------------------------------------

image = cv2.imread(
    image_path
)

if image is None:

    print(
        "\nERROR: Could not read image."
    )

    print(
        "Check the image path."
    )

    raise SystemExit


# ------------------------------------------------------------
# GENERATE TEST EMBEDDING
# ------------------------------------------------------------

test_embedding, input_type = get_test_embedding(
    image
)


if test_embedding is None:

    print("\n" + "=" * 60)
    print("NO FACE DETECTED")
    print("=" * 60)

    print(
        "The image appears to be a normal photo, "
        "but no face could be detected."
    )

    raise SystemExit


print(
    "\nInput type:",
    input_type
)

print(
    "Test embedding shape:",
    test_embedding.shape
)


# ============================================================
# COMPARE AGAINST ALL TRAINING EMBEDDINGS
# ============================================================

similarities = cosine_similarity(
    test_embedding,
    np.array([
        normalize_embedding(x)
        for x in X
    ])
)


# ============================================================
# TOP 10 INDIVIDUAL MATCHES
# ============================================================

top_indices = np.argsort(
    similarities
)[::-1][:10]


print("\n" + "=" * 60)
print("TOP 10 CLOSEST TRAINING IMAGES")
print("=" * 60)

for rank, idx in enumerate(
    top_indices,
    start=1
):

    print(
        f"{rank:2d}. "
        f"{y[idx]:30s} "
        f"similarity = {similarities[idx]:.4f}"
    )


# ============================================================
# CLASS-LEVEL RESULTS
# ============================================================

class_results = calculate_class_scores(
    similarities
)


print("\n" + "=" * 60)
print("CLASS-LEVEL RESULTS")
print("=" * 60)

for rank, (
    person,
    class_score,
    best_score
) in enumerate(
    class_results[:10],
    start=1
):

    print(
        f"{rank}. "
        f"{person:30s} "
        f"score = {class_score:.4f} "
        f"(best = {best_score:.4f})"
    )


# ============================================================
# FINAL RESULT
# ============================================================

best_person = class_results[0][0]
best_class_score = class_results[0][1]
best_individual_score = class_results[0][2]

second_class_score = (
    class_results[1][1]
    if len(class_results) > 1
    else 0
)

margin = (
    best_class_score
    - second_class_score
)


# ============================================================
# UNKNOWN / LOW-CONFIDENCE CHECK
# ============================================================

# This is deliberately conservative.
#
# A similarity above ~0.60 is generally much more meaningful
# for ArcFace embeddings than forcing every image to a name.
#
# We also require a reasonable margin over the second class.

if (
    best_class_score >= 0.60
    and margin >= 0.10
):

    decision = "MATCH FOUND"

elif best_class_score >= 0.50:

    decision = "POSSIBLE MATCH"

else:

    decision = "NO RELIABLE MATCH"


# ============================================================
# FINAL OUTPUT
# ============================================================

print("\n" + "=" * 60)
print("FINAL ARCFACE PREDICTION")
print("=" * 60)

print(
    "Result:",
    decision
)

print(
    "Predicted person:",
    best_person
)

print(
    f"Best class similarity: "
    f"{best_class_score:.4f}"
)

print(
    f"Closest image similarity: "
    f"{best_individual_score:.4f}"
)

print(
    f"Margin over second class: "
    f"{margin:.4f}"
)

print(
    "=" * 60
)