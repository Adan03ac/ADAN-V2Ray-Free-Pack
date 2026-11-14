"""Regression evidence for the kickoff security and correctness fixes.

All destinations, DNS answers and sockets below are mocked; no live probes.
"""
import concurrent.futures
import json
import logging
import socket
import threading
import time
from types import SimpleNamespace

import httpx
import pytest
from fastapi import Request

from app.api.deps import client_ip
from app.core.config import Settings, settings
from app.core.logging import JsonFormatter, TextFormatter
from app.core.security import encrypt_secret, hash_password, verify_password
from app.models import Configuration, Source, SubscriptionProfile, User
from app.services import adapters, fetcher, health, ingestion, subscriptions
from app.services.seed import ensure_admin
from tests.conftest import login
from tests.test_ingestion import VALID_A, _make_source
from tests.test_subscriptions import LINKS, _profile, _seed_configs


def mock_fetch(monkeypatch, handler, retries=0):
    real_client = httpx.Client
    monkeypatch.setattr(fetcher.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(settings, "source_max_retries", retries)


def test_redirect_relative_target_and_tls_identity(monkeypatch):
    seen = []
    def handler(request):
        seen.append(request)
        if request.url.path == "/first":
            return httpx.Response(302, headers={"location": "/final"})
        return httpx.Response(200, content=b"feed")
    mock_fetch(monkeypatch, handler)
    result = fetcher.SafeFetcher().fetch("https://feed.example/first")
    assert result.ok and result.content == b"feed" and result.attempts == 2
    assert result.final_url == "https://feed.example/final"
    assert [r.url.path for r in seen] == ["/first", "/final"]
    assert all(r.url.host == "93.184.216.34" for r in seen)
    assert all(r.headers["host"] == "feed.example" for r in seen)
    assert all(r.extensions["sni_hostname"] == "feed.example" for r in seen)
    assert "if-none-match" not in seen[1].headers


def test_redirect_to_metadata_never_requested(monkeypatch):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(302, headers={"location": "https://169.254.169.254/metadata"})
    mock_fetch(monkeypatch, handler)
    result = fetcher.SafeFetcher().fetch("https://feed.example/start")
    assert result.error_category == "unsafe_url" and len(seen) == 1


def test_redirect_limit_independent_of_retries(monkeypatch):
    mock_fetch(monkeypatch, lambda request: httpx.Response(302, headers={"location": "/again"}))
    result = fetcher.SafeFetcher().fetch("https://feed.example/start")
    assert result.error_category == "redirect" and result.attempts == 4


def test_dns_rebinding_blocked_before_transport(monkeypatch):
    answers = iter([["93.184.216.34"], ["93.184.216.34"], ["127.0.0.1"]])
    monkeypatch.setattr(fetcher, "_resolve", lambda *args: next(answers))
    def forbidden(request):
        pytest.fail("Rebound private address reached transport")
    mock_fetch(monkeypatch, forbidden)
    result = fetcher.SafeFetcher().fetch("https://feed.example/start")
    assert result.error_category == "unsafe_url"


def test_fetch_size_limit(monkeypatch):
    mock_fetch(monkeypatch, lambda request: httpx.Response(200, content=b"x" * 100))
    assert fetcher.SafeFetcher(max_bytes=10).fetch("https://feed.example/f").error_category == "too_large"


def test_retry_then_success(monkeypatch):
    statuses = iter([503, 200])
    mock_fetch(monkeypatch, lambda r: httpx.Response(next(statuses), content=b"ok"), retries=1)
    monkeypatch.setattr(fetcher.time, "sleep", lambda seconds: None)
    result = fetcher.SafeFetcher().fetch("https://feed.example/f")
    assert result.ok and result.attempts == 2


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "::ffff:127.0.0.1", "100.64.0.1"])
def test_health_blocks_non_public_dns(monkeypatch, address):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))])
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("private socket attempted"))
    result = health.test_configuration(SimpleNamespace(validation_status="valid", host="node.example", port=443), ["tcp"], 1, True)
    assert result.category == "blocked_target"


