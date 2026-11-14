#!/usr/bin/env python3
"""Manual ingestion entrypoint.

Usage:
    python -m scripts.ingest                 # all enabled sources
    python -m scripts.ingest --source 3      # one source
    python -m scripts.ingest --list          # show the registry
"""

from __future__ import annotations

import argparse
import json
import sys

from app.core.config import settings
from app.core.db import engine, session_scope
from app.core.logging import configure_logging
from app.models import Base
from app.services.ingestion import PipelineBusy, run_pipeline
from app.services.seed import bootstrap


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the ADAN NEXUS ingestion pipeline")
    parser.add_argument("--source", action="append", type=int, default=None, help="source id (repeatable)")
    parser.add_argument("--trigger", default="cli")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    configure_logging()
    if settings.database_auto_create:
        Base.metadata.create_all(bind=engine)
    with session_scope() as db:
        bootstrap(db)
        if args.list:
            from sqlalchemy import select

            from app.models import Source

            for source in db.execute(select(Source).order_by(Source.id)).scalars():
                print(f"{source.id:>3}  {'on ' if source.enabled else 'off'}  {source.source_type:<14} {source.name}")
            return 0

    try:
        run = run_pipeline(trigger=args.trigger, source_ids=args.source)
    except PipelineBusy as exc:
        print(f"pipeline busy: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "run_id": run.id,
                "status": run.status,
                "sources_ok": run.sources_ok,
                "sources_failed": run.sources_failed,
                "parsed": run.parsed_count,
                "accepted": run.accepted_count,
                "new": run.new_count,
                "invalid": run.invalid_count,
                "published": run.published,
                "publish_skipped_reason": run.publish_skipped_reason,
                "output_hash": run.output_hash,
                "duration_ms": round(run.duration_ms or 0, 1),
            },
            indent=2,
        )
    )
    return 0 if run.status in {"succeeded", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
