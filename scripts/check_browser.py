#!/usr/bin/env python3
"""Smoke-test an isolated Flask instance in Chromium, without external delivery.

Requires requirements-dev.txt and `python -m playwright install chromium`.
Screenshots are written to a fresh temporary directory. Never contacts production.
"""
import os
import secrets
import sys
import tempfile
import threading
import logging
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check():
    from playwright.sync_api import sync_playwright
    from werkzeug.serving import make_server
    with tempfile.TemporaryDirectory() as directory:
        os.environ['DATABASE_PATH'] = str(Path(directory) / 'browser.db')
        os.environ['SECRET_KEY'] = secrets.token_hex(32)
        password = secrets.token_urlsafe(24)
        os.environ['ADMIN_PASSWORD'] = password
        os.environ.pop('ICEBERG_STATIC_BUILD', None)
        from app import app
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        import app as module
        from scripts.build_firebase import PUBLIC_ROUTES
        module.send_telegram_notification = lambda *_args: None
        module.send_registration_lead_to_management = lambda *_args: False
        server = make_server('127.0.0.1', 0, app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'
        screenshots = Path(tempfile.mkdtemp(prefix='iceberg-audit-'))
        failures = []
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                for width in (375, 1280):
                    context = browser.new_context(viewport={'width': width, 'height': 900})
                    context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(origin) else route.abort())
                    page = context.new_page()
                    page.on('pageerror', lambda error: failures.append(str(error)))
                    for route in PUBLIC_ROUTES:
                        response = page.goto(origin + route, wait_until='networkidle')
                        if response.status != 200:
                            failures.append(f'{width}px {route}: HTTP {response.status}')
                        if page.locator('h1').count() != 1:
                            failures.append(f'{width}px {route}: expected one heading')
                        if page.evaluate('document.documentElement.scrollWidth > innerWidth'):
                            failures.append(f'{width}px {route}: horizontal overflow')
                    page.goto(origin + '/', wait_until='networkidle')
                    page.screenshot(path=str(screenshots / f'home-{width}.png'), full_page=True)
                    page.locator('.public-menu summary').click()
                    if not page.locator('.public-menu').evaluate('(element) => element.open'):
                        failures.append('Mobile/desktop menu did not open')
                    page.keyboard.press('Escape')
                    if page.locator('.public-menu').evaluate('(element) => element.open'):
                        failures.append('Escape did not close menu')
                    context.close()
                context = browser.new_context(viewport={'width': 375, 'height': 900})
                context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(origin) else route.abort())
                page = context.new_page()
                page.on('pageerror', lambda error: failures.append(str(error)))
                page.goto(origin + '/register?program=chemistry&branch=gayrat', wait_until='networkidle')
                page.locator('.language-link').click()
                page.wait_for_load_state('networkidle')
                require(page.locator('#course').input_value() == 'chemistry', "Browser behavior check failed")
                require(page.locator('#preferred_branch').input_value() == 'gayrat', "Browser behavior check failed")
                page.locator('#student_name').fill('Audit Test Student')
                page.locator('#student_phone').fill('901234567')
                page.locator('button[type=submit]').click()
                page.wait_for_url('**/en/register?success=1')
                require(page.locator('[data-registration-success]').is_visible(), "Browser behavior check failed")
                require(not page.locator('[data-registration-form]').is_visible(), "Browser behavior check failed")
                page.goto(origin + '/en/contact', wait_until='networkidle')
                captured = []
                page.route('https://t.me/**', lambda route: (captured.append(route.request.url), route.fulfill(status=200, body='<h1>Local Telegram draft test</h1>'))[-1])
                page.locator('#name').fill('Audit Test Student')
                page.locator('#phone').fill('901234567')
                page.locator('#message').fill('Tuition question: 日本語 & O‘zbekcha')
                page.locator('button[type=submit]').click()
                page.wait_for_url('https://t.me/**')
                draft = parse_qs(urlsplit(captured[0]).query)['text'][0]
                require('日本語 & O‘zbekcha' in draft, "Browser behavior check failed")
                require(urlsplit(captured[0]).path == '/iceberg_qabulxona', "Browser behavior check failed")
                page.goto(origin + '/portal/' + module.ADMIN_LOGIN_SLUG, wait_until='networkidle')
                page.locator('#password').fill(password)
                page.locator('button[type=submit]').click()
                page.wait_for_url('**/admin/dashboard')
                for path in ('/admin/content', '/admin/assets', '/admin/editor', '/admin/news', '/admin/faq', '/admin/tools', '/students', '/contacts_list'):
                    result = page.goto(origin + path, wait_until='networkidle')
                    require(result.status == 200, path)
                page.goto(origin + '/admin/content', wait_until='networkidle')
                page.locator('#hero_main_title').fill('Browser audit headline')
                page.locator('#content-editor-form button[type=submit]').click()
                page.wait_for_load_state('networkidle')
                page.goto(origin + '/', wait_until='networkidle')
                require(page.locator('h1').inner_text() == 'Browser audit headline', "Browser behavior check failed")
                context.close()
                context = browser.new_context(java_script_enabled=False, viewport={'width': 375, 'height': 900})
                context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(origin) else route.abort())
                page = context.new_page()
                page.goto(origin + '/questions')
                page.locator('.faq-detail summary').first.click()
                require(page.locator('.faq-detail').first.evaluate('(element) => element.open'), "Browser behavior check failed")
                page.locator('.public-menu summary').click()
                require(page.locator('.public-menu').evaluate('(element) => element.open'), "Browser behavior check failed")
                context.close()
                # Test the generated static form separately; its API response is
                # mocked so this never creates a real Apps Script registration.
                class StaticHandler(SimpleHTTPRequestHandler):
                    def __init__(self, *args, **kwargs):
                        super().__init__(*args, directory=str(ROOT / 'public'), **kwargs)

                    def do_GET(self):
                        parsed = urlsplit(self.path)
                        if parsed.path in PUBLIC_ROUTES:
                            self.path = '/' + PUBLIC_ROUTES[parsed.path]
                        super().do_GET()

                    def log_message(self, *_args):
                        pass

                static_server = ThreadingHTTPServer(('127.0.0.1', 0), StaticHandler)
                threading.Thread(target=static_server.serve_forever, daemon=True).start()
                static_origin = f'http://127.0.0.1:{static_server.server_port}'
                try:
                    context = browser.new_context(viewport={'width': 375, 'height': 900})
                    context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(static_origin) else route.abort())
                    page = context.new_page()
                    page.on('pageerror', lambda error: failures.append(str(error)))
                    submitted = []
                    page.route('**/api/register', lambda route: (submitted.append(route.request.post_data_json), route.fulfill(status=201, content_type='application/json', body='{"ok":true,"id":"local-test"}'))[-1])
                    page.goto(static_origin + '/en/register?program=chemistry&branch=gayrat', wait_until='networkidle')
                    require(page.locator('input[name=submission_id]').input_value() == '', 'Static HTML must not freeze a shared submission ID')
                    page.locator('#student_name').fill('Static Audit Student')
                    page.locator('#student_phone').fill('901234567')
                    page.locator('button[type=submit]').click()
                    page.locator('[data-registration-success]').wait_for(state='visible')
                    require(submitted[0]['program'] == 'chemistry' and submitted[0]['branch'] == 'gayrat', 'Static selection was not preserved')
                    context.close()
                finally:
                    static_server.shutdown()
                    static_server.server_close()
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
        if failures:
            raise SystemExit('\n'.join(failures))
        print('Browser checks passed: 26 public routes at 375px and 1280px, language switching, Flask/static registration, Telegram drafts, admin forms, and navigation/FAQ without JavaScript.')
        print(f'Screenshots: {screenshots}')


if __name__ == '__main__':
    check()