def test_tcp_requires_authorization_and_pins_ip(monkeypatch):
    monkeypatch.setattr(settings, "health_authorized_cidrs", "")
    assert health._tcp_stage("93.184.216.34", 443, 1).category == "unauthorized_target"
    assert health._tcp_stage("node.example", 443, 1).category == "blocked_target"
    monkeypatch.setattr(settings, "health_authorized_cidrs", "93.184.216.34/32")
    seen = []
    class Socket:
        def __enter__(self): return self
        def __exit__(self, *args): pass
    monkeypatch.setattr(socket, "create_connection", lambda target, **kwargs: (seen.append(target) or Socket()))
    result = health._tcp_stage("93.184.216.34", 443, 1)
    assert result.status == "reachable" and result.stage == "tcp"
    assert seen == [("93.184.216.34", 443)]


def test_dns_deadline_returns_without_executor_shutdown_wait(monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: (release.wait(2) or []))
    started = time.monotonic()
    try:
        result = health._dns_stage("node.example", .02)
        assert result.category == "dns_timeout"
        assert time.monotonic() - started < .5
    finally:
        release.set()


def test_health_concurrent_job_rejected(db):
    health._JOB_SLOT.acquire()
    try:
        with pytest.raises(health.HealthBusy):
            health.start_job(db, configuration_ids=[], limit=1, stages=["syntax"], user_id=1)
    finally:
        health._JOB_SLOT.release()


def test_other_users_profile_exports_are_private(admin, db):
    profile = _profile(db)
    other = User(email="private-regression@test.local", password_hash=hash_password("viewer-password-1"), display_name="Viewer", role="read_only")
    db.add(other); db.commit()
    client = admin["client"]
    login(client, other.email, "viewer-password-1")
    for suffix in ("preview", "export"):
        assert client.get(f"/api/v1/subscription-profiles/{profile.id}/{suffix}").status_code == 404


def test_admin_create_user_requires_csrf(admin):
    response = admin["client"].post("/api/v1/auth/users", json={"email": "csrf-regression@test.local", "password": "a-strong-password"})
    assert response.status_code == 403


def test_logout_requires_session_csrf(admin):
    assert admin["client"].post("/api/v1/auth/logout").status_code == 403
    assert admin["client"].get("/api/v1/auth/me").status_code == 200


def test_forwarded_headers_cannot_bypass_rate_identity():
    request = Request({"type": "http", "headers": [(b"x-forwarded-for", b"forged")], "client": ("127.0.0.1", 1234)})
    assert client_ip(request) == "127.0.0.1"


def test_custom_cookie_names_work(client, monkeypatch):
    monkeypatch.setattr(settings, "session_cookie_name", "custom_session")
    monkeypatch.setattr(settings, "csrf_cookie_name", "custom_csrf")
    csrf = login(client)
    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.post("/api/v1/auth/logout", headers={"x-csrf-token": csrf}).status_code == 200


def test_overlong_password_not_silently_truncated():
    hashed = hash_password("x" * 72)
    assert verify_password("x" * 72, hashed)
    assert not verify_password("x" * 73, hashed)


def test_json_rows_stay_paired_after_decryption_failure(db):
    _seed_configs(db)
    configs = db.query(Configuration).order_by(Configuration.id).all()
    configs[0].raw_link_encrypted = "corrupted"
    db.commit()
    profile = _profile(db, "json")
    profile.sort = "newest"
    result = subscriptions.render(db, profile)
    rows = json.loads(result.content)["configurations"]
    assert result.config_count == 1
    assert rows[0]["id"] == configs[1].id and rows[0]["share_link"] == LINKS[1]


def test_public_format_override_preserves_db_and_supports_persian_title(db, client):
    profile = _profile(db, "plain")
    profile.name = "اشتراک ادن"
    db.commit()
    raw, _ = subscriptions.issue_token(db, profile)
    response = client.get(f"/api/v1/public/subscriptions/{raw}?format=json")
    assert response.status_code == 200
    db.refresh(profile)
    assert profile.export_format == "plain"
    assert response.headers["profile-title"].startswith("base64:")


def test_manual_source_ingests_without_http_and_redacts_secret(admin, db, monkeypatch):
    client = admin["client"]
    response = client.post("/api/v1/sources", json={"name": "Manual regression", "source_type": "manual", "url": VALID_A}, headers={"x-csrf-token": admin["csrf"]})
    assert response.status_code == 201
    source = db.get(Source, response.json()["id"])
    assert source.url.startswith("nexus:fernet:") and VALID_A not in source.url
    assert response.json()["url"] == "<redacted>"
    monkeypatch.setattr(ingestion.SafeFetcher, "fetch", lambda *a, **k: pytest.fail("manual source fetched"))
    run = ingestion.run_pipeline(trigger="test", source_ids=[source.id])
    assert run.new_count == 1
    patched = client.patch(f"/api/v1/sources/{source.id}", json={"url": "<redacted>", "name": "Updated manual"}, headers={"x-csrf-token": admin["csrf"]})
    assert patched.status_code == 200
    db.refresh(source)
    assert adapters.registry.for_source(source).parse_response(source, fetcher.FetchResult(True)).raw_links == [VALID_A]
    assert "aaaaaaaa-1111" not in client.get("/api/v1/sources").text


