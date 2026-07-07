from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from backend.app.models.camera import CameraStatus, CameraType, ZoneType
from backend.app.schemas.common import ORMModel


class ZoneCreate(BaseModel):
    name: str
    type: ZoneType = ZoneType.aisle
    polygon: list[list[float]] = Field(min_length=3)

    @field_validator("polygon")
    @classmethod
    def normalized(cls, v: list[list[float]]) -> list[list[float]]:
        for pt in v:
            if len(pt) != 2 or not all(0.0 <= c <= 1.0 for c in pt):
                raise ValueError("polygon points must be [x, y] normalized to [0, 1]")
        return v


class ZoneOut(ORMModel):
    id: int
    camera_id: int
    name: str
    type: ZoneType
    polygon: list[list[float]]


class CameraCreate(BaseModel):
    name: str
    source: str
    type: CameraType = CameraType.rtsp
    location: str = ""
    fps_target: int = Field(default=5, ge=1, le=30)


class CameraUpdate(BaseModel):
    name: str | None = None
    source: str | None = None
    type: CameraType | None = None
    location: str | None = None
    fps_target: int | None = Field(default=None, ge=1, le=30)
    is_active: bool | None = None


class StreamTokenOut(BaseModel):
    token: str
    expires_in: int


class CameraOut(ORMModel):
    id: int
    name: str
    source: str
    type: CameraType
    status: CameraStatus
    location: str
    fps_target: int
    is_active: bool
    last_heartbeat: datetime | None
    measured_fps: float
    zones: list[ZoneOut] = []
