"""Import a checked-out public bank through the normal validation pipeline.

This CLI does not fetch a URL, probe endpoints or write repository artifacts.
It is useful for a first boot or a disconnected test of a known checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.db import session_scope
from app.core.logging import configure_logging
from app.models import Source
from app.services.fetcher import FetchResult
from app.services.ingestion import run_pipeline
from app.services.seed import bootstrap


def import_bank(path: Path) -> dict:
    with path.open("rb") as handle:
        content = handle.read(settings.source_max_bytes + 1)
    if not content or len(content) > settings.source_max_bytes:
        raise ValueError("Repository bank is empty or exceeds SOURCE_MAX_BYTES")
    with session_scope() as db:
        bootstrap(db)
        source = db.execute(select(Source).where(Source.slug == "adan-public-bank")).scalar_one()
        if not source.enabled or source.source_type != "github_raw" or source.is_discovery:
            raise ValueError("The adan-public-bank source must be enabled with type github_raw")
        source_id = source.id
        # A checkout snapshot may differ from the last HTTP response. Do not
        # reuse validators for a remote payload we just replaced locally.
        source.etag = None
        source.last_modified = None
    run = run_pipeline(
        trigger="repository-import",
        source_ids=[source_id],
        prefetched={source_id: FetchResult(ok=True, status_code=200, content=content)},
    )
    return {
        "run_id": run.id,
        "status": run.status,
        "accepted": run.accepted_count,
        "new": run.new_count,
        "invalid": run.invalid_count,
        "sha256": hashlib.sha256(content).hexdigest(),
        "note": "Syntax validation only; no VPN connectivity claim or network probe.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, required=True)
    args = parser.parse_args()
    configure_logging()
    result = import_bank(args.bank)
    print(json.dumps(result))
    return 0 if result["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
