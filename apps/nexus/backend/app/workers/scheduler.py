"""Scheduled ingestion. One scheduler only: no duplicate ingestion jobs."""

from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.db import session_scope
from app.models import PipelineRun
from app.services.ingestion import PipelineBusy, run_pipeline

logger = logging.getLogger("nexus.scheduler")


class IngestionScheduler:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.last_attempt_at: datetime | None = None
        self.next_run_at: datetime | None = None
        self.last_error: str | None = None
        self.runs_started = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="nexus-scheduler", daemon=True)
        self._thread.start()
        logger.info("ingestion scheduler started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _compute_next(self) -> datetime:
        base = datetime.now(timezone.utc)
        jitter = random.uniform(0, max(0, settings.ingestion_jitter_seconds))
        return base + timedelta(minutes=settings.ingestion_interval_minutes, seconds=jitter)

    def _loop(self) -> None:
        time.sleep(random.uniform(2, 8))  # avoid thundering herd at boot
        self.next_run_at = self._compute_next()
        while not self._stop.is_set():
            try:
                if settings.ingestion_enabled and self.next_run_at and datetime.now(timezone.utc) >= self.next_run_at:
                    self._trigger()
                    self.next_run_at = self._compute_next()
            except Exception:  # pragma: no cover - loop guard
                logger.exception("scheduler loop error")
                self.next_run_at = self._compute_next()
            self._stop.wait(20)

    def _trigger(self) -> None:
        self.last_attempt_at = datetime.now(timezone.utc)
        try:
            run = run_pipeline(trigger="schedule")
            self.runs_started += 1
            logger.info("scheduled ingestion finished", extra={"context": {"run_id": run.id, "status": run.status}})
        except PipelineBusy as exc:
            self.last_error = str(exc)
            logger.info("scheduled ingestion skipped: pipeline busy")
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"[:200]
            logger.exception("scheduled ingestion failed")

    def status(self) -> dict:
        return {
            "embedded": settings.embedded_worker,
            "enabled": settings.ingestion_enabled,
            "running": self.is_running(),
            "interval_minutes": settings.ingestion_interval_minutes,
            "jitter_seconds": settings.ingestion_jitter_seconds,
            "last_attempt_at": self.last_attempt_at.isoformat() if self.last_attempt_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "last_error": self.last_error,
            "runs_started": self.runs_started,
        }


scheduler = IngestionScheduler()


def due_check(db) -> dict:  # type: ignore[no-untyped-def]
    """Report whether ingestion is due without starting it."""
    last_run = db.execute(select(PipelineRun).order_by(PipelineRun.started_at.desc())).scalars().first()
    return {
        "last_run_at": last_run.started_at.isoformat() if last_run else None,
        "last_status": last_run.status if last_run else None,
        "interval_minutes": settings.ingestion_interval_minutes,
    }
