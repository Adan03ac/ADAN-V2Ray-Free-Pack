"""Idempotent bootstrap: admin account, real source registry entries, defaults."""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models import Setting, Source, User
from app.services.fetcher import UnsafeUrlError, validate_source_url

logger = logging.getLogger("nexus.seed")

DEFAULT_SOURCES: list[dict] = [
    {
        "slug": "eevanescence-4diana",
        "name": "4Diana — AllConfigsSub",
        "url": "https://raw.githubusercontent.com/EEvanescence/4Diana/main/AllConfigsSub.txt",
        "source_type": "github_raw",
        "trust_level": "community",
        "tags": ["github", "direct-feed"],
    },
    {
        "slug": "hidashimora-anti-rkn",
        "name": "free-vpn-anti-rkn — configs/1.1",
        "url": "https://raw.githubusercontent.com/Hidashimora/free-vpn-anti-rkn/main/configs/1.1.txt",
        "source_type": "github_raw",
        "trust_level": "community",
        "tags": ["github", "direct-feed"],
    },
    {
        "slug": "barry-far-v2ray-config",
        "name": "barry-far — All_Configs_Sub",
        "url": "https://raw.githubusercontent.com/barry-far/V2ray-config/main/All_Configs_Sub.txt",
        "source_type": "github_raw",
        "trust_level": "community",
        "tags": ["github", "direct-feed"],
    },
    {
        "slug": "adan-public-bank",
        "name": "ADAN published bank (mirror)",
        "url": f"https://raw.githubusercontent.com/{settings.upstream_repo}/{settings.upstream_branch}/subscription.txt",
        "source_type": "github_raw",
        "trust_level": "community",
        "tags": ["upstream-bank", "mirror", "hourly"],
        "notes": "Read-only mirror of the existing public bank produced by build.py.",
    },
    {
        "slug": "hidashimora-discovery",
        "name": "free-vpn-anti-rkn (discovery page)",
        "url": "https://hidashimora.github.io/free-vpn-anti-rkn/",
        "source_type": "html_discovery",
        "trust_level": "unknown",
        "tags": ["discovery"],
        "enabled": False,
        "notes": "HTML landing page. Discovery only, never ingested as a feed.",
    },
    {
        "slug": "smbcryp-discovery",
        "name": "V2V (discovery page)",
        "url": "https://smbcryp.github.io/V2V/",
        "source_type": "html_discovery",
        "trust_level": "unknown",
        "tags": ["discovery"],
        "enabled": False,
        "notes": "HTML landing page. Discovery only, never ingested as a feed.",
    },
]

DEFAULT_SETTINGS: dict[str, dict] = {
    "ingestion": {"interval_minutes": 60, "enabled": True, "retry_attempts": 2},
    "health": {"concurrency": 8, "timeout_seconds": 3.0, "max_batch": 50, "tcp_enabled": True},
    "retention": {"pipeline_days": 90, "fetch_days": 30, "health_days": 90},
    "subscription": {"default_max_configs": 50, "token_ttl_days": None},
    "ui": {"default_language": "en", "default_theme": "dark"},
}


def ensure_admin(db: Session) -> User | None:
    total = db.execute(select(func.count(User.id))).scalar_one()
    if total:
        return None
    password = settings.bootstrap_admin_password
    if not password:
        raise RuntimeError("Set BOOTSTRAP_ADMIN_PASSWORD before first startup")
    user = User(
        email=settings.bootstrap_admin_email.lower(),
        password_hash=hash_password(password),
        display_name=settings.bootstrap_admin_name,
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def ensure_sources(db: Session) -> int:
    created = 0
    for entry in DEFAULT_SOURCES:
        exists = db.execute(select(Source).where(Source.slug == entry["slug"])).scalars().first()
        if exists:
            continue
        try:
            validate_source_url(entry["url"], resolve_dns=False)
        except UnsafeUrlError as exc:  # pragma: no cover - defensive
            logger.error("default source rejected by SSRF policy", extra={"context": {"slug": entry["slug"], "error": str(exc)}})
            continue
        db.add(
            Source(
                slug=entry["slug"],
                name=entry["name"],
                url=entry["url"],
                source_type=entry["source_type"],
                trust_level=entry["trust_level"],
                tags=entry["tags"],
                enabled=entry.get("enabled", True),
                is_discovery=entry["source_type"] == "html_discovery",
                notes=entry.get("notes"),
            )
        )
        created += 1
    db.commit()
    return created


def ensure_settings(db: Session) -> None:
    for key, value in DEFAULT_SETTINGS.items():
        if db.get(Setting, key) is None:
            db.add(Setting(key=key, value=value))
    db.commit()


def bootstrap(db: Session) -> dict[str, int | str | None]:
    admin = ensure_admin(db)
    sources = ensure_sources(db)
    ensure_settings(db)
    return {
        "admin_created": bool(admin),
        "admin_email": admin.email if admin else None,
        "sources_created": sources,
    }
