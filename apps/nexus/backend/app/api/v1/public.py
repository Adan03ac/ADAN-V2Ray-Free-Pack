"""Public subscription endpoints authenticated by revocable tokens."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services import subscriptions

router = APIRouter(prefix="/public", tags=["public"])

NO_STORE = {
    "Cache-Control": "no-store, no-cache, must-revalidate, private",
    "Referrer-Policy": "no-referrer",
}


@router.get("/subscriptions/{token}")
def public_subscription(
    token: str,
    format: str | None = Query(default=None, pattern="^(plain|base64|json)$"),
    db: Session = Depends(get_db),
) -> Response:
    resolved = subscriptions.resolve_token(db, token)
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found or revoked")
    profile, _token_row = resolved
    rendered = subscriptions.render(db, profile, export_format=format)
    headers = {
        **NO_STORE,
        "X-Config-Count": str(rendered.config_count),
        "Profile-Title": "base64:" + __import__("base64").b64encode(profile.name.encode("utf-8")).decode("ascii"),
    }
    return Response(content=rendered.content, media_type=rendered.media_type, headers=headers)
