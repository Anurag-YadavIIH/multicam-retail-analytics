"""Prometheus metrics exposed at /metrics."""

from prometheus_client import Counter, Gauge, Histogram

INGESTED_FRAMES = Counter(
    "rva_ingested_frames_total", "Frames ingested from vision workers", ["camera_id"]
)
DETECTIONS_TOTAL = Counter(
    "rva_detections_total", "Detections ingested", ["camera_id", "class_name"]
)
CAMERA_FPS = Gauge("rva_camera_fps", "Measured pipeline FPS per camera", ["camera_id"])
QUEUE_LENGTH = Gauge("rva_queue_length", "Current queue length per camera", ["camera_id"])
PEOPLE_COUNT = Gauge("rva_people_count", "Current people count per camera", ["camera_id"])
API_LATENCY = Histogram(
    "rva_api_latency_seconds",
    "API latency",
    ["path", "method"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
)
ALERTS_TOTAL = Counter("rva_alerts_total", "Alerts raised", ["type", "severity"])
