import os
import sys
import cv2
import numpy as np
import mediapipe as mp
import joblib


# ============================================================
# MEDIAPIPE FACE RECOGNITION PREDICTOR
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
    "face_landmarker.task"
)

KNN_PATH = os.path.join(
    BASE_DIR,
    "models",
    "mediapipe_knn.joblib"
)

LABELS_PATH = os.path.join(
    BASE_DIR,
    "data",
    "mediapipe_features",
    "y.npy"
)


# ============================================================
# CREATE MEDIAPIPE LANDMARKER
# ============================================================

def create_landmarker():

    BaseOptions = mp.tasks.BaseOptions

    FaceLandmarker = mp.tasks.vision.FaceLandmarker

    FaceLandmarkerOptions = (
        mp.tasks.vision.FaceLandmarkerOptions
    )

    RunningMode = mp.tasks.vision.RunningMode

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


# ============================================================
# EXTRACT SAME FEATURES USED DURING TRAINING
# ============================================================

def extract_features(
    image_path,
    landmarker
):

    image = cv2.imread(
        image_path
    )

    if image is None:

        raise FileNotFoundError(
            f"Could not read image: {image_path}"
        )

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


# ============================================================
# MAIN
# ============================================================

print("=" * 60)
print("MEDIAPIPE FACE RECOGNITION PREDICTOR")
print("=" * 60)


# ============================================================
# CHECK FILES
# ============================================================

for path in [
    MODEL_PATH,
    KNN_PATH,
    LABELS_PATH
]:

    if not os.path.exists(path):

        raise FileNotFoundError(
            f"\nRequired file not found:\n{path}"
        )


# ============================================================
# LOAD KNN
# ============================================================

print("\nLoading MediaPipe KNN...")

knn = joblib.load(
    KNN_PATH
)

print("KNN loaded!")

print(
    "Number of neighbors:",
    knn.n_neighbors
)

print(
    "Distance metric:",
    knn.metric
)


# ============================================================
# LOAD LABELS
# ============================================================

labels = np.load(
    LABELS_PATH,
    allow_pickle=True
)

labels = labels.astype(str)

print(
    "Registered images:",
    len(labels)
)

print(
    "Number of people:",
    len(np.unique(labels))
)


# ============================================================
# GET IMAGE
# ============================================================

if len(sys.argv) >= 2:

    image_path = sys.argv[1]

else:

    image_path = input(
        "\nEnter image path: "
    ).strip().strip('"')


if not os.path.isabs(
    image_path
):

    image_path = os.path.join(
        BASE_DIR,
        image_path
    )


if not os.path.exists(
    image_path
):

    raise FileNotFoundError(
        f"\nImage not found:\n{image_path}"
    )


print(
    "\nImage:",
    image_path
)


# ============================================================
# EXTRACT FEATURES
# ============================================================

print(
    "\nDetecting face landmarks..."
)

with create_landmarker() as landmarker:

    features = extract_features(
        image_path,
        landmarker
    )


if features is None:

    print(
        "\nNo face detected."
    )

    sys.exit(0)


print(
    "Face detected!"
)

print(
    "Feature shape:",
    features.shape
)


# ============================================================
# PREDICTION
# ============================================================

X = features.reshape(
    1,
    -1
)

print(
    "\nRunning MediaPipe KNN prediction..."
)

prediction = knn.predict(
    X
)[0]

predicted_person = str(
    prediction
)


# ============================================================
# DISTANCE / CONFIDENCE
# ============================================================

distances, indices = knn.kneighbors(
    X,
    n_neighbors=knn.n_neighbors
)

distances = distances[0]
indices = indices[0]

neighbor_labels = labels[
    indices
]


# Convert distance to a simple relative score.
# This is NOT a calibrated probability.
similarities = 1.0 / (
    1.0 + distances
)

confidence_score = float(
    np.mean(similarities)
)


# ============================================================
# TOP NEIGHBORS
# ============================================================

print(
    "\n" + "=" * 60
)

print(
    "MEDIAPIPE PREDICTION"
)

print(
    "=" * 60
)

print(
    "\nPredicted person:",
    predicted_person
)

print(
    f"Relative confidence score: "
    f"{confidence_score * 100:.2f}%"
)

print(
    "\n" + "=" * 60
)

print(
    "TOP 5 NEAREST TRAINING IMAGES"
)

print(
    "=" * 60
)

for rank, (
    distance,
    index,
    person
) in enumerate(
    zip(
        distances,
        indices,
        neighbor_labels
    ),
    start=1
):

    similarity = 1.0 / (
        1.0 + distance
    )

    print(
        f"{rank}. "
        f"{person:30s} "
        f"distance = {distance:.6f} "
        f"score = {similarity * 100:.2f}%"
    )


# ============================================================
# CLASS VOTE SUMMARY
# ============================================================

print(
    "\n" + "=" * 60
)

print(
    "NEIGHBOR VOTE"
)

print(
    "=" * 60
)

unique_people, counts = np.unique(
    neighbor_labels,
    return_counts=True
)

order = np.argsort(
    counts
)[::-1]

for rank, idx in enumerate(
    order,
    start=1
):

    print(
        f"{rank}. "
        f"{unique_people[idx]:30s} "
        f"{counts[idx]}/{len(neighbor_labels)} neighbors"
    )


print(
    "\n" + "=" * 60
)

print(
    "PREDICTION COMPLETE"
)

print(
    "=" * 60
)