"""Self-service account creation and admin role management."""

from __future__ import annotations

from app.core.config import settings
from app.models import User
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, login


def test_registration_creates_read_only_session(client, db):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "signup@test.local", "password": "a-strong-password", "display_name": "Signup User"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user"]["role"] == "read_only"
    assert body["user"]["email"] == "signup@test.local"
    csrf = body["csrf_token"]

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["role"] == "read_only"

    # A self-service account can read but never mutate.
    assert client.get("/api/v1/sources").status_code == 200
    assert client.post("/api/v1/automation/refresh", headers={"x-csrf-token": csrf}).status_code == 403

    stored = db.query(User).filter(User.email == "signup@test.local").one()
    assert stored.password_hash.startswith("$2")
    assert "a-strong-password" not in stored.password_hash


def test_registration_rejects_duplicates_and_weak_passwords(client):
    duplicate = client.post(
        "/api/v1/auth/register",
        json={"email": ADMIN_EMAIL, "password": "another-strong-pass", "display_name": "Dup"},
    )
    assert duplicate.status_code == 409

    weak = client.post(
        "/api/v1/auth/register",
        json={"email": "weak@test.local", "password": "short", "display_name": "Weak"},
    )
    assert weak.status_code == 422

    invalid_email = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "another-strong-pass"},
    )
    assert invalid_email.status_code == 422


def test_registration_can_be_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "allow_registration", False)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "closed@test.local", "password": "another-strong-pass"},
    )
    assert response.status_code == 403


def test_admin_promotes_operator_and_self_demotion_is_blocked(admin, client, db):
    csrf = admin["csrf"]
    created = client.post(
        "/api/v1/auth/register",
        json={"email": "promote@test.local", "password": "another-strong-pass", "display_name": "Promote"},
    )
    assert created.status_code == 201
    user_id = created.json()["user"]["id"]

    # Registration replaced the cookie jar with the read-only session; sign back in as admin.
    csrf = login(client)
    promoted = client.patch(
        f"/api/v1/auth/users/{user_id}",
        json={"role": "admin"},
        headers={"x-csrf-token": csrf},
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["role"] == "admin"

    deactivated = client.patch(
        f"/api/v1/auth/users/{user_id}",
        json={"is_active": False},
        headers={"x-csrf-token": csrf},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    me = client.get("/api/v1/auth/me").json()
    self_demote = client.patch(
        f"/api/v1/auth/users/{me['user']['id']}",
        json={"role": "read_only"},
        headers={"x-csrf-token": me["csrf_token"]},
    )
    assert self_demote.status_code == 409
    assert db.query(User).filter(User.id == user_id).one().role == "admin"


def test_login_still_works_after_registration(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "again@test.local", "password": "another-strong-pass"},
    )
    client.cookies.clear()
    csrf = login(client, "again@test.local", "another-strong-pass")
    assert csrf
    assert client.get("/api/v1/auth/me").json()["user"]["email"] == "again@test.local"


def test_admin_login_unaffected(client):
    client.cookies.clear()
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert client.get("/api/v1/dashboard/summary").status_code == 200
