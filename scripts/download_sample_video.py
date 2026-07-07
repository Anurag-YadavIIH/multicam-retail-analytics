"""Fetch a small, license-friendly pedestrian clip for the demo camera.

Tries a set of public sample-video mirrors; if all fail (offline), synthesizes
a moving-shapes clip with OpenCV so the pipeline still runs end-to-end.
"""

import urllib.request
from pathlib import Path

OUT = Path("datasets/samples/retail_demo.mp4")
SOURCES = [
    # MOT17-09 style pedestrian street scenes / generic people-walking samples
    "https://github.com/intel-iot-devkit/sample-videos/raw/master/people-detection.mp4",
    "https://github.com/intel-iot-devkit/sample-videos/raw/master/store-aisle-detection.mp4",
    "https://github.com/intel-iot-devkit/sample-videos/raw/master/one-by-one-person-detection.mp4",
]


def synthesize(path: Path) -> None:
    import cv2
    import numpy as np

    print("all downloads failed - synthesizing a test clip instead")
    w, h, fps, seconds = 960, 540, 10, 30
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    rng = np.random.default_rng(7)
    actors = [
        (rng.integers(0, w), rng.integers(0, h), rng.integers(-4, 5), rng.integers(-4, 5))
        for _ in range(6)
    ]
    actors = [list(a) for a in actors]
    for _ in range(fps * seconds):
        frame = np.full((h, w, 3), 30, np.uint8)
        for a in actors:
            a[0] = (a[0] + a[2]) % w
            a[1] = (a[1] + a[3]) % h
            cv2.rectangle(
                frame,
                (int(a[0]), int(a[1])),
                (int(a[0]) + 40, int(a[1]) + 100),
                (200, 200, 200),
                -1,
            )
        writer.write(frame)
    writer.release()


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        print(f"already present: {OUT}")
        return
    for url in SOURCES:
        try:
            print(f"downloading {url} ...")
            urllib.request.urlretrieve(url, OUT)  # noqa: S310
            print(f"saved -> {OUT}")
            return
        except Exception as exc:
            print(f"  failed: {exc}")
    synthesize(OUT)


if __name__ == "__main__":
    main()
