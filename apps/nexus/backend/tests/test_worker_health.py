import json
import time

from app.workers.healthcheck import is_healthy, write_heartbeat


def test_worker_heartbeat_requires_fresh_running_scheduler(tmp_path):
    path = str(tmp_path / "worker.heartbeat")
    assert not is_healthy(path)
    write_heartbeat(path, True)
    assert is_healthy(path)
    write_heartbeat(path, False)
    assert not is_healthy(path)


def test_worker_heartbeat_rejects_stale_or_corrupt_content(tmp_path):
    path = tmp_path / "worker.heartbeat"
    for content in ["broken", "{}", json.dumps({"updated_at": time.time() - 60, "scheduler_running": True})]:
        path.write_text(content)
        assert not is_healthy(str(path))
