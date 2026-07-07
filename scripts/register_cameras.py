"""Bulk-register cameras from configs/cameras.example.yaml via the REST API."""

import os

import httpx
import yaml

BACKEND = os.getenv("BACKEND_URL", "http://localhost:8000")


def main() -> None:
    email = os.getenv("FIRST_ADMIN_EMAIL", "admin@retail.local")
    password = os.getenv("FIRST_ADMIN_PASSWORD", "admin12345")
    token = httpx.post(
        f"{BACKEND}/api/v1/auth/login", data={"username": email, "password": password}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    with open("configs/cameras.example.yaml") as fh:
        cfg = yaml.safe_load(fh)
    for cam in cfg["cameras"]:
        r = httpx.post(f"{BACKEND}/api/v1/cameras", json=cam, headers=headers)
        print(cam["name"], r.status_code)


if __name__ == "__main__":
    main()
