"""Subscription Studio exports with revocable, hashed access tokens."""

from __future__ import annotations

import base64
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decrypt_secret, token_hash
from app.models import Configuration, ConfigurationSource, SubscriptionProfile, SubscriptionToken, utcnow

EXPORT_FORMATS = ("plain", "base64", "json")
SORT_OPTIONS = ("latency_asc", "newest", "recently_seen", "protocol")
MAX_EXPORT = 500


@dataclass
class RenderedSubscription:
    content: str
    media_type: str
    config_count: int
    total_matched: int


def _apply_filters(query, filters: dict):  # type: ignore[no-untyped-def]
    if filters.get("protocols"):
        query = query.where(Configuration.protocol.in_(filters["protocols"]))
    if filters.get("connectivity"):
        query = query.where(Configuration.connectivity_status.in_(filters["connectivity"]))
    if filters.get("transports"):
        query = query.where(Configuration.transport.in_(filters["transports"]))
    if filters.get("source_ids"):
        query = query.where(
            Configuration.id.in_(
                select(ConfigurationSource.configuration_id).where(
                    ConfigurationSource.source_id.in_(filters["source_ids"])
                )
            )
        )
    if filters.get("search"):
        term = f"%{filters['search'][:80]}%"
        query = query.where(Configuration.host.ilike(term) | Configuration.protocol.ilike(term))
    return query


def build_query(profile: SubscriptionProfile):
    filters = profile.filters or {}
    query = select(Configuration).where(Configuration.validation_status == "valid")
    query = _apply_filters(query, filters)
    if profile.favorites_only:
        query = query.where(Configuration.is_favorite.is_(True))
    excluded = [int(value) for value in (profile.exclude_ids or []) if isinstance(value, (int, str)) and str(value).isdigit()]
    if excluded:
        query = query.where(Configuration.id.notin_(excluded[:500]))
    return query


def _sorted(query, sort: str):
    if sort == "newest":
        return query.order_by(Configuration.first_seen_at.desc())
    if sort == "recently_seen":
        return query.order_by(Configuration.last_seen_at.desc())
    if sort == "protocol":
        return query.order_by(Configuration.protocol.asc(), Configuration.last_latency_ms.asc().nullslast())
    return query.order_by(Configuration.last_latency_ms.asc().nullslast(), Configuration.first_seen_at.desc())


def render(db: Session, profile: SubscriptionProfile, export_format: str | None = None) -> RenderedSubscription:
    limit = max(1, min(profile.max_configs or 50, MAX_EXPORT))
    statement = _sorted(build_query(profile), profile.sort).limit(limit)
    matched = list(db.execute(statement).scalars().all())
    total_matched = int(
        db.execute(select(func.count()).select_from(build_query(profile).subquery())).scalar_one()
    )
    links: list[str] = []
    export_rows = []
    for config in matched:
        link = decrypt_secret(config.raw_link_encrypted)
        if link:
            links.append(link)
            export_rows.append((config, link))

    export_format = export_format or profile.export_format
    export_format = export_format if export_format in EXPORT_FORMATS else "base64"
    if export_format == "json":
        payload = [
            {
                "id": config.id,
                "protocol": config.protocol,
                "host": config.host,
                "port": config.port,
                "transport": config.transport,
                "security": config.security,
                "sni": config.sni,
                "latency_ms": config.last_latency_ms,
                "connectivity": config.connectivity_status,
                "share_link": link,
            }
            for config, link in export_rows
        ]
        content = json.dumps(
            {
                "generated_at": utcnow().isoformat(),
                "profile": profile.name,
                "count": len(payload),
                "configurations": payload,
            },
            indent=2,
        )
        media_type = "application/json"
    else:
        plain = "\n".join(links) + ("\n" if links else "")
        if export_format == "base64":
            content = base64.b64encode(plain.encode("utf-8")).decode("ascii")
            media_type = "text/plain"
        else:
            content = plain
            media_type = "text/plain"

    profile.last_generated_at = utcnow()
    profile.last_config_count = len(links)
    db.commit()
    return RenderedSubscription(content=content, media_type=media_type, config_count=len(links), total_matched=total_matched)


def preview(db: Session, profile: SubscriptionProfile) -> dict:
    limit = max(1, min(profile.max_configs or 50, MAX_EXPORT))
    rows = list(db.execute(_sorted(build_query(profile), profile.sort).limit(limit)).scalars().all())
    library_size = int(
        db.execute(
            select(func.count(Configuration.id)).where(Configuration.validation_status == "valid")
        ).scalar_one()
    )
    return {
        "preview": [
            {
                "id": config.id,
                "protocol": config.protocol,
                "host": config.host,
                "port": config.port,
                "transport": config.transport,
                "security": config.security,
                "connectivity": config.connectivity_status,
                "latency_ms": config.last_latency_ms,
            }
            for config in rows
        ],
        "returned": len(rows),
        "library_size": library_size,
    }


def issue_token(db: Session, profile: SubscriptionProfile, label: str | None = None) -> tuple[str, SubscriptionToken]:
    raw = secrets.token_urlsafe(24)
    token = SubscriptionToken(
        profile_id=profile.id,
        token_hash=token_hash(raw),
        token_prefix=raw[:8],
        label=label or "Studio token",
        expires_at=None,
    )
    db.add(token)
    db.commit()
    return raw, token


def resolve_token(db: Session, raw_token: str) -> tuple[SubscriptionProfile, SubscriptionToken] | None:
    if not raw_token or len(raw_token) > 120:
        return None
    token = db.execute(
        select(SubscriptionToken).where(SubscriptionToken.token_hash == token_hash(raw_token))
    ).scalars().first()
    if token is None or token.revoked_at is not None:
        return None
    if token.expires_at is not None:
        expires = token.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            return None
    profile = db.get(SubscriptionProfile, token.profile_id)
    if profile is None:
        return None
    token.last_used_at = utcnow()
    token.use_count += 1
    db.commit()
    return profile, token


def subscription_url(raw_token: str, export_format: str = "plain") -> str:
    suffix = "" if export_format in {"plain", "base64"} else f"?format={export_format}"
    return f"{settings.public_base_url.rstrip('/')}{settings.api_v1_prefix}/public/subscriptions/{raw_token}{suffix}"
