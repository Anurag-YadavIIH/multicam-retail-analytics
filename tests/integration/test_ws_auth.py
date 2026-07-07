"""WebSocket auth: a normal access token still works everywhere (unchanged
behavior); a create_stream_token() token additionally works for its own
camera's /ws/detections/{camera_id} channel, but nowhere else."""

import pytest
from fastapi import WebSocketDisconnect

from backend.app.core.security import create_stream_token


def test_detections_channel_accepts_scoped_stream_token(client):
    token = create_stream_token(1)
    with client.websocket_connect(f"/ws/detections/1?token={token}"):
        pass


def test_detections_channel_rejects_stream_token_for_another_camera(client):
    token = create_stream_token(2)
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(f"/ws/detections/1?token={token}"),
    ):
        pass


def test_detections_channel_rejects_missing_token(client):
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws/detections/1"):
        pass


def test_detections_channel_accepts_full_access_token(client, admin_token):
    with client.websocket_connect(f"/ws/detections/1?token={admin_token}"):
        pass


def test_alerts_channel_rejects_stream_token(client):
    """Stream tokens are scoped to one camera's detections channel only -
    the global alerts/analytics channels have no camera_id to scope against."""
    token = create_stream_token(1)
    with pytest.raises(WebSocketDisconnect), client.websocket_connect(f"/ws/alerts?token={token}"):
        pass


def test_alerts_channel_accepts_full_access_token(client, admin_token):
    with client.websocket_connect(f"/ws/alerts?token={admin_token}"):
        pass


def test_analytics_channel_rejects_invalid_token(client):
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/ws/analytics?token=garbage"),
    ):
        pass
