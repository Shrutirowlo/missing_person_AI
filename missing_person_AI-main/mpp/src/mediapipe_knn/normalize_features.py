import os
import numpy as np


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

FEATURE_DIR = os.path.join(
    BASE_DIR,
    "data",
    "mediapipe_features"
)


# --------------------------------------------------
# LOAD ORIGINAL FEATURES
# --------------------------------------------------

X = np.load(
    os.path.join(
        FEATURE_DIR,
        "X.npy"
    )
)

print("Original X shape:", X.shape)


# --------------------------------------------------
# RESHAPE
# --------------------------------------------------

# Each image has:
# 478 landmarks × 3 coordinates

X_landmarks = X.reshape(
    -1,
    478,
    3
)


# --------------------------------------------------
# NORMALIZE EACH FACE
# --------------------------------------------------

X_normalized = []

for face in X_landmarks:

    # ----------------------------------------------
    # STEP 1: CENTER THE FACE
    # ----------------------------------------------

    # Use landmark 1 as reference point
    reference = face[1]

    centered = face - reference


    # ----------------------------------------------
    # STEP 2: NORMALIZE SCALE
    # ----------------------------------------------

    # Calculate distance of every landmark
    # from the reference point

    distances = np.linalg.norm(
        centered,
        axis=1
    )

    scale = np.max(distances)

    # Avoid division by zero
    if scale > 0:
        normalized = centered / scale
    else:
        normalized = centered


    X_normalized.append(
        normalized.flatten()
    )


# --------------------------------------------------
# CONVERT TO NUMPY ARRAY
# --------------------------------------------------

X_normalized = np.array(
    X_normalized,
    dtype=np.float32
)


# --------------------------------------------------
# SAVE
# --------------------------------------------------

output_path = os.path.join(
    FEATURE_DIR,
    "X_normalized.npy"
)

np.save(
    output_path,
    X_normalized
)


# --------------------------------------------------
# SUMMARY
# --------------------------------------------------

print("\nNormalization complete!")

print(
    "Original shape:",
    X.shape
)

print(
    "Normalized shape:",
    X_normalized.shape
)

print(
    "Saved to:",
    output_path
)