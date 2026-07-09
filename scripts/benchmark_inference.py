"""Measure detector latency/FPS on this machine (CPU or GPU).

Usage (run as a module - `python scripts/benchmark_inference.py` puts
scripts/ itself on sys.path instead of the repo root, so `vision` fails
to import):
    python -m scripts.benchmark_inference --model yolo11n.pt --device cpu
"""

import argparse
import time

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--frames", type=int, default=50)
    parser.add_argument("--width", type=int, default=960)
    args = parser.parse_args()

    from vision.detector import YoloDetector

    det = YoloDetector(args.model, args.device)
    frame = (np.random.rand(int(args.width * 9 / 16), args.width, 3) * 255).astype(np.uint8)
    det.detect(frame)  # warmup
    t0 = time.perf_counter()
    for _ in range(args.frames):
        det.detect(frame)
    dt = time.perf_counter() - t0
    print(
        f"{args.frames} frames in {dt:.2f}s -> {args.frames / dt:.2f} FPS "
        f"({dt / args.frames * 1000:.1f} ms/frame) on {args.device}"
    )


if __name__ == "__main__":
    main()
