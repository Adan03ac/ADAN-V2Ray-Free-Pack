"""FastAPI application entrypoint for ADAN NEXUS | CONNECT."""

from __future__ import annotations

import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import (
    analytics,
    auth,
    automation,
    cloudflare,
    configurations,
    dashboard,
    health,
    public,
    sources,
    subscriptions,
    system,
)
from app.core.config import settings
from app.core.db import engine, session_scope
from app.core.logging import configure_logging, _redact
from app.models import Base
from app.services.seed import bootstrap
from app.workers.scheduler import scheduler

logger = logging.getLogger("nexus.api")
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _origin_allowed(origin: str, request: Request) -> bool:
    """Allow configured origins, the served origin itself, and configured suffixes.

    A same-origin browser request is not a CSRF risk: the comparison uses the host
    the request actually arrived on (including the proxy's forwarded host), so a
    page on another domain can never satisfy it.
    """
    if origin in settings.origins:
        return True
    parsed = urlsplit(origin)
    if not parsed.scheme or not parsed.netloc:
        return False
    # Only the host this request actually arrived on counts. A forwarded-host
    # header is deliberately not trusted: behind a proxy, deployments list their
    # public origin (or suffix) in configuration instead.
    host = request.headers.get("host")
    if host and parsed.netloc.lower() == host.strip().lower():
        return True
    hostname = (parsed.hostname or "").lower()
    for raw_suffix in settings.origin_suffixes:
        suffix = raw_suffix.strip().lstrip(".").lower()
        if suffix and (hostname == suffix or hostname.endswith(f".{suffix}")):
            return True
    return False


def _cors_origin_regex() -> str | None:
    suffixes = [suffix.strip().lstrip(".") for suffix in settings.origin_suffixes if suffix.strip()]
    if not suffixes:
        return None
    alternation = "|".join(re.escape(suffix) for suffix in suffixes)
    return rf"^https?://([a-z0-9-]+\.)*({alternation})$"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    if settings.database_auto_create:
        Base.metadata.create_all(bind=engine)
    with session_scope() as db:
        bootstrap(db)
    if settings.embedded_worker and settings.ingestion_enabled:
        scheduler.start()
    logger.info(
        "service started",
        extra={"context": {"environment": settings.environment, "scheduler": scheduler.is_running()}},
    )
    yield
    scheduler.stop()
    logger.info("service stopped")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0-mvp",
    description=(
        "Connectivity Intelligence and Subscription Management Platform. "
        "Source ingestion, configuration provenance, health testing and subscription exports. "
        "No metric is synthesized: unavailable data is reported as unavailable."
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_origin_regex=_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
    max_age=600,
)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    origin = request.headers.get("origin")
    if request.method not in SAFE_METHODS and origin and not _origin_allowed(origin, request):
        logger.warning(
            "cross-origin mutation rejected",
            extra={"context": {"origin": origin, "path": _redact(request.url.path), "host": request.headers.get("host")}},
        )
        return JSONResponse(
            status_code=403,
            content={"detail": "Cross-origin request rejected"},
            headers={"X-Request-ID": request_id},
        )
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if request.url.path.startswith(settings.api_v1_prefix) and "no-store" not in response.headers.get(
        "cache-control", ""
    ):
        response.headers["Cache-Control"] = "no-store"
    duration_ms = (time.perf_counter() - started) * 1000
    if duration_ms > 1500 or response.status_code >= 500:
        logger.warning(
            "slow or failing request",
            extra={
                "context": {
                    "path": _redact(request.url.path),
                    "method": request.method,
                    "status": response.status_code,
                    "duration_ms": round(duration_ms, 1),
                }
            },
        )
    return response


for router in (
    auth.router,
    dashboard.router,
    sources.router,
    configurations.router,
    health.router,
    subscriptions.router,
    automation.router,
    analytics.router,
    cloudflare.router,
    system.router,
    public.router,
):
    app.include_router(router, prefix=settings.api_v1_prefix)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "service": settings.app_name,
        "version": "1.0.0-mvp",
        "docs": "/api/docs",
        "health": f"{settings.api_v1_prefix}/system/health",
        "statement": "Public subscription pipeline is independent of this service.",
    }
