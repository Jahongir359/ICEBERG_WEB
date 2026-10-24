#!/usr/bin/env python3
"""Fail fast on broken links or unsafe output in the Firebase static build."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
HTML_FILES = sorted(PUBLIC.rglob("*.html"))
EXPECTED_PAGES = {
    "/": "index.html",
    "/about": "about.html",
    "/programs": "programs.html",
    "/admissions": "admissions.html",
    "/courses": "courses.html",
    "/news": "news.html",
    "/contact": "contact.html",
    "/register": "register.html",
}
EXPECTED_REDIRECTS = (
    "/our_programs /courses 301",
    "/questions /courses#savollar 301",
    "/programs/sat /courses#sat 301",
    "/faq /courses#savollar 301",
    "/contacts /contact 301",
    "/news/* /news 301",
    "/en/* / 302",
)
IGNORED_SCHEMES = {"data", "mailto", "tel", "javascript"}
PRIVATE_MARKERS = (
    "admin_password",
    "admin_secret_code",
    "registration-leads",
    "REGISTRATION_LEADS_API_TOKEN",
)


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[tuple[str, str]] = []
        self.forms: list[str] = []
        self.has_title = False
        self.has_description = False
        self.lang = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "html":
            self.lang = values.get("lang") or ""
        elif tag == "title":
            self.has_title = True
        elif tag == "meta" and values.get("name", "").lower() == "description":
            self.has_description = bool(values.get("content"))
        elif tag == "form":
            self.forms.append(values.get("action") or "")

        for attribute in ("href", "src", "poster"):
            value = values.get(attribute)
            if value:
                self.references.append((attribute, value))


def resolve_local_reference(reference: str) -> Path | None:
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc or parsed.scheme in IGNORED_SCHEMES:
        return None

    path = unquote(parsed.path)
    if not path:
        return None
    if path in EXPECTED_PAGES:
        return PUBLIC / EXPECTED_PAGES[path]
    if path.endswith(".html") and path.removesuffix(".html") in EXPECTED_PAGES:
        return PUBLIC / path.lstrip("/")
    # Cloudflare Pages serves /name from name.html (pages kept out of the sitemap, e.g. /ilova).
    html_twin = PUBLIC / (path.strip("/") + ".html")
    if path != "/" and html_twin.is_file():
        return html_twin
    return PUBLIC / path.lstrip("/")


def check() -> None:
    errors: list[str] = []
    if not PUBLIC.is_dir():
        raise SystemExit("public/ is missing; run scripts/build_firebase.py first")

    expected_files = {PUBLIC / name for name in EXPECTED_PAGES.values()} | {
        PUBLIC / "404.html"
    }
    for path in sorted(expected_files):
        if not path.is_file():
            errors.append(f"missing generated page: {path.relative_to(ROOT)}")

    for page in HTML_FILES:
        text = page.read_text(encoding="utf-8")
        relative_page = page.relative_to(ROOT)
        parser = PageParser()
        parser.feed(text)

        if "{{" in text or "{%" in text:
            errors.append(f"{relative_page}: unresolved Jinja template syntax")
        if not parser.lang:
            errors.append(f"{relative_page}: missing html lang attribute")
        if not parser.has_title:
            errors.append(f"{relative_page}: missing title")
        if page.name != "404.html" and not parser.has_description:
            errors.append(f"{relative_page}: missing meta description")
        for marker in PRIVATE_MARKERS:
            if marker in text:
                errors.append(f"{relative_page}: contains private marker {marker}")
        if "cdn.tailwindcss.com" in text:
            errors.append(f"{relative_page}: uses the Tailwind CDN script")
        if page.name != "404.html" and not re.search(r'<html[^>]+data-brand="(center|school)"', text):
            errors.append(f"{relative_page}: missing html data-brand attribute")

        for attribute, reference in parser.references:
            target = resolve_local_reference(reference)
            if target is not None and not target.exists():
                errors.append(
                    f"{relative_page}: broken {attribute}={reference!r} "
                    f"(expected {target.relative_to(ROOT)})"
                )

        for action in parser.forms:
            parsed_action = urlsplit(action)
            if action == "/api/register":
                continue
            if parsed_action.scheme != "https" or not parsed_action.netloc:
                errors.append(
                    f"{relative_page}: form action must be an absolute HTTPS URL: {action!r}"
                )

        if page.name in ("register.html", "admissions.html") and page.parent == PUBLIC:
            if 'action="/api/register"' not in text:
                errors.append(f"{relative_page}: registration form must submit same-origin")
            if not re.search(r'data-turnstile-sitekey="[^\"]+"', text):
                errors.append(f"{relative_page}: Turnstile site key is missing")
            if re.search(r'action="https?://[^"]+\.pages\.dev/api/register"', text):
                errors.append(f"{relative_page}: registration form points to a preview host")

    manifest_path = PUBLIC / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for icon in manifest.get("icons", []):
            target = resolve_local_reference(icon.get("src", ""))
            if target is None or not target.is_file():
                errors.append(f"manifest.json: missing icon {icon.get('src')!r}")
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"manifest.json: {error}")

    registration_options_path = PUBLIC / "registration-options.json"
    try:
        registration_options = json.loads(registration_options_path.read_text(encoding="utf-8"))
        active_programs = {
            item.get("id") for item in registration_options.get("programs", []) if item.get("active")
        }
        active_branches = {
            item.get("id") for item in registration_options.get("branches", []) if item.get("active")
        }
        if not {"ielts", "english", "sat"}.issubset(active_programs):
            errors.append("registration-options.json: missing core active programs")
        if not {"main", "gayrat", "unknown"}.issubset(active_branches):
            errors.append("registration-options.json: missing required active branches")
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"registration-options.json: {error}")

    sitemap_path = PUBLIC / "sitemap.xml"
    try:
        sitemap = ElementTree.parse(sitemap_path)
        namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locations = {
            node.text for node in sitemap.findall("s:url/s:loc", namespace) if node.text
        }
        for route in EXPECTED_PAGES:
            suffix = "/" if route == "/" else route
            if not any(urlsplit(location).path == suffix for location in locations):
                errors.append(f"sitemap.xml: missing route {route}")
    except (OSError, ElementTree.ParseError) as error:
        errors.append(f"sitemap.xml: {error}")

    redirects_path = PUBLIC / "_redirects"
    redirects = redirects_path.read_text(encoding="utf-8") if redirects_path.is_file() else ""
    for rule in EXPECTED_REDIRECTS:
        if rule not in redirects.splitlines():
            errors.append(f"_redirects: missing {rule!r}")
    if not (PUBLIC / "admissions" / "thanks.html").is_file():
        errors.append("missing generated page: public/admissions/thanks.html")
    if not (PUBLIC / "ilova.html").is_file():
        errors.append("missing generated page: public/ilova.html")

    robots = (PUBLIC / "robots.txt").read_text(encoding="utf-8")
    if not re.search(r"^Sitemap:\s+https://", robots, flags=re.MULTILINE):
        errors.append("robots.txt: missing HTTPS sitemap declaration")

    headers = (PUBLIC / "_headers").read_text(encoding="utf-8")
    for required_header in (
        "X-Content-Type-Options:",
        "X-Frame-Options:",
        "Referrer-Policy:",
        "Permissions-Policy:",
    ):
        if required_header not in headers:
            errors.append(f"_headers: missing {required_header}")

    for required_asset in ("static/brand/tokens.css", "static/css/site.css"):
        if not (PUBLIC / required_asset).is_file():
            errors.append(f"missing {required_asset}")
    tokens_check = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_brand_tokens.py"), "--check"],
        capture_output=True, text=True,
    )
    if tokens_check.returncode:
        errors.append(tokens_check.stdout.strip() or "static/brand/tokens.css check failed")

    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        raise SystemExit(1)

    print(
        f"Firebase build check passed: {len(HTML_FILES)} HTML files, "
        f"{sum(1 for path in PUBLIC.rglob('*') if path.is_file())} total files"
    )


if __name__ == "__main__":
    check()
