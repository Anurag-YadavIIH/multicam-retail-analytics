from tests.conftest import auth


def test_camera_crud(client, admin_token):
    created = client.post(
        "/api/v1/cameras",
        headers=auth(admin_token),
        json={
            "name": "cam-1",
            "source": "rtsp://x",
            "type": "rtsp",
            "location": "door",
        },
    )
    assert created.status_code == 201
    cam_id = created.json()["id"]

    listed = client.get("/api/v1/cameras", headers=auth(admin_token)).json()
    assert len(listed) == 1

    patched = client.patch(
        f"/api/v1/cameras/{cam_id}", headers=auth(admin_token), json={"location": "aisle 5"}
    )
    assert patched.json()["location"] == "aisle 5"

    zone = client.post(
        f"/api/v1/cameras/{cam_id}/zones",
        headers=auth(admin_token),
        json={
            "name": "queue-1",
            "type": "queue",
            "polygon": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]],
        },
    )
    assert zone.status_code == 201

    deleted = client.delete(f"/api/v1/cameras/{cam_id}", headers=auth(admin_token))
    assert deleted.status_code == 204
    assert client.get("/api/v1/cameras", headers=auth(admin_token)).json() == []


def test_rbac_viewer_cannot_create(client, viewer_token):
    resp = client.post(
        "/api/v1/cameras", headers=auth(viewer_token), json={"name": "x", "source": "rtsp://x"}
    )
    assert resp.status_code == 403


def test_invalid_zone_polygon_rejected(client, admin_token):
    cam = client.post(
        "/api/v1/cameras",
        headers=auth(admin_token),
        json={"name": "c", "source": "0", "type": "usb"},
    ).json()
    resp = client.post(
        f"/api/v1/cameras/{cam['id']}/zones",
        headers=auth(admin_token),
        json={
            "name": "bad",
            "polygon": [[2.0, 0.1], [0.9, 0.1], [0.9, 0.9]],
        },
    )
    assert resp.status_code == 422
