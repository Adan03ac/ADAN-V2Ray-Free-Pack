"""Audit trail for privileged actions."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def record(
    db: Session,
    *,
    action: str,
    user: User | None = None,
    target_type: str | None = None,
    target_id: str | int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    outcome: str = "success",
    detail: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user.id if user else None,
        actor_email=user.email if user else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:255] or None,
        outcome=outcome,
        detail=detail or {},
    )
    db.add(entry)
    db.commit()
    return entry
