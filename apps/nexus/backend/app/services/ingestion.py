"""The ingestion pipeline: FETCH → DECODE → PARSE → NORMALIZE → VALIDATE → DEDUPLICATE → STORE → PUBLISH."""

from __future__ import annotations

import contextlib
import hashlib
import logging
import threading
import time
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import session_scope
from app.core.security import encrypt_secret
from app.models import (
    Configuration,
    ConfigurationSource,
    PipelineRun,
    Source,
    SourceFetch,
    utcnow,
)
from app.services import publisher
from app.services.adapters import AdapterPayload, registry
from app.services.fetcher import FetchResult, SafeFetcher
from app.services.parsers import ParseError, parse_share_link

logger = logging.getLogger("nexus.ingestion")
CHUNK = 400
INVALID_SAMPLE_LIMIT = 15


class PipelineBusy(RuntimeError):
    pass


@contextlib.contextmanager
def pipeline_guard() -> Iterator[None]:
    """Cross-process single-flight protection for ingestion."""
    lock_path = Path(settings.pipeline_lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "a+")
    try:
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:  # pragma: no cover - Windows development only
            pass
        except BlockingIOError as exc:
            raise PipelineBusy("another ingestion run is already in progress") from exc
        yield
    finally:
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception:  # pragma: no cover
            pass
        handle.close()


def _assert_not_stale_running(db: Session) -> None:
    running = db.execute(
        select(PipelineRun).where(PipelineRun.status == "running").order_by(PipelineRun.started_at.desc())
    ).scalars().first()
    if running is None:
        return
    started = running.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    age = (utcnow() - started).total_seconds()
    if age > 3600:
        running.status = "failed"
        running.error = "stale run closed automatically after 60 minutes"
        running.finished_at = utcnow()
        db.commit()
    else:
        raise PipelineBusy("a pipeline run is already recorded as running")


