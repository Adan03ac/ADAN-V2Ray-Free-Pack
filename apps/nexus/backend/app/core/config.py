"""Environment-driven configuration. No credential is ever hardcoded here."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


def _default_database_url() -> str:
    """SQLite is the development fallback; PostgreSQL is used in Docker."""
    return f"sqlite:///{PROJECT_DIR / 'data' / 'nexus.db'}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", PROJECT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- application -------------------------------------------------------
    app_name: str = "ADAN NEXUS | CONNECT"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    log_json: bool = True

    # --- security ----------------------------------------------------------
    secret_key: str = ""
    session_ttl_hours: int = 12
    session_cookie_name: str = "nexus_session"
    csrf_cookie_name: str = "nexus_csrf"
    cookie_secure: bool = False
    cookie_domain: str | None = None
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Optional suffix allow-list for ephemeral dev/preview hostnames, e.g. ".style.dev".
    # Leave empty in production and list exact origins instead.
    allowed_origin_suffixes: str = ""
    login_max_attempts: int = 5
    login_lock_minutes: int = 15
    login_rate_limit: int = 10
    allow_registration: bool = False
    register_rate_limit: int = 5
    public_base_url: str = "http://localhost:8000"

    # --- bootstrap ---------------------------------------------------------
    bootstrap_admin_email: str = "admin@adan.local"
    bootstrap_admin_password: str | None = None
    bootstrap_admin_name: str = "Nexus Operator"

    # --- database / cache --------------------------------------------------
    database_url: str = Field(default_factory=_default_database_url)
    database_auto_create: bool = True
    db_echo: bool = False
    redis_url: str | None = None

    # --- ingestion ---------------------------------------------------------
    embedded_worker: bool = True
    ingestion_enabled: bool = True
    ingestion_upstream_only: bool = False
    ingestion_interval_minutes: int = 60
    ingestion_jitter_seconds: int = 180
    source_timeout_seconds: float = 25.0
    source_max_bytes: int = 8 * 1024 * 1024
    source_max_retries: int = 2
    source_retry_base_seconds: float = 1.5
    fetch_user_agent: str = "ADAN-NEXUS-CONNECT/1.0 (+connectivity-intelligence)"
    allow_private_source_hosts: bool = False
    pipeline_lock_path: str = str(PROJECT_DIR / "data" / "pipeline.lock")
    worker_heartbeat_path: str = str(PROJECT_DIR / "data" / "worker.heartbeat")

    # --- publication -------------------------------------------------------
    publish_mode: str = "local"  # local | github (github provider is not implemented)
    publish_dir: str = str(PROJECT_DIR / "data" / "published")
    publish_retention_runs: int = 200

    # --- health testing ----------------------------------------------------
    health_max_batch: int = 50
    health_concurrency: int = 8
    health_timeout_seconds: float = 3.0
    health_dns_timeout_seconds: float = 3.0
    health_allow_tcp: bool = False
    # Explicit operator authorization; no TCP probes without public target CIDRs.
    health_authorized_cidrs: str = ""
    health_agent_label: str = "primary-agent"
    health_agent_region: str = "unspecified (no geo verification)"
    health_job_history_limit: int = 50

    # --- upstream public bank (read-only) ----------------------------------
    upstream_enabled: bool = True
    upstream_repo: str = "Adan03ac/ADAN-V2Ray-Free-Pack"
    upstream_branch: str = "main"
    upstream_status_url: str = (
        "https://raw.githubusercontent.com/Adan03ac/ADAN-V2Ray-Free-Pack/main/status.json"
    )
    upstream_schedule_cron: str = "7 * * * *"
    github_token: str | None = None

    # --- retention ---------------------------------------------------------
    retention_pipeline_days: int = 90
    retention_fetch_days: int = 30
    retention_health_days: int = 90

    # --- cloudflare (architecturally prepared, disabled by default) --------
    cloudflare_enabled: bool = False
    cloudflare_account_id: str | None = None
    cloudflare_api_token: str | None = None

    @model_validator(mode="after")
    def _production_security(self):
        if len(self.secret_key) < 32:
            raise ValueError("Set a persistent SECRET_KEY (at least 32 characters) before startup")
        if self.is_production and (
            "secret_key" not in self.model_fields_set
            or len(self.secret_key) < 32
            or any(marker in self.secret_key.lower() for marker in ("replace-with", "change-me", "test-secret"))
        ):
            raise ValueError("Production requires an explicit, strong SECRET_KEY (at least 32 characters)")
        import ipaddress
        for cidr in self.health_authorized_cidrs.split(","):
            if cidr.strip():
                ipaddress.ip_network(cidr.strip(), strict=False)
        return self

    @field_validator("allowed_origins")
    @classmethod
    def _strip_origins(cls, value: str) -> str:
        return ",".join(item.strip() for item in value.split(",") if item.strip())

    @property
    def origins(self) -> list[str]:
        return [origin for origin in self.allowed_origins.split(",") if origin]

    @property
    def origin_suffixes(self) -> list[str]:
        return [suffix for suffix in self.allowed_origin_suffixes.split(",") if suffix.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
