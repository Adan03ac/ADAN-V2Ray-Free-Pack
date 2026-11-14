"""Pydantic request/response models (validation lives here, not in routers)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PROTOCOLS = ["vless", "vmess", "trojan", "shadowsocks", "hysteria2"]
SOURCE_TYPES = ["plain_text", "base64", "github_raw", "manual", "html_discovery"]
CONNECTIVITY = ["untested", "dns_resolved", "reachable", "failed", "unknown"]
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{2,118}$")
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,}$")


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        value = value.strip().lower()
        if not _EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address")
        return value


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    display_name: str
    role: str
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=10, max_length=200)
    display_name: str = Field(default="Operator", min_length=1, max_length=120)
    role: Literal["admin", "read_only"] = "read_only"

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        value = value.strip().lower()
        if not _EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address")
        return value


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=10, max_length=200)
    display_name: str = Field(default="Operator", min_length=1, max_length=120)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        value = value.strip().lower()
        if not _EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address")
        return value


class PartialUpdate(BaseModel):
    @model_validator(mode="after")
    def reject_null_required_fields(self):
        nullable = {"notes", "description"}
        for field in self.model_fields_set:
            if field not in nullable and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class UserUpdate(PartialUpdate):
    role: Literal["admin", "read_only"] | None = None
    is_active: bool | None = None


class LoginResponse(BaseModel):
    user: UserOut
    csrf_token: str
    expires_at: datetime


class SourceBase(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    url: str = Field(min_length=8, max_length=2000)
    source_type: str = "plain_text"
    trust_level: Literal["trusted", "community", "unknown", "low"] = "unknown"
    tags: list[str] = Field(default_factory=list, max_length=12)
    refresh_interval_minutes: int = Field(default=60, ge=5, le=1440)
    enabled: bool = True
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("source_type")
    @classmethod
    def _source_type(cls, value: str) -> str:
        if value not in SOURCE_TYPES:
            raise ValueError(f"source_type must be one of {', '.join(SOURCE_TYPES)}")
        return value

    @field_validator("tags")
    @classmethod
    def _tags(cls, values: list[str]) -> list[str]:
        cleaned = []
        for value in values:
            tag = re.sub(r"[^A-Za-z0-9._-]", "", value.strip())[:32]
            if tag and tag not in cleaned:
                cleaned.append(tag)
        return cleaned


class SourceCreate(SourceBase):
    slug: str | None = Field(default=None, max_length=120)

    @field_validator("slug")
    @classmethod
    def _slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _SLUG_RE.match(value):
            raise ValueError("slug must be lowercase letters, digits and dashes")
        return value


class SourceUpdate(PartialUpdate):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    url: str | None = Field(default=None, min_length=8, max_length=2000)
    source_type: str | None = None
    trust_level: Literal["trusted", "community", "unknown", "low"] | None = None
    tags: list[str] | None = None
    refresh_interval_minutes: int | None = Field(default=None, ge=5, le=1440)
    enabled: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("source_type")
    @classmethod
    def _source_type(cls, value: str | None) -> str | None:
        if value is not None and value not in SOURCE_TYPES:
            raise ValueError(f"source_type must be one of {', '.join(SOURCE_TYPES)}")
        return value


class SourceOut(BaseModel):
    id: int
    slug: str
    name: str
    url: str
    source_type: str
    enabled: bool
    is_discovery: bool
    trust_level: str
    tags: list[str]
    refresh_interval_minutes: int
    notes: str | None
    last_attempted_at: datetime | None
    last_success_at: datetime | None
    last_http_status: int | None
    etag: str | None
    last_modified: str | None
    config_count: int
    new_config_count: int
    duplicate_count: int
    invalid_count: int
    consecutive_failures: int
    last_error: str | None
    last_duration_ms: float | None


class ConfigurationOut(BaseModel):
    """Public projection: never contains share links or credentials."""

    id: int
    fingerprint: str
    protocol: str
    host: str
    port: int
    transport: str
    security: str
    sni: str | None
    credential_hint: str
    validation_status: str
    connectivity_status: str
    last_tested_at: datetime | None
    last_latency_ms: float | None
    latency_avg_ms: float | None
    test_agent: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    source_count: int
    failure_count: int
    tags: list[str]
    notes: str | None
    is_favorite: bool
    sources: list[dict] = Field(default_factory=list)


class ConfigurationDetail(ConfigurationOut):
    latency_samples: list[float] = Field(default_factory=list)
    source_links: list[dict] = Field(default_factory=list)
    canonical_endpoint: str


class ConfigurationUpdate(PartialUpdate):
    is_favorite: bool | None = None
    notes: str | None = Field(default=None, max_length=1000)
    tags: list[str] | None = None


class BulkFavorite(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)
    favorite: bool = True


class HealthTestRequest(BaseModel):
    configuration_ids: list[int] = Field(default_factory=list, max_length=50)
    limit: int = Field(default=10, ge=1, le=50)
    stages: list[Literal["syntax", "dns", "tcp"]] = Field(default_factory=lambda: ["syntax", "dns", "tcp"])


class SubscriptionFilters(BaseModel):
    protocols: list[str] = Field(default_factory=list, max_length=5)
    connectivity: list[str] = Field(default_factory=list, max_length=5)
    transports: list[str] = Field(default_factory=list, max_length=10)
    source_ids: list[int] = Field(default_factory=list, max_length=50)
    search: str | None = Field(default=None, max_length=80)

    @field_validator("protocols")
    @classmethod
    def _protocols(cls, values: list[str]) -> list[str]:
        invalid = [value for value in values if value not in PROTOCOLS]
        if invalid:
            raise ValueError(f"unsupported protocol filter: {invalid[0]}")
        return values

    @field_validator("connectivity")
    @classmethod
    def _connectivity(cls, values: list[str]) -> list[str]:
        invalid = [value for value in values if value not in CONNECTIVITY]
        if invalid:
            raise ValueError(f"unsupported connectivity filter: {invalid[0]}")
        return values


class ProfileCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    filters: SubscriptionFilters = Field(default_factory=SubscriptionFilters)
    max_configs: int = Field(default=50, ge=1, le=500)
    sort: Literal["latency_asc", "newest", "recently_seen", "protocol"] = "latency_asc"
    export_format: Literal["plain", "base64", "json"] = "base64"
    favorites_only: bool = False
    exclude_ids: list[int] = Field(default_factory=list, max_length=500)


class ProfileUpdate(PartialUpdate):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    filters: SubscriptionFilters | None = None
    max_configs: int | None = Field(default=None, ge=1, le=500)
    sort: Literal["latency_asc", "newest", "recently_seen", "protocol"] | None = None
    export_format: Literal["plain", "base64", "json"] | None = None
    favorites_only: bool | None = None
    exclude_ids: list[int] | None = Field(default=None, max_length=500)


class ProfileOut(BaseModel):
    id: int
    name: str
    description: str | None
    filters: dict
    max_configs: int
    sort: str
    export_format: str
    favorites_only: bool
    exclude_ids: list[int]
    last_generated_at: datetime | None
    last_config_count: int | None
    created_at: datetime
    updated_at: datetime
    tokens: list[dict] = Field(default_factory=list)


class TokenCreate(BaseModel):
    label: str | None = Field(default=None, max_length=120)


class SettingsPatch(BaseModel):
    key: str = Field(pattern=r"^[a-z_]{2,40}$")
    value: dict


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int
