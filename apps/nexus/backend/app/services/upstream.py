"""Read-only view of the independent public GitHub pipeline."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.core.cache import cache_get, cache_set
from app.core.config import settings
from app.services.fetcher import UnsafeUrlError, validate_source_url

logger = logging.getLogger("nexus.upstream")
CACHE_KEY = "upstream:status"
CACHE_TTL = 300


def _next_github_schedule(now: datetime | None = None) -> str:
    """Next occurrence of the workflow cron minute, in UTC (GitHub may delay it)."""
    now = now or datetime.now(timezone.utc)
    minute = 7
    try:
        minute = int(settings.upstream_schedule_cron.split()[0])
    except (ValueError, IndexError):
        minute = 7
    candidate = now.replace(minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(hours=1)
    return candidate.isoformat()


def upstream_status(force: bool = False) -> dict:
    if not force and settings.upstream_enabled:
        cached = cache_get(CACHE_KEY)
        if cached:
            return cached
    result: dict = {
        "available": False,
        "source": settings.upstream_status_url,
        "repo": settings.upstream_repo,
        "branch": settings.upstream_branch,
        "schedule_cron": settings.upstream_schedule_cron,
        "schedule_note": "GitHub Actions schedules are approximate and may be delayed.",
        "next_expected_workflow_run": _next_github_schedule(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "error": None,
    }
    if not settings.upstream_enabled:
        result["error"] = "Upstream network access disabled by operator policy"
        return result
    try:
        validate_source_url(settings.upstream_status_url)
        with httpx.Client(timeout=8.0, follow_redirects=False, trust_env=False) as client:
            response = client.get(settings.upstream_status_url, headers={"User-Agent": settings.fetch_user_agent})
        if response.status_code != 200:
            raise httpx.HTTPStatusError("unexpected status", request=response.request, response=response)
        payload = response.json()
        result.update(
            {
                "available": True,
                "updated_at_utc": payload.get("updated_at_utc"),
                "total": payload.get("total"),
                "warning": payload.get("warning"),
                "sources": payload.get("sources", []),
            }
        )
    except (httpx.HTTPError, ValueError, UnsafeUrlError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"[:200]
        logger.warning("upstream status unavailable", extra={"context": {"error": result["error"]}})
    cache_set(CACHE_KEY, result, CACHE_TTL if result["available"] else 60)
    return result


def workflow_runs(limit: int = 5) -> dict:
    """GitHub Actions history requires an operator token; never guessed."""
    if not settings.upstream_enabled:
        return {"available": False, "reason": "Upstream network access disabled by operator policy", "runs": []}
    if not settings.github_token:
        return {
            "available": False,
            "reason": "GITHUB_TOKEN is not configured; workflow run history is unavailable.",
            "runs": [],
        }
    url = f"https://api.github.com/repos/{settings.upstream_repo}/actions/workflows/hourly-update.yml/runs"
    try:
        validate_source_url(url)
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            response = client.get(
                url,
                params={"per_page": limit},
                headers={
                    "Authorization": f"Bearer {settings.github_token}",
                    "Accept": "application/vnd.github+json",
                    "User-Agent": settings.fetch_user_agent,
                },
            )
        if response.status_code != 200:
            return {"available": False, "reason": f"GitHub API returned {response.status_code}", "runs": []}
        data = response.json()
        return {
            "available": True,
            "runs": [
                {
                    "id": run.get("id"),
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                    "created_at": run.get("created_at"),
                    "updated_at": run.get("updated_at"),
                    "event": run.get("event"),
                    "html_url": run.get("html_url"),
                }
                for run in data.get("workflow_runs", [])[:limit]
            ],
        }
    except (httpx.HTTPError, ValueError, UnsafeUrlError) as exc:
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"[:180], "runs": []}
