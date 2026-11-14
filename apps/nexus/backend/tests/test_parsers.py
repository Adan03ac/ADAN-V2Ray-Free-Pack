"""Protocol parser tests: every supported format, plus hostile input."""

from __future__ import annotations

import base64
import json

import pytest

from app.services.parsers import ParseError, decode_subscription_bytes, parse_share_link, split_share_links

UUID = "8d2cbffd-43d0-458d-906b-7c54b7b51f38"
VLESS = (
    f"vless://{UUID}@199.232.78.120:443?encryption=none&type=ws&security=tls"
    "&host=example.fastly.net&sni=cdn.example.com&path=%2Fws#Sample%20Node"
)
TROJAN = "trojan://s3cret-pass@trojan.example.com:443?security=tls&sni=t.example.com#Trojan"
HY2 = "hysteria2://hy-pass@hy.example.com:443?sni=hy.example.com&insecure=1#HY2"


def vmess_link(payload: dict, prefix: str = "vmess://") -> str:
    raw = json.dumps(payload).encode()
    return prefix + base64.b64encode(raw).decode()


def test_vless_parsing():
    config = parse_share_link(VLESS)
    assert config.protocol == "vless"
    assert config.host == "199.232.78.120"
    assert config.port == 443
    assert config.transport == "ws"
    assert config.security == "tls"
    assert config.sni == "cdn.example.com"
    assert config.name == "Sample Node"
    assert config.fingerprint and len(config.fingerprint) == 48
    assert UUID not in config.canonical_endpoint


def test_vmess_parsing():
    link = vmess_link(
        {
            "v": "2",
            "ps": "vm node",
            "add": "vm.example.com",
            "port": "8443",
            "id": UUID,
            "aid": "0",
            "net": "grpc",
            "tls": "tls",
            "sni": "vm.example.com",
            "path": "svc",
        }
    )
    config = parse_share_link(link)
    assert config.protocol == "vmess"
    assert config.port == 8443
    assert config.transport == "grpc"
    assert config.security == "tls"


def test_trojan_and_hysteria2():
    trojan = parse_share_link(TROJAN)
    assert trojan.protocol == "trojan"
    assert trojan.security == "tls"
    hy2 = parse_share_link(HY2)
    assert hy2.protocol == "hysteria2"
    assert hy2.transport == "quic"
    assert parse_share_link(HY2.replace("hysteria2://", "hy2://")).fingerprint == hy2.fingerprint


def test_shadowsocks_sip002_and_legacy():
    userinfo = base64.urlsafe_b64encode(b"aes-256-gcm:ss-pass").decode().rstrip("=")
    sip002 = parse_share_link(f"ss://{userinfo}@ss.example.com:8388#SIP002")
    assert sip002.protocol == "shadowsocks"
    assert sip002.port == 8388
    assert sip002.security == "aes-256-gcm"
    legacy_payload = base64.b64encode(b"chacha20-ietf-poly1305:legacy-pass@ss.example.com:8389").decode()
    legacy = parse_share_link(f"ss://{legacy_payload}#Legacy")
    assert legacy.host == "ss.example.com"
    assert legacy.port == 8389


def test_fingerprint_identity_is_endpoint_based():
    renamed = VLESS.replace("#Sample%20Node", "#Different%20Label")
    assert parse_share_link(VLESS).fingerprint == parse_share_link(renamed).fingerprint
    other_uuid = VLESS.replace(UUID, "11111111-2222-3333-4444-555555555555")
    assert parse_share_link(VLESS).fingerprint != parse_share_link(other_uuid).fingerprint
    other_port = VLESS.replace(":443?", ":8443?")
    assert parse_share_link(VLESS).fingerprint != parse_share_link(other_port).fingerprint


@pytest.mark.parametrize(
    "link, category",
    [
        ("", "empty"),
        ("not-a-link", "unsupported_scheme"),
        ("http://example.com/config", "unsupported_scheme"),
        (f"vless://{UUID}@1.2.3.4:99999", "invalid_port"),
        (f"vless://{UUID}@bad host:443", "invalid_host"),
        ("vless://@example.com:443", "missing_credential"),
        ("vmess://not-base64!!", "encoding"),
        ("ss://@@", "malformed"),
        ("trojan://", "missing_credential"),
        (f"vless://{UUID}@1.2.3.4:443?type=ws&x=" + "a" * 9000, "too_long"),
    ],
)
def test_malformed_links_raise_parse_error(link, category):
    with pytest.raises(ParseError) as excinfo:
        parse_share_link(link)
    assert excinfo.value.category == category, excinfo.value.reason


def test_shadowsocks_hostile_payload_never_crashes():
    with pytest.raises(ParseError):
        parse_share_link('ss://abc@host:not-a-port?plugin=x')


def test_base64_subscription_detection():
    plain = f"{VLESS}\n{TROJAN}\n"
    encoded = base64.b64encode(plain.encode()).decode()
    text, encoding = decode_subscription_bytes(encoded.encode())
    assert encoding == "base64"
    assert len(split_share_links(text)) == 2
    text_plain, encoding_plain = decode_subscription_bytes(plain.encode())
    assert encoding_plain == "text"
    assert len(split_share_links(text_plain)) == 2


def test_control_characters_rejected():
    with pytest.raises(ParseError):
        parse_share_link(VLESS + "\x00oops")
