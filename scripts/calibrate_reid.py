"""Calibrate REID_MATCH_THRESHOLD against real embeddings from the demo video.

Two-phase, driven by whether models/reid/calibration_crops/labels.json exists
and has been filled in yet:

1. Extract (first run): runs the real detection/tracking/extraction pipeline
   (YoloDetector -> ByteTracker -> vision.reid, the same best-crop heuristic
   and ReidExtractor camera_worker.py uses) over the video, saving one crop
   image per track to models/reid/calibration_crops/track_<id>.jpg plus the
   raw embeddings, so you have an easy way to *see* each track for manual
   labeling. A labels.json template is written alongside (every track
   "UNLABELED"). Faces are NOT blurred here on purpose - unlike everywhere
   else in this project, these crops never leave your machine and you need
   to see faces to label confidently; don't reuse this script's output for
   anything beyond local, one-time threshold calibration.

2. Calibrate (subsequent runs, after you edit labels.json): give tracks that
   are the same person the same short label (e.g. "person_a"); leave a track
   as "UNLABELED" (or remove its line) to exclude it. Re-running this script
   then reports the cosine similarity distribution for same-person pairs vs.
   different-person pairs and recommends a threshold.

Usage (run as a module, not `python scripts/calibrate_reid.py` - the latter
puts scripts/ itself on sys.path instead of the repo root, so `tracking`/
`vision` fail to import):
    python -m scripts.calibrate_reid
    python -m scripts.calibrate_reid --video path/to/other.mp4
"""

import argparse
import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import cv2
import numpy as np

from tracking.tracker import ByteTracker
from vision.detector import YoloDetector
from vision.reid import MIN_CROP_CONFIDENCE, ReidExtractor, bbox_area, crop_bbox
from vision.video_source import VideoSource

