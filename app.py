"""iceberglc.com — the Iceberg School website.

Flask renders the Jinja templates in templates/site/; scripts/build_static.py turns every page into
static HTML for Cloudflare Pages, which serves the live site. The forms post to /api/register, a
Cloudflare Pages Function (functions/api/register.js). Run `python app.py` for a local preview.
"""
import json
import os
import re
import tomllib
from datetime import UTC, date, datetime

from flask import Flask, Response, g, redirect, render_template, request, url_for
from markupsafe import Markup

app = Flask(__name__)
SITE_URL = 'https://iceberglc.com'


def load_json(*parts):
    with open(os.path.join(app.root_path, *parts), 'r', encoding='utf-8') as file:
        return json.load(file)


def load_registration_config():
    config = load_json('config', 'registration.json')
    config['programs'] = [item for item in config.get('programs', []) if item.get('active')]
    config['branches'] = [item for item in config.get('branches', []) if item.get('active')]
    for group_name in ('programs', 'branches'):
        ids = [item.get('id', '') for item in config[group_name]]
        if len(ids) != len(set(ids)) or any(not re.fullmatch(r'[a-z0-9-]+', item_id) for item_id in ids):
            raise RuntimeError(f'Invalid or duplicate active registration {group_name} ID')
    return config


def load_turnstile_site_key():
    """Public Turnstile key: from the environment, else the [vars] in wrangler.toml."""
    key = os.environ.get('PUBLIC_TURNSTILE_SITE_KEY', '').strip()
    if key:
        return key
    with open(os.path.join(app.root_path, 'wrangler.toml'), 'rb') as file:
        return str(tomllib.load(file).get('vars', {}).get('PUBLIC_TURNSTILE_SITE_KEY', '')).strip()


REGISTRATION_CONFIG = load_registration_config()
SCHOOL_CONFIG = load_json('config', 'school.json')
COURSE_FAQS = load_json('config', 'faq.json')['faqs']
TURNSTILE_SITE_KEY = load_turnstile_site_key()


def read_static(path):
    with open(os.path.join(app.root_path, 'static', *path.split('/')), 'r', encoding='utf-8') as file:
        return file.read().strip()


# Small stylesheets inlined in <head> (brand tokens, @font-face) so the first paint waits on one CSS file.
INLINE_CSS = Markup('\n'.join(read_static(path) for path in ('brand/tokens.css', 'fonts/fonts.css')))
SCHOOL_GRADES = [str(number) for number in range(1, 12)]
SCHOOL_LANGUAGES = {'uz': "O'zbek", 'ru': 'Rus', 'en': 'Ingliz'}


def news_posts():
    """Posts from config/news.json, newest first, shaped for the news templates."""
    posts = load_json('config', 'news.json')['posts']
    for post in posts:
        post['media_items'] = (
            [{'media_type': 'image', 'file_path': post['image'], 'caption': post.get('image_alt', '')}]
            if post.get('image') else []
        )
    return sorted(posts, key=lambda post: post.get('event_date') or '', reverse=True)


# ---- Languages ---------------------------------------------------------------------------------
# Uzbek is the source language: templates wrap their Uzbek text in _() and translations/<lang>.json
# maps that exact text to Russian and English. Public pages are also served under /ru/ and /en/.
LANGUAGES = ('uz', 'ru', 'en')
TRANSLATIONS = {lang: load_json('translations', f'{lang}.json') for lang in ('ru', 'en')}
MISSING_TRANSLATIONS = set()

# endpoint -> (Uzbek path, path under /ru/ and /en/). Each page is registered once per language
# with a "lang" default, so url_for(endpoint) follows the current page's language.
LOCALIZED_ROUTES = {
    'index': ('/', '/'),
    'about': ('/about', '/about'),
    'programs': ('/programs', '/programs'),
    'admissions': ('/admissions', '/admissions'),
    'admissions_thanks': ('/admissions/thanks', '/admissions/thanks'),
    'courses': ('/courses', '/courses'),
    'register': ('/register', '/register'),
    'news': ('/news', '/news'),
    'contact': ('/contact', '/contact'),
    'partnerships': ('/hamkorlik', '/partners'),
}
LOCALIZED_PATHS = {endpoint: other for endpoint, (_uz, other) in LOCALIZED_ROUTES.items()}
OG_LOCALES = {'uz': 'uz_UZ', 'ru': 'ru_RU', 'en': 'en_US'}

SITE_NAV = [
    ('about', "Maktab haqida"),
    ('programs', "Ta'lim dasturlari"),
    ('admissions', 'Qabul'),
    ('courses', 'Kurslar'),
    ('news', 'Yangiliklar'),
    ('contact', 'Aloqa'),
]


def current_lang():
    return getattr(g, 'lang', 'uz')


def translate(text, **values):
    """Translate Uzbek source text into the page language; falls back to Uzbek if missing."""
    lang = current_lang()
    if lang != 'uz' and text:
        translated = TRANSLATIONS[lang].get(text)
        if translated is None:
            MISSING_TRANSLATIONS.add((lang, text))
            translated = text
        text = translated
    return text.format(**values) if values else text


def translate_html(text, **values):
    """Same as translate() for our own strings that contain markup."""
    return Markup(translate(text, **values))


def lang_url(lang, endpoint=None, **values):
    """URL of the current (or given) page in another language, or None if it has no translation."""
    endpoint = endpoint or request.endpoint
    if endpoint not in LOCALIZED_PATHS:
        return None
    if endpoint == request.endpoint and not values:
        values = dict(request.view_args or {})
    return url_for(endpoint, lang=lang, **values)


@app.url_value_preprocessor
def pull_lang(endpoint, values):
    g.lang = (values or {}).pop('lang', 'uz')