def _process_source(db: Session, source: Source, run: PipelineRun, prefetched: FetchResult | None = None) -> tuple[int, int, int, int, str, dict]:
    """Returns parsed, accepted, new, invalid counts and status."""
    adapter = registry.for_source(source)
    started = time.perf_counter()
    fetch_row = SourceFetch(
        source_id=source.id,
        pipeline_run_id=run.id,
        status="running",
        started_at=utcnow(),
        invalid_samples=[],
        fetch_metadata={},
    )
    db.add(fetch_row)
    db.flush()
    source.last_attempted_at = utcnow()

    if prefetched is not None:
        result = prefetched
    elif not adapter.requires_fetch():
        result = FetchResult(ok=True, status_code=None, duration_ms=0.0)
    else:
        result = SafeFetcher().fetch(source.url, etag=source.etag, last_modified=source.last_modified)

    fetch_row.http_status = result.status_code
    fetch_row.bytes_read = len(result.content)
    fetch_row.duration_ms = (time.perf_counter() - started) * 1000
    source.last_duration_ms = fetch_row.duration_ms
    source.last_http_status = result.status_code

    if not result.ok:
        fetch_row.status = "error"
        fetch_row.finished_at = utcnow()
        fetch_row.error = result.error
        source.last_error = result.error
        source.consecutive_failures += 1
        db.commit()
        logger.warning(
            "source fetch failed",
            extra={"context": {"source": source.slug, "error": result.error, "category": result.error_category}},
        )
        return 0, 0, 0, 0, "error", {"error": result.error, "category": result.error_category}

    if result.not_modified:
        fetch_row.status = "not_modified"
        fetch_row.finished_at = utcnow()
        source.last_error = None
        source.consecutive_failures = 0
        db.commit()
        return 0, 0, 0, 0, "not_modified", {"reason": "HTTP 304"}

    try:
        payload: AdapterPayload = adapter.parse_response(source, result)
    except ParseError as exc:
        fetch_row.status = "error"
        fetch_row.finished_at = utcnow()
        fetch_row.error = f"decode failed: {exc.reason}"
        source.last_error = fetch_row.error
        source.consecutive_failures += 1
        db.commit()
        return 0, 0, 0, 0, "error", {"error": fetch_row.error, "category": exc.category}

    fetch_row.fetch_metadata = payload.metadata

    if payload.discovery_only:
        fetch_row.status = "skipped"
        fetch_row.finished_at = utcnow()
        fetch_row.invalid_samples = [{"note": item} for item in payload.diagnostics[:INVALID_SAMPLE_LIMIT]]
        source.last_error = None
        source.consecutive_failures = 0
        source.last_success_at = utcnow()
        db.commit()
        return 0, 0, 0, 0, "skipped", {"diagnostics": payload.diagnostics}

    # PARSE + NORMALIZE + VALIDATE
    parsed: dict[str, tuple] = {}
    invalid_samples: list[dict] = []
    invalid_count = 0
    duplicates_in_feed = 0
    for link in payload.raw_links:
        try:
            config = parse_share_link(link)
        except ParseError as exc:
            invalid_count += 1
            if len(invalid_samples) < INVALID_SAMPLE_LIMIT:
                invalid_samples.append(
                    {
                        "scheme": link.split("://", 1)[0][:20],
                        "category": exc.category,
                        "reason": exc.reason[:160],
                    }
                )
            continue
        if config.fingerprint in parsed:
            duplicates_in_feed += 1
            continue
        parsed[config.fingerprint] = (
            config.protocol,
            config.host,
            config.port,
            config.transport,
            config.security,
            config.sni,
            config.canonical_endpoint,
            config.credential,
            link,
        )

    fingerprints = list(parsed.keys())
    existing: dict[str, int] = {}
    for start in range(0, len(fingerprints), CHUNK):
        chunk = fingerprints[start : start + CHUNK]
        rows = db.execute(
            select(Configuration.id, Configuration.fingerprint).where(Configuration.fingerprint.in_(chunk))
        ).all()
        existing.update({fingerprint: config_id for config_id, fingerprint in rows})

    now = utcnow()
    new_rows: list[Configuration] = []
    new_fingerprints: list[str] = []
    for fingerprint in fingerprints:
        if fingerprint in existing:
            continue
        protocol, host, port, transport, security, sni, canonical, credential, link = parsed[fingerprint]
        new_rows.append(
            Configuration(
                fingerprint=fingerprint,
                protocol=protocol,
                host=host,
                port=port,
                transport=transport,
                security=security,
                sni=sni,
                canonical_endpoint=canonical,
                credential_hint=f"{credential[:4]}…" if len(credential) > 6 else "•••",
                raw_link_encrypted=encrypt_secret(link),
                raw_link_length=len(link),
                first_seen_at=now,
                last_seen_at=now,
                source_count=1,
            )
        )
        new_fingerprints.append(fingerprint)

    inserted_ids: dict[str, int] = {}
    for start in range(0, len(new_rows), CHUNK):
        batch = new_rows[start : start + CHUNK]
        db.add_all(batch)
        db.flush()
        for row in batch:
            inserted_ids[row.fingerprint] = row.id

    accepted = len(parsed)
    new_count = len(new_rows)
    duplicate_count = len(payload.raw_links) - accepted + duplicates_in_feed
    duplicate_count = max(duplicate_count, 0)

    # STORE provenance
    linked_existing = {cid for cid in existing.values()}
    existing_links: set[int] = set()
    if linked_existing:
        for start in range(0, len(linked_existing), CHUNK):
            chunk = list(linked_existing)[start : start + CHUNK]
            rows = db.execute(
                select(ConfigurationSource.configuration_id).where(
                    ConfigurationSource.source_id == source.id,
                    ConfigurationSource.configuration_id.in_(chunk),
                )
            ).all()
            existing_links.update(row[0] for row in rows)

    link_rows: list[ConfigurationSource] = []
    for fingerprint, config_id in existing.items():
        if config_id not in existing_links:
            link_rows.append(
                ConfigurationSource(
                    configuration_id=config_id, source_id=source.id, first_seen_at=now, last_seen_at=now
                )
            )
    for fingerprint, config_id in inserted_ids.items():
        link_rows.append(
            ConfigurationSource(configuration_id=config_id, source_id=source.id, first_seen_at=now, last_seen_at=now)
        )
    if link_rows:
        db.add_all(link_rows)

    # Refresh last_seen + occurrence counters
    existing_ids = [cid for cid in existing.values()]
    for start in range(0, len(existing_ids), CHUNK):
        chunk = existing_ids[start : start + CHUNK]
        db.execute(update(Configuration).where(Configuration.id.in_(chunk)).values(last_seen_at=now))
        db.execute(
            update(ConfigurationSource)
            .where(ConfigurationSource.configuration_id.in_(chunk), ConfigurationSource.source_id == source.id)
            .values(last_seen_at=now, occurrences=ConfigurationSource.occurrences + 1)
        )

    db.flush()

    source.last_success_at = now
    source.etag = result.etag or source.etag
    source.last_modified = result.last_modified or source.last_modified
    source.config_count = accepted
    source.new_config_count = new_count
    source.duplicate_count = duplicate_count
    source.invalid_count = invalid_count
    source.consecutive_failures = 0
    source.last_error = None
    source.last_content_hash = hashlib.sha256(result.content).hexdigest() if result.content else source.last_content_hash

    fetch_row.status = "ok"
    fetch_row.finished_at = utcnow()
    fetch_row.parsed_count = len(payload.raw_links)
    fetch_row.accepted_count = accepted
    fetch_row.duplicate_count = duplicate_count
    fetch_row.invalid_count = invalid_count
    fetch_row.invalid_samples = invalid_samples
    db.commit()
    return len(payload.raw_links), accepted, new_count, invalid_count, "ok", {}


