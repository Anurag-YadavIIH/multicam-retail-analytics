"""Vision worker: one thread per active camera.

Pipeline per camera:
  VideoSource -> YoloDetector -> ByteTracker -> AnalyticsEngine
             -> POST /api/v1/ingest/frame (+ /ingest/track on track close)
             -> heartbeat to backend, optional Kafka publish
             -> periodic heatmap PNG report

Designed for CPU on 8 GB machines: frames are throttled to INFERENCE_FPS and
resized to FRAME_WIDTH before inference.
"""

import contextlib
import logging
import os
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import redis

from analytics.engine import AnalyticsEngine
from analytics.zones import ZoneDef
from streaming.kafka_client import DetectionProducer
from tracking.tracker import ByteTracker
from vision.detector import YoloDetector
from vision.preview import annotate, encode_jpeg
from vision.privacy import blur_faces
from vision.video_source import VideoSource

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("camera-worker")

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
WORKER_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me-please-32chars!")
DEVICE = os.getenv("DEVICE", "cpu")
MODEL = os.getenv("YOLO_MODEL", "yolo11n.pt")
CONF = float(os.getenv("CONF_THRESHOLD", "0.35"))
IOU = float(os.getenv("IOU_THRESHOLD", "0.5"))
INFER_FPS = int(os.getenv("INFERENCE_FPS", "5"))
FRAME_WIDTH = int(os.getenv("FRAME_WIDTH", "960"))
FACE_BLUR = os.getenv("ENABLE_FACE_BLUR", "true").lower() == "true"
HEATMAP_EVERY_S = 600
KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "false").lower() == "true"
KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_DETECTIONS_TOPIC", "detections")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
PREVIEW_FPS = float(os.getenv("PREVIEW_FPS", "3"))
PREVIEW_TTL_S = 5
PREVIEW_JPEG_QUALITY = 70


