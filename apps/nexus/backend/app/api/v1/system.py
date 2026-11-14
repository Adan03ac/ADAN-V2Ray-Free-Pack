"""System health, settings, publication status and audit logs."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import desc, select, text
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, client_ip, require_admin, require_auth, require_csrf
from app.core.config import settings
from app.core.db import get_db
from app.models import AuditLog, Setting, utcnow
from app.schemas import SettingsPatch
from app.services import audit
from app.workers.scheduler import scheduler

router = APIRouter(prefix="/system", tags=["system"])
STARTED_AT = time.time()
VERSION = "1.0.0-mvp"


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    database_ok = True
    database_error = None
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - only on a broken database
        database_ok = False
        database_error = f"{type(exc).__name__}"
    publish_dir = Path(settings.publish_dir)
    publish_writable = False
    try:
        publish_dir.mkdir(parents=True, exist_ok=True)
        probe = publish_dir / ".write-probe"
        probe.write_text("ok", "utf-8")
        publish_writable = True
        probe.unlink(missing_ok=True)
    except OSError:
        publish_writable = False
    return {
        "status": "ok" if database_ok else "degraded",
        "service": settings.app_name,
        "version": VERSION,
        "environment": settings.environment,
        "server_time_utc": utcnow().isoformat(),
        "uptime_seconds": round(time.time() - STARTED_AT, 1),
        "checks": {
            "database": {"ok": database_ok, "error": database_error},
            "scheduler": {"ok": scheduler.is_running(), "enabled": settings.ingestion_enabled},
            "publication": {"ok": publish_writable, "mode": settings.publish_mode},
            "cache": {"ok": True, "backend": "redis" if settings.redis_url else "memory"},
        },
        "printable_note": "Readiness reflects this process only; it does not assert upstream feed health.",
    }


@router.get("/settings")
def get_settings(
    context: AuthContext = Depends(require_auth), db: Session = Depends(get_db)
) -> dict:
    rows = db.execute(select(Setting).order_by(Setting.key)).scalars().all()
    return {
        "items": [
            {"key": row.key, "value": row.value, "updated_at": row.updated_at}
            for row in rows
        ],
        "runtime": {
            "ingestion_interval_minutes": settings.ingestion_interval_minutes,
            "health_concurrency": settings.health_concurrency,
            "health_timeout_seconds": settings.health_timeout_seconds,
            "health_max_batch": settings.health_max_batch,
            "retention_pipeline_days": settings.retention_pipeline_days,
            "retention_fetch_days": settings.retention_fetch_days,
            "retention_health_days": settings.retention_health_days,
            "publish_mode": settings.publish_mode,
            "cloudflare_enabled": settings.cloudflare_enabled,
            "environment": settings.environment,
        },
        "capabilities": {
            "subscription_formats": ["plain", "base64", "json"],
            "health_stages": ["syntax", "dns", "tcp"],
            "cloudflare_deployments": False,
            "end_to_end_verification": False,
            "iran_testing_agent": False,
        },
    }


@router.patch("/settings")
def patch_setting(
    payload: SettingsPatch,
    request: Request,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict:
    """Store operator preferences. Environment-level limits stay authoritative."""
    allowed = {
        "ingestion",
        "health",
        "retention",
        "subscription",
        "ui",
        "alerts",
    }
    if payload.key not in allowed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown settings namespace")
    row = db.get(Setting, payload.key)
    if row is None:
        row = Setting(key=payload.key, value=payload.value, updated_by=context.user.id)
        db.add(row)
    else:
        row.value = {**(row.value or {}), **payload.value}
        row.updated_by = context.user.id
        row.updated_at = utcnow()
    db.commit()
    audit.record(
        db,
        action="system.settings_updated",
        user=context.user,
        target_type="settings",
        target_id=payload.key,
        ip_address=client_ip(request),
        detail={"keys": sorted(payload.value.keys())},
    )
    return {"key": row.key, "value": row.value, "note": "Environment variables override stored preferences at boot."}


@router.get("/audit-logs")
def audit_logs(
    limit: int = 50,
    context: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    rows = db.execute(select(AuditLog).order_by(desc(AuditLog.created_at)).limit(max(1, min(limit, 200)))).scalars().all()
    return {
        "items": [
            {
                "id": row.id,
                "actor": row.actor_email,
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "outcome": row.outcome,
                "ip_address": row.ip_address,
                "detail": row.detail,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }


@router.get("/publication")
def publication(context: AuthContext = Depends(require_auth)) -> dict:
    root = Path(settings.publish_dir)
    manifest_path = root / "manifest.json"
    manifest = None
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = None
    files = []
    if root.exists():
        for path in sorted(root.glob("*.*")):
            if path.is_file():
                stat = path.stat()
                files.append(
                    {
                        "name": path.name,
                        "bytes": stat.st_size,
                        "modified_at": utcnow().fromtimestamp(stat.st_mtime).isoformat(),
                    }
                )
    return {
        "mode": settings.publish_mode,
        "directory": str(root),
        "manifest": manifest,
        "files": files,
        "statement": (
            "Local publication only. The GitHub Actions workflow remains the public publisher and "
            "works independently of this application."
        ),
    }
