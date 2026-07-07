from datetime import datetime

from pydantic import BaseModel

from backend.app.models.event import AlertSeverity, AlertType
from backend.app.schemas.common import ORMModel


class SnapshotOut(ORMModel):
    ts: datetime
    camera_id: int
    people_count: int
    unique_visitors: int
    avg_dwell_s: float
    queue_length: int
    avg_wait_s: float
    zone_occupancy: dict
    fps: float


class OverviewOut(BaseModel):
    total_visitors_today: int
    current_occupancy: int
    avg_dwell_s: float
    max_queue_length: int
    active_cameras: int
    open_alerts: int


class TrafficPoint(BaseModel):
    ts: datetime
    count: int


class AlertOut(ORMModel):
    id: int
    camera_id: int | None
    ts: datetime
    type: AlertType
    severity: AlertSeverity
    message: str
    acknowledged: bool


class HeatmapRequest(BaseModel):
    camera_id: int
    hours: int = 24
    kind: str = "movement"  # movement | footfall | shelf | queue


class IngestDetection(BaseModel):
    """Payload posted by the vision worker per processed frame."""

    camera_id: int
    ts: datetime
    fps: float
    detections: list[dict]  # {class_name, confidence, bbox: [x1,y1,x2,y2], track_id}
    events: list[dict] = []
    snapshot: dict | None = None
