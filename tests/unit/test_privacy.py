import numpy as np

from vision.privacy import blur_faces


def _gradient_frame(h: int = 100, w: int = 100) -> np.ndarray:
    """BGR frame whose pixel value increases smoothly by column, so pixelation
    (blocky nearest-neighbor resample) is easy to detect as a deviation."""
    row = np.arange(w, dtype=np.uint8)
    return np.tile(row, (h, 1))[:, :, None].repeat(3, axis=2)


def test_blur_faces_pixelates_head_region_only():
    frame = _gradient_frame()
    original = frame.copy()

    out = blur_faces(frame, [(10, 10, 50, 90)])

    assert out is frame  # mutates and returns the same array
    head_y2 = int(10 + (90 - 10) * 0.22)
    assert not np.array_equal(frame[10:head_y2, 10:50], original[10:head_y2, 10:50])
    # body below the head region is untouched
    assert np.array_equal(frame[head_y2:90, 10:50], original[head_y2:90, 10:50])
    # pixels entirely outside the box are untouched
    assert np.array_equal(frame[:, 60:], original[:, 60:])


def test_tiny_box_is_skipped():
    frame = _gradient_frame()
    original = frame.copy()

    blur_faces(frame, [(10, 10, 12, 12)])  # under the 4px minimum on both axes

    assert np.array_equal(frame, original)


def test_box_clamped_to_frame_bounds():
    frame = _gradient_frame(h=50, w=50)
    original = frame.copy()

    out = blur_faces(frame, [(-5, -5, 60, 40)])  # spills past every edge

    assert out is frame
    assert frame.shape == original.shape
    assert not np.array_equal(frame, original)


def test_multiple_boxes_each_processed():
    frame = _gradient_frame()
    original = frame.copy()

    blur_faces(frame, [(0, 10, 40, 90), (55, 10, 95, 90)])

    head_y2 = int(10 + (90 - 10) * 0.22)
    assert not np.array_equal(frame[10:head_y2, 0:40], original[10:head_y2, 0:40])
    assert not np.array_equal(frame[10:head_y2, 55:95], original[10:head_y2, 55:95])


def test_no_boxes_returns_frame_unchanged():
    frame = _gradient_frame()
    original = frame.copy()

    out = blur_faces(frame, [])

    assert out is frame
    assert np.array_equal(frame, original)
