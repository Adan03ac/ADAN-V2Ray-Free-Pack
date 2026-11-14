"""Analytics endpoints. Every number is a database aggregate."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_auth
from app.core.db import get_db
from app.services import analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
def overview(context: AuthContext = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    return {
        "overview": analytics.overview(db),
        "source_contribution": analytics.source_contribution(db),
        "source_reliability": analytics.source_reliability(db),
        "health": analytics.health_summary(db),
    }


@router.get("/series")
def series(
    days: int = Query(default=30),
    context: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    days = days if days in analytics.PERIOD_CHOICES else 30
    return {
        "days": days,
        "growth": analytics.growth_series(db, days),
        "latency_trend": analytics.latency_trend(db, min(days, 30)),
        "pipeline_activity": analytics.pipeline_activity(db, min(days, 30)),
        "heatmap": analytics.heatmap(db, weeks=6),
        "protocol_distribution": analytics.overview(db)["protocol_distribution"],
        "health_distribution": analytics.overview(db)["health_distribution"],
    }
