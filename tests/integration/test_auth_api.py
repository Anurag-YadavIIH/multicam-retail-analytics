from tests.conftest import auth, make_user


def test_login_success_and_me(client, db_session):
    make_user(db_session)
    resp = client.post(
        "/api/v1/auth/login", data={"username": "admin@test.local", "password": "secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers=auth(token))
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


def test_login_wrong_password(client, db_session):
    make_user(db_session)
    resp = client.post(
        "/api/v1/auth/login", data={"username": "admin@test.local", "password": "nope"}
    )
    assert resp.status_code == 401


def test_refresh_flow(client, db_session):
    make_user(db_session)
    tokens = client.post(
        "/api/v1/auth/login", data={"username": "admin@test.local", "password": "secret123"}
    ).json()
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_protected_route_requires_token(client):
    assert client.get("/api/v1/cameras").status_code == 401
