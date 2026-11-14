"""Dashboard aggregates for the Overview page."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_auth
from app.core.config import settings
from app.core.db import get_db
from app.models import PipelineRun, Source, SourceFetch
from app.services import analytics, upstream
from app.workers.scheduler import scheduler

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(
    days: int = Query(default=7, description="7, 30 or 90"),
    context: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    days = days if days in analytics.PERIOD_CHOICES else 7
    events = db.execute(select(PipelineRun).order_by(desc(PipelineRun.started_at)).limit(6)).scalars().all()
    errors = db.execute(
        select(Source)
        .where(Source.consecutive_failures > 0)
        .order_by(desc(Source.consecutive_failures))
        .limit(5)
    ).scalars().all()
    recent_fetches = db.execute(
        select(SourceFetch, Source.name)
        .join(Source, Source.id == SourceFetch.source_id)
        .order_by(desc(SourceFetch.started_at))
        .limit(8)
    ).all()

    return {
        "period_days": days,
        "overview": analytics.overview(db),
        "growth": analytics.growth_series(db, days),
        "source_contribution": analytics.source_contribution(db),
        "latency_trend": analytics.latency_trend(db, min(days, 30)),
        "pipeline_activity": analytics.pipeline_activity(db, min(days, 30)),
        "heatmap": analytics.heatmap(db, weeks=6),
        "health": analytics.health_summary(db),
        "automation": analytics.automation_summary(db),
        "scheduler": scheduler.status(),
        "publication": {
            "provider": settings.publish_mode,
            "directory": settings.publish_dir,
            "statement": "Publication is local to this deployment; the GitHub Actions pipeline remains independent.",
        },
        "latest_events": [
            {
                "id": run.id,
                "trigger": run.trigger,
                "status": run.status,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "accepted": run.accepted_count,
                "new": run.new_count,
                "invalid": run.invalid_count,
                "published": run.published,
                "publish_skipped_reason": run.publish_skipped_reason,
                "error": run.error,
                "sources_ok": run.sources_ok,
                "sources_failed": run.sources_failed,
            }
            for run in events
        ],
        "recent_source_errors": [
            {
                "id": source.id,
                "name": source.name,
                "last_error": source.last_error,
                "consecutive_failures": source.consecutive_failures,
                "last_attempted_at": source.last_attempted_at,
            }
            for source in errors
        ],
        "recent_fetches": [
            {
                "source": name,
                "status": fetch.status,
                "started_at": fetch.started_at,
                "duration_ms": round(fetch.duration_ms, 1) if fetch.duration_ms else None,
                "http_status": fetch.http_status,
                "accepted": fetch.accepted_count,
            }
            for fetch, name in recent_fetches
        ],
        "upstream": upstream.upstream_status(),
    }
