"""
recognize.py
Loads the three trained models and runs a query image through all of them,
printing the predicted person + confidence score for each algorithm side by side.

UPDATED: now includes "Unknown / No match found" rejection logic. Each
algorithm's predict() call always returns SOME label, even for a total
stranger's photo -- it just finds whichever trained person is mathematically
closest. To make the system report "no match" honestly when appropriate, we
compare each prediction's confidence/distance against a per-algorithm
threshold derived from held-out testing (see metrics.py / results/
confidence_analysis.csv). If the distance is WORSE (numerically higher) than
the threshold, we report "Unknown" instead of naming a person.

Note on confidence scores:
    - For Eigenfaces/Fisherfaces/LBPH in OpenCV, LOWER confidence = BETTER
      match (it's actually a distance, not a similarity score).
    - The three algorithms' confidence scales are NOT directly comparable to
      each other -- only compare confidence values within the same algorithm.
    - These thresholds were derived from held-out testing on the LFW + biswa
      dataset (~373 test predictions). Correct/wrong confidence ranges
      OVERLAP for all three algorithms (see project log Section 10) -- LBPH
      has the narrowest, most trustworthy gap. Treat these as reasonable
      starting points, not guaranteed-perfect cutoffs, since the test set
      only contained people who WERE in the database (a true stranger's
      photo may produce an even worse distance than anything seen here).

Run:
    python src/recognize.py path/to/query_image.pgm
"""

import os
import sys
import json
import cv2

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")
LABELS_PATH = os.path.join(BASE_DIR, "labels.json")

IMG_SIZE = (100, 100)  # must match train.py

# Thresholds derived from metrics.py's confidence threshold analysis
# (results/confidence_analysis.csv). If a prediction's distance is HIGHER
# than this value, we treat it as "no match" rather than naming a person.
# Adjust these here if you re-run metrics.py and get updated numbers.
CONFIDENCE_THRESHOLDS = {
    "eigenfaces": 3079.2,
    "fisherfaces": 67.4,
    "lbph": 80.9,
}


def load_labels():
    with open(LABELS_PATH, "r") as f:
        label_to_name = json.load(f)
    return {int(k): v for k, v in label_to_name.items()}


def load_models():
    models = {}

    eigen = cv2.face.EigenFaceRecognizer_create()
    eigen.read(os.path.join(MODELS_DIR, "eigenfaces_model.yml"))
    models["eigenfaces"] = eigen

    fisher = cv2.face.FisherFaceRecognizer_create()
    fisher.read(os.path.join(MODELS_DIR, "fisherfaces_model.yml"))
    models["fisherfaces"] = fisher

    lbph = cv2.face.LBPHFaceRecognizer_create()
    lbph.read(os.path.join(MODELS_DIR, "lbph_model.yml"))
    models["lbph"] = lbph

    return models


def preprocess(image_path):
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")
    img = cv2.resize(img, IMG_SIZE)
    return img


def predict_all(query_img, models, label_to_name):
    results = {}
    for name, model in models.items():
        label, confidence = model.predict(query_img)
        threshold = CONFIDENCE_THRESHOLDS.get(name)

        if threshold is not None and confidence > threshold:
            person_name = "Unknown / No match found"
            is_match = False
        else:
            person_name = label_to_name.get(label, "Unknown")
            is_match = True

        results[name] = {
            "person": person_name,
            "confidence": round(float(confidence), 2),
            "threshold": threshold,
            "is_match": is_match,
        }
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python src/recognize.py <path_to_query_image>")
        sys.exit(1)

    query_path = sys.argv[1]

    label_to_name = load_labels()
    models = load_models()
    query_img = preprocess(query_path)

    results = predict_all(query_img, models, label_to_name)

    print(f"\nQuery image: {query_path}")
    print("-" * 65)
    for algo, res in results.items():
        match_tag = "MATCH" if res["is_match"] else "NO MATCH"
        print(f"{algo:12s} -> [{match_tag:8s}] predicted: {res['person']:25s} "
              f"(confidence/distance: {res['confidence']}, "
              f"threshold: {res['threshold']}, lower = better match)")
    print("-" * 65)
    print("Note: confidence scales differ between algorithms -- "
          "don't compare the numbers across rows directly.")
    print("Note: thresholds are approximate (correct/wrong confidence ranges "
          "overlap for all 3 algorithms) -- see project log Section 10.")


if __name__ == "__main__":
    main()
