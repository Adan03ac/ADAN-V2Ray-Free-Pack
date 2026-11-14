"""Verify the running local stack without endpoint probes or external services."""
import argparse
import http.cookiejar
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--base", default="http://127.0.0.1:3000")
    args = parser.parse_args()
    base = args.base.rstrip("/")
    parsed = urllib.parse.urlsplit(base)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.scheme != "http":
        raise ValueError("Smoke tests are restricted to a local loopback HTTP server")
    config = json.loads(args.config.read_text())
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    csrf = ""
    checks = []
    def request(path, method="GET", payload=None):
        headers = {"origin": base}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["content-type"] = "application/json"
        if method != "GET" and csrf:
            headers["x-csrf-token"] = csrf
        req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
        try:
            response = opener.open(req, timeout=30)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            raw = response.read()
            body = json.loads(raw) if "application/json" in response.headers.get("content-type", "") else raw.decode()
            return response.code, body
    def check(condition, name):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    check(request("/login")[0] == 200, "frontend login")
    check(request("/api/v1/configurations")[0] == 401, "anonymous access denied")
    status, body = request("/api/v1/auth/login", "POST", {"email": config["BOOTSTRAP_ADMIN_EMAIL"], "password": config["BOOTSTRAP_ADMIN_PASSWORD"]})
    check(status == 200, "proxied authentication")
    csrf = body["csrf_token"]
    check(request("/api/v1/auth/me")[0] == 200, "session cookie")
    status, listing = request("/api/v1/configurations")
    check(status == 200 and listing["total"] > 0, "repository bank imported")
    status, dashboard = request("/api/v1/dashboard/summary?days=7")
    check(status == 200 and dashboard["overview"]["kpis"]["verified_working_configurations"] == 0, "no false VPN verification")
    status, profile = request("/api/v1/subscription-profiles", "POST", {"name": "CI integration", "export_format": "plain", "max_configs": 5})
    check(status == 201, "profile creation")
    status, rendered = request(f"/api/v1/subscription-profiles/{profile['id']}/render", "POST")
    check(status == 200 and rendered["config_count"] > 0, "subscription rendering")
    path = "/api/v1/public/subscriptions/" + rendered["token"]
    status, content = request(path)
    check(status == 200 and "://" in content, "token-scoped subscription")
    check(request(f"/api/v1/subscription-profiles/tokens/{rendered['token_id']}/revoke", "POST")[0] == 200, "token revocation")
    check(request(path)[0] == 404, "revoked token rejected")
    check(request("/api/v1/auth/logout", "POST")[0] == 200, "logout")
    check(request("/api/v1/auth/me")[0] == 401, "session revoked")
    print(json.dumps({"status": "passed", "checks": checks, "configuration_count": listing["total"]}))


if __name__ == "__main__":
    main()
