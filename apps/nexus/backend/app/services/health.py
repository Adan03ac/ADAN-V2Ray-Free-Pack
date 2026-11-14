"""Isolated health-testing engine.

TCP reachability is deliberately NOT reported as a working VPN connection. Only
syntax, DNS and TCP stages are implemented; protocol-level and end-to-end tests
require an operator-provided, authorized test agent and are marked unavailable.
"""

from __future__ import annotations

import concurrent.futures
import logging
import ipaddress
import socket
import threading
import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import session_scope
from app.models import Configuration, HealthTest, HealthTestJob, utcnow

from app.services.fetcher import _is_blocked_address

logger = logging.getLogger("nexus.health")

VALID_CONNECTIVITY = {"untested", "dns_resolved", "reachable", "unreachable", "failed", "unknown"}
_ACTIVE_THREADS: dict[int, threading.Thread] = {}
_ACTIVE_LOCK = threading.Lock()
_JOB_SLOT = threading.BoundedSemaphore(1)


class HealthBusy(RuntimeError):
    pass

_DNS_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="health-dns")
_DNS_SLOTS = threading.BoundedSemaphore(8)

STAGE_SYNTAX = "syntax"
STAGE_DNS = "dns"
STAGE_TCP = "tcp"


@dataclass
class StageResult:
    status: str
    stage: str
    latency_ms: float | None = None
    category: str | None = None
    detail: str | None = None


def _dns_stage(host: str, timeout: float) -> StageResult:
    def resolve() -> list[str]:
        return [info[4][0] for info in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)]

    try:
        if not _DNS_SLOTS.acquire(blocking=False):
            return StageResult("failed", STAGE_DNS, category="dns_busy", detail="DNS resolver capacity exhausted")
        future = _DNS_POOL.submit(resolve)
        future.add_done_callback(lambda _future: _DNS_SLOTS.release())
        addresses = future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        return StageResult("failed", STAGE_DNS, category="dns_timeout", detail=f"DNS lookup exceeded {timeout}s")
    except (socket.gaierror, OSError) as exc:
        return StageResult("failed", STAGE_DNS, category="dns_failure", detail=str(exc)[:200])
    if not addresses:
        return StageResult("failed", STAGE_DNS, category="dns_failure", detail="no addresses returned")
    if any(_is_blocked_address(address) for address in addresses):
        return StageResult("failed", STAGE_DNS, category="blocked_target", detail="private or non-global destination blocked")
    return StageResult("dns_resolved", STAGE_DNS, detail=addresses[0])


def _tcp_stage(host: str, port: int, timeout: float) -> StageResult:
    # Only a numeric IP from the checked DNS stage is accepted. No second DNS
    # lookup may redirect a probe into an internal network.
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return StageResult("unknown", STAGE_TCP, category="blocked_target", detail="numeric target required")
    authorized = [ipaddress.ip_network(c.strip(), strict=False) for c in settings.health_authorized_cidrs.split(",") if c.strip()]
    if _is_blocked_address(host) or not any(address in network for network in authorized):
        return StageResult("unknown", STAGE_TCP, category="unauthorized_target", detail="destination not authorized by operator policy")
    started = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            elapsed = (time.perf_counter() - started) * 1000
            return StageResult("reachable", STAGE_TCP, latency_ms=round(elapsed, 1))
    except socket.timeout:
        return StageResult("failed", STAGE_TCP, category="tcp_timeout", detail=f"connect exceeded {timeout}s")
    except ConnectionRefusedError:
        return StageResult("failed", STAGE_TCP, category="tcp_refused", detail="connection refused")
    except OSError as exc:
        return StageResult("failed", STAGE_TCP, category="tcp_error", detail=str(exc)[:200])


def test_configuration(config: Configuration, stages: list[str], timeout: float, allow_tcp: bool) -> StageResult:
    """Run the requested stages against one registered configuration."""
    if config.validation_status != "valid":
        return StageResult("failed", STAGE_SYNTAX, category="invalid_syntax", detail="configuration failed validation")

    if STAGE_DNS in stages or STAGE_TCP in stages:
        dns = _dns_stage(config.host, min(timeout, settings.health_dns_timeout_seconds))
        if dns.status != "dns_resolved":
            return dns
        if STAGE_TCP not in stages:
            return dns

    if STAGE_TCP in stages:
        if not allow_tcp:
            return StageResult("unknown", STAGE_TCP, detail="TCP stage disabled by policy")
        if getattr(config, "transport", "tcp") == "quic":
            return StageResult("unknown", STAGE_TCP, category="unsupported_transport", detail="QUIC/UDP verification is unavailable")
        return _tcp_stage(dns.detail or "", config.port, timeout)

    return StageResult("valid_format", STAGE_SYNTAX)


