"""Protocol parsers for VLESS, VMess, Trojan, Shadowsocks and Hysteria2.

Each parser is pure and independently testable: bytes/str in, ParsedConfig out.
Malformed input raises ParseError and is recorded as a diagnostic by the pipeline.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import ipaddress
import json
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlsplit

SUPPORTED_PROTOCOLS = ("vless", "vmess", "trojan", "shadowsocks", "hysteria2")
SCHEME_MAP = {
    "vless": "vless",
    "vmess": "vmess",
    "trojan": "trojan",
    "ss": "shadowsocks",
    "shadowsocks": "shadowsocks",
    "hysteria2": "hysteria2",
    "hy2": "hysteria2",
}
SCHEME_PREFIXES = tuple(f"{scheme}://" for scheme in SCHEME_MAP)
MAX_LINK_LENGTH = 8192
_HOSTNAME_RE = re.compile(r"^(?=.{1,253}$)(?!-)[A-Za-z0-9\-_.]{1,253}(?<!-)$")
_SS_METHOD_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,39}$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


class ParseError(ValueError):
    """A share link that could not be normalized into a configuration."""

    def __init__(self, reason: str, category: str = "malformed") -> None:
        super().__init__(reason)
        self.reason = reason
        self.category = category


@dataclass(slots=True)
class ParsedConfig:
    protocol: str
    host: str
    port: int
    transport: str
    security: str
    sni: str | None
    credential: str
    canonical_endpoint: str
    fingerprint: str
    name: str | None


def _b64decode(value: str) -> bytes:
    cleaned = "".join(value.split())
    cleaned = cleaned.replace("-", "+").replace("_", "/")
    padding = (-len(cleaned)) % 4
    try:
        return base64.b64decode(cleaned + "=" * padding, validate=False)
    except (binascii.Error, ValueError) as exc:  # pragma: no cover - defensive
        raise ParseError("invalid base64 payload", "encoding") from exc


def _normalize_host(raw: str) -> str:
    host = unquote(raw or "").strip().lower()
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    if not host:
        raise ParseError("missing host", "missing_host")
    if _CONTROL_RE.search(host):
        raise ParseError("host contains control characters", "invalid_host")
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    if not _HOSTNAME_RE.match(host) or "." not in host:
        raise ParseError(f"invalid host: {host[:60]}", "invalid_host")
    return host


def _parse_port(raw: str | int | None, default: int | None = None) -> int:
    if raw is None or raw == "":
        if default is None:
            raise ParseError("missing port", "missing_port")
        return default
    try:
        port = int(str(raw))
    except (TypeError, ValueError) as exc:
        raise ParseError("port is not numeric", "invalid_port") from exc
    if not 1 <= port <= 65535:
        raise ParseError(f"port out of range: {port}", "invalid_port")
    return port


def _url_port(parts) -> int:  # type: ignore[no-untyped-def]
    """urlsplit defers port validation; convert its ValueError into a diagnostic."""
    try:
        return _parse_port(parts.port)
    except ParseError:
        raise
    except ValueError as exc:
        raise ParseError("port is outside 1-65535", "invalid_port") from exc


def _clean(value: str | None, limit: int = 120) -> str | None:
    if value is None:
        return None
    text = unquote(value).strip()
    if not text:
        return None
    text = _CONTROL_RE.sub("", text)
    return text[:limit]


def _fingerprint(canonical_endpoint: str, credential: str) -> str:
    secret_digest = hashlib.sha256(credential.encode("utf-8")).hexdigest()[:24]
    return hashlib.sha256(f"{canonical_endpoint}|{secret_digest}".encode("utf-8")).hexdigest()[:48]


def _credential_hint(credential: str) -> str:
    if not credential:
        return "—"
    if len(credential) <= 8:
        return "•••"
    return f"{credential[:4]}…{credential[-2:]}"


def mask(value: str | None) -> str:
    return _credential_hint(value or "")


def _build(
    *,
    protocol: str,
    host: str,
    port: int,
    transport: str,
    security: str,
    sni: str | None,
    credential: str,
    identity_extra: str = "",
    name: str | None = None,
) -> ParsedConfig:
    host = _normalize_host(host)
    port = _parse_port(port)
    if not credential:
        raise ParseError("missing credential", "missing_credential")
    transport = (transport or "tcp").lower()[:30]
    security = (security or "none").lower()[:30]
    canonical = (
        f"{protocol}|{host}|{port}|{transport}|{security}|{(sni or '').lower()}|{identity_extra}"
    )
    return ParsedConfig(
        protocol=protocol,
        host=host,
        port=port,
        transport=transport,
        security=security,
        sni=sni,
        credential=credential,
        canonical_endpoint=canonical,
        fingerprint=_fingerprint(canonical, credential),
        name=name,
    )


def _split_params(query: str) -> dict[str, str]:
    parsed = parse_qs(query, keep_blank_values=False, max_num_fields=80)
    return {key.lower(): values[0] for key, values in parsed.items() if values}


def _parse_vless(raw: str) -> ParsedConfig:
    parts = urlsplit(raw)
    if not parts.username:
        raise ParseError("vless link missing user id", "missing_credential")
    if not _UUID_RE.fullmatch(unquote(parts.username)):
        raise ParseError("vless user id must be a UUID", "invalid_credential")
    params = _split_params(parts.query)
    transport = params.get("type", "tcp")
    security = params.get("security", "none")
    sni = _clean(params.get("sni") or params.get("host") if security in {"tls", "reality", "xtls"} else params.get("sni"))
    extra = "|".join(
        filter(
            None,
            [
                _clean(params.get("path"), 80),
                _clean(params.get("servicename"), 80),
                _clean(params.get("pbk"), 80),
                _clean(params.get("mode"), 30),
            ],
        )
    )
    return _build(
        protocol="vless",
        host=parts.hostname or "",
        port=_url_port(parts),
        transport=transport,
        security=security,
        sni=sni,
        credential=unquote(parts.username),
        identity_extra=extra,
        name=_clean(unquote(parts.fragment), 120),
    )


def _parse_vmess(raw: str) -> ParsedConfig:
    payload = raw[len("vmess://") :].strip()
    if not payload:
        raise ParseError("empty vmess payload", "malformed")
    # Some clients append query/fragment data outside the base64 blob.
    payload = payload.split("#", 1)[0].split("?", 1)[0]
    try:
        decoded = _b64decode(payload).decode("utf-8", errors="replace")
        data = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ParseError("vmess payload is not base64 JSON", "encoding") from exc
    if not isinstance(data, dict):
        raise ParseError("vmess payload is not an object", "malformed")
    host = str(data.get("add") or "").strip()
    credential = str(data.get("id") or "").strip()
    if not credential:
        raise ParseError("vmess link missing id", "missing_credential")
    if not _UUID_RE.fullmatch(credential):
        raise ParseError("vmess id must be a UUID", "invalid_credential")
    net = str(data.get("net") or "tcp")
    tls = str(data.get("tls") or "")
    security = "tls" if tls.lower() in {"tls", "reality", "xtls"} else "none"
    sni = _clean(str(data.get("sni") or data.get("host") or "") or None)
    extra = "|".join(
        filter(None, [_clean(str(data.get("path") or "") or None, 80), _clean(str(data.get("host") or "") or None, 80)])
    )
    return _build(
        protocol="vmess",
        host=host,
        port=_parse_port(data.get("port")),
        transport=net,
        security=security,
        sni=sni,
        credential=credential,
        identity_extra=extra,
        name=_clean(str(data.get("ps") or "") or None, 120),
    )


def _parse_trojan(raw: str) -> ParsedConfig:
    parts = urlsplit(raw)
    if not parts.username:
        raise ParseError("trojan link missing password", "missing_credential")
    params = _split_params(parts.query)
    security = params.get("security", "tls")
    sni = _clean(params.get("sni") or params.get("peer"))
    extra = "|".join(filter(None, [_clean(params.get("path"), 80), _clean(params.get("host"), 80)]))
    return _build(
        protocol="trojan",
        host=parts.hostname or "",
        port=_url_port(parts) if parts.port is not None else 443,
        transport=params.get("type", "tcp"),
        security=security,
        sni=sni,
        credential=unquote(parts.username),
        identity_extra=extra,
        name=_clean(unquote(parts.fragment), 120),
    )


def _parse_shadowsocks(raw: str) -> ParsedConfig:
    body = raw[len("ss://") :].strip()
    fragment = ""
    if "#" in body:
        body, fragment = body.split("#", 1)
    plugin = ""
    if "?" in body:
        body, query = body.split("?", 1)
        params = _split_params(query)
        plugin = params.get("plugin", "").split(";")[0][:40]
    body = body.rstrip("/")

    if "@" in body:
        userinfo, endpoint = body.rsplit("@", 1)
        if ":" not in unquote(userinfo):
            try:
                userinfo = _b64decode(userinfo).decode("utf-8", errors="replace")
            except ParseError as exc:
                raise ParseError("shadowsocks credentials are not decodable", "encoding") from exc
        if ":" not in userinfo:
            raise ParseError("shadowsocks credentials are malformed", "malformed")
        method, password = userinfo.split(":", 1)
        endpoint_parts = urlsplit(f"//{endpoint}")
        host, port = endpoint_parts.hostname or "", _url_port(endpoint_parts)
    else:
        try:
            decoded = _b64decode(body).decode("utf-8", errors="replace")
        except ParseError as exc:
            raise ParseError("shadowsocks link is not base64", "encoding") from exc
        if "@" not in decoded or ":" not in decoded:
            raise ParseError("shadowsocks link is malformed", "malformed")
        userinfo, endpoint = decoded.rsplit("@", 1)
        method, password = userinfo.split(":", 1)
        endpoint_parts = urlsplit(f"//{endpoint}")
        host, port = endpoint_parts.hostname or "", _url_port(endpoint_parts)

    method = method.strip().lower()
    if not _SS_METHOD_RE.match(method):
        raise ParseError("unsupported shadowsocks cipher", "unsupported_cipher")
    return _build(
        protocol="shadowsocks",
        host=host,
        port=_parse_port(port),
        transport="tcp" if not plugin else "plugin",
        security="2022" if method.startswith("2022-") else method,
        sni=None,
        credential=password,
        identity_extra=f"{method}|{plugin}",
        name=_clean(unquote(fragment), 120),
    )


def _parse_hysteria2(raw: str) -> ParsedConfig:
    parts = urlsplit(raw)
    credential = unquote(parts.username or "")
    if not credential and parts.password:
        credential = unquote(parts.password)
    if not credential:
        raise ParseError("hysteria2 link missing password", "missing_credential")
    params = _split_params(parts.query)
    sni = _clean(params.get("sni") or params.get("peer"))
    obfs = _clean(params.get("obfs"), 30)
    return _build(
        protocol="hysteria2",
        host=parts.hostname or "",
        port=_url_port(parts) if parts.port is not None else 443,
        transport="quic",
        security="tls",
        sni=sni,
        credential=credential,
        identity_extra=obfs or "",
        name=_clean(unquote(parts.fragment), 120),
    )


_PARSERS = {
    "vless": _parse_vless,
    "vmess": _parse_vmess,
    "trojan": _parse_trojan,
    "ss": _parse_shadowsocks,
    "shadowsocks": _parse_shadowsocks,
    "hysteria2": _parse_hysteria2,
    "hy2": _parse_hysteria2,
}


def parse_share_link(raw: str) -> ParsedConfig:
    """Parse one share link. Raises ParseError with a machine-readable category."""
    if not isinstance(raw, str):
        raise ParseError("share link is not text", "malformed")
    link = raw.strip()
    if not link:
        raise ParseError("empty share link", "empty")
    if len(link) > MAX_LINK_LENGTH:
        raise ParseError("share link is too long", "too_long")
    if _CONTROL_RE.search(link):
        raise ParseError("share link contains control characters", "malformed")
    if "://" not in link:
        raise ParseError("share link has no scheme", "unsupported_scheme")
    scheme = link.split("://", 1)[0].lower()
    parser = _PARSERS.get(scheme)
    if parser is None:
        raise ParseError(f"unsupported protocol: {scheme[:20]}", "unsupported_scheme")
    try:
        return parser(link)
    except ParseError:
        raise
    except (ValueError, TypeError, KeyError) as exc:
        # urlsplit and JSON payloads can raise on hostile input; never let one bad
        # link abort a whole source.
        raise ParseError(f"unparsable link ({type(exc).__name__})", "malformed") from exc


def looks_like_share_link(value: str) -> bool:
    return value.strip().lower().startswith(SCHEME_PREFIXES)


def decode_text_payload(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8", errors="replace")


def split_share_links(text: str) -> list[str]:
    links: list[str] = []
    for line in text.splitlines():
        candidate = line.strip().strip('"').strip("'")
        if not candidate or candidate.startswith("#"):
            continue
        if looks_like_share_link(candidate):
            links.append(candidate)
    return links


def decode_subscription_bytes(data: bytes) -> tuple[str, str]:
    """Return (text, encoding) where encoding is 'text' or 'base64'."""
    text = decode_text_payload(data)
    if split_share_links(text):
        return text, "text"
    compact = "".join(text.split())
    if compact and re.fullmatch(r"[A-Za-z0-9+/_\-=]+", compact):
        try:
            decoded = _b64decode(compact).decode("utf-8", errors="replace")
            if split_share_links(decoded):
                return decoded, "base64"
        except ParseError:
            pass
    return text, "text"
