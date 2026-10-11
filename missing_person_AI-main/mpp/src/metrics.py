"""
metrics.py — Held-out accuracy comparison for Eigenfaces / Fisherfaces / LBPH

Retrains all three algorithms on a TRAIN split only, then evaluates them on
a held-out TEST split (images the models never saw during training). This
is the "real generalization" proof for the report, redone on the CURRENT
dataset (LFW + biswa), not the old AT&T-only numbers.

Run from the project root (D:\\mpp):
    python src/metrics.py

Also analyzes confidence/distance scores for correct vs. wrong predictions,
and suggests a starting "unknown face" rejection threshold per algorithm
(used later in recognize.py / the Search screen to say "No match found"
instead of confidently naming the wrong person).

Outputs:
    results/metrics_report.csv       - per-algorithm accuracy + per-person breakdown
    results/accuracy_chart.png       - bar chart comparing the 3 algorithms
    results/confidence_analysis.csv  - correct vs wrong confidence stats + suggested thresholds
"""

import os
import csv
import random
import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Config — matches the conventions used in train.py / recognize.py
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data", "registered")
RESULTS_DIR = os.path.join(BASE_DIR, "..", "results")
IMG_SIZE = (100, 100)          # same fixed size train.py resizes to
RANDOM_SEED = 42
MIN_TEST_HOLD_THRESHOLD = 5    # people with >=5 images get a ~20% test split
TEST_FRACTION = 0.2            # for people with enough images

random.seed(RANDOM_SEED)


# ---------------------------------------------------------------------------
# Step 1: Load every image, grouped by person
# ---------------------------------------------------------------------------
def load_dataset_by_person(data_dir):
    """Returns {person_name: [gray_100x100_images...]}"""
    people = {}
    for person_name in sorted(os.listdir(data_dir)):
        person_dir = os.path.join(data_dir, person_name)
        if not os.path.isdir(person_dir):
            continue

        images = []
        for fname in sorted(os.listdir(person_dir)):
            fpath = os.path.join(person_dir, fname)
            img = cv2.imread(fpath, cv2.IMREAD_GRAYSCALE)
            if img is None:
                print(f"  [skip] could not read: {fpath}")
                continue
            img = cv2.resize(img, IMG_SIZE)
            images.append(img)

        if images:
            people[person_name] = images
        else:
            print(f"  [skip] no readable images for person: {person_name}")

    return people


# ---------------------------------------------------------------------------
# Step 2: Per-person train/test split
# ---------------------------------------------------------------------------
def split_train_test(people):
    """
    For each person, splits their images into train/test.
    - >=5 images: hold out ~20% (min 1) for test
    - <5 images: leave-one-out (hold out exactly 1) so biswa-style small
      folders still contribute to both training and evaluation
    - exactly 1 image: goes entirely into train (can't test with zero left)
    Returns (train_dict, test_dict) with same shape as `people`.
    """
    train, test = {}, {}

    for person, images in people.items():
        imgs = images[:]  # copy
        random.shuffle(imgs)
        n = len(imgs)

        if n <= 1:
            train[person] = imgs
            test[person] = []
            print(f"  [note] '{person}' has only {n} image — no test split possible")
            continue

        if n < MIN_TEST_HOLD_THRESHOLD:
            n_test = 1  # leave-one-out
        else:
            n_test = max(1, round(n * TEST_FRACTION))

        test[person] = imgs[:n_test]
        train[person] = imgs[n_test:]

    return train, test


def flatten(person_dict):
    """{person: [imgs]} -> (images_list, labels_list, label_to_name dict)"""
    label_to_name = {}
    name_to_label = {}
    images_out, labels_out = [], []

    for idx, person in enumerate(sorted(person_dict.keys())):
        name_to_label[person] = idx
        label_to_name[idx] = person
        for img in person_dict[person]:
            images_out.append(img)
            labels_out.append(idx)

    return images_out, np.array(labels_out), label_to_name, name_to_label


