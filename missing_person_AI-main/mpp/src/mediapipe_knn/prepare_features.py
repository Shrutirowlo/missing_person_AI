import os
import sys
import cv2
import numpy as np
import mediapipe as mp


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

REGISTERED_DIR = os.path.join(
    BASE_DIR,
    "data",
    "registered"
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "data",
    "mediapipe_features"
)


# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)


MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "face_landmarker.task"
)


# --------------------------------------------------
# CREATE MEDIAPIPE LANDMARKER
# --------------------------------------------------

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

    return FaceLandmarker.create_from_options(options)


# --------------------------------------------------
# EXTRACT FEATURES FROM ONE IMAGE
# --------------------------------------------------

def extract_features(image_path, landmarker):

    image = cv2.imread(image_path)

    if image is None:
        print(f"Could not read: {image_path}")
        return None

    image_rgb = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2RGB
    )

    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=image_rgb
    )

    result = landmarker.detect(mp_image)

    # No face detected
    if not result.face_landmarks:
        return None

    # Take first detected face
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


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    all_features = []
    all_labels = []
    all_paths = []

    processed = 0
    failed = 0


    # Create MediaPipe once
    # instead of creating it for every image
    with create_landmarker() as landmarker:

        # Get every person folder
        person_names = sorted(
            os.listdir(REGISTERED_DIR)
        )


        for person_name in person_names:

            person_dir = os.path.join(
                REGISTERED_DIR,
                person_name
            )

            if not os.path.isdir(person_dir):
                continue


            print(
                f"\nProcessing: {person_name}"
            )


            # Get image files
            image_files = sorted(
                os.listdir(person_dir)
            )


            for filename in image_files:

                if not filename.lower().endswith(
                    (".jpg", ".jpeg", ".png")
                ):
                    continue


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


                all_features.append(features)

                all_labels.append(person_name)

                all_paths.append(image_path)

                processed += 1


            print(
                f"  Processed so far: {processed}"
            )


    # --------------------------------------------------
    # CONVERT TO NUMPY ARRAYS
    # --------------------------------------------------

    X = np.array(
        all_features,
        dtype=np.float32
    )

    y = np.array(
        all_labels
    )

    paths = np.array(
        all_paths
    )


    # --------------------------------------------------
    # SAVE
    # --------------------------------------------------

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


    # --------------------------------------------------
    # SUMMARY
    # --------------------------------------------------

    print("\n" + "=" * 50)

    print("FEATURE EXTRACTION COMPLETE")

    print("=" * 50)

    print(
        "Successful images:",
        processed
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
        len(np.unique(y))
    )

    print(
        "Features per image:",
        X.shape[1] if len(X) > 0 else 0
    )


if __name__ == "__main__":
    main()