def run_pipeline(
    *,
    trigger: str = "manual",
    source_ids: list[int] | None = None,
    actor: str | None = None,
    prefetched: dict[int, FetchResult] | None = None,
) -> PipelineRun:
    """Execute one full pipeline run. Returns the persisted run record."""
    started = time.perf_counter()
    with pipeline_guard():
        with session_scope() as db:
            _assert_not_stale_running(db)
            query = select(Source).where(Source.enabled.is_(True))
            if source_ids:
                query = query.where(Source.id.in_(source_ids))
            elif settings.ingestion_upstream_only:
                query = query.where(Source.slug == "adan-public-bank")
            sources = list(db.execute(query.order_by(Source.id)).scalars())
            run = PipelineRun(trigger=trigger, status="running", sources_total=len(sources), details={"actor": actor})
            db.add(run)
            db.commit()

            totals = {"parsed": 0, "accepted": 0, "new": 0, "invalid": 0, "ok": 0, "failed": 0}
            per_source: list[dict] = []
            for source in sources:
                try:
                    parsed, accepted, new, invalid, status, detail = _process_source(
                        db, source, run, (prefetched or {}).get(source.id)
                    )
                except Exception as exc:  # isolate partial failures
                    db.rollback()
                    logger.exception("source processing crashed", extra={"context": {"source": source.slug}})
                    parsed = accepted = new = invalid = 0
                    status = "error"
                    detail = {"error": f"{type(exc).__name__}: {exc}"[:300]}
                    source_row = db.get(Source, source.id)
                    if source_row is not None:
                        source_row.last_error = detail["error"]
                        source_row.consecutive_failures += 1
                        db.commit()
                totals["parsed"] += parsed
                totals["accepted"] += accepted
                totals["new"] += new
                totals["invalid"] += invalid
                if status in {"ok", "not_modified", "skipped"}:
                    totals["ok"] += 1
                else:
                    totals["failed"] += 1
                per_source.append({"source": source.slug, "status": status, **detail})

            run.sources_ok = totals["ok"]
            run.sources_failed = totals["failed"]
            run.parsed_count = totals["parsed"]
            run.accepted_count = totals["accepted"]
            run.new_count = totals["new"]
            run.invalid_count = totals["invalid"]
            # Duplicates = parsed links that did not contribute a unique fingerprint
            # (in-feed repeats plus links already held by another source).
            run.duplicate_count = max(0, run.parsed_count - run.accepted_count)
            run.details = {"actor": actor, "sources": per_source}
            db.commit()
            try:
                publish_result = publisher.publish_bank(db, run)
            except Exception as exc:
                # Retain successfully ingested rows and a terminal job status.
                # Do not leave the pipeline blocked for an hour after disk errors.
                db.rollback()
                run.status = "failed"
                run.error = f"publication failed: {type(exc).__name__}"
                run.published = False
                run.publish_skipped_reason = "publication failed; inspect local snapshot integrity"
                run.finished_at = utcnow()
                run.duration_ms = (time.perf_counter() - started) * 1000
                db.commit()
                logger.exception("publication failed", extra={"context": {"run_id": run.id}})
                return run
            run.published = publish_result.published
            run.publish_skipped_reason = None if publish_result.published else publish_result.reason
            run.publish_path = publish_result.path
            run.output_hash = publish_result.content_hash

            if totals["failed"] and not totals["ok"]:
                run.status = "failed"
                run.error = "every enabled source failed"
            elif totals["failed"]:
                run.status = "partial"
            else:
                run.status = "succeeded"
            run.finished_at = utcnow()
            run.duration_ms = (time.perf_counter() - started) * 1000
            db.commit()
            prune_history(db)
            logger.info(
                "pipeline finished",
                extra={
                    "context": {
                        "run_id": run.id,
                        "status": run.status,
                        "accepted": run.accepted_count,
                        "new": run.new_count,
                        "published": run.published,
                        "duration_ms": round(run.duration_ms or 0),
                    }
                },
            )
            return run