# ---------------------------------------------------------------------------
# Step 3: Train each algorithm on TRAIN split, evaluate on TEST split
# ---------------------------------------------------------------------------
def evaluate_algorithm(recognizer_factory, name,
                        train_images, train_labels,
                        test_images, test_labels, label_to_name):
    recognizer = recognizer_factory()
    recognizer.train(train_images, train_labels)

    correct = 0
    per_person_correct = {}
    per_person_total = {}
    correct_confidences = []   # confidence scores when prediction was RIGHT
    wrong_confidences = []     # confidence scores when prediction was WRONG

    for img, true_label in zip(test_images, test_labels):
        pred_label, confidence = recognizer.predict(img)
        true_name = label_to_name[true_label]

        per_person_total[true_name] = per_person_total.get(true_name, 0) + 1
        if pred_label == true_label:
            correct += 1
            per_person_correct[true_name] = per_person_correct.get(true_name, 0) + 1
            correct_confidences.append(confidence)
        else:
            wrong_confidences.append(confidence)

    total = len(test_labels)
    accuracy = (correct / total * 100) if total else 0.0

    return {
        "name": name,
        "correct": correct,
        "total": total,
        "accuracy": accuracy,
        "per_person_correct": per_person_correct,
        "per_person_total": per_person_total,
        "correct_confidences": correct_confidences,
        "wrong_confidences": wrong_confidences,
    }


# ---------------------------------------------------------------------------
# Step 3b: Confidence-score distribution analysis (for choosing thresholds)
# ---------------------------------------------------------------------------
def summarize_confidences(values):
    if not values:
        return None
    arr = np.array(values)
    return {
        "count": len(arr),
        "min": float(arr.min()),
        "max": float(arr.max()),
        "avg": float(arr.mean()),
        "median": float(np.median(arr)),
    }


def suggest_threshold(correct_conf, wrong_conf):
    """
    Rough starting-point threshold: midpoint between the worst (highest)
    correct-match confidence and the best (lowest) wrong-match confidence.
    If the two ranges overlap, falls back to the midpoint of their averages
    and flags that the separation isn't clean.
    NOTE: this is a data-informed STARTING POINT, not a guaranteed-perfect
    cutoff — tune it further after testing with real unknown-face photos.
    """
    if not correct_conf or not wrong_conf:
        return None, "insufficient data (need both correct and wrong predictions)"

    worst_correct = max(correct_conf)
    best_wrong = min(wrong_conf)

    if worst_correct < best_wrong:
        threshold = (worst_correct + best_wrong) / 2
        note = "clean separation — correct and wrong ranges don't overlap"
    else:
        threshold = (np.mean(correct_conf) + np.mean(wrong_conf)) / 2
        note = ("ranges OVERLAP — correct and wrong confidences aren't "
                "cleanly separated, this threshold will misclassify some cases")

    return threshold, note


def print_confidence_analysis(results):
    print("\n" + "=" * 60)
    print("CONFIDENCE-SCORE ANALYSIS (for setting 'unknown face' cutoffs)")
    print("Reminder: LOWER confidence = better/closer match")
    print("=" * 60)

    thresholds = {}
    for r in results:
        name = r["name"]
        c_stats = summarize_confidences(r["correct_confidences"])
        w_stats = summarize_confidences(r["wrong_confidences"])

        print(f"\n{name}")
        if c_stats:
            print(f"  Correct matches ({c_stats['count']}): "
                  f"avg={c_stats['avg']:.1f}  median={c_stats['median']:.1f}  "
                  f"range={c_stats['min']:.1f}-{c_stats['max']:.1f}")
        else:
            print("  Correct matches: none in test set")

        if w_stats:
            print(f"  Wrong matches   ({w_stats['count']}): "
                  f"avg={w_stats['avg']:.1f}  median={w_stats['median']:.1f}  "
                  f"range={w_stats['min']:.1f}-{w_stats['max']:.1f}")
        else:
            print("  Wrong matches: none (all test predictions were correct)")

        threshold, note = suggest_threshold(
            r["correct_confidences"], r["wrong_confidences"])
        thresholds[name] = threshold
        if threshold is not None:
            print(f"  -> Suggested starting threshold: {threshold:.1f}  ({note})")
        else:
            print(f"  -> No threshold suggestion: {note}")

    print("\n" + "=" * 60)
    print("How to use these: in recognize.py, after recognizer.predict(),")
    print("if confidence > threshold_for_that_algorithm: report 'Unknown /")
    print("No match found' instead of the predicted name.")
    print("=" * 60)

    return thresholds