def test_legacy_plaintext_manual_sources_still_ingest(db, monkeypatch):
    source = _make_source(db, "legacy-manual", VALID_A, "manual")
    assert not adapters.registry.for_source(source).requires_fetch()
    assert adapters.registry.for_source(source).parse_response(source, fetcher.FetchResult(True)).raw_links == [VALID_A]


def test_publication_failure_finishes_pipeline_without_losing_ingestion(db, monkeypatch):
    source = _make_source(db, "publication-failure", VALID_A, "manual")
    def fail(*args, **kwargs):
        raise PermissionError("simulated disk failure")
    monkeypatch.setattr(ingestion.publisher, "publish_bank", fail)
    run = ingestion.run_pipeline(trigger="test", source_ids=[source.id])
    assert run.status == "failed" and run.finished_at is not None
    assert run.error == "publication failed: PermissionError"
    assert db.query(Configuration).count() == 1
    ingestion._assert_not_stale_running(db)


@pytest.mark.parametrize("kwargs", [{"secret_key": "short"}, {"secret_key": "replace-with-openssl-rand-base64-48"}])
def test_production_rejects_weak_key(kwargs):
    with pytest.raises(ValueError):
        Settings(_env_file=None, environment="production", **kwargs)


def test_bootstrap_never_prints_generated_password(db, monkeypatch, capsys):
    monkeypatch.setattr(settings, "bootstrap_admin_password", None)
    # Empty isolated session stub avoids deleting the shared test administrator.
    empty_db = SimpleNamespace(execute=lambda query: SimpleNamespace(scalar_one=lambda: 0))
    with pytest.raises(RuntimeError, match="BOOTSTRAP_ADMIN_PASSWORD"):
        ensure_admin(empty_db)
    assert capsys.readouterr().out == ""


def test_logs_redact_tokens_and_share_links():
    record = logging.LogRecord("test", logging.WARNING, "", 1, "failure /api/v1/public/subscriptions/SECRET and trojan://password@example.com", (), None)
    record.context = {"password": "PRIVATE", "path": "/public/subscriptions/SECRET"}
    for formatter in (JsonFormatter(), TextFormatter()):
        result = formatter.format(record)
        assert "SECRET" not in result and "PRIVATE" not in result and "trojan://" not in result


@pytest.mark.parametrize("path,payload", [("/auth/users/1", {"role": None}), ("/sources/1", {"enabled": None}), ("/subscription-profiles/1", {"filters": None})])
def test_null_updates_return_validation_error(admin, path, payload):
    response = admin["client"].patch("/api/v1" + path, json=payload, headers={"x-csrf-token": admin["csrf"]})
    assert response.status_code == 422


def test_missing_persistent_key_rejected(monkeypatch):
    monkeypatch.delenv("SECRET_KEY")
    with pytest.raises(ValueError, match="persistent SECRET_KEY"):
        Settings(_env_file=None, environment="development")


def test_offline_upstream_mode_never_creates_client(monkeypatch):
    from app.services import upstream
    monkeypatch.setattr(settings, "upstream_enabled", False)
    monkeypatch.setattr(upstream.httpx, "Client", lambda **kwargs: pytest.fail("offline upstream opened a client"))
    assert not upstream.upstream_status(force=True)["available"]
    assert upstream.workflow_runs()["runs"] == []


@pytest.mark.parametrize("link", ["vless://not-a-uuid@node.example:443", "vmess://eyJhZGQiOiJub2RlLmV4YW1wbGUiLCJwb3J0Ijo0NDMsImlkIjoibm90LWEtdXVpZCJ9"])
def test_uuid_protocols_reject_malformed_credentials(link):
    from app.services.parsers import ParseError, parse_share_link
    with pytest.raises(ParseError, match="UUID"):
        parse_share_link(link)
