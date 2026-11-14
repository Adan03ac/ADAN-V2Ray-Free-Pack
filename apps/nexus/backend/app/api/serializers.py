"""Safe serialization helpers. Credentials never leave the server."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Configuration, ConfigurationSource, Source, SubscriptionToken


def source_out(source: Source) -> dict:
    return {
        "id": source.id,
        "slug": source.slug,
        "name": source.name,
        "url": "<redacted>" if source.source_type == "manual" else source.url,
        "source_type": source.source_type,
        "enabled": source.enabled,
        "is_discovery": source.is_discovery,
        "trust_level": source.trust_level,
        "tags": list(source.tags or []),
        "refresh_interval_minutes": source.refresh_interval_minutes,
        "notes": source.notes,
        "last_attempted_at": source.last_attempted_at,
        "last_success_at": source.last_success_at,
        "last_http_status": source.last_http_status,
        "etag": source.etag,
        "last_modified": source.last_modified,
        "config_count": source.config_count,
        "new_config_count": source.new_config_count,
        "duplicate_count": source.duplicate_count,
        "invalid_count": source.invalid_count,
        "consecutive_failures": source.consecutive_failures,
        "last_error": source.last_error,
        "last_duration_ms": round(source.last_duration_ms, 1) if source.last_duration_ms else None,
    }


def _source_names(db: Session, config_id: int) -> list[dict]:
    rows = db.execute(
        select(Source.id, Source.name, Source.slug)
        .join(ConfigurationSource, ConfigurationSource.source_id == Source.id)
        .where(ConfigurationSource.configuration_id == config_id)
    ).all()
    return [{"id": source_id, "name": name, "slug": slug} for source_id, name, slug in rows]


def configuration_out(config: Configuration, sources: list[dict] | None = None) -> dict:
    return {
        "id": config.id,
        "fingerprint": config.fingerprint,
        "protocol": config.protocol,
        "host": config.host,
        "port": config.port,
        "transport": config.transport,
        "security": config.security,
        "sni": config.sni,
        "credential_hint": config.credential_hint,
        "validation_status": config.validation_status,
        "connectivity_status": config.connectivity_status,
        "last_tested_at": config.last_tested_at,
        "last_latency_ms": config.last_latency_ms,
        "latency_avg_ms": config.latency_avg_ms,
        "test_agent": config.test_agent,
        "first_seen_at": config.first_seen_at,
        "last_seen_at": config.last_seen_at,
        "source_count": config.source_count,
        "failure_count": config.failure_count,
        "tags": list(config.tags or []),
        "notes": config.notes,
        "is_favorite": config.is_favorite,
        "sources": sources or [],
    }


def configuration_detail(db: Session, config: Configuration) -> dict:
    payload = configuration_out(config, _source_names(db, config.id))
    payload["latency_samples"] = [value for value in (config.latency_samples or []) if isinstance(value, (int, float))]
    payload["canonical_endpoint"] = config.canonical_endpoint
    rows = db.execute(
        select(
            Source.id,
            Source.name,
            Source.slug,
            ConfigurationSource.first_seen_at,
            ConfigurationSource.last_seen_at,
            ConfigurationSource.occurrences,
        )
        .join(ConfigurationSource, ConfigurationSource.source_id == Source.id)
        .where(ConfigurationSource.configuration_id == config.id)
    ).all()
    payload["source_links"] = [
        {
            "source_id": row[0],
            "name": row[1],
            "slug": row[2],
            "first_seen_at": row[3],
            "last_seen_at": row[4],
            "occurrences": row[5],
        }
        for row in rows
    ]
    return payload


def token_out(token: SubscriptionToken, include_secret: str | None = None) -> dict:
    payload = {
        "id": token.id,
        "token_prefix": token.token_prefix,
        "label": token.label,
        "created_at": token.created_at,
        "expires_at": token.expires_at,
        "revoked_at": token.revoked_at,
        "last_used_at": token.last_used_at,
        "use_count": token.use_count,
    }
    if include_secret:
        payload["token"] = include_secret
    return payload