def write_confidence_csv(results, out_path):
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Algorithm", "Match Type", "Count", "Min", "Max", "Avg", "Median"])
        for r in results:
            for label, values in [("Correct", r["correct_confidences"]),
                                   ("Wrong", r["wrong_confidences"])]:
                stats = summarize_confidences(values)
                if stats:
                    writer.writerow([r["name"], label, stats["count"],
                                      f"{stats['min']:.2f}", f"{stats['max']:.2f}",
                                      f"{stats['avg']:.2f}", f"{stats['median']:.2f}"])
                else:
                    writer.writerow([r["name"], label, 0, "-", "-", "-", "-"])

        writer.writerow([])
        writer.writerow(["Algorithm", "Suggested threshold"])
        for r in results:
            threshold, _ = suggest_threshold(r["correct_confidences"], r["wrong_confidences"])
            writer.writerow([r["name"], f"{threshold:.2f}" if threshold is not None else "n/a"])

    print(f"Saved confidence analysis -> {out_path}")


# ---------------------------------------------------------------------------
# Step 4: Output — CSV report + bar chart
# ---------------------------------------------------------------------------
def write_csv_report(results, all_person_names, out_path):
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)

        writer.writerow(["Algorithm", "Correct", "Total", "Accuracy (%)"])
        for r in results:
            writer.writerow([r["name"], r["correct"], r["total"], f"{r['accuracy']:.2f}"])

        writer.writerow([])
        writer.writerow(["Per-person breakdown"])
        header = ["Person"] + [r["name"] for r in results]
        writer.writerow(header)
        for person in all_person_names:
            row = [person]
            for r in results:
                c = r["per_person_correct"].get(person, 0)
                t = r["per_person_total"].get(person, 0)
                row.append(f"{c}/{t}" if t else "no test images")
            writer.writerow(row)

    print(f"\nSaved CSV report -> {out_path}")


def write_chart(results, out_path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n[warning] matplotlib not installed — skipping chart.")
        print("          Install with: python -m pip install matplotlib")
        return

    names = [r["name"] for r in results]
    accuracies = [r["accuracy"] for r in results]

    plt.figure(figsize=(6, 4.5))
    bars = plt.bar(names, accuracies, color=["#4C72B0", "#55A868", "#C44E52"])
    plt.ylim(0, 100)
    plt.ylabel("Accuracy (%)")
    plt.title("Held-out Test Accuracy by Algorithm\n(LFW + biswa dataset)")

    for bar, acc in zip(bars, accuracies):
        plt.text(bar.get_x() + bar.get_width() / 2, acc + 1.5,
                  f"{acc:.1f}%", ha="center", fontsize=10)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved chart -> {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print(f"Loading dataset from: {os.path.abspath(DATA_DIR)}")
    people = load_dataset_by_person(DATA_DIR)
    total_images = sum(len(v) for v in people.values())
    print(f"Loaded {total_images} images across {len(people)} people.\n")

    print("Splitting into train/test per person...")
    train_dict, test_dict = split_train_test(people)

    train_images, train_labels, label_to_name, name_to_label = flatten(train_dict)

    # Test set must use the SAME label mapping as train, so map manually
    test_images, test_labels = [], []
    for person, imgs in test_dict.items():
        label = name_to_label[person]
        for img in imgs:
            test_images.append(img)
            test_labels.append(label)
    test_labels = np.array(test_labels)

    print(f"Train set: {len(train_images)} images")
    print(f"Test set:  {len(test_images)} images\n")

    algorithms = [
        (cv2.face.EigenFaceRecognizer_create, "Eigenfaces"),
        (cv2.face.FisherFaceRecognizer_create, "Fisherfaces"),
        (cv2.face.LBPHFaceRecognizer_create, "LBPH"),
    ]

    results = []
    for factory, name in algorithms:
        print(f"Training + evaluating {name}...")
        r = evaluate_algorithm(
            factory, name,
            train_images, train_labels,
            test_images, test_labels,
            label_to_name,
        )
        results.append(r)
        print(f"  {name}: {r['correct']}/{r['total']} correct "
              f"({r['accuracy']:.2f}%)")

    print("\n" + "=" * 45)
    print("SUMMARY — Held-out Accuracy Comparison")
    print("=" * 45)
    for r in results:
        print(f"  {r['name']:<12} {r['accuracy']:6.2f}%  "
              f"({r['correct']}/{r['total']})")
    print("=" * 45)

    all_person_names = sorted(people.keys())
    write_csv_report(results, all_person_names,
                      os.path.join(RESULTS_DIR, "metrics_report.csv"))
    write_chart(results, os.path.join(RESULTS_DIR, "accuracy_chart.png"))

    print_confidence_analysis(results)
    write_confidence_csv(results,
                          os.path.join(RESULTS_DIR, "confidence_analysis.csv"))


if __name__ == "__main__":
    main()
