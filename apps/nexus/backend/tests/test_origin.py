"""Origin handling: same-origin, suffix allow-list and foreign origins."""

from __future__ import annotations

from app.core.config import settings


def test_same_origin_mutation_is_allowed(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "same-origin@test.local", "password": "another-strong-pass"},
        headers={"origin": "http://testserver"},
    )
    assert response.status_code == 201, response.text


def test_configured_suffix_is_allowed(client, monkeypatch):
    monkeypatch.setattr(settings, "allowed_origin_suffixes", ".preview.test")
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "suffix@test.local", "password": "another-strong-pass"},
        headers={"origin": "https://pv-1234.preview.test"},
    )
    assert response.status_code == 201, response.text


def test_foreign_origin_is_still_rejected(admin, client):
    response = client.post(
        "/api/v1/automation/refresh",
        headers={"x-csrf-token": admin["csrf"], "origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert "Cross-origin" in response.json()["detail"]


def test_forwarded_host_cannot_whitelist_a_foreign_origin(admin, client):
    response = client.post(
        "/api/v1/automation/refresh",
        headers={
            "x-csrf-token": admin["csrf"],
            "origin": "https://evil.example",
            "x-forwarded-host": "evil.example",
        },
    )
    assert response.status_code == 403
