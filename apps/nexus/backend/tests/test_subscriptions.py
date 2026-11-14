"""Subscription exports, revocable tokens and the public endpoint."""

from __future__ import annotations

import base64
from uuid import uuid4

from app.core.security import encrypt_secret
from app.models import Configuration, SubscriptionProfile, SubscriptionToken
from app.services import subscriptions

LINKS = [
    "vless://aaaaaaaa-1111-2222-3333-444444444444@198.51.100.20:443?type=ws&security=tls&sni=x.example.com#X",
    "trojan://pw@198.51.100.21:443?sni=y.example.com#Y",
]


def _seed_configs(db) -> None:
    for index, link in enumerate(LINKS):
        fingerprint = uuid4().hex[:48]
        db.add(
            Configuration(
                fingerprint=fingerprint,
                protocol="vless" if index == 0 else "trojan",
                host=f"198.51.100.2{index}",
                port=443,
                transport="ws",
                security="tls",
                canonical_endpoint=f"test|{index}",
                credential_hint="aaaa…aa",
                raw_link_encrypted=encrypt_secret(link),
                raw_link_length=len(link),
            )
        )
    db.commit()


def _profile(db, export_format: str = "base64") -> SubscriptionProfile:
    profile = SubscriptionProfile(
        user_id=1,
        name="Test profile",
        filters={},
        max_configs=10,
        sort="latency_asc",
        export_format=export_format,
        favorites_only=False,
        exclude_ids=[],
    )
    db.add(profile)
    db.commit()
    return profile


def test_render_plain_base64_json(db):
    _seed_configs(db)
    plain = subscriptions.render(db, _profile(db, "plain"))
    assert plain.config_count == 2
    schemes = {line.split("://", 1)[0] for line in plain.content.strip().splitlines()}
    assert schemes == {"vless", "trojan"}

    base64_profile = _profile(db, "base64")
    encoded = subscriptions.render(db, base64_profile)
    decoded = base64.b64decode(encoded.content).decode()
    assert decoded.count("://") == 2

    json_profile = _profile(db, "json")
    rendered_json = subscriptions.render(db, json_profile)
    assert '"configurations"' in rendered_json.content


def test_filters_and_excludes(db):
    _seed_configs(db)
    profile = _profile(db)
    profile.filters = {"protocols": ["trojan"]}
    db.commit()
    rendered = subscriptions.render(db, profile)
    assert rendered.config_count == 1

    profile.filters = {}
    first = db.query(Configuration).first()
    profile.exclude_ids = [first.id]
    db.commit()
    assert subscriptions.render(db, profile).config_count == 1


def test_token_lifecycle_and_revocation(db, client):
    _seed_configs(db)
    profile = _profile(db)
    raw, token = subscriptions.issue_token(db, profile, label="unit")
    resolved = subscriptions.resolve_token(db, raw)
    assert resolved is not None and resolved[0].id == profile.id

    response = client.get(f"/api/v1/public/subscriptions/{raw}")
    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("no-store")
    assert response.headers["x-config-count"] == "2"

    json_response = client.get(f"/api/v1/public/subscriptions/{raw}?format=json")
    assert json_response.status_code == 200
    assert json_response.headers["content-type"].startswith("application/json")

    token.revoked_at = subscriptions.utcnow()
    db.commit()
    assert subscriptions.resolve_token(db, raw) is None
    assert client.get(f"/api/v1/public/subscriptions/{raw}").status_code == 404
    assert client.get("/api/v1/public/subscriptions/not-a-real-token").status_code == 404


def test_token_is_stored_hashed(db):
    _seed_configs(db)
    profile = _profile(db)
    raw, token = subscriptions.issue_token(db, profile)
    assert raw not in token.token_hash
    assert len(token.token_hash) == 64
    assert db.query(SubscriptionToken).count() == 1
