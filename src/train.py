"""
train.py
Trains three classical face recognition algorithms (Eigenfaces, Fisherfaces, LBPH)
on the images stored in data/registered/<person_name>/*.pgm (or .jpg/.png).

Folder structure expected:
    data/registered/
        person_1/
            img1.pgm
            img2.pgm
        person_2/
            img1.pgm
            ...

Run:
    python src/train.py
"""

import os
import json
import cv2
import numpy as np

# ---- Paths ----
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "registered")
MODELS_DIR = os.path.join(BASE_DIR, "models")
LABELS_PATH = os.path.join(BASE_DIR, "labels.json")

# Fixed size all training/query images get resized to before training/prediction.
# Must be IDENTICAL at train time and predict time, or the recognizers will error.
IMG_SIZE = (100, 100)


def load_dataset(data_dir):
    """
    Walks data_dir, reads every image in every person-subfolder, resizes to IMG_SIZE,
    and returns (images, labels, label_to_name) where labels are integer IDs.
    """
    images = []
    labels = []
    label_to_name = {}
    current_label = 0

    person_folders = sorted(
        f for f in os.listdir(data_dir)
        if os.path.isdir(os.path.join(data_dir, f))
    )

    if not person_folders:
        raise RuntimeError(f"No person folders found in {data_dir}")

    for person_name in person_folders:
        person_path = os.path.join(data_dir, person_name)
        image_files = [
            f for f in os.listdir(person_path)
            if f.lower().endswith((".pgm", ".jpg", ".jpeg", ".png"))
        ]

        if not image_files:
            continue

        for image_file in image_files:
            img_path = os.path.join(person_path, image_file)
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                print(f"  [skip] could not read {img_path}")
                continue
            img = cv2.resize(img, IMG_SIZE)
            images.append(img)
            labels.append(current_label)

        label_to_name[current_label] = person_name
        current_label += 1

    return images, np.array(labels), label_to_name


def train_and_save(images, labels, label_to_name):
    os.makedirs(MODELS_DIR, exist_ok=True)

    recognizers = {
        "eigenfaces": cv2.face.EigenFaceRecognizer_create(),
        "fisherfaces": cv2.face.FisherFaceRecognizer_create(),
        "lbph": cv2.face.LBPHFaceRecognizer_create(),
    }

    num_people = len(set(labels))
    if num_people < 2:
        print("WARNING: Fisherfaces requires at least 2 people to train (LDA needs "
              "multiple classes). Training will likely fail with only 1 person.")

    for name, recognizer in recognizers.items():
        print(f"Training {name} ...")
        recognizer.train(images, labels)
        save_path = os.path.join(MODELS_DIR, f"{name}_model.yml")
        recognizer.save(save_path)
        print(f"  saved -> {save_path}")

    with open(LABELS_PATH, "w") as f:
        json.dump(label_to_name, f, indent=2)
    print(f"Labels saved -> {LABELS_PATH}")


def main():
    print(f"Loading dataset from: {DATA_DIR}")
    images, labels, label_to_name = load_dataset(DATA_DIR)
    print(f"Loaded {len(images)} images across {len(set(labels))} people.")

    train_and_save(images, labels, label_to_name)
    print("\nDone. All three models trained and saved to /models.")


if __name__ == "__main__":
    main()
