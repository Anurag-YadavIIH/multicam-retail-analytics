"""Fetch small, license-friendly demo clips for the seeded cameras.

Both clips are CC-BY-4.0 (attribution required - see NOTICE) from
intel-iot-devkit/sample-videos, already vetted for this project:
https://github.com/intel-iot-devkit/sample-videos

Tries a set of public sample-video mirrors per clip; if all fail (offline),
synthesizes a moving-shapes clip with OpenCV so the pipeline still runs
end-to-end.

retail_demo.mp4 feeds the entrance camera (sparse: max ~3 people at once -
see docs/DEMO.md). queue_demo.mp4 feeds the second, queue-alert-focused
camera: a real, steady 4 people for its full length, which is what actually
crosses the queue_length_threshold - a genuine, reproducible trigger rather
than a lucky frame on sparser footage.
"""

import urllib.request
from pathlib import Path

CLIPS: list[tuple[Path, list[str]]] = [
    (
        Path("datasets/samples/retail_demo.mp4"),
        [
            "https://github.com/intel-iot-devkit/sample-videos/raw/master/people-detection.mp4",
            "https://github.com/intel-iot-devkit/sample-videos/raw/master/store-aisle-detection.mp4",
            "https://github.com/intel-iot-devkit/sample-videos/raw/master/one-by-one-person-detection.mp4",
        ],
    ),
    (
        Path("datasets/samples/queue_demo.mp4"),
        ["https://github.com/intel-iot-devkit/sample-videos/raw/master/classroom.mp4"],
    ),
]


def synthesize(path: Path, actor_count: int, seed: int) -> None:
    import cv2
    import numpy as np

    print(f"all downloads failed for {path} - synthesizing a test clip instead")
    w, h, fps, seconds = 960, 540, 10, 30
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    rng = np.random.default_rng(seed)
    actors = [
        (rng.integers(0, w), rng.integers(0, h), rng.integers(-4, 5), rng.integers(-4, 5))
        for _ in range(actor_count)
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


def fetch(out: Path, sources: list[str], actor_count: int, seed: int) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        print(f"already present: {out}")
        return
    for url in sources:
        try:
            print(f"downloading {url} ...")
            urllib.request.urlretrieve(url, out)  # noqa: S310
            print(f"saved -> {out}")
            return
        except Exception as exc:
            print(f"  failed: {exc}")
    synthesize(out, actor_count, seed)


def main() -> None:
    for i, (out, sources) in enumerate(CLIPS):
        fetch(out, sources, actor_count=6 - i * 2, seed=7 + i)


if __name__ == "__main__":
    main()
