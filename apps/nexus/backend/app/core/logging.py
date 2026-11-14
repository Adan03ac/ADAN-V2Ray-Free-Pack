"""Structured logging. Secrets and share links are never logged."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone

from app.core.config import settings

_SENSITIVE_KEYS = {
    "password",
    "token",
    "authorization",
    "cookie",
    "secret",
    "api_token",
    "raw_link",
    "raw_share_link",
    "uuid",
}


def _redact(value: object, depth: int = 0) -> object:
    if depth > 3:
        return "<truncated>"
    if isinstance(value, dict):
        return {
            key: ("<redacted>" if str(key).lower() in _SENSITIVE_KEYS else _redact(val, depth + 1))
            for key, val in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item, depth + 1) for item in value[:20]]
    if isinstance(value, str):
        value = re.sub(r"(/public/subscriptions/)[^/?\s\"]+", r"\1<redacted>", value)
        value = re.sub(r"(?:vless|vmess|trojan|ss|shadowsocks|hysteria2|hy2)://[^\s\"]+", "<redacted-share-link>", value, flags=re.I)
        return value[:500] + ("…" if len(value) > 500 else "")
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _redact(record.getMessage()),
        }
        extra = getattr(record, "context", None)
        if isinstance(extra, dict):
            payload["context"] = _redact(extra)
        if record.exc_info:
            payload["exception"] = _redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = f"{record.levelname:<7} {record.name}: {_redact(record.getMessage())}"
        extra = getattr(record, "context", None)
        if isinstance(extra, dict) and extra:
            base += " " + json.dumps(_redact(extra), default=str)
        if record.exc_info:
            base += "\n" + _redact(self.formatException(record.exc_info))
        return base


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if settings.log_json else TextFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def log_event(logger: logging.Logger, level: int, message: str, **context: object) -> None:
    logger.log(level, message, extra={"context": context})
