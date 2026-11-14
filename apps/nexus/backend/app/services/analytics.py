"""Analytics derived exclusively from persisted telemetry. Nothing is fabricated."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    Configuration,
    ConfigurationSource,
    HealthTest,
    HealthTestJob,
    PipelineRun,
    Source,
    SourceFetch,
    SubscriptionProfile,
    utcnow,
)
from app.services import health

PERIOD_CHOICES = {7: "7d", 30: "30d", 90: "90d"}


def _day_range(days: int) -> list[date]:
    today = utcnow().date()
    return [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def _as_date(value) -> date | None:  # type: ignore[no-untyped-def]
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def overview(db: Session) -> dict:
    unique = int(db.execute(select(func.count(Configuration.id))).scalar_one())
    occurrence_total = int(
        db.execute(select(func.coalesce(func.sum(ConfigurationSource.occurrences), 0))).scalar_one()
    )
    active_sources = int(
        db.execute(select(func.count(Source.id)).where(Source.enabled.is_(True))).scalar_one()
    )
    source_errors = int(
        db.execute(
            select(func.count(Source.id)).where(Source.enabled.is_(True), Source.consecutive_failures > 0)
        ).scalar_one()
    )
    tested = int(
        db.execute(select(func.count(Configuration.id)).where(Configuration.last_tested_at.is_not(None))).scalar_one()
    )
    reachable = int(
        db.execute(
            select(func.count(Configuration.id)).where(Configuration.connectivity_status == "reachable")
        ).scalar_one()
    )
    avg_latency = db.execute(
        select(func.avg(Configuration.last_latency_ms)).where(Configuration.last_latency_ms.is_not(None))
    ).scalar_one()
    last_source_success = db.execute(select(func.max(Source.last_success_at))).scalar_one()
    last_run = db.execute(select(PipelineRun).order_by(PipelineRun.started_at.desc())).scalars().first()
    failures = int(
        db.execute(select(func.count(Configuration.id)).where(Configuration.connectivity_status == "failed")).scalar_one()
    )

    protocols = db.execute(
        select(Configuration.protocol, func.count(Configuration.id))
        .group_by(Configuration.protocol)
        .order_by(func.count(Configuration.id).desc())
    ).all()
    sources = db.execute(
        select(Source.id, Source.name, Source.enabled, Source.last_success_at, Source.last_error, Source.config_count)
        .order_by(Source.id)
    ).all()
    connectivity = dict(
        db.execute(select(Configuration.connectivity_status, func.count(Configuration.id)).group_by(Configuration.connectivity_status)).all()
    )
    for key in ("untested", "reachable", "failed", "dns_resolved", "unknown"):
        connectivity.setdefault(key, 0)

    protocol_counts = [{"protocol": protocol, "count": count} for protocol, count in protocols]
    total_known = sum(item["count"] for item in protocol_counts) or 1

    return {
        "generated_at": utcnow().isoformat(),
        "kpis": {
            "unique_configurations": unique,
            "total_configurations": occurrence_total,
            "active_sources": active_sources,
            "sources_with_errors": source_errors,
            "tested_configurations": tested,
            "reachable_configurations": reachable,
            "verified_working_configurations": 0,
            "verification_available": False,
            "verification_note": (
                "End-to-end tunnel verification requires an authorized test agent and is not implemented. "
                "TCP reachability is reported separately and is not proof of a working connection."
            ),
            "failing_configurations": failures,
            "average_measured_latency_ms": round(float(avg_latency), 1) if avg_latency is not None else None,
            "last_successful_update": last_source_success.isoformat() if last_source_success else None,
            "last_pipeline_run": {
                "id": last_run.id,
                "status": last_run.status,
                "started_at": last_run.started_at.isoformat(),
                "finished_at": last_run.finished_at.isoformat() if last_run.finished_at else None,
                "published": last_run.published,
                "accepted": last_run.accepted_count,
                "new": last_run.new_count,
            }
            if last_run
            else None,
        },
        "protocol_distribution": [
            {"protocol": item["protocol"], "count": item["count"], "share": round(item["count"] / total_known, 4)}
            for item in protocol_counts
        ],
        "health_distribution": connectivity,
        "sources": [
            {
                "id": source.id,
                "name": source.name,
                "enabled": source.enabled,
                "last_success_at": source.last_success_at.isoformat() if source.last_success_at else None,
                "last_error": source.last_error,
                "config_count": source.config_count,
            }
            for source in sources
        ],
    }


def growth_series(db: Session, days: int) -> list[dict]:
    days = days if days in PERIOD_CHOICES else 30
    since = utcnow() - timedelta(days=days - 1)
    rows = db.execute(
        select(func.date(Configuration.first_seen_at), func.count(Configuration.id))
        .where(Configuration.first_seen_at >= since)
        .group_by(func.date(Configuration.first_seen_at))
    ).all()
    daily = {_as_date(day): int(count) for day, count in rows}
    baseline = int(
        db.execute(select(func.count(Configuration.id)).where(Configuration.first_seen_at < since)).scalar_one()
    )
    series: list[dict] = []
    cumulative = baseline
    for day in _day_range(days):
        added = daily.get(day, 0)
        cumulative += added
        series.append({"date": day.isoformat(), "added": added, "cumulative": cumulative})
    return series


def source_contribution(db: Session) -> list[dict]:
    rows = db.execute(
        select(Source.id, Source.name, func.count(ConfigurationSource.id), func.coalesce(func.sum(ConfigurationSource.occurrences), 0))
        .join(ConfigurationSource, ConfigurationSource.source_id == Source.id, isouter=True)
        .group_by(Source.id, Source.name)
        .order_by(func.count(ConfigurationSource.id).desc())
    ).all()
    total = sum(int(count) for _sid, _name, count, _occ in rows) or 1
    return [
        {
            "source_id": source_id,
            "name": name,
            "configurations": int(count),
            "occurrences": int(occurrences),
            "share": round(int(count) / total, 4),
        }
        for source_id, name, count, occurrences in rows
    ]


def latency_trend(db: Session, days: int) -> list[dict]:
    days = days if days in PERIOD_CHOICES else 7
    since = utcnow() - timedelta(days=days - 1)
    rows = db.execute(
        select(func.date(HealthTest.started_at), func.avg(HealthTest.latency_ms), func.count(HealthTest.id))
        .where(HealthTest.started_at >= since, HealthTest.latency_ms.is_not(None))
        .group_by(func.date(HealthTest.started_at))
    ).all()
    daily = {_as_date(day): (float(avg), int(count)) for day, avg, count in rows if avg is not None}
    return [
        {
            "date": day.isoformat(),
            "avg_latency_ms": round(daily[day][0], 1) if day in daily else None,
            "samples": daily[day][1] if day in daily else 0,
        }
        for day in _day_range(days)
    ]


def pipeline_activity(db: Session, days: int = 7) -> list[dict]:
    days = days if days in PERIOD_CHOICES else 7
    since = utcnow() - timedelta(days=days - 1)
    rows = db.execute(
        select(
            func.date(PipelineRun.started_at),
            func.count(PipelineRun.id),
            func.coalesce(func.sum(PipelineRun.accepted_count), 0),
            func.coalesce(func.sum(PipelineRun.new_count), 0),
        )
        .where(PipelineRun.started_at >= since)
        .group_by(func.date(PipelineRun.started_at))
    ).all()
    daily = {
        _as_date(day): (int(runs), int(accepted), int(new)) for day, runs, accepted, new in rows
    }
    return [
        {
            "date": day.isoformat(),
            "runs": daily.get(day, (0, 0, 0))[0],
            "accepted": daily.get(day, (0, 0, 0))[1],
            "new": daily.get(day, (0, 0, 0))[2],
        }
        for day in _day_range(days)
    ]


def heatmap(db: Session, weeks: int = 6) -> dict:
    """Activity grid: configuration additions and tests per day."""
    days = weeks * 7
    since = utcnow() - timedelta(days=days - 1)
    added = dict(
        db.execute(
            select(func.date(Configuration.first_seen_at), func.count(Configuration.id))
            .where(Configuration.first_seen_at >= since)
            .group_by(func.date(Configuration.first_seen_at))
        ).all()
    )
    tested = dict(
        db.execute(
            select(func.date(HealthTest.started_at), func.count(HealthTest.id))
            .where(HealthTest.started_at >= since)
            .group_by(func.date(HealthTest.started_at))
        ).all()
    )
    runs = dict(
        db.execute(
            select(func.date(PipelineRun.started_at), func.count(PipelineRun.id))
            .where(PipelineRun.started_at >= since)
            .group_by(func.date(PipelineRun.started_at))
        ).all()
    )
    cells = []
    for day in _day_range(days):
        add = int(added.get(day, 0) or 0)
        tests = int(tested.get(day, 0) or 0)
        run_count = int(runs.get(day, 0) or 0)
        cells.append(
            {
                "date": day.isoformat(),
                "added": add,
                "tests": tests,
                "runs": run_count,
                "intensity": min(4, add // 250 + (1 if tests else 0) + (1 if run_count else 0)),
            }
        )
    return {"weeks": weeks, "cells": cells, "max_added": max((cell["added"] for cell in cells), default=0)}


def source_reliability(db: Session) -> list[dict]:
    rows = db.execute(select(Source).order_by(Source.id)).scalars().all()
    results = []
    for source in rows:
        fetches = db.execute(
            select(SourceFetch.status, func.count(SourceFetch.id))
            .where(SourceFetch.source_id == source.id)
            .group_by(SourceFetch.status)
        ).all()
        counts = {status: int(count) for status, count in fetches}
        total = sum(counts.values())
        ok = counts.get("ok", 0) + counts.get("not_modified", 0)
        durations = db.execute(
            select(func.avg(SourceFetch.duration_ms)).where(
                SourceFetch.source_id == source.id, SourceFetch.duration_ms.is_not(None)
            )
        ).scalar_one()
        results.append(
            {
                "source_id": source.id,
                "name": source.name,
                "fetches": total,
                "success_rate": round(ok / total, 4) if total else None,
                "errors": counts.get("error", 0),
                "avg_duration_ms": round(float(durations), 1) if durations is not None else None,
                "consecutive_failures": source.consecutive_failures,
            }
        )
    return results


def health_summary(db: Session) -> dict:
    total_jobs = int(db.execute(select(func.count(HealthTestJob.id))).scalar_one())
    recent_tests = db.execute(
        select(
            HealthTest.status,
            HealthTest.stage_reached,
            HealthTest.error_category,
            func.count(HealthTest.id),
            func.avg(HealthTest.latency_ms),
        )
        .group_by(HealthTest.status, HealthTest.stage_reached, HealthTest.error_category)
        .order_by(func.count(HealthTest.id).desc())
    ).all()
    last_test = db.execute(select(func.max(HealthTest.finished_at))).scalar_one()
    return {
        "queue": health.queue_snapshot(db),
        "total_jobs": total_jobs,
        "last_test_at": last_test.isoformat() if last_test else None,
        "breakdown": [
            {
                "status": status,
                "stage": stage,
                "category": category,
                "count": int(count),
                "avg_latency_ms": round(float(avg), 1) if avg is not None else None,
            }
            for status, stage, category, count, avg in recent_tests
        ],
        "agent": {
            "label": settings.health_agent_label,
            "region": settings.health_agent_region,
            "tcp_enabled": settings.health_allow_tcp,
            "concurrency": settings.health_concurrency,
            "timeout_seconds": settings.health_timeout_seconds,
        },
        "stages_implemented": ["syntax", "dns", "tcp"],
        "stages_unavailable": [
            "protocol-level handshake",
            "end-to-end tunnel verification",
            "Iran-based measurement (no authorized agent configured)",
        ],
    }


def automation_summary(db: Session) -> dict:
    runs = db.execute(select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(10)).scalars().all()
    last_success = db.execute(
        select(PipelineRun).where(PipelineRun.status.in_(["succeeded", "partial"])).order_by(PipelineRun.started_at.desc())
    ).scalars().first()
    next_run = None
    if last_success and last_success.started_at:
        started = last_success.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        next_run = (started + timedelta(minutes=settings.ingestion_interval_minutes)).isoformat()
    error_sources = db.execute(
        select(Source).where(Source.enabled.is_(True), Source.consecutive_failures > 0).order_by(Source.consecutive_failures.desc())
    ).scalars().all()
    return {
        "runs": [
            {
                "id": run.id,
                "trigger": run.trigger,
                "status": run.status,
                "started_at": run.started_at.isoformat(),
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "duration_ms": round(run.duration_ms, 1) if run.duration_ms else None,
                "sources_total": run.sources_total,
                "sources_ok": run.sources_ok,
                "sources_failed": run.sources_failed,
                "accepted": run.accepted_count,
                "new": run.new_count,
                "invalid": run.invalid_count,
                "published": run.published,
                "publish_skipped_reason": run.publish_skipped_reason,
                "error": run.error,
            }
            for run in runs
        ],
        "next_expected_run": next_run,
        "next_expected_note": "Approximate. Schedules are best-effort and may be delayed.",
        "error_sources": [
            {
                "id": source.id,
                "name": source.name,
                "consecutive_failures": source.consecutive_failures,
                "last_error": source.last_error,
            }
            for source in error_sources
        ],
        "profiles": int(db.execute(select(func.count(SubscriptionProfile.id))).scalar_one()),
        "enabled_sources": int(
            db.execute(select(func.count(Source.id)).where(Source.enabled.is_(True))).scalar_one()
        ),
    }
