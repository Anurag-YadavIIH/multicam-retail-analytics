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


def _create_camera_with_zone(client, token, name="cam") -> tuple[int, int]:
    cam_id = client.post(
        "/api/v1/cameras",
        headers=auth(token),
        json={"name": name, "source": "0", "type": "usb"},
    ).json()["id"]
    zone_id = client.post(
        f"/api/v1/cameras/{cam_id}/zones",
        headers=auth(token),
        json={"name": "queue-1", "type": "queue", "polygon": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]]},
    ).json()["id"]
    return cam_id, zone_id


def test_update_zone_success(client, admin_token):
    cam_id, zone_id = _create_camera_with_zone(client, admin_token)

    resp = client.patch(
        f"/api/v1/cameras/{cam_id}/zones/{zone_id}",
        headers=auth(admin_token),
        json={
            "name": "checkout-queue",
            "type": "checkout",
            "polygon": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "checkout-queue"
    assert body["type"] == "checkout"
    assert body["polygon"] == [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]


def test_update_zone_partial_leaves_other_fields_untouched(client, admin_token):
    cam_id, zone_id = _create_camera_with_zone(client, admin_token)

    resp = client.patch(
        f"/api/v1/cameras/{cam_id}/zones/{zone_id}",
        headers=auth(admin_token),
        json={"name": "renamed"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "renamed"
    assert body["type"] == "queue"
    assert body["polygon"] == [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]]


def test_update_zone_invalid_polygon_rejected(client, admin_token):
    cam_id, zone_id = _create_camera_with_zone(client, admin_token)

    resp = client.patch(
        f"/api/v1/cameras/{cam_id}/zones/{zone_id}",
        headers=auth(admin_token),
        json={"polygon": [[1.5, 0.1], [0.9, 0.1], [0.9, 0.9]]},
    )

    assert resp.status_code == 422


def test_update_zone_404_for_missing_zone(client, admin_token):
    cam_id, _ = _create_camera_with_zone(client, admin_token)

    resp = client.patch(
        f"/api/v1/cameras/{cam_id}/zones/9999", headers=auth(admin_token), json={"name": "x"}
    )

    assert resp.status_code == 404


def test_update_zone_404_when_zone_belongs_to_another_camera(client, admin_token):
    cam_a, zone_a = _create_camera_with_zone(client, admin_token, name="cam-a")
    cam_b, _ = _create_camera_with_zone(client, admin_token, name="cam-b")

    resp = client.patch(
        f"/api/v1/cameras/{cam_b}/zones/{zone_a}", headers=auth(admin_token), json={"name": "x"}
    )

    assert resp.status_code == 404


def test_update_zone_forbidden_for_viewer(client, admin_token, viewer_token):
    cam_id, zone_id = _create_camera_with_zone(client, admin_token)

    resp = client.patch(
        f"/api/v1/cameras/{cam_id}/zones/{zone_id}",
        headers=auth(viewer_token),
        json={"name": "x"},
    )

    assert resp.status_code == 403