def _run_job(job_id: int, configuration_ids: list[int] | None = None) -> None:
    try:
        with session_scope() as db:
            job = db.get(HealthTestJob, job_id)
            if job is None:
                return
            job.status = "running"
            job.started_at = utcnow()
            db.commit()

            query = select(Configuration).where(Configuration.validation_status == "valid")
            if configuration_ids:
                query = query.where(Configuration.id.in_(configuration_ids))
            targets = db.execute(query.order_by(Configuration.id).limit(job.total)).scalars().all()

            done = threaded = failed = 0
            stage_results: dict[int, StageResult] = {}

            def worker(config: Configuration) -> tuple[int, StageResult]:
                return config.id, test_configuration(
                    config,
                    stages=job.stages or [STAGE_SYNTAX, STAGE_DNS, STAGE_TCP],
                    timeout=settings.health_timeout_seconds,
                    allow_tcp=settings.health_allow_tcp,
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(job.concurrency, 16))) as pool:
                futures = {pool.submit(worker, config): config for config in targets}
                for future in concurrent.futures.as_completed(futures):
                    config = futures[future]
                    try:
                        config_id, result = future.result()
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.exception("health worker crashed", extra={"context": {"config_id": config.id}})
                        config_id, result = config.id, StageResult("unknown", STAGE_TCP, detail=str(exc)[:200])
                    stage_results[config_id] = result
                    done += 1
                    if result.status == "reachable":
                        threaded += 1
                    elif result.status == "failed":
                        failed += 1
                    job.completed = done
                    job.reachable = threaded
                    job.failed = failed
                    if done % 10 == 0:
                        db.commit()

            now = utcnow()
            for config in targets:
                result = stage_results.get(config.id)
                if result is None:
                    continue
                config.last_tested_at = now
                config.test_agent = job.agent_label
                if result.status == "reachable":
                    config.connectivity_status = "reachable"
                    config.last_latency_ms = result.latency_ms
                    samples = list(config.latency_samples or [])
                    samples.append(result.latency_ms)
                    config.latency_samples = samples[-25:]
                    values = [value for value in config.latency_samples if isinstance(value, (int, float))]
                    config.latency_avg_ms = round(sum(values) / len(values), 1) if values else None
                elif result.status == "failed":
                    config.connectivity_status = "failed"
                    config.failure_count = (config.failure_count or 0) + 1
                    config.last_latency_ms = None
                elif result.status == "dns_resolved":
                    config.connectivity_status = "dns_resolved"
                elif result.status != "valid_format":
                    config.connectivity_status = "unknown"

                db.add(
                    HealthTest(
                        configuration_id=config.id,
                        job_id=job.id,
                        status=result.status,
                        stage_reached=result.stage,
                        latency_ms=result.latency_ms,
                        error_category=result.category,
                        error_detail=result.detail,
                        agent_label=job.agent_label,
                        agent_region=job.agent_region,
                        started_at=job.started_at or now,
                        finished_at=now,
                    )
                )
            job.status = "completed"
            job.finished_at = utcnow()
            db.commit()
    except Exception as exc:
        logger.exception("health job failed", extra={"context": {"job_id": job_id}})
        with session_scope() as db:
            job = db.get(HealthTestJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error = f"{type(exc).__name__}: {exc}"[:300]
                job.finished_at = utcnow()
                db.commit()
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE_THREADS.pop(job_id, None)
        _JOB_SLOT.release()


def start_job(
    db: Session,
    *,
    configuration_ids: list[int] | None,
    limit: int,
    stages: list[str],
    user_id: int | None,
) -> HealthTestJob:
    if not _JOB_SLOT.acquire(blocking=False):
        raise HealthBusy("A health job is already active in this process")
    limit = max(1, min(limit, settings.health_max_batch))
    stages = [stage for stage in stages if stage in {STAGE_SYNTAX, STAGE_DNS, STAGE_TCP}] or [
        STAGE_SYNTAX,
        STAGE_DNS,
        STAGE_TCP,
    ]
    job = HealthTestJob(
        status="queued",
        requested_by=user_id,
        stages=stages,
        concurrency=settings.health_concurrency,
        agent_label=settings.health_agent_label,
        agent_region=settings.health_agent_region,
    )
    try:
        query = select(Configuration.id).where(Configuration.validation_status == "valid")
        if configuration_ids:
            query = query.where(Configuration.id.in_(configuration_ids))
        selected_ids = list(db.execute(query.order_by(Configuration.id).limit(limit)).scalars())
        job.total = len(selected_ids)
        db.add(job)
        db.commit()
    except Exception:
        _JOB_SLOT.release()
        raise

    # The job row is authoritative; selection happens inside the worker thread so
    # an explicit id list cannot be tampered with between request and execution.
    with _ACTIVE_LOCK:
        thread = threading.Thread(
            target=_run_job, args=(job.id, selected_ids), name=f"health-job-{job.id}", daemon=True
        )
        _ACTIVE_THREADS[job.id] = thread
        thread.start()
    return job


def active_workers() -> int:
    with _ACTIVE_LOCK:
        return sum(1 for thread in _ACTIVE_THREADS.values() if thread.is_alive())


def queue_snapshot(db: Session) -> dict[str, int]:
    jobs = db.execute(select(HealthTestJob).order_by(HealthTestJob.requested_at.desc()).limit(20)).scalars().all()
    return {
        "active_workers": active_workers(),
        "queued": sum(1 for job in jobs if job.status == "queued"),
        "running": sum(1 for job in jobs if job.status == "running"),
        "concurrency_limit": settings.health_concurrency,
        "max_batch": settings.health_max_batch,
    }
