from tests.conftest import auth


def test_admin_can_create_list_and_update_user(client, admin_token):
    created = client.post(
        "/api/v1/users",
        headers=auth(admin_token),
        json={"email": "new@example.com", "password": "secret123", "role": "manager"},
    )
    assert created.status_code == 201
    user_id = created.json()["id"]

    listed = client.get("/api/v1/users", headers=auth(admin_token)).json()
    assert any(u["email"] == "new@example.com" for u in listed)

    patched = client.patch(
        f"/api/v1/users/{user_id}",
        headers=auth(admin_token),
        json={"full_name": "New Name", "password": "newpass123"},
    )
    assert patched.status_code == 200
    assert patched.json()["full_name"] == "New Name"

    relogin = client.post(
        "/api/v1/auth/login", data={"username": "new@example.com", "password": "newpass123"}
    )
    assert relogin.status_code == 200


def test_duplicate_email_rejected(client, admin_token):
    client.post(
        "/api/v1/users",
        headers=auth(admin_token),
        json={"email": "dup@example.com", "password": "secret123"},
    )
    dup = client.post(
        "/api/v1/users",
        headers=auth(admin_token),
        json={"email": "dup@example.com", "password": "secret123"},
    )
    assert dup.status_code == 409


def test_update_missing_user_404(client, admin_token):
    resp = client.patch(
        "/api/v1/users/9999", headers=auth(admin_token), json={"full_name": "nobody"}
    )
    assert resp.status_code == 404


def test_viewer_cannot_manage_users(client, viewer_token):
    assert client.get("/api/v1/users", headers=auth(viewer_token)).status_code == 403
    resp = client.post(
        "/api/v1/users",
        headers=auth(viewer_token),
        json={"email": "x@example.com", "password": "secret123"},
    )
    assert resp.status_code == 403
