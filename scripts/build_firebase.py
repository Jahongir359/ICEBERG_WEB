#!/usr/bin/env python3
"""Build the public Flask pages as static files for Firebase Hosting."""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public"
PUBLIC_ROUTES = {
    "/": "index.html",
    "/about": "about.html",
    "/our_programs": "our_programs.html",
    "/news": "news.html",
    "/questions": "questions.html",
    "/contact": "contact.html",
    "/register": "register.html",
}
ROOT_ASSETS = ("/favicon.ico", "/manifest.json", "/robots.txt", "/sitemap.xml")


def make_form_static(
    html: str,
    route: str,
    whatsapp_number: str,
    site_url: str,
    turnstile_site_key: str,
) -> str:
    local_action = f'action="{route}" method="post"'
    if route == "/register":
        turnstile_attribute = (
            f' data-turnstile-sitekey="{turnstile_site_key}"'
            if turnstile_site_key
            else ""
        )
        static_action = (
            f'action="{site_url}/api/register" method="post" '
            f'data-static-lead-form="register"{turnstile_attribute}'
        )
    else:
        static_action = (
            f'action="https://wa.me/{whatsapp_number}" method="get" '
            f'data-static-lead-form="{route.lstrip("/")}"'
        )
    return html.replace(local_action, static_action)


def build() -> None:
    # Imports happen here so running --help or inspecting this script has no app side effects.
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    # Some hosting build images compile Python without the optional _sqlite3
    # extension. Public static pages use checked-in defaults and need no DB.
    os.environ["ICEBERG_STATIC_BUILD"] = "1"
    from app import app  # pylint: disable=import-outside-toplevel

    site_url = os.environ.get("PUBLIC_SITE_URL", "https://iceberglc.com").rstrip("/")
    whatsapp_number = re.sub(
        r"\D", "", os.environ.get("PUBLIC_WHATSAPP_NUMBER", "998939461699")
    )
    turnstile_site_key = os.environ.get("PUBLIC_TURNSTILE_SITE_KEY", "").strip()
    if not whatsapp_number:
        raise RuntimeError("PUBLIC_WHATSAPP_NUMBER must contain a phone number")

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    shutil.copytree(ROOT / "static", OUTPUT / "static")
    shutil.copy2(ROOT / "cloudflare" / "_headers", OUTPUT / "_headers")

    client = app.test_client()
    for route, filename in PUBLIC_ROUTES.items():
        response = client.get(route, base_url=site_url)
        if response.status_code != 200:
            raise RuntimeError(f"GET {route} returned HTTP {response.status_code}")

        html = response.get_data(as_text=True)
        html = make_form_static(
            html, "/contact", whatsapp_number, site_url, turnstile_site_key
        )
        html = make_form_static(
            html, "/register", whatsapp_number, site_url, turnstile_site_key
        )
        # The Flask-only hidden admin login must not be exposed on the static site.
        html = re.sub(r'\sdata-admin-trigger-name="[^"]*"', "", html)
        html = re.sub(
            r'\s*<div id="admin-(?:password|secret)-wrap".*?</div>',
            "",
            html,
            flags=re.DOTALL,
        )
        html = re.sub(
            r"\s*const form = document\.getElementById\('contactForm'\);"
            r".*?\s*syncHiddenAdminMode\(\);",
            "",
            html,
            flags=re.DOTALL,
        )
        if "data-static-lead-form" in html:
            html = html.replace(
                "</body>",
                '<script src="/static/js/firebase-forms.js" defer></script>\n</body>',
            )
        (OUTPUT / filename).write_text(html, encoding="utf-8")

    for route in ROOT_ASSETS:
        response = client.get(route, base_url=site_url)
        if response.status_code != 200:
            raise RuntimeError(f"GET {route} returned HTTP {response.status_code}")
        (OUTPUT / route.lstrip("/")).write_bytes(response.data)

    # Firebase serves this file only when no static file or configured route matches.
    (OUTPUT / "404.html").write_text(
        """<!doctype html>
<html lang="uz">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex">
  <title>Sahifa topilmadi | ICEBERG</title>
  <style>
    body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f4f8fc;
    color:#10284c;font:16px system-ui,sans-serif;text-align:center}
    main{padding:2rem}h1{font-size:clamp(4rem,15vw,8rem);margin:0;color:#3ba3ff}
    a{display:inline-block;margin-top:1rem;padding:.8rem 1.2rem;border-radius:999px;
    background:#10284c;color:white;text-decoration:none;font-weight:700}
  </style>
</head>
<body><main><h1>404</h1><h2>Sahifa topilmadi</h2>
<p>Siz izlagan sahifa ko'chirilgan yoki mavjud emas.</p>
<a href="/">Bosh sahifaga qaytish</a></main></body>
</html>
""",
        encoding="utf-8",
    )

    print(f"Built {len(PUBLIC_ROUTES)} pages and static assets in {OUTPUT}")
    print(f"Static contact form opens WhatsApp for +{whatsapp_number}")
    print("Static registration form submits to /api/register")


if __name__ == "__main__":
    build()
