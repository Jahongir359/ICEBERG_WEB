#!/usr/bin/env python3
"""Fail fast on broken links or unsafe output in the Firebase static build."""

from __future__ import annotations

import json
import re
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
    "/programs/ielts": "programs/ielts.html",
    "/programs/sat": "programs/sat.html",
    "/news": "news.html",
    "/faq": "faq.html",
    "/contact": "contact.html",
    "/register": "register.html",
}
IGNORED_SCHEMES = {"data", "mailto", "tel", "javascript"}
PRIVATE_MARKERS = (
    "admin_password",
    "admin_secret_code",
    "data-admin-trigger-name",
    "app.iceberglc.com",
)
IMPORTANT_NAV_ROUTES = set(EXPECTED_PAGES)


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[tuple[str, str]] = []
        self.forms: list[str] = []
        self.has_title = False
        self.has_description = False
        self.title = ""
        self.description = ""
        self.canonical = ""
        self.robots = ""
        self.h1_count = 0
        self.json_ld: list[str] = []
        self._in_json_ld = False
        self._json_buffer: list[str] = []
        self._in_title = False
        self.headings: list[int] = []
        self.image_issues: list[str] = []
        self.lang = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "html":
            self.lang = values.get("lang") or ""
        elif tag == "title":
            self.has_title = True
            self._in_title = True
        elif tag == "meta" and values.get("name", "").lower() == "description":
            self.has_description = bool(values.get("content"))
            self.description = values.get("content") or ""
        elif tag == "meta" and values.get("name", "").lower() == "robots":
            self.robots = values.get("content") or ""
        elif tag == "link" and values.get("rel", "").lower() == "canonical":
            self.canonical = values.get("href") or ""
        elif tag == "h1":
            self.h1_count += 1
            self.headings.append(1)
        elif tag in {"h2", "h3", "h4", "h5", "h6"}:
            self.headings.append(int(tag[1]))
        elif tag == "img":
            if "alt" not in values:
                self.image_issues.append(f"{values.get('src', '<unknown>')}: missing alt")
            if not values.get("width") or not values.get("height"):
                self.image_issues.append(
                    f"{values.get('src', '<unknown>')}: missing intrinsic width/height"
                )
        elif tag == "script" and values.get("type") == "application/ld+json":
            self._in_json_ld = True
            self._json_buffer = []
        elif tag == "form":
            self.forms.append(values.get("action") or "")

        for attribute in ("href", "src", "poster"):
            value = values.get(attribute)
            if value:
                self.references.append((attribute, value))

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._in_json_ld:
            self._json_buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag == "script" and self._in_json_ld:
            self.json_ld.append("".join(self._json_buffer))
            self._in_json_ld = False


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
    return PUBLIC / path.lstrip("/")


def check() -> None:
    errors: list[str] = []
    titles: dict[str, Path] = {}
    descriptions: dict[str, Path] = {}
    canonicals: dict[str, Path] = {}
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
        if page.name != "404.html":
            expected_route = next(
                (route for route, filename in EXPECTED_PAGES.items() if filename == str(page.relative_to(PUBLIC))),
                None,
            )
            expected_canonical = "https://iceberglc.com" + (expected_route or "")
            if parser.canonical != expected_canonical:
                errors.append(f"{relative_page}: canonical {parser.canonical!r} != {expected_canonical!r}")
            if parser.h1_count != 1:
                errors.append(f"{relative_page}: expected one h1, found {parser.h1_count}")
            for previous, current in zip(parser.headings, parser.headings[1:]):
                if current > previous + 1:
                    errors.append(
                        f"{relative_page}: heading level jumps from h{previous} to h{current}"
                    )
            for image_issue in parser.image_issues:
                errors.append(f"{relative_page}: {image_issue}")
            if "noindex" in parser.robots.lower():
                errors.append(f"{relative_page}: canonical public page is noindex")
            normalized_title = parser.title.strip().casefold()
            normalized_description = parser.description.strip().casefold()
            for value, seen, label in (
                (normalized_title, titles, "title"),
                (normalized_description, descriptions, "description"),
                (parser.canonical, canonicals, "canonical"),
            ):
                if value in seen:
                    errors.append(
                        f"{relative_page}: duplicate {label} also used by "
                        f"{seen[value].relative_to(ROOT)}"
                    )
                elif value:
                    seen[value] = page
            for raw_json_ld in parser.json_ld:
                try:
                    json.loads(raw_json_ld)
                except json.JSONDecodeError as error:
                    errors.append(f"{relative_page}: invalid JSON-LD: {error}")
        for marker in PRIVATE_MARKERS:
            if marker in text:
                errors.append(f"{relative_page}: contains private marker {marker}")

        for attribute, reference in parser.references:
            target = resolve_local_reference(reference)
            if target is not None and not target.exists():
                errors.append(
                    f"{relative_page}: broken {attribute}={reference!r} "
                    f"(expected {target.relative_to(ROOT)})"
                )

        if page.name != "404.html":
            linked_routes = {
                urlsplit(reference).path
                for attribute, reference in parser.references
                if attribute == "href" and not urlsplit(reference).netloc
            }
            missing_nav_routes = IMPORTANT_NAV_ROUTES - linked_routes
            if missing_nav_routes:
                errors.append(
                    f"{relative_page}: missing shared navigation links: "
                    + ", ".join(sorted(missing_nav_routes))
                )
            if page.name != "index.html" and 'class="breadcrumbs' not in text:
                errors.append(f"{relative_page}: missing visible breadcrumbs")

        for action in parser.forms:
            parsed_action = urlsplit(action)
            if parsed_action.scheme != "https" or not parsed_action.netloc:
                errors.append(
                    f"{relative_page}: form action must be an absolute HTTPS URL: {action!r}"
                )

    manifest_path = PUBLIC / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for icon in manifest.get("icons", []):
            target = resolve_local_reference(icon.get("src", ""))
            if target is None or not target.is_file():
                errors.append(f"manifest.json: missing icon {icon.get('src')!r}")
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"manifest.json: {error}")

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
        expected_locations = {
            "https://iceberglc.com" + ("/" if route == "/" else route)
            for route in EXPECTED_PAGES
        }
        unexpected_locations = locations - expected_locations
        if unexpected_locations:
            errors.append(
                "sitemap.xml: unexpected or non-canonical URLs: "
                + ", ".join(sorted(unexpected_locations))
            )
    except (OSError, ElementTree.ParseError) as error:
        errors.append(f"sitemap.xml: {error}")

    robots = (PUBLIC / "robots.txt").read_text(encoding="utf-8")
    if not re.search(r"^Sitemap:\s+https://", robots, flags=re.MULTILINE):
        errors.append("robots.txt: missing HTTPS sitemap declaration")

    redirects = (PUBLIC / "_redirects").read_text(encoding="utf-8")
    for expected_redirect in ("/our_programs /programs 301", "/questions /faq 301"):
        if expected_redirect not in redirects:
            errors.append(f"_redirects: missing {expected_redirect}")

    headers = (PUBLIC / "_headers").read_text(encoding="utf-8")
    for required_header in (
        "X-Content-Type-Options:",
        "X-Frame-Options:",
        "Referrer-Policy:",
        "Permissions-Policy:",
    ):
        if required_header not in headers:
            errors.append(f"_headers: missing {required_header}")

    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        raise SystemExit(1)

    print(
        f"Firebase build check passed: {len(HTML_FILES)} HTML files, "
        f"{sum(1 for path in PUBLIC.rglob('*') if path.is_file())} total files"
    )


if __name__ == "__main__":
    check()
