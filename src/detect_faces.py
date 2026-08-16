"""
detect_faces.py
Takes ordinary photos (with background, shoulders, etc.) and produces clean,
cropped, grayscale, resized face images -- ready to be used by train.py.

HOW TO USE:
1. Put a person's raw photos in: data/raw_photos/<person_name>/*.jpg (or .png)
2. Run:
       python src/detect_faces.py <person_name>
3. This finds the face in each photo, crops it, and saves the result into:
       data/registered/<person_name>/*.jpg
   -- which is exactly where train.py expects to find it.

Example:
    python src/detect_faces.py ravi_kumar
"""

import os
import sys
import cv2

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw_photos")
REGISTERED_DIR = os.path.join(BASE_DIR, "data", "registered")

# Face size the cropped output gets resized to before saving.
# (train.py will resize again to its own IMG_SIZE, but saving at a
# reasonable size here keeps files small and crops easy to sanity-check.)
OUTPUT_SIZE = (200, 200)

# Built-in Haar Cascade that ships with OpenCV -- no separate download needed.
# NOTE: if OpenCV's bundled data files are missing/corrupted on your system,
# download haarcascade_frontalface_default.xml yourself and place it in this
# same src/ folder -- this script will use that local copy automatically.
_LOCAL_CASCADE = os.path.join(BASE_DIR, "src", "haarcascade_frontalface_default.xml")
if os.path.isfile(_LOCAL_CASCADE):
    CASCADE_PATH = _LOCAL_CASCADE
else:
    CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"


def detect_and_crop_faces(person_name):
    raw_person_dir = os.path.join(RAW_DIR, person_name)
    out_person_dir = os.path.join(REGISTERED_DIR, person_name)

    if not os.path.isdir(raw_person_dir):
        raise FileNotFoundError(
            f"No folder found at {raw_person_dir}. "
            f"Create it and put this person's raw photos inside first."
        )

    os.makedirs(out_person_dir, exist_ok=True)

    face_cascade = cv2.CascadeClassifier(CASCADE_PATH)
    if face_cascade.empty():
        raise RuntimeError("Failed to load Haar Cascade file -- check OpenCV install.")

    photo_files = [
        f for f in os.listdir(raw_person_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    if not photo_files:
        print(f"No photos found in {raw_person_dir}")
        return

    saved_count = 0
    skipped_count = 0

    for filename in photo_files:
        filepath = os.path.join(raw_person_dir, filename)
        img = cv2.imread(filepath)
        if img is None:
            print(f"  [skip] could not read {filename}")
            skipped_count += 1
            continue

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # detectMultiScale finds face-shaped regions in the image.
        # scaleFactor / minNeighbors are tuning knobs -- these defaults
        # work well for typical phone photos.
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60),
        )

        if len(faces) == 0:
            print(f"  [skip] no face detected in {filename}")
            skipped_count += 1
            continue

        if len(faces) > 1:
            # If multiple faces found, just take the largest one
            # (assumes the intended subject is the biggest face in frame).
            faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)

        x, y, w, h = faces[0]
        face_crop = gray[y:y + h, x:x + w]
        face_crop = cv2.resize(face_crop, OUTPUT_SIZE)

        out_name = os.path.splitext(filename)[0] + "_face.jpg"
        out_path = os.path.join(out_person_dir, out_name)
        cv2.imwrite(out_path, face_crop)
        print(f"  [ok] {filename} -> {out_name}")
        saved_count += 1

    print(f"\nDone. {saved_count} face(s) saved, {skipped_count} skipped.")
    print(f"Output folder: {out_person_dir}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python src/detect_faces.py <person_name>")
        print(f"(person_name must match a folder inside {RAW_DIR})")
        sys.exit(1)

    person_name = sys.argv[1]
    detect_and_crop_faces(person_name)


if __name__ == "__main__":
    main()