@app.url_defaults
def add_lang(endpoint, values):
    if endpoint in LOCALIZED_ROUTES:
        values.setdefault('lang', current_lang())
    else:
        values.pop('lang', None)


@app.context_processor
def inject_site_context():
    return {
        'lang': current_lang(),
        'languages': LANGUAGES,
        'og_locale': OG_LOCALES[current_lang()],
        '_': translate,
        '_h': translate_html,
        'lang_url': lang_url,
        'school': SCHOOL_CONFIG,
        'registration': REGISTRATION_CONFIG,
        'site_nav': SITE_NAV,
        'turnstile_site_key': TURNSTILE_SITE_KEY,
        'inline_css': INLINE_CSS,
        'current_year': datetime.now(UTC).year,
    }


# ---- Pages -------------------------------------------------------------------------------------
def index():
    return render_template('site/home.html', posts=news_posts())


def about():
    return render_template('site/about.html')


def programs():
    return render_template('site/programs.html')


def admissions():
    return render_template('site/admissions.html', grades=SCHOOL_GRADES, school_languages=SCHOOL_LANGUAGES)


def admissions_thanks():
    return render_template('site/thanks.html')


def courses():
    return render_template('site/courses.html', faqs=COURSE_FAQS)


def register():
    return render_template('site/register.html')


def news():
    return render_template('site/news.html', posts=news_posts())


def contact():
    return render_template('site/contact.html')


def partnerships():
    return render_template('site/partnerships.html')


for _endpoint, (_uz_path, _other_path) in LOCALIZED_ROUTES.items():
    for _lang in LANGUAGES:
        if _lang == 'uz':
            _rule = _uz_path
        else:
            _rule = f'/{_lang}{_other_path}' if _other_path != '/' else f'/{_lang}/'
        app.add_url_rule(_rule, endpoint=_endpoint, view_func=globals()[_endpoint], defaults={'lang': _lang})


@app.route('/ilova')
def coming_soon():
    # Portal and app links point here while the new portal and app are built (config/school.json).
    return render_template('site/coming_soon.html')


# ---- Old URLs ----------------------------------------------------------------------------------
# Every old public URL that search engines still list -> its page today. One list feeds both the
# Flask routes below and the Cloudflare `_redirects` file (scripts/build_static.py); specific
# rules come before the `/*` catch-alls.
LEGACY_REDIRECTS = (
    ('/our_programs', '/courses', 301),
    ('/questions', '/courses#savollar', 301),
    ('/our_programs.html', '/courses', 301),
    ('/questions.html', '/courses#savollar', 301),
    ('/programs/sat', '/courses#sat', 301),
    ('/programs/ielts', '/courses#ielts', 301),
    ('/programs/*', '/programs', 301),
    ('/faq', '/courses#savollar', 301),
    ('/contacts', '/contact', 301),
    ('/news/*', '/news', 301),
    # Old English URLs now land on the real English pages.
    ('/en/our_programs', '/en/courses', 301),
    ('/partners', '/en/partners', 301),
)


def _legacy_redirect(target, code):
    return lambda **_: redirect(target, code=code)


for _index, (_source, _target, _code) in enumerate(LEGACY_REDIRECTS):
    _rule = _source[:-2] + '/<path:_rest>' if _source.endswith('/*') else _source
    app.add_url_rule(_rule, f'legacy_redirect_{_index}', _legacy_redirect(_target, _code))


# ---- Files for browsers and search engines ------------------------------------------------------
@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.ico')


@app.route('/manifest.json')
def manifest():
    return app.send_static_file('manifest.json')


@app.route('/robots.txt')
def robots_txt():
    return Response(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n", mimetype='text/plain')


SITEMAP_PAGES = (
    # (endpoint, priority, changefreq, source template)
    ('index', '1.0', 'weekly', 'site/home.html'),
    ('admissions', '0.9', 'weekly', 'site/admissions.html'),
    ('programs', '0.8', 'monthly', 'site/programs.html'),
    ('about', '0.8', 'monthly', 'site/about.html'),
    ('courses', '0.9', 'weekly', 'site/courses.html'),
    ('register', '0.8', 'monthly', 'site/register.html'),
    ('news', '0.7', 'weekly', 'site/news.html'),
    ('contact', '0.7', 'monthly', 'site/contact.html'),
    ('partnerships', '0.6', 'monthly', 'site/partnerships.html'),
)


@app.route('/sitemap.xml')
def sitemap_xml():
    def last_modified(template_name):
        # When the page's template last changed (the last deploy that touched it), not today.
        path = os.path.join(app.root_path, 'templates', template_name)
        return date.fromtimestamp(os.path.getmtime(path)).isoformat()

    # Every page is listed in all three languages with hreflang alternates.
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for endpoint, priority, changefreq, template_name in SITEMAP_PAGES:
        lastmod = last_modified(template_name)
        urls = {lang: SITE_URL + url_for(endpoint, lang=lang) for lang in LANGUAGES}
        for lang in LANGUAGES:
            lines.append('  <url>')
            lines.append(f'    <loc>{urls[lang]}</loc>')
            for alt in LANGUAGES:
                lines.append(f'    <xhtml:link rel="alternate" hreflang="{alt}" href="{urls[alt]}"/>')
            lines.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{urls["uz"]}"/>')
            lines.append(f'    <lastmod>{lastmod}</lastmod>')
            lines.append(f'    <changefreq>{changefreq}</changefreq>')
            lines.append(f'    <priority>{priority}</priority>')
            lines.append('  </url>')
    lines.append('</urlset>')
    return Response('\n'.join(lines), mimetype='application/xml')


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=int(os.environ.get('PORT', 8080)))
