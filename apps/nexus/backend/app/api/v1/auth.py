"""Session authentication with lockout, audit trail and CSRF tokens."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, client_ip, rate_limit, require_admin, require_auth, require_csrf, require_session_csrf
from app.core.config import settings
from app.core.db import get_db
from app.core.security import new_token, token_hash, verify_password, hash_password
from app.models import AuthSession, User, utcnow
from app.schemas import LoginRequest, LoginResponse, RegisterRequest, UserCreate, UserOut, UserUpdate
from app.services import audit

router = APIRouter(prefix="/auth", tags=["authentication"])


def _set_session_cookies(response: Response, raw_token: str, csrf_token: str, expires_at: datetime) -> None:
    max_age = max(1, int((expires_at - datetime.now(timezone.utc)).total_seconds()))
    response.set_cookie(
        settings.session_cookie_name,
        raw_token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
        domain=settings.cookie_domain,
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
        domain=settings.cookie_domain,
    )


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    rate_limit(request, "login", limit=settings.login_rate_limit, window_seconds=60)
    user = db.execute(select(User).where(User.email == payload.email)).scalars().first()
    ip = client_ip(request)
    if user is None:
        audit.record(db, action="auth.login", outcome="failure", ip_address=ip, detail={"reason": "unknown_email"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    now = datetime.now(timezone.utc)
    if user.locked_until is not None:
        locked_until = user.locked_until if user.locked_until.tzinfo else user.locked_until.replace(tzinfo=timezone.utc)
        if locked_until > now:
            audit.record(
                db, action="auth.login", user=user, outcome="blocked", ip_address=ip, detail={"reason": "locked"}
            )
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account temporarily locked after repeated failures",
            )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    if not verify_password(payload.password, user.password_hash):
        user.failed_logins += 1
        locked = user.failed_logins >= settings.login_max_attempts
        if locked:
            user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
            user.failed_logins = 0
        db.commit()
        audit.record(
            db,
            action="auth.login",
            user=user,
            outcome="failure",
            ip_address=ip,
            detail={"reason": "bad_password", "locked": locked},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    raw_token, csrf_token, expires_at = _issue_session(db, user, request)
    _set_session_cookies(response, raw_token, csrf_token, expires_at)
    audit.record(db, action="auth.login", user=user, outcome="success", ip_address=ip)
    return LoginResponse(user=UserOut.model_validate(user), csrf_token=csrf_token, expires_at=expires_at)


def _issue_session(db: Session, user: User, request: Request) -> tuple[str, str, datetime]:
    raw_token = new_token(32)
    csrf_token = new_token(24)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=settings.session_ttl_hours)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_hash(raw_token),
            csrf_token=csrf_token,
            ip_address=client_ip(request),
            user_agent=(request.headers.get("user-agent") or "")[:255] or None,
            expires_at=expires_at,
        )
    )
    user.last_login_at = now
    user.failed_logins = 0
    user.locked_until = None
    db.commit()
    return raw_token, csrf_token, expires_at


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Self-service signup. Always creates a read-only operator."""
    if not settings.allow_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-service registration is disabled; ask an administrator for an account.",
        )
    rate_limit(request, "register", limit=settings.register_rate_limit, window_seconds=3600)
    existing = db.execute(select(User).where(User.email == payload.email)).scalars().first()
    if existing:
        audit.record(
            db,
            action="auth.register",
            outcome="failure",
            ip_address=client_ip(request),
            detail={"reason": "email_taken"},
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    user = User(
        email=payload.email,
        password_hash=password_hash,
        display_name=payload.display_name.strip()[:120] or "Operator",
        role="read_only",  # elevation requires an administrator
        is_active=True,
    )
    db.add(user)
    db.commit()
    raw_token, csrf_token, expires_at = _issue_session(db, user, request)
    _set_session_cookies(response, raw_token, csrf_token, expires_at)
    audit.record(
        db,
        action="auth.register",
        user=user,
        target_type="user",
        target_id=user.id,
        ip_address=client_ip(request),
        detail={"role": "read_only", "self_service": True},
    )
    return LoginResponse(user=UserOut.model_validate(user), csrf_token=csrf_token, expires_at=expires_at)


@router.get("/me")
def me(context: AuthContext = Depends(require_auth)) -> dict:
    return {
        "user": UserOut.model_validate(context.user).model_dump(mode="json"),
        "csrf_token": context.session.csrf_token,
        "expires_at": context.session.expires_at.isoformat(),
    }


@router.post("/logout")
def logout(
    response: Response,
    context: AuthContext = Depends(require_session_csrf),
    db: Session = Depends(get_db),
) -> dict:
    context.session.revoked_at = utcnow()
    db.commit()
    audit.record(db, action="auth.logout", user=context.user, ip_address=None)
    response.delete_cookie(settings.session_cookie_name, path="/", domain=settings.cookie_domain)
    response.delete_cookie(settings.csrf_cookie_name, path="/", domain=settings.cookie_domain)
    return {"ok": True}


@router.get("/users", response_model=list[UserOut])
def list_users(
    context: AuthContext = Depends(require_admin), db: Session = Depends(get_db)
) -> list[UserOut]:
    users = db.execute(select(User).order_by(User.id)).scalars().all()
    return [UserOut.model_validate(user) for user in users]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> UserOut:
    existing = db.execute(select(User).where(User.email == payload.email)).scalars().first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    user = User(
        email=payload.email,
        password_hash=password_hash,
        display_name=payload.display_name,
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    audit.record(
        db,
        action="auth.user_created",
        user=context.user,
        target_type="user",
        target_id=user.id,
        detail={"role": user.role},
    )
    return UserOut.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> UserOut:
    """Role/activation changes. Guards against an administrator locking themselves out."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    changes = payload.model_dump(exclude_unset=True)
    if user.id == context.user.id and (
        changes.get("role", user.role) != user.role or changes.get("is_active") is False
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot change your own role or deactivate your own account",
        )
    for field, value in changes.items():
        setattr(user, field, value)
    db.commit()
    audit.record(
        db,
        action="auth.user_updated",
        user=context.user,
        target_type="user",
        target_id=user.id,
        detail={key: changes[key] for key in changes},
    )
    return UserOut.model_validate(user)
