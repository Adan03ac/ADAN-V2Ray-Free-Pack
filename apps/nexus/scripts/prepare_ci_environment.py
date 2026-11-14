"""Create fresh disposable Docker smoke-test credentials; never prints them."""
import json
import os
from pathlib import Path
import secrets

APP = Path(__file__).resolve().parents[1]
values = {
    "SECRET_KEY": secrets.token_urlsafe(48),
    "BOOTSTRAP_ADMIN_EMAIL": "ci@nexus.local",
    "BOOTSTRAP_ADMIN_PASSWORD": secrets.token_urlsafe(24),
    "POSTGRES_PASSWORD": secrets.token_urlsafe(24),
    "POSTGRES_USER": "nexus", "POSTGRES_DB": "nexus",
    "ALLOW_REGISTRATION": "false", "COOKIE_SECURE": "false",
    "ALLOWED_ORIGINS": "http://127.0.0.1:3000", "ALLOWED_ORIGIN_SUFFIXES": "",
    "PUBLIC_BASE_URL": "http://127.0.0.1:3000",
    "INGESTION_ENABLED": "false", "UPSTREAM_ENABLED": "false", "HEALTH_ALLOW_TCP": "false",
    "INGESTION_UPSTREAM_ONLY": "true", "EMBEDDED_WORKER": "false",
}
for path, content in [
    (APP / ".env", "\n".join(f"{k}={v}" for k, v in values.items()) + "\n"),
    (APP / "data/ci-environment.json", json.dumps(values)),
]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as handle:
        handle.write(content)
print("Disposable CI environment prepared; credentials kept local to the runner.")