OUT_DIR = Path("models/reid/calibration_crops")
EMBEDDINGS_FILE = OUT_DIR / "embeddings.json"
LABELS_FILE = OUT_DIR / "labels.json"
UNLABELED = "UNLABELED"
EXPECTED_EMBEDDING_DIM = 512  # vision/reid.py and the /ingest/reid schema both assume this
PINNED_ORT_VERSION = "1.20.1"  # vision/requirements.txt - the worker's actual runtime


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def extract(video_path: str, model_path: str, max_frames: int) -> None:
    import onnxruntime as ort  # lazy - not installed in the lint-test/CI env, see docs/REID.md

    if ort.__version__ != PINNED_ORT_VERSION:
        print(
            f"WARNING: onnxruntime {ort.__version__} is installed, but the vision "
            f"worker runs onnxruntime=={PINNED_ORT_VERSION} (vision/requirements.txt). "
            "Install the pinned version so calibration reflects production behavior."
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    extractor = ReidExtractor(model_path)
    if not extractor.enabled:
        raise SystemExit(f"No Re-ID model at {model_path} - export it first (see docs/REID.md).")
    if extractor.output_dim != EXPECTED_EMBEDDING_DIM:
        raise SystemExit(
            f"Model at {model_path} outputs {extractor.output_dim}-dim embeddings, but "
            f"vision/reid.py and the /ingest/reid schema assume {EXPECTED_EMBEDDING_DIM}. "
            "Re-export the correct model, or update both before calibrating - a silent "
            "shape mismatch would otherwise produce garbage embeddings, not an error."
        )

    detector = YoloDetector(device="cpu")
    tracker = ByteTracker(fps=5)
    source = VideoSource(video_path, source_type="file", loop_file=False)

    best_area: dict[int, float] = {}
    best_crop: dict[int, np.ndarray] = {}
    frames_read = 0
    while frames_read < max_frames:
        frame = source.read()
        if frame is None:
            break
        frames_read += 1
        tracked = tracker.update(detector.detect(frame))
        for t in tracked:
            if t.class_name != "person" or t.confidence < MIN_CROP_CONFIDENCE:
                continue
            area = bbox_area(t.bbox)
            if area <= best_area.get(t.track_id, 0.0):
                continue
            crop = crop_bbox(frame, t.bbox)
            if crop.size == 0:
                continue
            best_area[t.track_id] = area
            best_crop[t.track_id] = crop.copy()
    source.release()

    embeddings: dict[str, list[float]] = {}
    for track_id, crop in best_crop.items():
        embedding = extractor.extract(crop)
        if embedding is None:
            continue
        embeddings[str(track_id)] = embedding
        cv2.imwrite(str(OUT_DIR / f"track_{track_id}.jpg"), crop)

    EMBEDDINGS_FILE.write_text(json.dumps(embeddings))
    if not LABELS_FILE.exists():
        LABELS_FILE.write_text(json.dumps(dict.fromkeys(embeddings, UNLABELED), indent=2))

    print(f"Processed {frames_read} frames, {len(embeddings)} tracks with a usable crop.")
    print(f"Crops:  {OUT_DIR}/track_<id>.jpg")
    print(f"Labels: {LABELS_FILE}")
    print(
        "\nOpen the crops and edit labels.json: give tracks that are the same "
        f'person the same label (e.g. "person_a"); leave others as {UNLABELED} '
        "or delete their entry. Then re-run this script to calibrate."
    )


def compute_report(embeddings: dict[str, list[float]], labels: dict[str, str]) -> dict:
    """Pure function: same/different-person cosine similarity distributions
    plus a recommended threshold, from already-extracted embeddings and a
    filled-in labels mapping. No model/video/filesystem access - the part of
    this script that's actually worth unit-testing in isolation."""
    by_label: dict[str, list[str]] = defaultdict(list)
    for track_id, label in labels.items():
        if label == UNLABELED or track_id not in embeddings:
            continue
        by_label[label].append(track_id)

    same_person = [
        cosine_similarity(embeddings[a], embeddings[b])
        for ids in by_label.values()
        for a, b in combinations(ids, 2)
    ]
    labeled = [tid for ids in by_label.values() for tid in ids]
    different_person = [
        cosine_similarity(embeddings[a], embeddings[b])
        for a, b in combinations(labeled, 2)
        if labels[a] != labels[b]
    ]

    report = {
        "same_person": same_person,
        "different_person": different_person,
        "recommended_threshold": None,
        "clean_separation": False,
    }
    if same_person and different_person:
        lowest_same, highest_diff = min(same_person), max(different_person)
        report["clean_separation"] = lowest_same > highest_diff
        if report["clean_separation"]:
            report["recommended_threshold"] = round((lowest_same + highest_diff) / 2, 2)
    return report


def calibrate() -> None:
    embeddings = json.loads(EMBEDDINGS_FILE.read_text())
    labels = json.loads(LABELS_FILE.read_text())
    report = compute_report(embeddings, labels)

    if not report["same_person"] or not report["different_person"]:
        raise SystemExit(
            "Need at least one same-person pair (two tracks with the same label) "
            f"and one different-person pair (two different labels) in {LABELS_FILE} "
            "to calibrate."
        )

    def stats(name: str, values: list[float]) -> None:
        print(
            f"{name}: n={len(values)} min={min(values):.3f} max={max(values):.3f} "
            f"mean={sum(values) / len(values):.3f}"
        )

    print("--- Cosine similarity distributions ---")
    stats("same-person     ", report["same_person"])
    stats("different-person", report["different_person"])

    if report["clean_separation"]:
        print(
            f"\nClean separation. Recommended REID_MATCH_THRESHOLD = "
            f"{report['recommended_threshold']} (midpoint between the closest "
            "different-person pair and the farthest same-person pair)."
        )
    else:
        print(
            "\nNo clean separation between the labeled pairs - there's no single "
            "threshold that gets every pair right. Pick a value that trades off "
            "false matches vs. missed matches for your use case, or label more "
            "pairs for a more reliable estimate."
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default="datasets/samples/retail_demo.mp4")
    parser.add_argument("--model", default="models/reid/osnet_x0_25.onnx")
    parser.add_argument("--max-frames", type=int, default=600)
    args = parser.parse_args()

    if EMBEDDINGS_FILE.exists() and LABELS_FILE.exists():
        labels = json.loads(LABELS_FILE.read_text())
        if any(v != UNLABELED for v in labels.values()):
            calibrate()
            return
        print(f"{LABELS_FILE} exists but nothing is labeled yet - edit it, then re-run.")
        return

    extract(args.video, args.model, args.max_frames)


if __name__ == "__main__":
    main()
