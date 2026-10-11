"""
prepare_lfw_dataset.py

Downloads the LFW (Labeled Faces in the Wild) dataset via scikit-learn,
keeps only people who have at least MIN_FACES_PER_PERSON photos, and saves
the images into data/registered/<person_name>/ -- the same folder structure
train.py already expects.

WHY min_faces_per_person:
    Most people in the full LFW dataset only have 1-2 photos, which isn't
    enough to train a per-person recognizer. This script only keeps people
    with "enough" photos, and lets you tune MIN_FACES_PER_PERSON up/down
    until the total image count is close to your target (e.g. ~5000).

HOW TO USE:
    1. Run this script once with the default MIN_FACES_PER_PERSON.
    2. It will print the total number of images and people found.
    3. If the total is too high or too low compared to your target (5000),
       adjust MIN_FACES_PER_PERSON below (higher number = fewer people,
       fewer total images; lower number = more people, more total images)
       and run again.
    4. Once you're happy with the total, the images are already saved --
       you're ready to run: python src/train.py

NOTE: This requires an internet connection (to download LFW the first
time -- it gets cached locally afterward) and takes a few minutes.
"""

import os
from sklearn.datasets import fetch_lfw_people
import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "registered")

# --- TUNE THIS to hit your target total (~5000 images) ---
MIN_FACES_PER_PERSON = 40
# Roughly (based on standard LFW stats -- your exact numbers may vary slightly):
#   min_faces_per_person=70  -> ~7 people,   ~1300 images  (too few)
#   min_faces_per_person=20  -> ~60 people,  ~3000 images
#   min_faces_per_person=10  -> ~150 people, ~4300 images
#   min_faces_per_person=8   -> ~200 people, ~5000 images  (good starting guess)
#   min_faces_per_person=5   -> ~430 people, ~6700 images  (too many)
# Adjust and re-run until the printed total is close to 5000.


def main():
    print(f"Downloading/loading LFW dataset (min_faces_per_person={MIN_FACES_PER_PERSON})...")
    print("(First run downloads ~200MB and may take a few minutes; cached after that.)")

    lfw = fetch_lfw_people(
        min_faces_per_person=MIN_FACES_PER_PERSON,
        resize=1.0,        # keep original resolution; train.py resizes anyway
        color=False,        # grayscale, matches our pipeline
    )

    images = lfw.images          # shape: (num_images, height, width)
    labels = lfw.target          # numeric label per image
    target_names = lfw.target_names  # label -> person name

    total_images = len(images)
    total_people = len(target_names)

    print(f"\nLoaded {total_images} images across {total_people} people.")
    print("If this isn't close to your target (~5000), adjust MIN_FACES_PER_PERSON "
          "in this script and re-run.\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    saved_count = 0
    for idx in range(total_images):
        person_name = target_names[labels[idx]].replace(" ", "_").lower()
        person_dir = os.path.join(OUTPUT_DIR, person_name)
        os.makedirs(person_dir, exist_ok=True)

        # images from sklearn are float arrays normalized to 0.0-1.0 -- must scale
        # back to 0-255 BEFORE converting to uint8, or almost every pixel truncates to 0
        img = (images[idx] * 255).astype(np.uint8)

        # figure out the next available filename in this person's folder
        existing = len([f for f in os.listdir(person_dir) if f.endswith(".jpg")])
        out_path = os.path.join(person_dir, f"lfw_{existing + 1}.jpg")

        cv2.imwrite(out_path, img)
        saved_count += 1

        if saved_count % 500 == 0:
            print(f"  ...saved {saved_count}/{total_images}")

    print(f"\nDone. Saved {saved_count} images into {OUTPUT_DIR}")
    print(f"({total_people} people total)")


if __name__ == "__main__":
    main()
