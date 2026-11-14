"""Source adapters: one interface, several feed formats, no coupling to providers."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.security import decrypt_secret
from app.models import Source
from app.services.fetcher import FetchResult
from app.services.parsers import (
    ParseError,
    decode_subscription_bytes,
    decode_text_payload,
    parse_share_link,
    split_share_links,
)


@dataclass
class AdapterPayload:
    raw_links: list[str]
    encoding: str = "text"
    diagnostics: list[str] = field(default_factory=list)
    discovery_only: bool = False
    metadata: dict = field(default_factory=dict)


class SourceAdapter:
    """Converts a fetch result into raw share links without interpreting them."""

    source_types: tuple[str, ...] = ()

    def supports(self, source_type: str) -> bool:
        return source_type in self.source_types

    def requires_fetch(self) -> bool:
        return True

    def parse_response(self, source: Source, result: FetchResult) -> AdapterPayload:  # pragma: no cover - interface
        raise NotImplementedError


class PlainTextAdapter(SourceAdapter):
    source_types = ("plain_text",)

    def parse_response(self, source: Source, result: FetchResult) -> AdapterPayload:
        if source.source_type == "manual":
            links = split_share_links(source.url)
            if not links:
                raise ParseError("manual source does not contain a supported share link", "manual_invalid")
            return AdapterPayload(raw_links=links, encoding="manual")
        text, encoding = decode_subscription_bytes(result.content)
        links = split_share_links(text)
        diagnostics: list[str] = []
        if not links:
            diagnostics.append("no supported share links found in response")
        return AdapterPayload(raw_links=links, encoding=encoding, diagnostics=diagnostics)


class Base64SubscriptionAdapter(SourceAdapter):
    source_types = ("base64",)

    def parse_response(self, source: Source, result: FetchResult) -> AdapterPayload:
        text = decode_text_payload(result.content)
        compact = "".join(text.split())
        try:
            import base64
            import binascii

            padded = compact + "=" * ((-len(compact)) % 4)
            decoded = base64.b64decode(padded.replace("-", "+").replace("_", "/"), validate=False)
        except (binascii.Error, ValueError) as exc:
            raise ParseError("source did not return valid base64", "encoding") from exc
        links = split_share_links(decoded.decode("utf-8", errors="replace"))
        if not links:
            # A base64 source may still be served as plain text by some mirrors.
            links = split_share_links(text)
        diagnostics = [] if links else ["no supported share links found after base64 decoding"]
        return AdapterPayload(raw_links=links, encoding="base64", diagnostics=diagnostics)


class GithubRawAdapter(SourceAdapter):
    """GitHub-hosted feeds: auto-detect plain text or base64 payloads."""

    source_types = ("github_raw",)

    def parse_response(self, source: Source, result: FetchResult) -> AdapterPayload:
        if source.is_discovery:
            return AdapterPayload(raw_links=[], discovery_only=True)
        text, encoding = decode_subscription_bytes(result.content)
        links = split_share_links(text)
        return AdapterPayload(
            raw_links=links,
            encoding=encoding,
            diagnostics=[] if links else ["GitHub feed contained no supported share links"],
            metadata={"raw_url": source.url},
        )


class ManualShareLinkAdapter(SourceAdapter):
    """A single pasted share link, no network request."""

    source_types = ("manual",)

    def requires_fetch(self) -> bool:
        return False

    def parse_response(self, source: Source, result: FetchResult) -> AdapterPayload:
        raw = source.url
        if raw.startswith("nexus:fernet:"):
            raw = decrypt_secret(raw.removeprefix("nexus:fernet:")) or ""
        links = split_share_links(raw)
        if not links:
            raise ParseError("manual source does not contain a supported share link", "manual_invalid")
        return AdapterPayload(raw_links=links, encoding="manual")


class HtmlDiscoveryAdapter(SourceAdapter):
    """HTML landing pages are discovery sources: recorded, never ingested as feeds."""

    source_types = ("html_discovery",)

    def parse_response(self, source: Source, result: FetchResult) -> AdapterPayload:
        text = decode_text_payload(result.content[:200_000])
        title = ""
        marker = "<title>"
        if marker in text.lower():
            start = text.lower().index(marker) + len(marker)
            end = text.lower().find("</title>", start)
            if end > start:
                title = text[start:end].strip()[:120]
        candidates = [link for link in split_share_links(text) if len(link) > 20]
        return AdapterPayload(
            raw_links=[],
            encoding="html",
            discovery_only=True,
            diagnostics=[
                "HTML discovery page: not ingested as a subscription feed",
                f"page title: {title or 'unknown'}",
            ],
            metadata={"title": title, "candidate_links_in_html": len(candidates)},
        )


_ADAPTERS: tuple[SourceAdapter, ...] = (
    PlainTextAdapter(),
    Base64SubscriptionAdapter(),
    GithubRawAdapter(),
    ManualShareLinkAdapter(),
    HtmlDiscoveryAdapter(),
)


class AdapterRegistry:
    def __init__(self, adapters: tuple[SourceAdapter, ...] = _ADAPTERS) -> None:
        self.adapters = adapters

    def for_source(self, source: Source) -> SourceAdapter:
        for adapter in self.adapters:
            if adapter.supports(source.source_type):
                return adapter
        raise LookupError(f"no adapter registered for source type '{source.source_type}'")

    def supported_types(self) -> list[str]:
        return sorted({source_type for adapter in self.adapters for source_type in adapter.source_types})


registry = AdapterRegistry()
