"""Snapshot is a plain Response, safe to exercise end-to-end via the test client.
Stream is an intentionally infinite generator (real clients just keep the
connection open) - Starlette's TestClient fully drains a StreamingResponse
body before returning, so it can't be driven through a live HTTP round trip
here. Its framing is unit-tested directly via itertools.islice, and the route
wiring (status/media-type) is checked by calling the route function in-process."""

import itertools
from datetime import timedelta

from fastapi.responses import StreamingResponse

from backend.app.api.v1.cameras import _mjpeg_parts, stream_camera
from backend.app.core.security import _create_token, create_stream_token
from tests.conftest import auth


def _create_camera(client, token, name="cam") -> int:
    return client.post(
        "/api/v1/cameras", headers=auth(token), json={"name": name, "source": "0", "type": "usb"}
    ).json()["id"]


def test_snapshot_404_when_no_frame_cached(client, admin_token):
    cam_id = _create_camera(client, admin_token)
    resp = client.get(f"/api/v1/cameras/{cam_id}/snapshot", headers=auth(admin_token))
    assert resp.status_code == 404


def test_snapshot_returns_cached_jpeg(client, admin_token, fake_redis):
    cam_id = _create_camera(client, admin_token)
    fake_redis.store[f"frame:latest:{cam_id}"] = b"\xff\xd8fakejpeg"

    resp = client.get(f"/api/v1/cameras/{cam_id}/snapshot", headers=auth(admin_token))

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content == b"\xff\xd8fakejpeg"


def test_snapshot_requires_existing_camera(client, admin_token):
    resp = client.get("/api/v1/cameras/9999/snapshot", headers=auth(admin_token))
    assert resp.status_code == 404


def test_viewer_can_read_snapshot(client, viewer_token, admin_token, fake_redis):
    cam_id = _create_camera(client, admin_token)
    fake_redis.store[f"frame:latest:{cam_id}"] = b"jpegbytes"

    resp = client.get(f"/api/v1/cameras/{cam_id}/snapshot", headers=auth(viewer_token))

    assert resp.status_code == 200


def test_snapshot_rejects_missing_or_invalid_token(client, admin_token, fake_redis):
    cam_id = _create_camera(client, admin_token)
    fake_redis.store[f"frame:latest:{cam_id}"] = b"jpegbytes"

    assert client.get(f"/api/v1/cameras/{cam_id}/snapshot").status_code == 401
    assert client.get(f"/api/v1/cameras/{cam_id}/snapshot?token=garbage").status_code == 401


def test_snapshot_rejects_full_access_token_via_query_param(client, admin_token, fake_redis):
    """Hardening: ?token= must be a scoped stream token, never the long-lived
    access token - a leaked/logged URL should never grant full API access."""
    cam_id = _create_camera(client, admin_token)
    fake_redis.store[f"frame:latest:{cam_id}"] = b"jpegbytes"

    resp = client.get(f"/api/v1/cameras/{cam_id}/snapshot?token={admin_token}")

    assert resp.status_code == 401


def test_snapshot_accepts_scoped_stream_token_via_query_param(client, admin_token, fake_redis):
    cam_id = _create_camera(client, admin_token)
    fake_redis.store[f"frame:latest:{cam_id}"] = b"jpegbytes"
    token = create_stream_token(cam_id)

    resp = client.get(f"/api/v1/cameras/{cam_id}/snapshot?token={token}")

    assert resp.status_code == 200
    assert resp.content == b"jpegbytes"


def test_snapshot_rejects_expired_stream_token(client, admin_token, fake_redis):
    cam_id = _create_camera(client, admin_token)
    fake_redis.store[f"frame:latest:{cam_id}"] = b"jpegbytes"
    expired = _create_token(str(cam_id), "stream", timedelta(seconds=-5), {"camera_id": cam_id})

    resp = client.get(f"/api/v1/cameras/{cam_id}/snapshot?token={expired}")

    assert resp.status_code == 401


def test_snapshot_rejects_stream_token_scoped_to_another_camera(client, admin_token, fake_redis):
    cam_a = _create_camera(client, admin_token, name="cam-a")
    cam_b = _create_camera(client, admin_token, name="cam-b")
    fake_redis.store[f"frame:latest:{cam_b}"] = b"jpegbytes"
    token_for_a = create_stream_token(cam_a)

    resp = client.get(f"/api/v1/cameras/{cam_b}/snapshot?token={token_for_a}")

    assert resp.status_code == 401


def test_stream_token_rejected_on_other_endpoints(client, admin_token):
    cam_id = _create_camera(client, admin_token)
    token = create_stream_token(cam_id)

    resp = client.get("/api/v1/cameras", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 401


def test_issue_stream_token_requires_auth(client, admin_token):
    cam_id = _create_camera(client, admin_token)
    resp = client.post(f"/api/v1/cameras/{cam_id}/stream-token")
    assert resp.status_code == 401


def test_issue_stream_token_requires_existing_camera(client, admin_token):
    resp = client.post("/api/v1/cameras/9999/stream-token", headers=auth(admin_token))
    assert resp.status_code == 404


def test_issue_stream_token_end_to_end(client, admin_token, viewer_token, fake_redis):
    cam_id = _create_camera(client, admin_token)
    fake_redis.store[f"frame:latest:{cam_id}"] = b"jpegbytes"

    issued = client.post(f"/api/v1/cameras/{cam_id}/stream-token", headers=auth(viewer_token))
    assert issued.status_code == 200
    body = issued.json()
    assert body["expires_in"] == 60
    assert isinstance(body["token"], str) and body["token"]

    resp = client.get(f"/api/v1/cameras/{cam_id}/snapshot?token={body['token']}")
    assert resp.status_code == 200


def test_stream_requires_existing_camera(client, admin_token):
    resp = client.get("/api/v1/cameras/9999/stream", headers=auth(admin_token))
    assert resp.status_code == 404


def test_stream_camera_returns_mjpeg_response(admin_token, db_session, fake_redis, client):
    cam_id = _create_camera(client, admin_token)

    resp = stream_camera(camera_id=cam_id, db=db_session, r=fake_redis)

    assert isinstance(resp, StreamingResponse)
    assert resp.media_type == "multipart/x-mixed-replace; boundary=frame"


def test_mjpeg_parts_frames_the_cached_jpeg_with_content_length(fake_redis):
    fake_redis.store["frame:latest:1"] = b"jpegbytes"

    chunk = next(itertools.islice(_mjpeg_parts(fake_redis, 1), 1))

    assert b"--frame\r\n" in chunk
    assert b"Content-Type: image/jpeg\r\n" in chunk
    assert b"Content-Length: 9\r\n\r\n" in chunk
    assert chunk.endswith(b"jpegbytes\r\n")
