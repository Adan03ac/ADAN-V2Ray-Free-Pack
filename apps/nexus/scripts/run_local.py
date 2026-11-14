#!/usr/bin/env python3
"""Start a loopback-only development instance (Python 3.12+, Node 22+)."""
from __future__ import annotations

import getpass
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
import venv
import webbrowser

APP = Path(__file__).resolve().parents[1]
REPO = APP.parents[1]


def main() -> int:
    if sys.version_info < (3, 12):
        raise SystemExit("Python 3.12 or newer is required")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    node = shutil.which("node")
    if not npm or not node:
        raise SystemExit("Install Node.js 22 LTS (includes npm), then retry")
    if int(subprocess.check_output([node, "-p", "process.versions.node.split('.')[0]"], text=True).strip()) < 22:
        raise SystemExit("Node.js 22 or newer is required")
    if (APP / ".env").exists() or (APP / "backend/.env").exists():
        raise SystemExit("Existing .env detected: use the documented manual startup to preserve your configuration")
    runtime = APP / "data/local-runtime.json"
    if not runtime.exists():
        email = input("Local administrator email [admin@adan.local]: ").strip() or "admin@adan.local"
        password = getpass.getpass("Choose your local admin password (10-72 UTF-8 bytes): ")
        if len(password) < 10 or len(password.encode()) > 72:
            raise SystemExit("Password must be at least 10 characters and at most 72 UTF-8 bytes")
        if password != getpass.getpass("Repeat password: "):
            raise SystemExit("Passwords did not match")
        config = {
            "ENVIRONMENT": "development", "SECRET_KEY": secrets.token_urlsafe(48),
            "BOOTSTRAP_ADMIN_EMAIL": email, "BOOTSTRAP_ADMIN_PASSWORD": password,
            "DATABASE_URL": "sqlite:///" + (APP / "data/local.db").as_posix(),
            "DATABASE_AUTO_CREATE": "false", "REDIS_URL": "",
            "PUBLISH_DIR": str(APP / "data/published"), "PIPELINE_LOCK_PATH": str(APP / "data/pipeline.lock"),
            "EMBEDDED_WORKER": "true", "INGESTION_ENABLED": "true", "INGESTION_UPSTREAM_ONLY": "true",
            "INGESTION_INTERVAL_MINUTES": "60", "INGESTION_JITTER_SECONDS": "0",
            "HEALTH_ALLOW_TCP": "false", "HEALTH_AUTHORIZED_CIDRS": "", "ALLOW_REGISTRATION": "false",
            "COOKIE_SECURE": "false", "ALLOWED_ORIGIN_SUFFIXES": "",
            "ALLOWED_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000",
            "PUBLIC_BASE_URL": "http://localhost:3000", "API_PROXY_TARGET": "http://127.0.0.1:8000",
            "NEXT_TELEMETRY_DISABLED": "1",
        }
        runtime.parent.mkdir(parents=True, exist_ok=True)
        with os.fdopen(os.open(runtime, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as handle:
            json.dump(config, handle)
    config = json.loads(runtime.read_text(encoding="utf-8"))
    env = {**os.environ, **config}
    python = APP / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(APP / ".venv")
    def run(args, cwd=APP):
        subprocess.run([str(a) for a in args], cwd=cwd, env=env, check=True)
    run([python, "-m", "pip", "install", "-r", APP / "backend/requirements.txt"])
    run([npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"], APP / "frontend")
    run([python, "-m", "alembic", "upgrade", "head"], APP / "backend")
    bank = REPO / "subscription.txt"
    if bank.exists():
        run([python, "-m", "scripts.import_repository_bank", "--bank", bank], APP / "backend")
    processes = []
    try:
        processes.append(subprocess.Popen([str(python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--no-access-log"], cwd=APP / "backend", env=env))
        # Use node directly so Ctrl+C also terminates the actual Next process on Windows.
        processes.append(subprocess.Popen([node, "node_modules/next/dist/bin/next", "dev", "-H", "127.0.0.1", "-p", "3000"], cwd=APP / "frontend", env=env))
        print("Local console: http://localhost:3000 — sign in with the account you chose. Ctrl+C stops both services.", flush=True)
        while all(p.poll() is None for p in processes):
            time.sleep(.5)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
