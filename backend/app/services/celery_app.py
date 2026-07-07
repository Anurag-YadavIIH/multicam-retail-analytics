"""Celery app for background jobs (reports, retention, health sweeps)."""

from celery import Celery

from backend.app.core.config import get_settings

settings = get_settings()

celery = Celery(
    "retail_analytics",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["backend.app.services.tasks"],
)
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    beat_schedule={
        "camera-health-sweep": {
            "task": "backend.app.services.tasks.camera_health_sweep",
            "schedule": 30.0,
        },
        "daily-report": {
            "task": "backend.app.services.tasks.generate_daily_report",
            "schedule": 24 * 3600.0,
        },
        "retention-cleanup": {
            "task": "backend.app.services.tasks.purge_old_detections",
            "schedule": 6 * 3600.0,
        },
    },
)
