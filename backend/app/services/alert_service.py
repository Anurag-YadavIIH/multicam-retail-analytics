"""Alert evaluation + multi-channel dispatch (Slack, e-mail, webhook).

Rules are intentionally simple threshold checks; thresholds live in
configs/app.yaml so ops can tune them without a deploy.
"""

import logging
import smtplib
from datetime import UTC, datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path

import httpx
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.models.event import Alert, AlertSeverity, AlertType

logger = logging.getLogger(__name__)

DEDUP_WINDOW = timedelta(minutes=5)

DEFAULT_THRESHOLDS = {
    "queue_length": 6,
    "crowding_people": 25,
    "camera_offline_s": 60,
}

# configs/app.yaml key -> THRESHOLDS key
_YAML_KEYS = {
    "queue_length_threshold": "queue_length",
    "crowding_people_threshold": "crowding_people",
    "camera_offline_seconds": "camera_offline_s",
}


def load_thresholds(path: str | Path = "configs/app.yaml") -> dict[str, int]:
    """Same fail-soft pattern as vision/detector.py's load_class_map: read
    configs/app.yaml so ops can tune thresholds without a deploy, falling
    back to DEFAULT_THRESHOLDS if the file is missing or malformed."""
    p = Path(path)
    thresholds = dict(DEFAULT_THRESHOLDS)
    if p.exists():
        data = yaml.safe_load(p.read_text()) or {}
        alerts = data.get("alerts")
        if isinstance(alerts, dict):
            for yaml_key, threshold_key in _YAML_KEYS.items():
                if yaml_key in alerts:
                    thresholds[threshold_key] = alerts[yaml_key]
    return thresholds


THRESHOLDS = load_thresholds()


def _recent_duplicate(db: Session, type_: AlertType, camera_id: int | None) -> bool:
    since = datetime.now(UTC) - DEDUP_WINDOW
    stmt = (
        select(Alert.id)
        .where(
            Alert.type == type_,
            Alert.camera_id == camera_id,
            Alert.ts >= since,
        )
        .limit(1)
    )
    return db.scalar(stmt) is not None


def raise_alert(
    db: Session,
    type_: AlertType,
    severity: AlertSeverity,
    message: str,
    camera_id: int | None = None,
    payload: dict | None = None,
) -> Alert | None:
    """Persist an alert (deduped) and fan out to channels. Returns None if deduped."""
    if _recent_duplicate(db, type_, camera_id):
        return None
    alert = Alert(
        type=type_,
        severity=severity,
        message=message,
        camera_id=camera_id,
        payload=payload or {},
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    dispatch(alert)
    return alert


def evaluate_snapshot(db: Session, camera_id: int, snapshot: dict) -> list[Alert]:
    """Called on every ingested analytics snapshot."""
    created: list[Alert] = []
    q = snapshot.get("queue_length", 0)
    p = snapshot.get("people_count", 0)
    if q >= THRESHOLDS["queue_length"]:
        a = raise_alert(
            db,
            AlertType.high_queue,
            AlertSeverity.warning,
            f"Queue length {q} at camera {camera_id}",
            camera_id,
            {"queue_length": q},
        )
        if a:
            created.append(a)
    if p >= THRESHOLDS["crowding_people"]:
        a = raise_alert(
            db,
            AlertType.crowding,
            AlertSeverity.critical,
            f"Crowding: {p} people at camera {camera_id}",
            camera_id,
            {"people_count": p},
        )
        if a:
            created.append(a)
    return created


# ------------------------------------------------------------------ dispatch
def dispatch(alert: Alert) -> None:
    settings = get_settings()
    text = f"[{alert.severity.value.upper()}] {alert.type.value}: {alert.message}"
    if settings.slack_webhook_url:
        _safe(lambda: httpx.post(settings.slack_webhook_url, json={"text": text}, timeout=5))
    if settings.alert_webhook_url:
        _safe(
            lambda: httpx.post(
                settings.alert_webhook_url,
                json={
                    "type": alert.type.value,
                    "severity": alert.severity.value,
                    "message": alert.message,
                    "camera_id": alert.camera_id,
                },
                timeout=5,
            )
        )
    if settings.alert_email_smtp_host and settings.alert_email_to:
        _safe(lambda: _send_email(text))


def _send_email(text: str) -> None:
    settings = get_settings()
    msg = MIMEText(text)
    msg["Subject"] = f"[retail-analytics] {text[:80]}"
    msg["From"] = settings.alert_email_user
    msg["To"] = settings.alert_email_to
    with smtplib.SMTP(settings.alert_email_smtp_host, settings.alert_email_smtp_port) as s:
        s.starttls()
        s.login(settings.alert_email_user, settings.alert_email_password)
        s.send_message(msg)


def _safe(fn) -> None:
    try:
        fn()
    except Exception:  # channel failure must never break ingestion
        logger.exception("alert dispatch channel failed")
