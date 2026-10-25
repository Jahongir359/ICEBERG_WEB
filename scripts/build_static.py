#!/usr/bin/env python3
"""Render every public page of the Flask app to static files in public/ for Cloudflare Pages."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public"
# Pages that are not translated (the noindex "coming soon" page).
EXTRA_ROUTES = {"/ilova": "ilova.html"}
ROOT_ASSETS = ("/favicon.ico", "/manifest.json", "/robots.txt", "/sitemap.xml")

NOT_FOUND_PAGE = """<!doctype html>
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
    color:#4C0909;text-decoration:none;font-weight:800}nav a{background:none;color:#F2D9D6;padding:.4rem .6rem;font-weight:600}
  </style>
</head>
<body><main><img src="/static/school/img/crest-white-168.png" alt="Iceberg School"><h1>404</h1>
<p>Siz izlagan sahifa ko'chirilgan yoki mavjud emas.</p>
<a href="/">Bosh sahifaga qaytish</a>
<nav><a href="/ru/" lang="ru">На главную</a> · <a href="/en/" lang="en">Home page</a></nav></main></body>
</html>
"""


def page_routes(localized_routes: dict[str, tuple[str, str]]) -> dict[str, str]:
    """Route -> output file for every page in Uzbek, Russian and English."""
    routes = {}
    for uz_path, other_path in localized_routes.values():
        routes[uz_path] = "index.html" if uz_path == "/" else f"{uz_path.lstrip('/')}.html"
        for lang in ("ru", "en"):
            route = f"/{lang}{other_path}" if other_path != "/" else f"/{lang}/"
            routes[route] = f"{lang}/index.html" if other_path == "/" else f"{lang}{other_path}.html"
    return routes


def build() -> None:
    # Imports happen here so inspecting this script has no app side effects.
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    from app import LEGACY_REDIRECTS, LOCALIZED_ROUTES, SITE_URL, TURNSTILE_SITE_KEY, app  # pylint: disable=import-outside-toplevel

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    shutil.copytree(ROOT / "static", OUTPUT / "static")
    shutil.copy2(ROOT / "cloudflare" / "_headers", OUTPUT / "_headers")
    # The Pages Function validates programs and branches against this file.
    shutil.copy2(ROOT / "config" / "registration.json", OUTPUT / "registration-options.json")

    client = app.test_client()
    routes = {**page_routes(LOCALIZED_ROUTES), **EXTRA_ROUTES}
    for route, filename in routes.items():
        response = client.get(route, base_url=SITE_URL)
        if response.status_code != 200:
            raise RuntimeError(f"GET {route} returned HTTP {response.status_code}")
        (OUTPUT / filename).parent.mkdir(parents=True, exist_ok=True)
        (OUTPUT / filename).write_bytes(response.data)

    for route in ROOT_ASSETS:
        response = client.get(route, base_url=SITE_URL)
        if response.status_code != 200:
            raise RuntimeError(f"GET {route} returned HTTP {response.status_code}")
        (OUTPUT / route.lstrip("/")).write_bytes(response.data)

    (OUTPUT / "_redirects").write_text(
        "".join(f"{source} {target} {code}\n" for source, target, code in LEGACY_REDIRECTS),
        encoding="utf-8",
    )
    # Cloudflare Pages serves this for any URL without a file.
    (OUTPUT / "404.html").write_text(NOT_FOUND_PAGE, encoding="utf-8")

    print(f"Built {len(routes)} pages and static assets in {OUTPUT}")
    if not TURNSTILE_SITE_KEY:
        print("WARNING: no Turnstile site key; set PUBLIC_TURNSTILE_SITE_KEY under [vars] in wrangler.toml")


if __name__ == "__main__":
    build()