def fetch_cameras(client: httpx.Client) -> list[dict]:
    """Fetch active cameras (with zones) via an internal login."""
    email = os.getenv("FIRST_ADMIN_EMAIL", "admin@retail.local")
    password = os.getenv("FIRST_ADMIN_PASSWORD", "admin12345")
    token = client.post(
        f"{BACKEND_URL}/api/v1/auth/login",
        data={"username": email, "password": password},
    ).json()["access_token"]
    resp = client.get(
        f"{BACKEND_URL}/api/v1/cameras",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return [c for c in resp.json() if c["is_active"]]


class CameraPipeline(threading.Thread):
    def __init__(
        self,
        camera: dict,
        detector: YoloDetector,
        producer: DetectionProducer,
        redis_client: redis.Redis,
    ) -> None:
        super().__init__(daemon=True, name=f"cam-{camera['id']}")
        self.camera = camera
        self.detector = detector
        self.producer = producer
        self.redis = redis_client
        self.source = VideoSource(camera["source"], camera["type"], FRAME_WIDTH)
        self.tracker = ByteTracker(fps=INFER_FPS)
        self.engine: AnalyticsEngine | None = None
        self.client = httpx.Client(timeout=10, headers={"X-Worker-Key": WORKER_KEY})
        self._fps_window: list[float] = []
        self._last_heartbeat = 0.0
        self._last_heatmap = time.time()
        self._last_preview_push = 0.0

    def run(self) -> None:
        cam_id = self.camera["id"]
        logger.info("pipeline started for camera %s (%s)", cam_id, self.camera["name"])
        interval = 1.0 / INFER_FPS
        while True:
            t0 = time.perf_counter()
            frame = self.source.read()
            if frame is None:
                continue
            if self.engine is None:
                h, w = frame.shape[:2]
                zones = [
                    ZoneDef(
                        z["id"], z["name"], z["type"], tuple((p[0], p[1]) for p in z["polygon"])
                    )
                    for z in self.camera.get("zones", [])
                ]
                self.engine = AnalyticsEngine(cam_id, zones, (w, h))

            detections = self.detector.detect(frame)
            tracked = self.tracker.update(detections)
            if FACE_BLUR:
                blur_faces(frame, [t.bbox for t in tracked if t.class_name == "person"])
            self._maybe_push_preview(cam_id, frame, tracked)
            output = self.engine.process(tracked)

            elapsed = time.perf_counter() - t0
            self._fps_window = (self._fps_window + [1.0 / max(elapsed, 1e-6)])[-30:]
            fps = sum(self._fps_window) / len(self._fps_window)
            self._ship(cam_id, tracked, output, fps, frame.shape)
            self._maybe_heartbeat(cam_id, fps)
            self._maybe_heatmap(cam_id, frame)

            sleep_for = interval - (time.perf_counter() - t0)
            if sleep_for > 0:
                time.sleep(sleep_for)

    # ---------------------------------------------------------------- shipping
    def _ship(self, cam_id: int, tracked, output, fps: float, shape) -> None:
        h, w = shape[:2]
        ts = datetime.now(UTC).isoformat()
        dets = [
            {
                "class_name": t.class_name,
                "confidence": round(t.confidence, 3),
                "bbox": [
                    round(t.bbox[0] / w, 4),
                    round(t.bbox[1] / h, 4),
                    round(t.bbox[2] / w, 4),
                    round(t.bbox[3] / h, 4),
                ],
                "track_id": t.track_id,
            }
            for t in tracked
        ]
        payload = {
            "camera_id": cam_id,
            "ts": ts,
            "fps": round(fps, 2),
            "detections": dets,
            "events": output.events,
            "snapshot": output.snapshot,
        }
        try:
            self.client.post(f"{BACKEND_URL}/api/v1/ingest/frame", json=payload)
        except httpx.HTTPError:
            logger.warning("ingest POST failed (backend down?)")
        self.producer.send(KAFKA_TOPIC, payload)
        for ev in output.events:
            closed = ev.get("closed_track")
            if closed:
                try:
                    self.client.post(f"{BACKEND_URL}/api/v1/ingest/track", json=closed)
                except httpx.HTTPError:
                    logger.warning("track POST failed")

    def _maybe_push_preview(self, cam_id: int, frame, tracked) -> None:
        """Cache the latest annotated JPEG in Redis for the MJPEG/snapshot endpoints.
        Rate-capped independent of INFER_FPS - it's a preview, not the analytics path."""
        now = time.time()
        if now - self._last_preview_push < 1.0 / PREVIEW_FPS:
            return
        self._last_preview_push = now
        try:
            annotated = annotate(frame, tracked)
            jpeg = encode_jpeg(annotated, PREVIEW_JPEG_QUALITY)
            self.redis.set(f"frame:latest:{cam_id}", jpeg, ex=PREVIEW_TTL_S)
        except Exception:
            logger.exception("preview frame push failed")

    def _maybe_heartbeat(self, cam_id: int, fps: float) -> None:
        now = time.time()
        if now - self._last_heartbeat >= 15:
            self._last_heartbeat = now
            with contextlib.suppress(httpx.HTTPError):
                self.client.post(
                    f"{BACKEND_URL}/api/v1/cameras/{cam_id}/heartbeat",
                    params={"fps": round(fps, 2)},
                )

    def _maybe_heatmap(self, cam_id: int, frame) -> None:
        if time.time() - self._last_heatmap >= HEATMAP_EVERY_S and self.engine:
            self._last_heatmap = time.time()
            out = Path(f"models/heatmaps/camera_{cam_id}_movement.png")
            try:
                self.engine.heat_movement.render_png(out, background=frame)
                logger.info("heatmap written: %s", out)
            except Exception:
                logger.exception("heatmap render failed")


def main() -> None:
    logger.info("loading model %s on %s", MODEL, DEVICE)
    detector = YoloDetector(MODEL, DEVICE, CONF, IOU)
    producer = DetectionProducer(KAFKA_SERVERS, KAFKA_ENABLED)
    redis_client = redis.Redis.from_url(REDIS_URL)
    client = httpx.Client(timeout=10)
    cameras: list[dict] = []
    for attempt in range(30):
        try:
            cameras = fetch_cameras(client)
            break
        except Exception:
            logger.info("waiting for backend... (%s)", attempt)
            time.sleep(5)
    if not cameras:
        logger.error("no active cameras found; add one via the API/dashboard")
        return
    threads = [CameraPipeline(cam, detector, producer, redis_client) for cam in cameras]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
