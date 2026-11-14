"""Normalized database model for ADAN NEXUS | CONNECT."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


# --------------------------------------------------------------------------
# Identity and access
# --------------------------------------------------------------------------


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), default="Operator", nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="read_only", nullable=False)  # admin | read_only
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship()


# --------------------------------------------------------------------------
# Source registry and ingestion
# --------------------------------------------------------------------------


class Source(Base, TimestampMixin):
    __tablename__ = "sources"
    __table_args__ = (Index("ix_sources_enabled_type", "enabled", "source_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    # plain_text | base64 | github_raw | manual | html_discovery
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_discovery: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trust_level: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)  # trusted|community|unknown|low
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    refresh_interval_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(255), nullable=True)
    config_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_config_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class SourceFetch(Base):
    __tablename__ = "source_fetches"
    __table_args__ = (Index("ix_source_fetches_source_started", "source_id", "started_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    pipeline_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)  # ok|error|not_modified|skipped
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bytes_read: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parsed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    invalid_samples: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    fetch_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Configuration(Base):
    __tablename__ = "configurations"
    __table_args__ = (
        Index("ix_configurations_protocol", "protocol"),
        Index("ix_configurations_connectivity", "connectivity_status"),
        Index("ix_configurations_first_seen", "first_seen_at"),
        Index("ix_configurations_latency", "last_latency_ms"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    protocol: Mapped[str] = mapped_column(String(20), nullable=False)
    host: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    transport: Mapped[str] = mapped_column(String(30), default="tcp", nullable=False)
    security: Mapped[str] = mapped_column(String(30), default="none", nullable=False)
    sni: Mapped[str | None] = mapped_column(String(255), nullable=True)
    canonical_endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    credential_hint: Mapped[str] = mapped_column(String(40), default="", nullable=False)

    # Encrypted at rest with a key derived from SECRET_KEY; never serialized to API responses.
    raw_link_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    raw_link_length: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    validation_status: Mapped[str] = mapped_column(String(20), default="valid", nullable=False)
    connectivity_status: Mapped[str] = mapped_column(String(20), default="untested", nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_avg_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_samples: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    test_agent: Mapped[str | None] = mapped_column(String(120), nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ConfigurationSource(Base):
    __tablename__ = "configuration_sources"
    __table_args__ = (UniqueConstraint("configuration_id", "source_id", name="uq_configuration_source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    configuration_id: Mapped[int] = mapped_column(
        ForeignKey("configurations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    occurrences: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class HealthTestJob(Base):
    __tablename__ = "health_test_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)  # queued|running|completed|failed
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stages: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    concurrency: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reachable: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    agent_label: Mapped[str] = mapped_column(String(120), default="primary-agent", nullable=False)
    agent_region: Mapped[str] = mapped_column(String(120), default="unspecified", nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class HealthTest(Base):
    __tablename__ = "health_tests"
    __table_args__ = (Index("ix_health_tests_config_tested", "configuration_id", "started_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    configuration_id: Mapped[int] = mapped_column(
        ForeignKey("configurations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("health_test_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # valid_format|reachable|failed|unknown
    stage_reached: Mapped[str] = mapped_column(String(20), nullable=False)  # syntax|dns|tcp
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_label: Mapped[str] = mapped_column(String(120), nullable=False)
    agent_region: Mapped[str] = mapped_column(String(120), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --------------------------------------------------------------------------
# Personal subscriptions
# --------------------------------------------------------------------------


class SubscriptionProfile(Base, TimestampMixin):
    __tablename__ = "subscription_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    filters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    max_configs: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    sort: Mapped[str] = mapped_column(String(30), default="latency_asc", nullable=False)
    export_format: Mapped[str] = mapped_column(String(20), default="base64", nullable=False)
    favorites_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    exclude_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    last_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_config_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SubscriptionToken(Base):
    __tablename__ = "subscription_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("subscription_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


# --------------------------------------------------------------------------
# Operations
# --------------------------------------------------------------------------


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (Index("ix_pipeline_runs_started", "started_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trigger: Mapped[str] = mapped_column(String(30), default="schedule", nullable=False)  # schedule|manual|cli
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)  # running|succeeded|partial|failed
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    sources_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sources_ok: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sources_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parsed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    publish_skipped_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    publish_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), default="cloudflare", nullable=False)
    target: Mapped[str] = mapped_column(String(40), nullable=False)  # worker|pages
    environment: Mapped[str] = mapped_column(String(40), default="preview", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="unconfigured", nullable=False)
    version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    log: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_created", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), default="success", nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
