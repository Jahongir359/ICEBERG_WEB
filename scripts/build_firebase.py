#!/usr/bin/env python3
"""Build the public Flask pages as static files for Firebase Hosting."""

from __future__ import annotations

import os
import shutil
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public"
PUBLIC_ROUTES = {
    "/": "index.html",
    "/about": "about.html",
    "/programs": "programs.html",
    "/admissions": "admissions.html",
    "/admissions/thanks": "admissions/thanks.html",
    "/courses": "courses.html",
    "/news": "news.html",
    "/contact": "contact.html",
    "/register": "register.html",
}
# Former Learning Center URLs, kept working with permanent redirects.
REDIRECTS = (
    ("/our_programs", "/courses"),
    ("/questions", "/courses#savollar"),
)
ROOT_ASSETS = ("/favicon.ico", "/manifest.json", "/robots.txt", "/sitemap.xml")


def load_wrangler_vars() -> dict[str, str]:
    config_path = ROOT / "wrangler.toml"
    with config_path.open("rb") as config_file:
        config = tomllib.load(config_file)
    return {
        str(key): str(value)
        for key, value in config.get("vars", {}).items()
    }


def make_form_static(html: str, route: str, turnstile_site_key: str) -> str:
    """Point a Flask form at the Cloudflare /api/register function."""
    local_action = f'action="{route}" method="post"'
    turnstile_attribute = (
        f' data-turnstile-sitekey="{turnstile_site_key}"' if turnstile_site_key else ""
    )
    form_kind = "register" if route == "/register" else "school-enquiry"
    static_action = (
        'action="/api/register" method="post" '
        f'data-static-lead-form="{form_kind}"{turnstile_attribute}'
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

    wrangler_vars = load_wrangler_vars()
    site_url = os.environ.get(
        "PUBLIC_SITE_URL",
        wrangler_vars.get("PUBLIC_SITE_URL", "https://iceberglc.com"),
    ).rstrip("/")
    turnstile_site_key = (
        os.environ.get("PUBLIC_TURNSTILE_SITE_KEY", "").strip()
        or os.environ.get("TURNSTILE_SITE_KEY", "").strip()
        or wrangler_vars.get("PUBLIC_TURNSTILE_SITE_KEY", "").strip()
    )

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    shutil.copytree(ROOT / "static", OUTPUT / "static")
    shutil.copy2(ROOT / "cloudflare" / "_headers", OUTPUT / "_headers")
    shutil.copy2(
        ROOT / "config" / "registration.json",
        OUTPUT / "registration-options.json",
    )

    client = app.test_client()
    for route, filename in PUBLIC_ROUTES.items():
        response = client.get(route, base_url=site_url)
        if response.status_code != 200:
            raise RuntimeError(f"GET {route} returned HTTP {response.status_code}")

        html = response.get_data(as_text=True)
        for form_route in ("/register", "/admissions"):
            html = make_form_static(html, form_route, turnstile_site_key)
        if "data-static-lead-form" in html and "/static/js/firebase-forms.js" not in html:
            html = html.replace(
                "</body>",
                '<script src="/static/js/firebase-forms.js" defer></script>\n</body>',
            )
        (OUTPUT / filename).parent.mkdir(parents=True, exist_ok=True)
        (OUTPUT / filename).write_text(html, encoding="utf-8")

    (OUTPUT / "_redirects").write_text(
        "".join(f"{source} {target} 301\n" for source, target in REDIRECTS),
        encoding="utf-8",
    )

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
  <meta name="theme-color" content="#4C0909">
  <title>Sahifa topilmadi | Iceberg School</title>
  <link rel="icon" href="/favicon.ico" sizes="any">
  <style>
    body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;box-sizing:border-box;
    background:linear-gradient(165deg,#4C0909,#2E0505);color:#fff;font:16px/1.6 Inter,system-ui,sans-serif;text-align:center}
    img{width:84px;height:auto;margin:0 auto 12px}h1{font-size:clamp(4rem,18vw,7rem);margin:0;line-height:1;letter-spacing:-.04em}
    p{color:#F2D9D6;margin:.5rem 0 1.5rem}a{display:inline-block;padding:.85rem 1.4rem;border-radius:13px;background:#fff;
    color:#4C0909;text-decoration:none;font-weight:800}
  </style>
</head>
<body><main><img src="/static/school/img/crest-white.png" alt="Iceberg School"><h1>404</h1>
<p>Siz izlagan sahifa ko'chirilgan yoki mavjud emas.</p>
<a href="/">Bosh sahifaga qaytish</a></main></body>
</html>
""",
        encoding="utf-8",
    )

    print(f"Built {len(PUBLIC_ROUTES)} pages and static assets in {OUTPUT}")
    print("Static registration and admissions forms submit to /api/register")
    if not turnstile_site_key:
        print(
            "WARNING: Turnstile site key is missing; set PUBLIC_TURNSTILE_SITE_KEY "
            "under [vars] in wrangler.toml"
        )


if __name__ == "__main__":
    build()
