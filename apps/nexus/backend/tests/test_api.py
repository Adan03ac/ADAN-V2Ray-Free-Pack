"""API behaviour: dashboard aggregates, source CRUD, filters, health jobs."""

from __future__ import annotations

from app.core.security import encrypt_secret
from app.models import Configuration, Source


def test_dashboard_summary_uses_real_data(admin, db):
    client = admin["client"]
    db.add(
        Configuration(
            fingerprint="b" * 48,
            protocol="vmess",
            host="198.51.100.40",
            port=443,
            transport="tcp",
            security="tls",
            canonical_endpoint="vmess|198.51.100.40|443",
            credential_hint="vvvv…99",
            raw_link_encrypted=encrypt_secret("vmess://placeholder"),
            raw_link_length=10,
        )
    )
    db.commit()
    response = client.get("/api/v1/dashboard/summary?days=7")
    assert response.status_code == 200
    body = response.json()
    assert body["overview"]["kpis"]["unique_configurations"] >= 1
    assert body["overview"]["kpis"]["verified_working_configurations"] == 0
    assert body["overview"]["kpis"]["verification_available"] is False
    assert len(body["growth"]) == 7
    assert body["health"]["agent"]["region"]
    assert "upstream" in body


def test_source_crud_roundtrip(admin):
    client, csrf = admin["client"], admin["csrf"]
    created = client.post(
        "/api/v1/sources",
        json={
            "name": "New public feed",
            "url": "https://example.com/feed.txt",
            "source_type": "plain_text",
            "trust_level": "community",
            "tags": ["manual-add"],
        },
        headers={"x-csrf-token": csrf},
    )
    assert created.status_code == 201, created.text
    source_id = created.json()["id"]

    patched = client.patch(
        f"/api/v1/sources/{source_id}",
        json={"enabled": False, "name": "Renamed feed"},
        headers={"x-csrf-token": csrf},
    )
    assert patched.status_code == 200
    assert patched.json()["enabled"] is False

    listing = client.get("/api/v1/sources?search=Renamed")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    detail = client.get(f"/api/v1/sources/{source_id}")
    assert detail.status_code == 200
    assert detail.json()["source"]["slug"] == "new-public-feed"

    duplicate = client.post(
        "/api/v1/sources",
        json={"name": "New public feed", "url": "https://example.com/other.txt"},
        headers={"x-csrf-token": csrf},
    )
    assert duplicate.status_code == 409


def test_configuration_filters_and_facets(admin, db):
    client = admin["client"]
    for protocol, host in (("vless", "198.51.100.51"), ("trojan", "198.51.100.52")):
        db.add(
            Configuration(
                fingerprint=f"{protocol[0]}" * 48,
                protocol=protocol,
                host=host,
                port=443,
                transport="ws",
                security="tls",
                canonical_endpoint=f"{protocol}|{host}",
                credential_hint="xxxx…yy",
                raw_link_encrypted=encrypt_secret(f"{protocol}://placeholder"),
                raw_link_length=20,
            )
        )
    db.commit()

    filtered = client.get("/api/v1/configurations?protocol=trojan")
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["protocol"] == "trojan"

    searched = client.get("/api/v1/configurations?search=198.51.100.51")
    assert searched.json()["total"] == 1

    facets = client.get("/api/v1/configurations/facets")
    assert facets.status_code == 200
    assert any(item["value"] == "vless" for item in facets.json()["protocols"])


def test_subscription_profile_endpoints(admin, db):
    client, csrf = admin["client"], admin["csrf"]
    created = client.post(
        "/api/v1/subscription-profiles",
        json={"name": "My phone", "max_configs": 5, "export_format": "base64"},
        headers={"x-csrf-token": csrf},
    )
    assert created.status_code == 201, created.text
    profile_id = created.json()["id"]

    rendered = client.post(f"/api/v1/subscription-profiles/{profile_id}/render", headers={"x-csrf-token": csrf})
    assert rendered.status_code == 200
    payload = rendered.json()
    assert payload["url"].endswith("/plain") or "/public/subscriptions/" in payload["url"]
    assert payload["token"]

    preview = client.get(f"/api/v1/subscription-profiles/{profile_id}/preview")
    assert preview.status_code == 200
    assert "preview" in preview.json()

    public = client.get(f"/api/v1/public/subscriptions/{payload['token']}")
    assert public.status_code == 200

    revoked = client.post(
        f"/api/v1/subscription-profiles/tokens/{payload['token_id']}/revoke", headers={"x-csrf-token": csrf}
    )
    assert revoked.status_code == 200
    assert client.get(f"/api/v1/public/subscriptions/{payload['token']}").status_code == 404


def test_health_job_runs_against_registered_configs(admin, db):
    client, csrf = admin["client"], admin["csrf"]
    db.add(
        Configuration(
            fingerprint="c" * 48,
            protocol="vless",
            host="198.51.100.60",
            port=443,
            transport="ws",
            security="tls",
            canonical_endpoint="vless|198.51.100.60|443",
            credential_hint="cccc…dd",
            raw_link_encrypted=encrypt_secret("vless://placeholder"),
            raw_link_length=18,
        )
    )
    db.commit()
    config_id = db.query(Configuration).first().id

    response = client.post(
        "/api/v1/health-tests",
        json={"configuration_ids": [config_id], "limit": 1, "stages": ["syntax"]},
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code == 202, response.text
    assert response.json()["job"]["total"] == 1

    unknown = client.post(
        "/api/v1/health-tests",
        json={"configuration_ids": [999999], "limit": 1},
        headers={"x-csrf-token": csrf},
    )
    assert unknown.status_code == 422


def test_cloudflare_module_is_honest(admin):
    client = admin["client"]
    status = client.get("/api/v1/cloudflare/status")
    assert status.status_code == 200
    body = status.json()
    assert body["configured"] is False
    assert body["capabilities"]["worker_deploy"] is False
    assert body["deployments"] == []


def test_settings_and_audit_log(admin):
    client, csrf = admin["client"], admin["csrf"]
    settings = client.get("/api/v1/system/settings")
    assert settings.status_code == 200
    assert "capabilities" in settings.json()

    patched = client.patch(
        "/api/v1/system/settings",
        json={"key": "ui", "value": {"default_language": "fa"}},
        headers={"x-csrf-token": csrf},
    )
    assert patched.status_code == 200
    assert patched.json()["value"]["default_language"] == "fa"

    unknown = client.patch(
        "/api/v1/system/settings",
        json={"key": "root", "value": {"x": 1}},
        headers={"x-csrf-token": csrf},
    )
    assert unknown.status_code == 422

    logs = client.get("/api/v1/system/audit-logs")
    assert logs.status_code == 200
    assert any(item["action"] == "system.settings_updated" for item in logs.json()["items"])


def test_automation_schedule_and_publication(admin, db):
    client = admin["client"]
    schedule = client.get("/api/v1/automation/schedule")
    assert schedule.status_code == 200
    assert schedule.json()["upstream"]["schedule_cron"] == "7 * * * *"
    publication = client.get("/api/v1/system/publication")
    assert publication.status_code == 200
    assert publication.json()["mode"] == "local"


def test_logout_revokes_session(admin, client):
    csrf = admin["csrf"]
    assert client.post("/api/v1/auth/logout", headers={"x-csrf-token": csrf}).status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401
