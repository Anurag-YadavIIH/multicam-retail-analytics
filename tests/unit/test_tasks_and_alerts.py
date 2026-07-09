from datetime import UTC, datetime, timedelta

from backend.app.models import Camera, CameraStatus, Detection
from backend.app.models.event import AlertSeverity, AlertType
from backend.app.services import tasks
from backend.app.services.alert_service import (
    DEFAULT_THRESHOLDS,
    _safe,
    load_thresholds,
    raise_alert,
)


def test_health_sweep_flags_stale_camera(db_session, monkeypatch):
    monkeypatch.setattr(tasks, "SessionLocal", lambda: db_session)
    db_session.close = lambda: None  # keep fixture session usable
    cam = Camera(
        name="c1",
        source="rtsp://x",
        status=CameraStatus.online,
        last_heartbeat=datetime.now(UTC) - timedelta(minutes=5),
    )
    db_session.add(cam)
    db_session.commit()
    flagged = tasks.camera_health_sweep.run()
    assert flagged == 1
    db_session.refresh(cam)
    assert cam.status == CameraStatus.offline


def test_purge_old_detections(db_session, monkeypatch):
    monkeypatch.setattr(tasks, "SessionLocal", lambda: db_session)
    db_session.close = lambda: None
    cam = Camera(name="c2", source="0")
    db_session.add(cam)
    db_session.commit()
    old = datetime.now(UTC) - timedelta(days=30)
    db_session.add(
        Detection(
            camera_id=cam.id, ts=old, class_name="person", confidence=0.9, x1=0, y1=0, x2=1, y2=1
        )
    )
    db_session.add(
        Detection(
            camera_id=cam.id,
            ts=datetime.now(UTC),
            class_name="person",
            confidence=0.9,
            x1=0,
            y1=0,
            x2=1,
            y2=1,
        )
    )
    db_session.commit()
    assert tasks.purge_old_detections.run() == 1


def test_daily_report_aggregates(db_session, monkeypatch):
    from backend.app.models import AnalyticsSnapshot, Report

    monkeypatch.setattr(tasks, "SessionLocal", lambda: db_session)
    db_session.close = lambda: None
    cam = Camera(name="c3", source="0")
    db_session.add(cam)
    db_session.commit()
    db_session.add(
        AnalyticsSnapshot(
            camera_id=cam.id,
            ts=datetime.now(UTC),
            unique_visitors=40,
            avg_dwell_s=90,
            queue_length=4,
        )
    )
    db_session.commit()
    assert tasks.generate_daily_report.run() == 1
    report = db_session.query(Report).one()
    assert report.summary["unique_visitors"] == 40


def test_raise_alert_dedup(db_session):
    a1 = raise_alert(db_session, AlertType.crowding, AlertSeverity.critical, "m", camera_id=None)
    a2 = raise_alert(db_session, AlertType.crowding, AlertSeverity.critical, "m", camera_id=None)
    assert a1 is not None and a2 is None


def test_safe_swallows_exceptions():
    _safe(lambda: 1 / 0)  # must not raise


def test_load_thresholds_defaults_when_file_missing(tmp_path):
    assert load_thresholds(tmp_path / "does-not-exist.yaml") == DEFAULT_THRESHOLDS


def test_load_thresholds_reads_yaml_overrides(tmp_path):
    config = tmp_path / "app.yaml"
    config.write_text("alerts:\n  queue_length_threshold: 3\n  camera_offline_seconds: 30\n")

    thresholds = load_thresholds(config)

    assert thresholds["queue_length"] == 3
    assert thresholds["camera_offline_s"] == 30
    assert thresholds["crowding_people"] == DEFAULT_THRESHOLDS["crowding_people"]  # unset - default


def test_load_thresholds_ignores_malformed_alerts_section(tmp_path):
    config = tmp_path / "app.yaml"
    config.write_text("alerts: not-a-mapping\n")

    assert load_thresholds(config) == DEFAULT_THRESHOLDS
