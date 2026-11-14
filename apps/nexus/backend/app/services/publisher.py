"""Atomic subscription publication with change detection.

The public GitHub pipeline (build.py + hourly workflow) remains independent. This
publisher writes a mirrored, versioned snapshot locally; a GitHub provider can be
plugged in later without the pipeline depending on this application's database.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decrypt_secret
from app.models import Configuration, PipelineRun, utcnow


@dataclass
class PublishResult:
    published: bool
    reason: str
    path: str | None = None
    content_hash: str | None = None
    total: int = 0


class PublicationProvider(Protocol):
    name: str

    def publish(self, payload: dict[str, bytes], content_hash: str) -> PublishResult: ...


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


class LocalPublicationProvider:
    name = "local"

    def publish(self, payload: dict[str, bytes], content_hash: str) -> PublishResult:
        root = Path(settings.publish_dir)
        manifest_path = root / "manifest.json"
        previous_hash = None
        if manifest_path.exists():
            try:
                previous_hash = json.loads(manifest_path.read_text("utf-8")).get("content_hash")
            except (json.JSONDecodeError, OSError):
                previous_hash = None
        if previous_hash == content_hash:
            return PublishResult(False, "unchanged output; publication skipped", str(root), content_hash)

        version_dir = root / "versions" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        for name, data in payload.items():
            _atomic_write(version_dir / name, data)
        for name, data in payload.items():
            _atomic_write(root / name, data)
        manifest = json.loads(payload.get("manifest.json", b"{}").decode("utf-8"))
        manifest["content_hash"] = content_hash
        manifest["published_at"] = utcnow().isoformat()
        _atomic_write(manifest_path, json.dumps(manifest, indent=2).encode("utf-8"))
        self._prune(root)
        return PublishResult(True, "published", str(root), content_hash, manifest.get("total", 0))

    @staticmethod
    def _prune(root: Path) -> None:
        versions = sorted((root / "versions").glob("*")) if (root / "versions").exists() else []
        for old in versions[: max(0, len(versions) - 10)]:
            shutil.rmtree(old, ignore_errors=True)


class GitHubPublicationProvider:
    """Reserved. Requires an operator-supplied token and explicit authorization."""

    name = "github"

    def publish(self, payload: dict[str, bytes], content_hash: str) -> PublishResult:  # pragma: no cover
        return PublishResult(
            False,
            "GitHub publication is not implemented in this build; "
            "the existing Actions workflow remains the authoritative publisher.",
        )


def get_provider() -> PublicationProvider:
    if settings.publish_mode == "github":
        return GitHubPublicationProvider()
    return LocalPublicationProvider()


def build_snapshot(db: Session, run: PipelineRun | None = None) -> tuple[dict[str, bytes], str, int]:
    rows = db.execute(
        select(Configuration.id, Configuration.raw_link_encrypted).where(Configuration.validation_status == "valid").order_by(Configuration.id)
    ).all()
    links: list[str] = []
    skipped = 0
    for _config_id, encrypted in rows:
        link = decrypt_secret(encrypted)
        if not link:
            skipped += 1
            continue
        links.append(link)
    plain = ("\n".join(links) + "\n").encode("utf-8") if links else b""
    encoded = base64.b64encode(plain)
    content_hash = hashlib.sha256(plain).hexdigest()
    status = {
        "updated_at_utc": utcnow().isoformat(),
        "total": len(links),
        "generator": "ADAN NEXUS | CONNECT",
        "pipeline_run_id": run.id if run else None,
        "undecryptable_skipped": skipped,
        "warning": "Public nodes are untrusted. No guarantee of connectivity, privacy or bandwidth.",
    }
    manifest = {
        "total": len(links),
        "content_hash": content_hash,
        "files": {
            "subscription.txt": {"sha256": hashlib.sha256(plain).hexdigest(), "bytes": len(plain)},
            "subscription_base64.txt": {
                "sha256": hashlib.sha256(encoded).hexdigest(),
                "bytes": len(encoded),
            },
        },
        "generated_by": "ADAN NEXUS | CONNECT",
        "generated_at": utcnow().isoformat(),
    }
    payload = {
        "subscription.txt": plain,
        "subscription_base64.txt": encoded,
        "status.json": json.dumps(status, indent=2).encode("utf-8"),
        "manifest.json": json.dumps(manifest, indent=2).encode("utf-8"),
    }
    return payload, content_hash, len(links)


def publish_bank(db: Session, run: PipelineRun | None = None) -> PublishResult:
    payload, content_hash, total = build_snapshot(db, run)
    if total == 0:
        return PublishResult(False, "no configurations available; previous bank preserved", None, None, 0)
    result = get_provider().publish(payload, content_hash)
    result.total = total
    return result
