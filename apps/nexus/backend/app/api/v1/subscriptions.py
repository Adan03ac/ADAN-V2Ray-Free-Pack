"""Subscription Studio: profiles, previews, exports and revocable tokens."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, client_ip, rate_limit, require_admin, require_auth, require_csrf
from app.api.serializers import token_out
from app.core.db import get_db
from app.models import SubscriptionProfile, SubscriptionToken, utcnow
from app.schemas import ProfileCreate, ProfileOut, ProfileUpdate, TokenCreate
from app.services import audit, subscriptions

router = APIRouter(prefix="/subscription-profiles", tags=["subscriptions"])


def _profile_out(db: Session, profile: SubscriptionProfile) -> dict:
    tokens = db.execute(
        select(SubscriptionToken)
        .where(SubscriptionToken.profile_id == profile.id)
        .order_by(desc(SubscriptionToken.created_at))
    ).scalars().all()
    payload = ProfileOut(
        id=profile.id,
        name=profile.name,
        description=profile.description,
        filters=profile.filters or {},
        max_configs=profile.max_configs,
        sort=profile.sort,
        export_format=profile.export_format,
        favorites_only=profile.favorites_only,
        exclude_ids=[int(value) for value in (profile.exclude_ids or []) if str(value).isdigit()],
        last_generated_at=profile.last_generated_at,
        last_config_count=profile.last_config_count,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
        tokens=[token_out(token) for token in tokens],
    )
    return payload.model_dump(mode="json")


def _get_profile(db: Session, profile_id: int, context: AuthContext) -> SubscriptionProfile:
    profile = db.get(SubscriptionProfile, profile_id)
    if profile is None or (context.user.role != "admin" and profile.user_id != context.user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile


@router.get("")
def list_profiles(
    context: AuthContext = Depends(require_auth), db: Session = Depends(get_db)
) -> dict:
    query = select(SubscriptionProfile).order_by(SubscriptionProfile.updated_at.desc())
    if context.user.role != "admin":
        query = query.where(SubscriptionProfile.user_id == context.user.id)
    rows = db.execute(query).scalars().all()
    return {"items": [_profile_out(db, profile) for profile in rows]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_profile(
    payload: ProfileCreate,
    request: Request,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict:
    rate_limit(request, "profile_write", limit=20)
    profile = SubscriptionProfile(
        user_id=context.user.id,
        name=payload.name,
        description=payload.description,
        filters=payload.filters.model_dump(),
        max_configs=payload.max_configs,
        sort=payload.sort,
        export_format=payload.export_format,
        favorites_only=payload.favorites_only,
        exclude_ids=payload.exclude_ids,
    )
    db.add(profile)
    db.commit()
    audit.record(
        db,
        action="subscription_profile.created",
        user=context.user,
        target_type="subscription_profile",
        target_id=profile.id,
        ip_address=client_ip(request),
        detail={"name": profile.name},
    )
    return _profile_out(db, profile)


@router.patch("/{profile_id}")
def update_profile(
    profile_id: int,
    payload: ProfileUpdate,
    request: Request,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict:
    profile = _get_profile(db, profile_id, context)
    changes = payload.model_dump(exclude_unset=True)
    if "filters" in changes and changes["filters"] is not None:
        changes["filters"] = payload.filters.model_dump() if payload.filters else {}
    for field, value in changes.items():
        setattr(profile, field, value)
    db.commit()
    audit.record(
        db,
        action="subscription_profile.updated",
        user=context.user,
        target_type="subscription_profile",
        target_id=profile.id,
        ip_address=client_ip(request),
        detail={"fields": sorted(changes.keys())},
    )
    return _profile_out(db, profile)


@router.delete("/{profile_id}", status_code=status.HTTP_200_OK)
def delete_profile(
    profile_id: int,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict:
    profile = _get_profile(db, profile_id, context)
    db.delete(profile)
    db.commit()
    audit.record(
        db,
        action="subscription_profile.deleted",
        user=context.user,
        target_type="subscription_profile",
        target_id=profile_id,
    )
    return {"deleted": True}


@router.get("/{profile_id}/preview")
def preview_profile(
    profile_id: int,
    context: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    profile = _get_profile(db, profile_id, context)
    body = subscriptions.preview(db, profile)
    body["export_format"] = profile.export_format
    body["profile"] = _profile_out(db, profile)
    return body


@router.post("/{profile_id}/render")
def render_profile(
    profile_id: int,
    request: Request,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict:
    """Create (or reuse) a revocable token and return the generated subscription URL."""
    rate_limit(request, "subscription_render", limit=20)
    profile = _get_profile(db, profile_id, context)
    raw_token, token = subscriptions.issue_token(db, profile)
    rendered = subscriptions.render(db, profile)
    audit.record(
        db,
        action="subscription.rendered",
        user=context.user,
        target_type="subscription_profile",
        target_id=profile.id,
        ip_address=client_ip(request),
        detail={"count": rendered.config_count, "format": profile.export_format},
    )
    return {
        "token": raw_token,
        "token_prefix": token.token_prefix,
        "token_id": token.id,
        "url": subscriptions.subscription_url(raw_token, profile.export_format),
        "config_count": rendered.config_count,
        "matched": rendered.total_matched,
        "generated_at": profile.last_generated_at,
        "format": profile.export_format,
        "note": "The full token is shown once. Revoke it to disable the URL immediately.",
    }


@router.get("/{profile_id}/export")
def export_profile(
    profile_id: int,
    context: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Response:
    profile = _get_profile(db, profile_id, context)
    rendered = subscriptions.render(db, profile)
    filename = f"adan-nexus-{profile.id}.{'json' if profile.export_format == 'json' else 'txt'}"
    return Response(
        content=rendered.content,
        media_type=rendered.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Config-Count": str(rendered.config_count),
        },
    )


@router.post("/{profile_id}/tokens", status_code=status.HTTP_201_CREATED)
def create_token(
    profile_id: int,
    payload: TokenCreate,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict:
    profile = _get_profile(db, profile_id, context)
    raw, token = subscriptions.issue_token(db, profile, label=payload.label)
    audit.record(
        db,
        action="subscription.token_created",
        user=context.user,
        target_type="subscription_profile",
        target_id=profile.id,
        detail={"token_prefix": token.token_prefix},
    )
    return {
        "token": raw,
        "url": subscriptions.subscription_url(raw, profile.export_format),
        **token_out(token),
    }


@router.post("/tokens/{token_id}/revoke")
def revoke_token(
    token_id: int,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict:
    token = db.get(SubscriptionToken, token_id)
    if token is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
    token.revoked_at = utcnow()
    db.commit()
    audit.record(
        db,
        action="subscription.token_revoked",
        user=context.user,
        target_type="subscription_token",
        target_id=token.id,
        detail={"token_prefix": token.token_prefix},
    )
    return {"revoked": True, "token_prefix": token.token_prefix}