_ASYNC_LOCK = threading.Lock()


def start_pipeline_async(*, trigger: str, source_ids: list[int] | None = None, actor: str | None = None) -> threading.Thread:
    """Queue one pipeline run in a background thread.

    Raises PipelineBusy when a run is already in flight, so the HTTP caller gets
    an immediate 409 instead of queueing duplicate work.
    """
    if not _ASYNC_LOCK.acquire(blocking=False):
        raise PipelineBusy("another ingestion run is already in progress")

    def _target() -> None:
        try:
            run_pipeline(trigger=trigger, source_ids=source_ids, actor=actor)
        except Exception:  # pragma: no cover - logged inside run_pipeline
            logger.exception("background pipeline run failed")
        finally:
            _ASYNC_LOCK.release()

    thread = threading.Thread(target=_target, name="nexus-pipeline", daemon=True)
    thread.start()
    return thread


def pipeline_in_flight() -> bool:
    return _ASYNC_LOCK.locked()


def prune_history(db: Session) -> dict[str, int]:
    """Apply configured retention windows. Called after each pipeline run."""
    from datetime import timedelta

    from app.models import HealthTest, SourceFetch

    now = utcnow()
    removed = 0
    for model, days in (
        (SourceFetch, settings.retention_fetch_days),
        (HealthTest, settings.retention_health_days),
    ):
        cutoff = now - timedelta(days=days)
        rows = db.query(model).filter(model.started_at < cutoff).delete(synchronize_session=False)  # type: ignore[attr-defined]
        removed += rows
    cutoff = now - timedelta(days=settings.retention_pipeline_days)
    keep = settings.publish_retention_runs
    old_runs = (
        db.execute(
            select(PipelineRun.id)
            .where(PipelineRun.started_at < cutoff, PipelineRun.status != "running")
            .order_by(PipelineRun.started_at.desc())
            .offset(keep)
        )
        .scalars()
        .all()
    )
    if old_runs:
        db.query(PipelineRun).filter(PipelineRun.id.in_(old_runs)).delete(synchronize_session=False)
    db.commit()
    return {"removed_rows": removed}


def source_count(db: Session) -> int:
    return int(db.execute(select(func.count(Source.id))).scalar_one())
