"""Resilient video capture: RTSP / USB / file with automatic reconnect.

- RTSP: reconnects with exponential backoff on stream drop.
- USB:  source is a device index ("0", "1", ...).
- FILE: loops forever (demo mode) so the pipeline behaves like a live camera.
"""

import logging
import time

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class VideoSource:
    def __init__(
        self,
        source: str,
        source_type: str = "rtsp",
        target_width: int = 960,
        loop_file: bool = True,
    ) -> None:
        self.source = source
        self.source_type = source_type
        self.target_width = target_width
        self.loop_file = loop_file
        self.cap: cv2.VideoCapture | None = None
        self._backoff = 1.0

    def _open(self) -> bool:
        src: str | int = int(self.source) if self.source_type == "usb" else self.source
        self.cap = cv2.VideoCapture(src)
        if self.source_type == "rtsp" and self.cap is not None:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        ok = self.cap is not None and self.cap.isOpened()
        if ok:
            self._backoff = 1.0
            logger.info("opened source %s", self.source)
        return ok

    def read(self) -> np.ndarray | None:
        """Returns a resized BGR frame, or None if source is (re)connecting."""
        if (self.cap is None or not self.cap.isOpened()) and not self._open():
            self._sleep_backoff()
            return None
        assert self.cap is not None
        ok, frame = self.cap.read()
        if not ok or frame is None:
            if self.source_type == "file" and self.loop_file:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = self.cap.read()
            if not ok or frame is None:
                logger.warning("stream lost (%s), reconnecting", self.source)
                self.release()
                self._sleep_backoff()
                return None
        h, w = frame.shape[:2]
        if w > self.target_width:
            scale = self.target_width / w
            frame = cv2.resize(frame, (self.target_width, int(h * scale)))
        return frame

    def _sleep_backoff(self) -> None:
        time.sleep(self._backoff)
        self._backoff = min(self._backoff * 2, 30.0)

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
