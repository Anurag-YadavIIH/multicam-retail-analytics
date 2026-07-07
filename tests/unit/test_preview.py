import cv2
import numpy as np

from tracking.tracker import TrackedObject
from vision.preview import annotate, encode_jpeg


def test_annotate_draws_on_a_copy_without_mutating_input():
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    original = frame.copy()
    tracked = [
        TrackedObject(track_id=7, class_name="person", confidence=0.9, bbox=(10, 10, 50, 90))
    ]

    out = annotate(frame, tracked)

    assert np.array_equal(frame, original)  # caller's array is untouched
    assert not np.array_equal(out, frame)  # boxes/labels were drawn on the copy
    assert out.shape == frame.shape


def test_annotate_with_no_tracked_objects_is_a_plain_copy():
    frame = np.full((50, 50, 3), 42, dtype=np.uint8)

    out = annotate(frame, [])

    assert out is not frame
    assert np.array_equal(out, frame)


def test_encode_jpeg_roundtrips_through_cv2():
    frame = np.full((40, 60, 3), 127, dtype=np.uint8)

    data = encode_jpeg(frame, quality=80)

    assert isinstance(data, bytes)
    assert len(data) > 0
    decoded = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape == frame.shape
