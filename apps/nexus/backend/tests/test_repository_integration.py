from pathlib import Path

import pytest

from app.core.config import settings
from app.models import Configuration, Source
from app.services import ingestion
from app.services.fetcher import FetchResult
from scripts.import_repository_bank import import_bank
from tests.test_ingestion import VALID_A, _make_source


def test_repository_import_uses_normal_validation_without_network(db, tmp_path, monkeypatch):
    bank = tmp_path / "subscription.txt"
    bank.write_text(VALID_A + "\n" + VALID_A + "\nvmess://invalid\n")
    monkeypatch.setattr(ingestion.SafeFetcher, "fetch", lambda *a, **k: pytest.fail("snapshot import fetched a URL"))
    before = bank.read_bytes()
    source = db.query(Source).filter(Source.slug == "adan-public-bank").one()
    source.etag = '"old-remote-etag"'
    source.last_modified = "old-remote-date"
    db.commit()
    first = import_bank(bank)
    second = import_bank(bank)
    assert first["new"] == 1 and first["invalid"] == 1
    assert second["new"] == 0 and db.query(Configuration).count() == 1
    assert bank.read_bytes() == before
    db.refresh(source)
    assert source.etag is None and source.last_modified is None


def test_repository_import_rejects_oversized_input(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "source_max_bytes", 4)
    bank = tmp_path / "bank"
    bank.write_bytes(b"12345")
    with pytest.raises(ValueError, match="exceeds"):
        import_bank(bank)


def test_scheduler_mode_selects_only_public_bank(db, monkeypatch):
    monkeypatch.setattr(settings, "ingestion_upstream_only", True)
    urls = []
    def fetch(self, url, **kwargs):
        urls.append(url)
        return FetchResult(ok=True, status_code=200, content=VALID_A.encode())
    monkeypatch.setattr(ingestion.SafeFetcher, "fetch", fetch)
    _make_source(db, "other-explicit-source", "https://other.example/feed")
    run = ingestion.run_pipeline(trigger="schedule")
    assert run.sources_total == 1 and len(urls) == 1
    assert "/Adan03ac/ADAN-V2Ray-Free-Pack/" in urls[0]
    # Explicit admin refreshes of other configured sources remain supported.
    source = db.query(Source).filter(Source.slug == "other-explicit-source").one()
    run = ingestion.run_pipeline(trigger="manual", source_ids=[source.id])
    assert run.sources_total == 1 and urls[-1] == source.url
