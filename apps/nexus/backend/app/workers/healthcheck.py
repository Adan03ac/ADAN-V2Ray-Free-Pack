"""Worker heartbeat healthcheck; the worker does not serve the API HTTP port."""
from __future__ import annotations

import json
import os
from pathlib import Path
import time


def write_heartbeat(path: str, scheduler_running: bool) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps({"updated_at": time.time(), "scheduler_running": scheduler_running}))
    os.replace(temporary, target)


def is_healthy(path: str, max_age: float = 30) -> bool:
    try:
        payload = json.loads(Path(path).read_text())
        age = time.time() - float(payload["updated_at"])
        return 0 <= age <= max_age and payload["scheduler_running"] is True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def main() -> int:
    from app.core.config import settings
    return 0 if is_healthy(settings.worker_heartbeat_path) else 1


if __name__ == "__main__":
    raise SystemExit(main())
