"""Security tests: SSRF, authorization, CSRF and credential exposure."""

from __future__ import annotations

import pytest

from app.core.security import decrypt_secret, encrypt_secret, hash_password, verify_password
from app.models import Configuration, User
from app.services.fetcher import UnsafeUrlError, validate_source_url
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, login


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/feed.txt",
        "https://localhost/feed.txt",
        "https://127.0.0.1/feed.txt",
        "https://10.0.0.5/feed.txt",
        "https://192.168.1.1/feed.txt",
        "https://169.254.169.254/latest/meta-data",
        "https://[::1]/feed.txt",
        "https://user:pass@example.com/feed.txt",
        "file:///etc/passwd",
    ],
)
def test_unsafe_source_urls_rejected(url):
    with pytest.raises(UnsafeUrlError):
        validate_source_url(url)


def test_https_public_url_allowed():
    assert validate_source_url("https://raw.githubusercontent.com/x/y/main/z.txt").startswith("https://")


def test_unauthenticated_requests_are_rejected(client):
    for path in (
        "/api/v1/dashboard/summary",
        "/api/v1/sources",
        "/api/v1/configurations",
        "/api/v1/subscription-profiles",
        "/api/v1/automation/runs",
        "/api/v1/system/settings",
    ):
        response = client.get(path)
        assert response.status_code == 401, path


def test_public_health_endpoint(client):
    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert body["checks"]["database"]["ok"] is True


def test_csrf_required_for_mutations(admin):
    client, csrf = admin["client"], admin["csrf"]
    assert client.post("/api/v1/automation/refresh").status_code == 403
    response = client.post("/api/v1/automation/refresh", headers={"x-csrf-token": "wrong"})
    assert response.status_code == 403
    response = client.post("/api/v1/sources", json={"name": "x", "url": "https://example.com/f.txt"})
    assert response.status_code == 403


def test_read_only_role_cannot_mutate(admin, db):
    client = admin["client"]
    user = User(
        email="viewer@test.local",
        password_hash=hash_password("viewer-password-1"),
        display_name="Viewer",
        role="read_only",
    )
    db.add(user)
    db.commit()
    csrf = login(client, "viewer@test.local", "viewer-password-1")
    response = client.post("/api/v1/automation/refresh", headers={"x-csrf-token": csrf})
    assert response.status_code == 403
    assert client.get("/api/v1/sources").status_code == 200
    assert client.get("/api/v1/auth/users").status_code == 403


def test_login_lockout_and_generic_error(client, db):
    user = User(
        email="lockme@test.local",
        password_hash=hash_password("correct-password-1"),
        display_name="Lock",
        role="read_only",
    )
    db.add(user)
    db.commit()
    for _ in range(5):
        response = client.post("/api/v1/auth/login", json={"email": "lockme@test.local", "password": "wrong-password"})
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]
    blocked = client.post("/api/v1/auth/login", json={"email": "lockme@test.local", "password": "correct-password-1"})
    assert blocked.status_code == 423


def test_configuration_payload_never_leaks_links(admin, db):
    client, csrf = admin["client"], admin["csrf"]
    secret_link = "vless://secret-uuid-1234@198.51.100.30:443?type=ws&security=tls#Leaky"
    db.add(
        Configuration(
            fingerprint="a" * 48,
            protocol="vless",
            host="198.51.100.30",
            port=443,
            transport="ws",
            security="tls",
            canonical_endpoint="vless|198.51.100.30|443",
            credential_hint="secr…34",
            raw_link_encrypted=encrypt_secret(secret_link),
            raw_link_length=len(secret_link),
        )
    )
    db.commit()
    listing = client.get("/api/v1/configurations")
    assert listing.status_code == 200
    body = listing.text
    assert "secret-uuid-1234" not in body
    assert "vless://" not in body
    detail = client.get("/api/v1/configurations")
    assert detail.json()["items"][0]["credential_hint"] == "secr…34"


def test_source_creation_rejects_private_targets(admin):
    client, csrf = admin["client"], admin["csrf"]
    response = client.post(
        "/api/v1/sources",
        json={"name": "Internal probe", "url": "https://127.0.0.1/feed.txt", "source_type": "plain_text"},
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code == 422


def test_password_and_secret_helpers():
    hashed = hash_password("a-strong-password")
    assert verify_password("a-strong-password", hashed)
    assert not verify_password("wrong-password", hashed)
    ciphertext = encrypt_secret("vless://secret")
    assert "vless" not in ciphertext
    assert decrypt_secret(ciphertext) == "vless://secret"


def test_cross_origin_mutation_rejected(admin):
    client, csrf = admin["client"], admin["csrf"]
    response = client.post(
        "/api/v1/automation/refresh",
        headers={"x-csrf-token": csrf, "origin": "https://evil.example"},
    )
    assert response.status_code == 403
