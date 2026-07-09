"""vision/reid.py tests. onnxruntime isn't installed in this test
environment (deliberately - see docs/REID.md: it's only ever needed by the
vision-worker image, and lint-test/CI must not require it), so the
successful-extraction path uses a fake module injected into sys.modules.
No real model inference anywhere here."""

import sys
import types
from unittest.mock import MagicMock

import numpy as np

from vision.reid import ReidExtractor, bbox_area, crop_bbox, preprocess


class FakeSession:
    def __init__(self, output: np.ndarray, output_dim: int | None = None):
        self._output = output
        self._output_dim = output.shape[-1] if output_dim is None else output_dim

    def get_inputs(self):
        return [types.SimpleNamespace(name="input")]

    def get_outputs(self):
        return [types.SimpleNamespace(shape=["batch", self._output_dim])]

    def run(self, output_names, feed):
        return [self._output]


class BrokenSession(FakeSession):
    def run(self, output_names, feed):
        raise RuntimeError("boom")


def _install_fake_onnxruntime(monkeypatch, session) -> None:
    fake_module = MagicMock()
    fake_module.InferenceSession = MagicMock(return_value=session)
    monkeypatch.setitem(sys.modules, "onnxruntime", fake_module)


def test_bbox_area():
    assert bbox_area((0, 0, 10, 20)) == 200


def test_bbox_area_degenerate_is_zero():
    assert bbox_area((10, 10, 5, 5)) == 0


def test_crop_bbox_clamps_to_frame_bounds():
    frame = np.zeros((50, 50, 3), dtype=np.uint8)
    crop = crop_bbox(frame, (-5, -5, 60, 40))
    assert crop.shape[:2] == (40, 50)


def test_preprocess_shape_and_dtype():
    crop = np.random.randint(0, 255, (80, 40, 3), dtype=np.uint8)
    batch = preprocess(crop)
    assert batch.shape == (1, 3, 256, 128)
    assert batch.dtype == np.float32


def test_extractor_disabled_when_model_unavailable():
    # onnxruntime genuinely isn't installed here, and the path doesn't exist
    # either way - both cases must be caught and disable extraction, not raise.
    extractor = ReidExtractor("does/not/exist.onnx")

    assert extractor.enabled is False
    assert extractor.extract(np.zeros((10, 10, 3), dtype=np.uint8)) is None


def test_extractor_extracts_and_l2_normalizes(monkeypatch):
    raw = np.zeros((1, 512), dtype=np.float32)
    raw[0, 0], raw[0, 1] = 3.0, 4.0  # norm = 5
    _install_fake_onnxruntime(monkeypatch, FakeSession(raw))

    extractor = ReidExtractor("fake/path.onnx")
    crop = np.random.randint(0, 255, (100, 60, 3), dtype=np.uint8)
    embedding = extractor.extract(crop)

    assert extractor.enabled is True
    assert embedding is not None
    assert len(embedding) == 512
    assert abs(embedding[0] - 0.6) < 1e-6
    assert abs(embedding[1] - 0.8) < 1e-6
    assert abs(sum(v * v for v in embedding) - 1.0) < 1e-6


def test_extractor_fails_soft_on_inference_error(monkeypatch):
    _install_fake_onnxruntime(monkeypatch, BrokenSession(np.zeros((1, 512), dtype=np.float32)))

    extractor = ReidExtractor("fake/path.onnx")

    assert extractor.enabled is True  # construction succeeded
    assert extractor.extract(np.zeros((10, 10, 3), dtype=np.uint8)) is None


def test_output_dim_none_when_disabled():
    extractor = ReidExtractor("does/not/exist.onnx")

    assert extractor.output_dim is None


def test_output_dim_matches_session_shape(monkeypatch):
    _install_fake_onnxruntime(monkeypatch, FakeSession(np.zeros((1, 512), dtype=np.float32)))
    extractor = ReidExtractor("fake/path.onnx")

    assert extractor.output_dim == 512


def test_output_dim_flags_mismatch(monkeypatch):
    _install_fake_onnxruntime(
        monkeypatch, FakeSession(np.zeros((1, 256), dtype=np.float32), output_dim=256)
    )
    extractor = ReidExtractor("fake/path.onnx")

    assert extractor.output_dim == 256


def test_extract_returns_none_for_empty_crop(monkeypatch):
    _install_fake_onnxruntime(monkeypatch, FakeSession(np.zeros((1, 512), dtype=np.float32)))
    extractor = ReidExtractor("fake/path.onnx")

    empty_crop = np.zeros((0, 0, 3), dtype=np.uint8)

    assert extractor.extract(empty_crop) is None
