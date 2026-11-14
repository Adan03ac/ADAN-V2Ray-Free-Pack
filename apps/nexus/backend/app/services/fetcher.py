"""SSRF-safe HTTP fetching with conditional requests, retries and size limits."""

from __future__ import annotations

import ipaddress
import logging
import socket
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

import httpx

from app.core.config import settings

logger = logging.getLogger("nexus.fetcher")

MAX_REDIRECTS = 3
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class UnsafeUrlError(ValueError):
    pass


def _resolve(host: str, port: int) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"host cannot be resolved: {host}") from exc
    addresses: list[str] = []
    for info in infos:
        address = info[4][0]
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise UnsafeUrlError(f"host has no addresses: {host}")
    return addresses


def _is_blocked_address(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return (
        not ip.is_global
        or ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_source_url(url: str, *, allow_private: bool | None = None, resolve_dns: bool = True) -> str:
    """Enforce HTTPS and reject internal network targets (including via DNS)."""
    if allow_private is None:
        allow_private = settings.allow_private_source_hosts
    raw = (url or "").strip()
    if not raw:
        raise UnsafeUrlError("source URL is empty")
    parts = urlsplit(raw)
    if parts.scheme.lower() != "https":
        raise UnsafeUrlError("source URLs must use HTTPS")
    if parts.username or parts.password:
        raise UnsafeUrlError("source URLs must not embed credentials")
    host = parts.hostname
    if not host:
        raise UnsafeUrlError("source URL has no host")
    try:
        port = parts.port or 443
    except ValueError as exc:
        raise UnsafeUrlError("source URL has an invalid port") from exc
    if allow_private:
        return raw
    if host.lower() in {"localhost", "localhost.localdomain"} or host.lower().endswith(".local"):
        raise UnsafeUrlError("source URL targets a local host")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if _is_blocked_address(str(literal)):
            raise UnsafeUrlError("source URL targets a private or reserved address")
        return raw
    if not resolve_dns:
        return raw
    for address in _resolve(host, port):
        if _is_blocked_address(address):
            raise UnsafeUrlError(f"source URL resolves to a blocked address: {address}")
    return raw


@dataclass
class FetchResult:
    ok: bool
    status_code: int | None = None
    content: bytes = b""
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False
    duration_ms: float = 0.0
    error: str | None = None
    error_category: str | None = None
    final_url: str | None = None
    attempts: int = 0
    headers: dict[str, str] = field(default_factory=dict)


class SafeFetcher:
    def __init__(self, timeout: float | None = None, max_bytes: int | None = None) -> None:
        self.timeout = timeout or settings.source_timeout_seconds
        self.max_bytes = max_bytes or settings.source_max_bytes

    def _request_once(self, client: httpx.Client, url: str, etag: str | None, last_modified: str | None) -> tuple[httpx.Response, bytes, str]:
        headers = {"User-Agent": settings.fetch_user_agent, "Accept": "*/*"}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        chunks: list[bytes] = []
        total = 0
        # Resolve immediately before connection and pin the validated address.
        # Host and TLS SNI remain the original hostname (certificate verified).
        validate_source_url(url)
        original = httpx.URL(url)
        addresses = _resolve(original.host, original.port or 443)
        if not settings.allow_private_source_hosts and any(_is_blocked_address(ip) for ip in addresses):
            raise UnsafeUrlError("source resolves to a blocked address")
        target = original.copy_with(host=addresses[0])
        headers["Host"] = original.netloc.decode("ascii")
        with client.stream("GET", target, headers=headers, extensions={"sni_hostname": original.host}) as response:
            for chunk in response.iter_bytes(chunk_size=65536):
                total += len(chunk)
                if total > self.max_bytes:
                    raise UnsafeUrlError(f"response exceeds {self.max_bytes} byte limit")
                chunks.append(chunk)
            return response, b"".join(chunks), url

    def fetch(self, url: str, etag: str | None = None, last_modified: str | None = None) -> FetchResult:
        started = time.perf_counter()
        attempts = 0
        last_error: str | None = None
        last_category = "fetch_error"
        try:
            validate_source_url(url)
        except UnsafeUrlError as exc:
            return FetchResult(
                ok=False,
                error=str(exc),
                error_category="unsafe_url",
                duration_ms=(time.perf_counter() - started) * 1000,
            )

        current_url = url
        with httpx.Client(timeout=self.timeout, follow_redirects=False, trust_env=False) as client:
            redirects = 0
            retries = 0
            while retries <= settings.source_max_retries:
                attempts += 1
                attempt = retries
                try:
                    response, body, final_url = self._request_once(client, current_url, etag, last_modified)
                except UnsafeUrlError as exc:
                    return FetchResult(
                        ok=False,
                        error=str(exc),
                        error_category="too_large" if "byte limit" in str(exc) else "unsafe_url",
                        attempts=attempts,
                        duration_ms=(time.perf_counter() - started) * 1000,
                    )
                except httpx.TimeoutException:
                    last_error, last_category = "request timed out", "timeout"
                except httpx.HTTPError as exc:
                    last_error, last_category = f"transport error: {type(exc).__name__}", "transport"
                else:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            return FetchResult(
                                ok=False,
                                status_code=response.status_code,
                                error="redirect without a location header",
                                error_category="redirect",
                                attempts=attempts,
                                duration_ms=(time.perf_counter() - started) * 1000,
                            )
                        if redirects >= MAX_REDIRECTS:
                            return FetchResult(
                                ok=False,
                                status_code=response.status_code,
                                error="too many redirects",
                                error_category="redirect",
                                attempts=attempts,
                                duration_ms=(time.perf_counter() - started) * 1000,
                            )
                        next_url = urljoin(current_url, location)
                        try:
                            validate_source_url(next_url)
                        except UnsafeUrlError as exc:
                            return FetchResult(
                                ok=False,
                                status_code=response.status_code,
                                error=f"unsafe redirect: {exc}",
                                error_category="unsafe_url",
                                attempts=attempts,
                                duration_ms=(time.perf_counter() - started) * 1000,
                            )
                        current_url = next_url
                        redirects += 1
                        etag = last_modified = None
                        continue

                    if response.status_code == 304:
                        return FetchResult(
                            ok=True,
                            status_code=304,
                            not_modified=True,
                            etag=response.headers.get("etag"),
                            last_modified=response.headers.get("last-modified"),
                            attempts=attempts,
                            duration_ms=(time.perf_counter() - started) * 1000,
                            final_url=final_url,
                        )

                    if response.status_code >= 400:
                        if response.status_code in RETRYABLE_STATUS and attempt < settings.source_max_retries:
                            last_error = f"HTTP {response.status_code}"
                            last_category = "http_error"
                        else:
                            return FetchResult(
                                ok=False,
                                status_code=response.status_code,
                                error=f"HTTP {response.status_code}",
                                error_category="http_error",
                                attempts=attempts,
                                duration_ms=(time.perf_counter() - started) * 1000,
                                final_url=final_url,
                            )
                    else:
                        if response.status_code not in {200, 203}:
                            last_error = f"unexpected HTTP {response.status_code}"
                            last_category = "http_error"
                        else:
                            return FetchResult(
                                ok=True,
                                status_code=response.status_code,
                                content=body,
                                etag=response.headers.get("etag"),
                                last_modified=response.headers.get("last-modified"),
                                attempts=attempts,
                                duration_ms=(time.perf_counter() - started) * 1000,
                                final_url=final_url,
                                headers={k.lower(): v for k, v in response.headers.items()},
                            )

                retries += 1
                if attempt < settings.source_max_retries:
                    delay = settings.source_retry_base_seconds * (2**attempt)
                    time.sleep(delay)

        return FetchResult(
            ok=False,
            error=last_error or "fetch failed",
            error_category=last_category,
            attempts=attempts,
            duration_ms=(time.perf_counter() - started) * 1000,
        )
