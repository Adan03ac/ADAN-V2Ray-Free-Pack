"""Health Monitor endpoints. Reachability is never presented as a working tunnel."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, client_ip, rate_limit, require_auth, require_csrf
from app.core.db import get_db
from app.models import Configuration, HealthTest, HealthTestJob
from app.schemas import HealthTestRequest
from app.services import analytics, audit, health

router = APIRouter(prefix="/health-tests", tags=["health"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def request_tests(
    payload: HealthTestRequest,
    request: Request,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict:
    rate_limit(request, "health_start", limit=6, window_seconds=60)
    ids = payload.configuration_ids[: payload.limit]
    if ids:
        existing = db.execute(select(func.count(Configuration.id)).where(Configuration.id.in_(ids))).scalar_one()
        if int(existing) != len(set(ids)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Only registered configuration identifiers may be tested",
            )
    try:
        job = health.start_job(
            db,
            configuration_ids=ids or None,
            limit=payload.limit,
            stages=list(payload.stages),
            user_id=context.user.id,
        )
    except health.HealthBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit.record(
        db,
        action="health.tests_requested",
        user=context.user,
        target_type="health_test_job",
        target_id=job.id,
        ip_address=client_ip(request),
        detail={"count": job.total, "stages": job.stages},
    )
    return {
        "job": {
            "id": job.id,
            "status": job.status,
            "total": job.total,
            "stages": job.stages,
            "agent_label": job.agent_label,
            "agent_region": job.agent_region,
        },
        "note": "TCP reachability is not proof of a working VPN connection.",
    }


@router.get("")
def list_tests(
    configuration_id: int | None = Query(default=None),
    job_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status", max_length=20),
    limit: int = Query(default=50, ge=1, le=200),
    context: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    query = select(HealthTest)
    if configuration_id:
        query = query.where(HealthTest.configuration_id == configuration_id)
    if job_id:
        query = query.where(HealthTest.job_id == job_id)
    if status_filter:
        query = query.where(HealthTest.status == status_filter)
    rows = db.execute(query.order_by(desc(HealthTest.started_at)).limit(limit)).scalars().all()
    return {
        "items": [
            {
                "id": row.id,
                "configuration_id": row.configuration_id,
                "job_id": row.job_id,
                "status": row.status,
                "stage_reached": row.stage_reached,
                "latency_ms": row.latency_ms,
                "error_category": row.error_category,
                "error_detail": row.error_detail,
                "agent_label": row.agent_label,
                "agent_region": row.agent_region,
                "started_at": row.started_at,
                "finished_at": row.finished_at,
            }
            for row in rows
        ]
    }


@router.get("/jobs")
def list_jobs(
    context: AuthContext = Depends(require_auth), db: Session = Depends(get_db)
) -> dict:
    jobs = db.execute(select(HealthTestJob).order_by(desc(HealthTestJob.requested_at)).limit(25)).scalars().all()
    return {
        "items": [
            {
                "id": job.id,
                "status": job.status,
                "requested_at": job.requested_at,
                "started_at": job.started_at,
                "finished_at": job.finished_at,
                "total": job.total,
                "completed": job.completed,
                "reachable": job.reachable,
                "failed": job.failed,
                "stages": job.stages,
                "concurrency": job.concurrency,
                "agent_label": job.agent_label,
                "agent_region": job.agent_region,
                "error": job.error,
            }
            for job in jobs
        ],
        "queue": health.queue_snapshot(db),
    }


@router.get("/summary")
def summary(context: AuthContext = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    return analytics.health_summary(db)
