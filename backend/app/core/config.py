"""Application configuration loaded from environment variables (12-factor)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_name: str = "retail-vision-analytics"
    log_level: str = "INFO"

    secret_key: str = "dev-secret-key-change-me-please-32chars!"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    cors_origins: str = "http://localhost:5173"

    database_url: str = (
        "postgresql+psycopg://retail:retail_dev_password@localhost:5432/retail_analytics"
    )
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_detections_topic: str = "detections"
    kafka_events_topic: str = "events"
    kafka_enabled: bool = False

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_frames: str = "frames"
    minio_bucket_reports: str = "reports"
    minio_secure: bool = False

    yolo_model: str = "yolo11n.pt"
    device: str = "cpu"
    conf_threshold: float = 0.35
    iou_threshold: float = 0.5
    inference_fps: int = 5
    frame_width: int = 960
    enable_face_blur: bool = True
    batch_size: int = 1

    mlflow_tracking_uri: str = ""
    mlflow_experiment: str = "retail-analytics"

    slack_webhook_url: str = ""
    alert_email_smtp_host: str = ""
    alert_email_smtp_port: int = 587
    alert_email_user: str = ""
    alert_email_password: str = ""
    alert_email_to: str = ""
    alert_webhook_url: str = ""

    first_admin_email: str = "admin@retail.local"
    first_admin_password: str = "admin12345"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
