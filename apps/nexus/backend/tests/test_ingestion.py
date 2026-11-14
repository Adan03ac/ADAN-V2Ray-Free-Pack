"""Pipeline tests: deduplication, malformed input, partial failure, retries, publication."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import Configuration, PipelineRun, Source, SourceFetch
from app.services import ingestion
from app.services.fetcher import FetchResult

VALID_A = "vless://aaaaaaaa-1111-2222-3333-444444444444@198.51.100.10:443?type=ws&security=tls&sni=a.example.com#A"
VALID_B = "trojan://pass-b@198.51.100.11:443?sni=b.example.com#B"
VALID_C = "hysteria2://pass-c@198.51.100.12:443?sni=c.example.com#C"
MALFORMED = "ss://this-is-not-a-valid-link"


class StubFetcher:
    responses: dict[str, FetchResult] = {}

    def __init__(self, *args, **kwargs) -> None:
        pass

    def fetch(self, url: str, etag: str | None = None, last_modified: str | None = None) -> FetchResult:
        return self.responses.get(url, FetchResult(ok=False, error="no stub", error_category="stub"))


def _make_source(db, slug: str, url: str, source_type: str = "plain_text") -> Source:
    source = Source(
        slug=slug,
        name=slug,
        url=url,
        source_type=source_type,
        enabled=True,
        trust_level="community",
        tags=["test"],
    )
    db.add(source)
    db.commit()
    return source


def test_pipeline_dedupes_and_records_invalid(db, monkeypatch):
    db.query(Configuration).delete()
    db.query(Source).delete()
    db.commit()
    payload = f"{VALID_A}\n{VALID_B}\n{VALID_A}\n{MALFORMED}\n"
    StubFetcher.responses = {"https://example.test/feed.txt": FetchResult(ok=True, status_code=200, content=payload.encode())}
    monkeypatch.setattr(ingestion, "SafeFetcher", StubFetcher)
    _make_source(db, "feed-one", "https://example.test/feed.txt")

    run = ingestion.run_pipeline(trigger="test")
    db.expire_all()

    assert run.status == "succeeded"
    assert run.accepted_count == 2
    assert run.new_count == 2
    assert run.invalid_count == 1
    configs = db.execute(select(func.count(Configuration.id))).scalar_one()
    assert configs == 2

    fetch = db.execute(select(SourceFetch).order_by(SourceFetch.id.desc())).scalars().first()
    assert fetch.status == "ok"
    assert fetch.invalid_samples and fetch.invalid_samples[0]["scheme"] == "ss"
    assert "this-is-not-a-valid-link" not in str(fetch.invalid_samples)

    # Second run: idempotent, nothing new, publication skipped (unchanged output).
    run2 = ingestion.run_pipeline(trigger="test")
    db.expire_all()
    assert run2.new_count == 0
    assert run2.duplicate_count >= 2
    assert run2.published is False
    assert "unchanged" in (run2.publish_skipped_reason or "")
    assert db.execute(select(func.count(Configuration.id))).scalar_one() == 2


def test_partial_failure_preserves_previous_bank(db, monkeypatch):
    db.query(Configuration).delete()
    db.query(Source).delete()
    db.commit()
    StubFetcher.responses = {
        "https://example.test/good.txt": FetchResult(ok=True, status_code=200, content=f"{VALID_C}\n".encode()),
        "https://example.test/broken.txt": FetchResult(
            ok=False, status_code=503, error="HTTP 503", error_category="http_error"
        ),
    }
    monkeypatch.setattr(ingestion, "SafeFetcher", StubFetcher)
    _make_source(db, "good-feed", "https://example.test/good.txt")
    broken = _make_source(db, "broken-feed", "https://example.test/broken.txt")

    run = ingestion.run_pipeline(trigger="test")
    db.expire_all()
    assert run.status == "partial"
    assert run.sources_ok == 1 and run.sources_failed == 1
    assert db.execute(select(func.count(Configuration.id))).scalar_one() == 1
    refreshed = db.get(Source, broken.id)
    assert refreshed.consecutive_failures == 1
    assert refreshed.last_error == "HTTP 503"


def test_total_failure_keeps_published_bank(db, monkeypatch):
    db.query(Configuration).delete()
    db.query(Source).delete()
    db.commit()
    StubFetcher.responses = {
        "https://example.test/down.txt": FetchResult(ok=False, error="timed out", error_category="timeout")
    }
    monkeypatch.setattr(ingestion, "SafeFetcher", StubFetcher)
    _make_source(db, "down-feed", "https://example.test/down.txt")

    run = ingestion.run_pipeline(trigger="test")
    assert run.status == "failed"
    assert run.published is False
    assert "previous bank preserved" in (run.publish_skipped_reason or "")


def test_pipeline_busy_is_rejected(db):
    with ingestion.pipeline_guard():
        try:
            ingestion.run_pipeline(trigger="test")
        except ingestion.PipelineBusy as exc:
            assert "already in progress" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("expected PipelineBusy")


def test_run_history_is_recorded(db, monkeypatch):
    db.query(Configuration).delete()
    db.query(Source).delete()
    db.commit()
    StubFetcher.responses = {
        "https://example.test/history.txt": FetchResult(ok=True, status_code=200, content=f"{VALID_A}\n".encode())
    }
    monkeypatch.setattr(ingestion, "SafeFetcher", StubFetcher)
    _make_source(db, "history-feed", "https://example.test/history.txt")
    run = ingestion.run_pipeline(trigger="test")

    runs = db.execute(select(PipelineRun).order_by(PipelineRun.id)).scalars().all()
    assert runs
    assert runs[-1].id == run.id
    assert all(item.finished_at is not None for item in runs)
    assert all(item.status != "running" for item in runs)
