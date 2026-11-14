"""Loopback-only UI smoke: login, configuration table, HttpOnly cookie, mobile."""
import argparse
import json
from pathlib import Path
import urllib.parse

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--base", default="http://127.0.0.1:3000")
    args = parser.parse_args()
    base = args.base.rstrip("/")
    if urllib.parse.urlsplit(base).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Browser smoke requires a loopback server")
    config = json.loads(args.config.read_text())
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base + "/") else route.abort())
        page = context.new_page()
        page.goto(base + "/login")
        page.locator("input[type=email]").fill(config["BOOTSTRAP_ADMIN_EMAIL"])
        page.locator("input[type=password]").first.fill(config["BOOTSTRAP_ADMIN_PASSWORD"])
        page.locator("button[type=submit]").click()
        page.wait_for_url(base + "/", timeout=30000)
        page.wait_for_selector("main", timeout=30000)
        page.goto(base + "/configurations")
        page.wait_for_selector("tbody tr", timeout=30000)
        assert page.locator("tbody tr").count() > 0
        assert "vless://" not in page.locator("body").inner_text()
        assert any(c["name"] == "nexus_session" and c["httpOnly"] for c in context.cookies())
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(base + "/")
        page.wait_for_selector("main", timeout=30000)
        page.wait_for_timeout(1000)
        width = page.evaluate("({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth})")
        if width["scroll"] > width["client"] + 1:
            overflow = page.evaluate("""() => [...document.querySelectorAll('main *')]
                .filter(el => el.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
                .slice(0, 12).map(el => ({tag: el.tagName, class: el.className.baseVal ?? el.className,
                    right: Math.round(el.getBoundingClientRect().right)}))""")
            raise AssertionError({"width": width, "overflow": overflow})
        browser.close()
    print(json.dumps({"status": "passed", "desktop_login": True, "configurations_visible": True, "httponly_cookie": True, "mobile_width": width}))


if __name__ == "__main__":
    main()
