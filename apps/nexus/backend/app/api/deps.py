"""Authentication, authorization, CSRF and rate-limit dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.config import settings
from app.core.ratelimit import check_rate_limit
from app.core.security import constant_time_equals, token_hash
from app.models import AuthSession, User


@dataclass
class AuthContext:
    user: User
    session: AuthSession


def client_ip(request: Request) -> str:
    # Only ASGI's peer identity is trusted. Uvicorn may normalize it when the
    # immediate proxy is explicitly trusted; raw forwarded headers are spoofable.
    return (request.client.host if request.client else "unknown")[:64]


def _resolve_session(request: Request, db: Session) -> AuthContext | None:
    raw = request.cookies.get(settings.session_cookie_name)
    if not raw or len(raw) > 200:
        return None
    session = db.execute(
        select(AuthSession).where(AuthSession.token_hash == token_hash(raw))
    ).scalars().first()
    if session is None or session.revoked_at is not None:
        return None
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        return None
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None
    return AuthContext(user=user, session=session)


def require_auth(request: Request, db: Session = Depends(get_db)) -> AuthContext:
    context = _resolve_session(request, db)
    if context is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return context


def optional_auth(request: Request, db: Session = Depends(get_db)) -> AuthContext | None:
    return _resolve_session(request, db)


def require_admin(context: AuthContext = Depends(require_auth)) -> AuthContext:
    if context.user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required")
    return context


def require_session_csrf(request: Request, context: AuthContext = Depends(require_auth)) -> AuthContext:
    """Double-submit token bound to the server-side session."""
    header = request.headers.get("x-csrf-token", "")
    cookie = request.cookies.get(settings.csrf_cookie_name, "")
    if not header or not cookie or not constant_time_equals(header, cookie):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing or invalid")
    if not constant_time_equals(header, context.session.csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token does not match this session")
    return context


def require_csrf(context: AuthContext = Depends(require_session_csrf)) -> AuthContext:
    return require_admin(context)


def rate_limit(request: Request, bucket: str, limit: int, window_seconds: int = 60) -> None:
    allowed, retry_after = check_rate_limit(f"{bucket}:{client_ip(request)}", limit, window_seconds)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests; slow down",
            headers={"Retry-After": str(retry_after)},
        )
