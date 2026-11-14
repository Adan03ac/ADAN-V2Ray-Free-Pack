"""Source Intelligence: registry management, history and manual refresh."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, client_ip, rate_limit, require_auth, require_csrf
from app.core.db import get_db
from app.core.security import encrypt_secret
from app.models import ConfigurationSource, Source, SourceFetch
from app.schemas import SourceCreate, SourceOut, SourceUpdate
from app.services import audit
from app.services.adapters import registry
from app.services.fetcher import UnsafeUrlError, validate_source_url
from app.services.ingestion import PipelineBusy, start_pipeline_async

router = APIRouter(prefix="/sources", tags=["sources"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:110]
    return slug or "source"


@router.get("")
def list_sources(
    search: str | None = Query(default=None, max_length=120),
    source_type: str | None = Query(default=None, max_length=40),
    enabled: bool | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status", pattern="^(ok|error|never)$"),
    sort: str = Query(default="name", pattern="^(name|config_count|last_success|errors|type)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    context: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    query = select(Source)
    if search:
        like = f"%{search}%"
        query = query.where(or_(Source.name.ilike(like), Source.url.ilike(like), Source.slug.ilike(like)))
    if source_type:
        query = query.where(Source.source_type == source_type)
    if enabled is not None:
        query = query.where(Source.enabled.is_(enabled))
    if status_filter == "ok":
        query = query.where(Source.consecutive_failures == 0, Source.last_success_at.is_not(None))
    elif status_filter == "error":
        query = query.where(Source.consecutive_failures > 0)
    elif status_filter == "never":
        query = query.where(Source.last_attempted_at.is_(None))

    order = {
        "name": Source.name.asc(),
        "config_count": desc(Source.config_count),
        "last_success": desc(Source.last_success_at).nullslast(),
        "errors": desc(Source.consecutive_failures),
        "type": Source.source_type.asc(),
    }[sort]
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = db.execute(query.order_by(order).offset((page - 1) * page_size).limit(page_size)).scalars().all()
    from app.api.serializers import source_out

    return {
        "items": [source_out(source) for source in rows],
        "page": page,
        "page_size": page_size,
        "total": int(total),
        "pages": max(1, (int(total) + page_size - 1) // page_size),
        "supported_types": registry.supported_types(),
    }


@router.get("/{source_id}")
def source_detail(
    source_id: int,
    context: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    from app.api.serializers import source_out

    fetches = db.execute(
        select(SourceFetch).where(SourceFetch.source_id == source_id).order_by(desc(SourceFetch.started_at)).limit(20)
    ).scalars().all()
    provenance = db.execute(
        select(
            func.count(ConfigurationSource.id),
            func.coalesce(func.sum(ConfigurationSource.occurrences), 0),
        ).where(ConfigurationSource.source_id == source_id)
    ).one()
    return {
        "source": source_out(source),
        "fetches": [
            {
                "id": fetch.id,
                "status": fetch.status,
                "started_at": fetch.started_at,
                "finished_at": fetch.finished_at,
                "http_status": fetch.http_status,
                "bytes_read": fetch.bytes_read,
                "parsed_count": fetch.parsed_count,
                "accepted_count": fetch.accepted_count,
                "duplicate_count": fetch.duplicate_count,
                "invalid_count": fetch.invalid_count,
                "duration_ms": round(fetch.duration_ms, 1) if fetch.duration_ms else None,
                "error": fetch.error,
                "invalid_samples": fetch.invalid_samples,
                "metadata": fetch.fetch_metadata,
            }
            for fetch in fetches
        ],
        "contribution": {
            "configurations": int(provenance[0]),
            "occurrences": int(provenance[1]),
            "duplicates_within_latest_fetch": source.duplicate_count,
        },
    }


@router.post("", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
def create_source(
    payload: SourceCreate,
    request: Request,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> SourceOut:
    rate_limit(request, "source_write", limit=30)
    if payload.source_type != "manual":
        try:
            validate_source_url(payload.url)
        except UnsafeUrlError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    slug = payload.slug or _slugify(payload.name)
    if db.execute(select(Source).where(Source.slug == slug)).scalars().first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A source with this slug already exists")
    source = Source(
        slug=slug,
        name=payload.name,
        url=("nexus:fernet:" + encrypt_secret(payload.url.strip())) if payload.source_type == "manual" else payload.url.strip(),
        source_type=payload.source_type,
        enabled=payload.enabled,
        is_discovery=payload.source_type == "html_discovery",
        trust_level=payload.trust_level,
        tags=payload.tags,
        refresh_interval_minutes=payload.refresh_interval_minutes,
        notes=payload.notes,
    )
    db.add(source)
    db.commit()
    audit.record(
        db,
        action="source.created",
        user=context.user,
        target_type="source",
        target_id=source.id,
        ip_address=client_ip(request),
        detail={"slug": source.slug, "type": source.source_type},
    )
    from app.api.serializers import source_out

    return SourceOut(**source_out(source))


@router.patch("/{source_id}", response_model=SourceOut)
def update_source(
    source_id: int,
    payload: SourceUpdate,
    request: Request,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> SourceOut:
    rate_limit(request, "source_write", limit=60)
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("url") == "<redacted>" and source.source_type == "manual":
        changes.pop("url")
    if "source_type" in changes and changes["source_type"] != source.source_type and "url" not in changes:
        raise HTTPException(status_code=422, detail="A new URL is required when changing source type")
    if "url" in changes and changes["url"]:
        source_type = changes.get("source_type", source.source_type)
        if source_type != "manual":
            try:
                validate_source_url(changes["url"])
            except UnsafeUrlError as exc:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        else:
            changes["url"] = "nexus:fernet:" + encrypt_secret(changes["url"].strip())
        source.etag = None
        source.last_modified = None
    if "source_type" in changes and changes["source_type"]:
        source.is_discovery = changes["source_type"] == "html_discovery"
    for field, value in changes.items():
        setattr(source, field, value)
    source.updated_at = datetime.now(timezone.utc)
    db.commit()
    audit.record(
        db,
        action="source.updated",
        user=context.user,
        target_type="source",
        target_id=source.id,
        ip_address=client_ip(request),
        detail={"fields": sorted(changes.keys())},
    )
    from app.api.serializers import source_out

    return SourceOut(**source_out(source))


@router.post("/{source_id}/refresh", status_code=status.HTTP_202_ACCEPTED)
def refresh_source(
    source_id: int,
    request: Request,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict:
    rate_limit(request, "source_refresh", limit=6, window_seconds=60)
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    if not source.enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Source is disabled")
    try:
        start_pipeline_async(trigger="manual", source_ids=[source.id], actor=context.user.email)
    except PipelineBusy as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    audit.record(
        db,
        action="source.refresh_requested",
        user=context.user,
        target_type="source",
        target_id=source.id,
        ip_address=client_ip(request),
    )
    return {"accepted": True, "detail": "Refresh queued. Track progress in the Automation Center."}
