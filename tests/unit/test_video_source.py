"""VideoSource tests use a fake cv2.VideoCapture fed synthetic numpy frames -
no real camera/file/RTSP I/O. Real cv2 constants/resize are used as-is."""

import numpy as np
import pytest

import vision.video_source as vs_module
from vision.video_source import VideoSource


class FakeCapture:
    """`results` is consumed by read() as-is; a POS_FRAMES seek to 0 (the file-loop
    path) refills from `loop_frames`, modeling a rewind to the real start of the file
    rather than a replay of whatever sentinel (e.g. EOF) triggered the seek."""

    def __init__(
        self,
        results: list[tuple[bool, np.ndarray | None]],
        loop_frames: list[tuple[bool, np.ndarray | None]] | None = None,
        opened: bool = True,
    ):
        self._results = list(results)
        self._loop_frames = list(loop_frames) if loop_frames is not None else list(results)
        self._opened = opened
        self.released = False
        self.set_calls: list[tuple[int, float]] = []

    def isOpened(self) -> bool:  # noqa: N802 - mirrors cv2.VideoCapture's own naming
        return self._opened and not self.released

    def read(self):
        if not self._results:
            return False, None
        return self._results.pop(0)

    def set(self, prop, value):
        self.set_calls.append((prop, value))
        if prop == vs_module.cv2.CAP_PROP_POS_FRAMES:
            self._results = list(self._loop_frames)

    def release(self):
        self.released = True


def _frame(w: int = 800, h: int = 600) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def _patch_capture(monkeypatch, results, loop_frames=None, opened: bool = True) -> list:
    """Patches cv2.VideoCapture; returns the list of args it was called with."""
    captured_args: list = []

    def fake_video_capture(src):
        captured_args.append(src)
        return FakeCapture(results, loop_frames=loop_frames, opened=opened)

    monkeypatch.setattr(vs_module.cv2, "VideoCapture", fake_video_capture)
    return captured_args


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    monkeypatch.setattr(vs_module.time, "sleep", lambda _seconds: None)


def test_usb_source_opens_with_int_device_index(monkeypatch):
    captured = _patch_capture(monkeypatch, [(True, _frame())])
    source = VideoSource("0", source_type="usb")

    frame = source.read()

    assert frame is not None
    assert captured == [0]
    assert isinstance(captured[0], int)


def test_rtsp_source_sets_small_buffer(monkeypatch):
    captured = _patch_capture(monkeypatch, [(True, _frame())])
    source = VideoSource("rtsp://cam", source_type="rtsp")

    source.read()

    assert captured == ["rtsp://cam"]
    assert source.cap.set_calls == [(vs_module.cv2.CAP_PROP_BUFFERSIZE, 1)]


def test_usb_source_does_not_set_buffer_size(monkeypatch):
    _patch_capture(monkeypatch, [(True, _frame())])
    source = VideoSource("0", source_type="usb")

    source.read()

    assert source.cap.set_calls == []


def test_wide_frame_is_resized_to_target_width(monkeypatch):
    _patch_capture(monkeypatch, [(True, _frame(w=1920, h=1080))])
    source = VideoSource("0", source_type="usb", target_width=960)

    frame = source.read()

    assert frame.shape[1] == 960
    assert frame.shape[0] == 540  # 1080 scaled by the same factor as width


def test_narrow_frame_is_not_resized(monkeypatch):
    _patch_capture(monkeypatch, [(True, _frame(w=640, h=480))])
    source = VideoSource("0", source_type="usb", target_width=960)

    frame = source.read()

    assert frame.shape[1] == 640
    assert frame.shape[0] == 480


def test_file_source_loops_at_eof(monkeypatch):
    frame = _frame()
    _patch_capture(monkeypatch, [(False, None)], loop_frames=[(True, frame)])
    source = VideoSource("clip.mp4", source_type="file", loop_file=True)

    out = source.read()

    assert out is not None
    assert source.cap.set_calls == [(vs_module.cv2.CAP_PROP_POS_FRAMES, 0)]


def test_file_source_without_loop_gives_up_at_eof(monkeypatch):
    _patch_capture(monkeypatch, [(False, None)])
    source = VideoSource("clip.mp4", source_type="file", loop_file=False)

    out = source.read()

    assert out is None
    assert source.cap is None  # released after the failed read


def test_rtsp_stream_loss_releases_and_backs_off(monkeypatch):
    _patch_capture(monkeypatch, [(False, None)])
    source = VideoSource("rtsp://cam", source_type="rtsp")

    out = source.read()

    assert out is None
    assert source.cap is None
    assert source._backoff == 2.0  # doubled from the initial 1.0


def test_open_failure_backs_off_without_reading(monkeypatch):
    _patch_capture(monkeypatch, [(True, _frame())], opened=False)
    source = VideoSource("rtsp://cam", source_type="rtsp")

    out = source.read()

    assert out is None
    assert source._backoff == 2.0


def test_backoff_caps_at_thirty_seconds(monkeypatch):
    _patch_capture(monkeypatch, [], opened=False)
    source = VideoSource("rtsp://cam", source_type="rtsp")

    for _ in range(10):
        source.read()

    assert source._backoff == 30.0


def test_successful_reopen_resets_backoff(monkeypatch):
    _patch_capture(monkeypatch, [], opened=False)
    source = VideoSource("rtsp://cam", source_type="rtsp")
    source.read()
    assert source._backoff == 2.0

    _patch_capture(monkeypatch, [(True, _frame())], opened=True)
    frame = source.read()

    assert frame is not None
    assert source._backoff == 1.0


def test_release_is_idempotent(monkeypatch):
    _patch_capture(monkeypatch, [(True, _frame())])
    source = VideoSource("0", source_type="usb")
    source.read()

    source.release()
    assert source.cap is None

    source.release()  # no-op, must not raise
    assert source.cap is None
