"""Configuration Explorer: browsing, filtering and safe detail views."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, client_ip, require_admin, require_auth, require_csrf
from app.core.db import get_db
from app.models import Configuration, ConfigurationSource, Source
from app.schemas import BulkFavorite, ConfigurationUpdate
from app.services import audit

router = APIRouter(prefix="/configurations", tags=["configurations"])


@router.get("")
def list_configurations(
    search: str | None = Query(default=None, max_length=120),
    protocol: str | None = Query(default=None, max_length=20),
    source_id: int | None = Query(default=None),
    connectivity: str | None = Query(default=None, max_length=20),
    transport: str | None = Query(default=None, max_length=30),
    favorites: bool | None = Query(default=None),
    sort: str = Query(default="newest", pattern="^(newest|latency|host|protocol|seen)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    context: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    query = select(Configuration)
    if search:
        like = f"%{search}%"
        query = query.where(
            or_(
                Configuration.host.ilike(like),
                Configuration.protocol.ilike(like),
                Configuration.fingerprint.ilike(like),
                Configuration.sni.ilike(like),
            )
        )
    if protocol:
        query = query.where(Configuration.protocol == protocol)
    if connectivity:
        query = query.where(Configuration.connectivity_status == connectivity)
    if transport:
        query = query.where(Configuration.transport == transport)
    if favorites is not None:
        query = query.where(Configuration.is_favorite.is_(favorites))
    if source_id:
        query = query.where(
            Configuration.id.in_(
                select(ConfigurationSource.configuration_id).where(ConfigurationSource.source_id == source_id)
            )
        )

    order = {
        "newest": desc(Configuration.first_seen_at),
        "latency": asc(Configuration.last_latency_ms).nullslast(),
        "host": asc(Configuration.host),
        "protocol": asc(Configuration.protocol),
        "seen": desc(Configuration.last_seen_at),
    }[sort]

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = db.execute(query.order_by(order, Configuration.id.asc()).offset((page - 1) * page_size).limit(page_size)).scalars().all()

    source_map: dict[int, list[dict]] = {}
    ids = [config.id for config in rows]
    if ids:
        links = db.execute(
            select(ConfigurationSource.configuration_id, Source.id, Source.name, Source.slug)
            .join(Source, Source.id == ConfigurationSource.source_id)
            .where(ConfigurationSource.configuration_id.in_(ids))
        ).all()
        for config_id, source_id, name, slug in links:
            source_map.setdefault(config_id, []).append({"id": source_id, "name": name, "slug": slug})

    from app.api.serializers import configuration_out

    return {
        "items": [configuration_out(config, source_map.get(config.id, [])) for config in rows],
        "page": page,
        "page_size": page_size,
        "total": int(total),
        "pages": max(1, (int(total) + page_size - 1) // page_size),
        "note": "Share links and credentials are never included in listings.",
    }


@router.get("/facets")
def facets(context: AuthContext = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    protocols = db.execute(
        select(Configuration.protocol, func.count(Configuration.id)).group_by(Configuration.protocol)
    ).all()
    transports = db.execute(
        select(Configuration.transport, func.count(Configuration.id)).group_by(Configuration.transport)
    ).all()
    connectivity = db.execute(
        select(Configuration.connectivity_status, func.count(Configuration.id)).group_by(Configuration.connectivity_status)
    ).all()
    sources = db.execute(select(Source.id, Source.name).where(Source.enabled.is_(True)).order_by(Source.name)).all()
    return {
        "protocols": [{"value": value, "count": int(count)} for value, count in protocols],
        "transports": [{"value": value, "count": int(count)} for value, count in transports],
        "connectivity": [{"value": value, "count": int(count)} for value, count in connectivity],
        "sources": [{"id": source_id, "name": name} for source_id, name in sources],
    }


@router.get("/{config_id}")
def configuration_detail(
    config_id: int,
    context: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    config = db.get(Configuration, config_id)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")
    from app.api.serializers import configuration_detail as serialize

    return serialize(db, config)


@router.patch("/{config_id}")
def update_configuration(
    config_id: int,
    payload: ConfigurationUpdate,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict:
    config = db.get(Configuration, config_id)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(config, field, value)
    db.commit()
    audit.record(
        db,
        action="configuration.updated",
        user=context.user,
        target_type="configuration",
        target_id=config.id,
        detail={"fields": sorted(changes.keys())},
    )
    from app.api.serializers import configuration_detail as serialize

    return serialize(db, config)


@router.post("/bulk-favorite")
def bulk_favorite(
    payload: BulkFavorite,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict:
    rows = db.execute(select(Configuration).where(Configuration.id.in_(payload.ids))).scalars().all()
    for config in rows:
        config.is_favorite = payload.favorite
    db.commit()
    audit.record(
        db,
        action="configuration.bulk_favorite",
        user=context.user,
        target_type="configuration",
        target_id=None,
        detail={"count": len(rows), "favorite": payload.favorite},
    )
    return {"updated": len(rows), "favorite": payload.favorite}
