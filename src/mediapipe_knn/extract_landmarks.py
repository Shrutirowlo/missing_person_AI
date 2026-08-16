
import os
import sys
import cv2
import numpy as np
import mediapipe as mp


# --------------------------------------------------
# 1. Find the project folder
# --------------------------------------------------

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)


# --------------------------------------------------
# 2. Location of MediaPipe model
# --------------------------------------------------

MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "face_landmarker.task"
)


# --------------------------------------------------
# 3. Create MediaPipe Face Landmarker
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
# 4. Extract landmarks from an image
# --------------------------------------------------

def extract_landmarks(image_path):

    # Read image
    image = cv2.imread(image_path)

    if image is None:
        raise FileNotFoundError(
            f"Could not read image: {image_path}"
        )


    # OpenCV uses BGR.
    # MediaPipe expects RGB.
    image_rgb = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2RGB
    )


    # Convert OpenCV image to MediaPipe image
    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=image_rgb
    )


    # Create detector
    with create_landmarker() as landmarker:

        # Detect face landmarks
        result = landmarker.detect(mp_image)


    # No face found
    if not result.face_landmarks:

        return None


    # Take the first detected face
    face_landmarks = result.face_landmarks[0]


    # Store x, y, z values
    features = []


    for landmark in face_landmarks:

        features.extend([
            landmark.x,
            landmark.y,
            landmark.z
        ])


    # Convert list to NumPy array
    return np.array(
        features,
        dtype=np.float32
    )


# --------------------------------------------------
# 5. Main program
# --------------------------------------------------

def main():

    if len(sys.argv) < 2:

        print(
            "Usage:"
            " py src/mediapipe_knn/"
            "extract_landmarks.py <image_path>"
        )

        return


    image_path = sys.argv[1]


    features = extract_landmarks(image_path)


    if features is None:

        print("No face detected.")

        return


    print("Face detected!")

    print(
        "Number of features:",
        len(features)
    )


    print("\nFirst 15 values:")

    print(features[:15])


# --------------------------------------------------
# 6. Run main()
# --------------------------------------------------

if __name__ == "__main__":
    main()