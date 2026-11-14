"""Standalone background worker process (docker-compose service `worker`).

Runs the ingestion scheduler only. The API's embedded scheduler is disabled with
EMBEDDED_WORKER=false so exactly one ingestion scheduler is active.
"""

from __future__ import annotations

import logging
import signal
import time

from app.core.config import settings
from app.core.db import engine
from app.core.logging import configure_logging
from app.models import Base
from app.workers.scheduler import scheduler

logger = logging.getLogger("nexus.worker")


def main() -> None:
    configure_logging()
    if settings.database_auto_create:
        Base.metadata.create_all(bind=engine)
    from app.core.db import session_scope
    from app.services.seed import bootstrap

    with session_scope() as db:
        bootstrap(db)
    scheduler.start()
    logger.info("worker started")
    stop = False

    def _handle(signum, _frame):  # type: ignore[no-untyped-def]
        nonlocal stop
        logger.info("worker received signal %s", signum)
        stop = True

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)
    while not stop:
        time.sleep(2)
    scheduler.stop()
    logger.info("worker stopped")


if __name__ == "__main__":
    main()
