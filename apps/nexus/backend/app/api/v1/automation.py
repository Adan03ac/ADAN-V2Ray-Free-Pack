"""Automation Center: schedules, run history and manual triggers."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, client_ip, rate_limit, require_auth, require_csrf
from app.core.config import settings
from app.core.db import get_db
from app.models import PipelineRun
from app.services import analytics, audit, upstream
from app.services.ingestion import PipelineBusy, pipeline_in_flight, start_pipeline_async
from app.workers.scheduler import scheduler

router = APIRouter(prefix="/automation", tags=["automation"])


@router.get("/runs")
def list_runs(
    limit: int = 25,
    context: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    summary = analytics.automation_summary(db)
    runs = db.execute(
        select(PipelineRun).order_by(desc(PipelineRun.started_at)).limit(max(1, min(limit, 100)))
    ).scalars().all()
    summary["runs"] = [
        {
            "id": run.id,
            "trigger": run.trigger,
            "status": run.status,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "duration_ms": round(run.duration_ms, 1) if run.duration_ms else None,
            "sources_total": run.sources_total,
            "sources_ok": run.sources_ok,
            "sources_failed": run.sources_failed,
            "parsed": run.parsed_count,
            "accepted": run.accepted_count,
            "new": run.new_count,
            "invalid": run.invalid_count,
            "published": run.published,
            "publish_skipped_reason": run.publish_skipped_reason,
            "error": run.error,
            "details": run.details,
        }
        for run in runs
    ]
    summary["pipeline_in_flight"] = pipeline_in_flight()
    summary["scheduler"] = scheduler.status()
    return summary


@router.get("/runs/{run_id}")
def run_detail(
    run_id: int,
    context: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    run = db.get(PipelineRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline run not found")
    return {
        "id": run.id,
        "trigger": run.trigger,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "duration_ms": run.duration_ms,
        "sources_total": run.sources_total,
        "sources_ok": run.sources_ok,
        "sources_failed": run.sources_failed,
        "parsed": run.parsed_count,
        "accepted": run.accepted_count,
        "new": run.new_count,
        "duplicate": run.duplicate_count,
        "invalid": run.invalid_count,
        "published": run.published,
        "publish_skipped_reason": run.publish_skipped_reason,
        "publish_path": run.publish_path,
        "output_hash": run.output_hash,
        "error": run.error,
        "details": run.details,
    }


@router.post("/refresh", status_code=status.HTTP_202_ACCEPTED)
def manual_refresh(
    request: Request,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict:
    rate_limit(request, "automation_refresh", limit=4, window_seconds=60)
    try:
        start_pipeline_async(trigger="manual", actor=context.user.email)
    except PipelineBusy as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    audit.record(
        db,
        action="automation.refresh_requested",
        user=context.user,
        ip_address=client_ip(request),
        detail={"trigger": "manual"},
    )
    return {
        "accepted": True,
        "detail": "Ingestion queued. GitHub Actions may still be the authoritative hourly publisher.",
    }


@router.get("/schedule")
def schedule(context: AuthContext = Depends(require_auth)) -> dict:
    return {
        "local_scheduler": scheduler.status(),
        "upstream": upstream.upstream_status(),
        "workflow_runs": upstream.workflow_runs(),
        "publication_mode": settings.publish_mode,
        "safeguards": [
            "Only one scheduler may run ingestion; the worker process owns it in Docker.",
            "GitHub cron '7 * * * *' is approximate and may be delayed or skipped.",
            "A failed run never deletes the previous successful bank.",
        ],
    }
