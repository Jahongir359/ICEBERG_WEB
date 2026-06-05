from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response, abort
import requests
import sqlite3
import os
import re
import hashlib
import csv
import io
import json
from datetime import UTC, date, datetime
from functools import wraps
from werkzeug.utils import secure_filename


def load_local_env_file(env_path):
    if not os.path.exists(env_path):
        return

    with open(env_path, 'r', encoding='utf-8') as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue

            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key and key not in os.environ:
                os.environ[key] = value


load_local_env_file(os.path.join(os.path.dirname(__file__), '.env'))

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-only-secret-change-me')
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)
if os.environ.get('FLASK_ENV') == 'production':
    app.config['SESSION_COOKIE_SECURE'] = True

# Telegram Bot configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
REGISTRATION_LEADS_API_URL = os.environ.get('REGISTRATION_LEADS_API_URL', '').strip()
REGISTRATION_LEADS_API_TOKEN = os.environ.get('REGISTRATION_LEADS_API_TOKEN', '').strip()
REGISTRATION_LEADS_API_TIMEOUT = float(os.environ.get('REGISTRATION_LEADS_API_TIMEOUT', '8'))

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'iceberg-admin')
ADMIN_SECRET_CODE = os.environ.get('ADMIN_SECRET_CODE', ADMIN_PASSWORD).strip()
ADMIN_CONTACT_TRIGGER_NAME = os.environ.get('ADMIN_CONTACT_TRIGGER_NAME', 'admin').strip().lower() or 'admin'
ADMIN_CONTACT_SECRET_CODE = os.environ.get('ADMIN_CONTACT_SECRET_CODE', ADMIN_SECRET_CODE).strip()


def build_admin_login_slug():
    configured_slug = re.sub(r'[^a-zA-Z0-9_-]', '', os.environ.get('ADMIN_LOGIN_SLUG', '').strip())
    if configured_slug:
        return configured_slug

    return 'iceberg-portal'


ADMIN_LOGIN_SLUG = build_admin_login_slug()
DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(app.root_path, 'database.db'))
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
ALLOWED_NEWS_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
ALLOWED_NEWS_VIDEO_EXTENSIONS = {'.mp4', '.webm', '.mov', '.m4v'}

ASSET_CATALOG = [
    {
        'key': 'site_logo',
        'label': 'Asosiy logo (header/footer/admin)',
        'default': 'img/logo.png'
    },
    {
        'key': 'index_hero_bg',
        'label': 'Bosh sahifa hero background',
        'default': 'https://images.unsplash.com/photo-1523050854058-8df90110c9f1?q=80&w=2070&auto=format&fit=crop'
    },
    {
        'key': 'index_method_image',
        'label': 'Bosh sahifa ICEBERG method rasmi',
        'default': 'img/logo2.png'
    },
    {
        'key': 'about_hero_bg',
        'label': 'About sahifa hero background',
        'default': 'https://images.unsplash.com/photo-1524178232363-1fb2b075b655?q=80&w=2070&auto=format&fit=crop'
    },
    {
        'key': 'about_team_1',
        'label': 'About sahifa 1-jamoa rasmi',
        'default': 'img/azizbek.png'
    },
    {
        'key': 'about_team_2',
        'label': 'About sahifa 2-jamoa rasmi',
        'default': 'img/maqsudbek.png'
    },
    {
        'key': 'about_team_3',
        'label': 'About sahifa 3-jamoa rasmi',
        'default': 'img/islomjon.png'
    },
    {
        'key': 'contact_hero_bg',
        'label': 'Contact sahifa hero background',
        'default': 'https://images.unsplash.com/photo-1586769852836-bc069f19e1b6?q=80&w=1974&auto=format&fit=crop'
    },
    {
        'key': 'programs_hero_bg',
        'label': 'Programs sahifa hero background',
        'default': 'https://images.unsplash.com/photo-1542744095-291d1f67b221?q=80&w=2070&auto=format&fit=crop'
    },
    {
        'key': 'program_card_1',
        'label': 'Programs kartasi 1 rasmi',
        'default': 'https://images.unsplash.com/photo-1523240795612-9a054b0db644?q=80&w=2070&auto=format&fit=crop'
    },
    {
        'key': 'program_card_2',
        'label': 'Programs kartasi 2 rasmi',
        'default': 'https://images.unsplash.com/photo-1522202176988-66273c2fd55f?q=80&w=2071&auto=format&fit=crop'
    },
    {
        'key': 'program_card_3',
        'label': 'Programs kartasi 3 rasmi',
        'default': 'https://images.unsplash.com/photo-1528642474498-1af0c17fd8c3?q=80&w=2069&auto=format&fit=crop'
    },
    {
        'key': 'program_card_4',
        'label': 'Programs kartasi 4 rasmi',
        'default': 'https://images.unsplash.com/photo-1521587760476-6c12a4b040da?q=80&w=2070&auto=format&fit=crop'
    },
    {
        'key': 'program_card_5',
        'label': 'Programs kartasi 5 rasmi',
        'default': 'https://images.unsplash.com/photo-1571260899304-425eee4c7efc?q=80&w=2070&auto=format&fit=crop'
    },
    {
        'key': 'program_card_6',
        'label': 'Programs kartasi 6 rasmi',
        'default': 'https://images.unsplash.com/photo-1456324504439-367cee3b3c32?q=80&w=2070&auto=format&fit=crop'
    }
]
ASSET_DEFAULTS = {asset['key']: asset['default'] for asset in ASSET_CATALOG}
EDITABLE_SITE_FILES = [
    ('static/css/style.css', 'Global CSS styles')
]
EDITOR_BACKUP_DIR = os.path.join(app.root_path, 'backups', 'site_editor')
EDITOR_MAX_BACKUPS_PER_FILE = max(int(os.environ.get('EDITOR_MAX_BACKUPS_PER_FILE', '20')), 1)

CONTENT_FIELDS = [
    {'key': 'site_title', 'label': 'Sayt sarlavhasi (browser title)', 'group': 'Global', 'default': "ICEBERG O'QUV MARKAZI", 'field_type': 'text'},
    {'key': 'site_tagline', 'label': 'Footer qisqa matni', 'group': 'Global', 'default': "Zamonaviy kasblarni biz bilan o'rganing va kelajuingizni quring.", 'field_type': 'textarea'},
    {'key': 'custom_css', 'label': 'Custom CSS (ixtiyoriy)', 'group': 'Global', 'default': '', 'field_type': 'textarea'},

    {'key': 'nav_home', 'label': 'Menyu: Bosh sahifa', 'group': 'Header', 'default': 'Bosh sahifa', 'field_type': 'text'},
    {'key': 'nav_about', 'label': 'Menyu: Biz haqimizda', 'group': 'Header', 'default': 'Biz haqimizda', 'field_type': 'text'},
    {'key': 'nav_programs', 'label': 'Menyu: Dasturlar', 'group': 'Header', 'default': 'Dasturlar', 'field_type': 'text'},
    {'key': 'nav_news', 'label': 'Menyu: Yangiliklar', 'group': 'Header', 'default': 'Yangiliklar', 'field_type': 'text'},
    {'key': 'nav_questions', 'label': 'Menyu: Savollar', 'group': 'Header', 'default': 'Savollar', 'field_type': 'text'},
    {'key': 'nav_testimonials', 'label': 'Menyu: Muvaffaqiyat hikoyalari', 'group': 'Header', 'default': 'Muvaffaqiyat Hikoyalari', 'field_type': 'text'},
    {'key': 'nav_contact', 'label': 'Menyu: Aloqa (nav havolasi)', 'group': 'Header', 'default': 'Aloqa', 'field_type': 'text'},
    {'key': 'nav_contact_button', 'label': 'Header tugma matni', 'group': 'Header', 'default': "Biz bilan bog'lanish", 'field_type': 'text'},

    {'key': 'hero_main_title', 'label': 'Bosh sahifa hero title (typewriter)', 'group': 'Home', 'default': 'HAPPINESS IS IN SCIENCE', 'field_type': 'text'},
    {'key': 'hero_main_subtitle', 'label': 'Bosh sahifa hero subtitle', 'group': 'Home', 'default': "Fundamental bilimlar - har qanday akademik cho'qqini zabt etishning kalitidir.", 'field_type': 'textarea'},
    {'key': 'hero_main_cta', 'label': 'Bosh sahifa hero CTA', 'group': 'Home', 'default': 'Maslaxatlar uchun aloqa bo`limi', 'field_type': 'text'},

    {'key': 'about_page_title', 'label': 'About sahifa title', 'group': 'About', 'default': 'Bizning Hikoyamiz', 'field_type': 'text'},
    {'key': 'about_page_subtitle', 'label': 'About sahifa subtitle', 'group': 'About', 'default': 'ICEBERG farqini belgilaydigan falsafa, odamlar va ishtiyoq.', 'field_type': 'textarea'},
    {'key': 'about_mission_title', 'label': 'About missiya sarlavhasi', 'group': 'About', 'default': 'Bizning Missiyamiz', 'field_type': 'text'},
    {'key': 'about_mission_text', 'label': 'About missiya matni', 'group': 'About', 'default': "Bizning missiyamiz - har bir o'quvchiga o'z potentsialini to'liq ochib berishga yordam beradigan, innovatsion va qo'llab-quvvatlovchi ta'lim muhitini taqdim etish.", 'field_type': 'textarea'},

    {'key': 'contact_page_title', 'label': 'Contact sahifa title', 'group': 'Contact', 'default': 'Aloqaga Chiqing', 'field_type': 'text'},
    {'key': 'contact_page_subtitle', 'label': 'Contact sahifa subtitle', 'group': 'Contact', 'default': "Savollaringizga javob berish va muvaffaqiyat sari yo'lingizni boshlashga yordam berish uchun shu yerdamiz.", 'field_type': 'textarea'},
    {'key': 'contact_email', 'label': 'Aloqa email', 'group': 'Contact', 'default': 'iceberg.edu.center@gmail.com', 'field_type': 'text'},
    {'key': 'contact_phone', 'label': 'Aloqa telefon (+998...)', 'group': 'Contact', 'default': '+998939461699', 'field_type': 'text'},
    {'key': 'contact_phone_display', 'label': 'Aloqa telefon ko`rinishi', 'group': 'Contact', 'default': '(+998) 939461699', 'field_type': 'text'},
    {'key': 'contact_address', 'label': 'Aloqa manzil matni', 'group': 'Contact', 'default': 'Uyci, Namangan Viloyati, Uzbekistan', 'field_type': 'text'},
    {'key': 'contact_address_url', 'label': 'Aloqa manzil URL', 'group': 'Contact', 'default': 'https://www.google.com/maps/place/Uychi,+Uzbekistan/', 'field_type': 'text'},

    {'key': 'register_page_title', 'label': 'Register sahifa title', 'group': 'Register', 'default': "Dasturga Ro'yxatdan O'tish", 'field_type': 'text'},
    {'key': 'register_page_subtitle', 'label': 'Register sahifa subtitle', 'group': 'Register', 'default': "Akademik maqsadlaringizga erishish yo'lida birinchi qadamni tashlang.", 'field_type': 'textarea'},

    {'key': 'faq_page_title', 'label': 'FAQ sahifa title', 'group': 'FAQ', 'default': "Ko'p Beriladigan Savollar", 'field_type': 'text'},
    {'key': 'faq_page_subtitle', 'label': 'FAQ sahifa subtitle', 'group': 'FAQ', 'default': 'SAVOLLARINGIZGA JAVOBLAR', 'field_type': 'text'},

    {'key': 'footer_quick_links_title', 'label': 'Footer tezkor havolalar sarlavhasi', 'group': 'Footer', 'default': 'Tezkor Havolalar', 'field_type': 'text'},
    {'key': 'footer_contact_title', 'label': 'Footer aloqa sarlavhasi', 'group': 'Footer', 'default': 'Biz bilan aloqa', 'field_type': 'text'},
    {'key': 'footer_social_title', 'label': 'Footer ijtimoiy sarlavha', 'group': 'Footer', 'default': 'Ijtimoiy Tarmoqlar', 'field_type': 'text'},
    {'key': 'footer_telegram_url', 'label': 'Footer Telegram URL', 'group': 'Footer', 'default': 'https://t.me/Iceberg_study_center/1703', 'field_type': 'text'},
    {'key': 'footer_instagram_url', 'label': 'Footer Instagram URL', 'group': 'Footer', 'default': 'https://www.instagram.com/Iceberg_Study_Center', 'field_type': 'text'},
    {'key': 'footer_youtube_url', 'label': 'Footer YouTube URL', 'group': 'Footer', 'default': 'https://www.youtube.com/@ice_podcast', 'field_type': 'text'},
]

CONTENT_KEYS = {field['key'] for field in CONTENT_FIELDS}

PHONE_RE = re.compile(r'^\d{9}$')


def utc_now():
    return datetime.now(UTC).replace(tzinfo=None)


APP_STARTED_AT = utc_now()


def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    # WAL mode: readers never block writers; writers never block readers.
    # Critical for gunicorn — prevents the "data appears/disappears" race
    # condition where one worker writes while another reads stale state.
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA cache_size=-64000')  # 64 MB page cache
    conn.execute('PRAGMA temp_store=MEMORY')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def normalize_phone(raw_phone):
    return ''.join(ch for ch in (raw_phone or '') if ch.isdigit())


def format_uz_phone(phone_digits):
    if not phone_digits:
        return ''
    if phone_digits.startswith('998') and len(phone_digits) == 12:
        return f'+{phone_digits}'
    return f'+998{phone_digits}'


def is_valid_dob(dob_text):
    try:
        dob = datetime.strptime(dob_text, '%Y-%m-%d').date()
        return dob <= date.today()
    except ValueError:
        return False


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Avval admin tizimiga kiring.', 'error')
            return redirect(url_for('secret_admin_login', access_slug=ADMIN_LOGIN_SLUG))
        return view(*args, **kwargs)
    return wrapped_view


def process_admin_login(password):
    candidate = (password or '').strip()
    valid_passwords = {ADMIN_PASSWORD}
    if ADMIN_SECRET_CODE:
        valid_passwords.add(ADMIN_SECRET_CODE)
    if ADMIN_CONTACT_SECRET_CODE:
        valid_passwords.add(ADMIN_CONTACT_SECRET_CODE)

    if candidate in valid_passwords:
        session['logged_in'] = True
        flash('Muvaffaqiyatli kirdingiz!', 'success')
        return True
    return False


def is_allowed_image(filename):
    _, ext = os.path.splitext(filename or '')
    return ext.lower() in ALLOWED_IMAGE_EXTENSIONS


def to_public_asset_url(path_or_url):
    if not path_or_url:
        return ''
    if path_or_url.startswith('http://') or path_or_url.startswith('https://'):
        return path_or_url
    return url_for('static', filename=path_or_url)


def get_asset_url(asset_key, fallback=''):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT file_path FROM site_assets WHERE asset_key = ?', (asset_key,))
        row = cursor.fetchone()
    if row and row['file_path']:
        return to_public_asset_url(row['file_path'])
    return to_public_asset_url(fallback or ASSET_DEFAULTS.get(asset_key, ''))


def save_asset_file(file_storage, asset_key):
    safe_name = secure_filename(file_storage.filename)
    _, ext = os.path.splitext(safe_name)
    timestamp = utc_now().strftime('%Y%m%d%H%M%S')
    final_name = f'{asset_key}_{timestamp}{ext.lower()}'
    target_dir = os.path.join(app.root_path, 'static', 'uploads', 'assets')
    os.makedirs(target_dir, exist_ok=True)
    final_path = os.path.join(target_dir, final_name)
    file_storage.save(final_path)
    return f'uploads/assets/{final_name}'


def detect_news_media_type(filename):
    _, ext = os.path.splitext(filename or '')
    lowered = ext.lower()
    if lowered in ALLOWED_NEWS_IMAGE_EXTENSIONS:
        return 'image'
    if lowered in ALLOWED_NEWS_VIDEO_EXTENSIONS:
        return 'video'
    return ''


def save_news_media_file(file_storage, post_id):
    safe_name = secure_filename(file_storage.filename)
    _, ext = os.path.splitext(safe_name)
    media_type = detect_news_media_type(file_storage.filename)
    timestamp = utc_now().strftime('%Y%m%d%H%M%S%f')
    final_name = f'news_{post_id}_{timestamp}{ext.lower()}'
    target_dir = os.path.join(app.root_path, 'static', 'uploads', 'news')
    os.makedirs(target_dir, exist_ok=True)
    final_path = os.path.join(target_dir, final_name)
    file_storage.save(final_path)
    return f'uploads/news/{final_name}', media_type


def remove_static_file(relative_path):
    if not relative_path:
        return
    safe_relative = relative_path.replace('\\', '/').lstrip('/')
    absolute_path = os.path.abspath(os.path.join(app.root_path, 'static', safe_relative))
    static_root = os.path.abspath(os.path.join(app.root_path, 'static'))
    if not absolute_path.startswith(static_root):
        return
    if os.path.exists(absolute_path):
        os.remove(absolute_path)


def fetch_news_posts(include_unpublished=False):
    query = '''
        SELECT *
        FROM news_posts
    '''
    params = []
    if not include_unpublished:
        query += ' WHERE is_published = 1 '
    query += ' ORDER BY COALESCE(event_date, created_at) DESC, id DESC '

    with get_db_connection() as conn:
        conn.execute('BEGIN')
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        posts = [dict(row) for row in cursor.fetchall()]

        cursor.execute('SELECT * FROM news_media ORDER BY sort_order ASC, id ASC')
        all_media = [dict(row) for row in cursor.fetchall()]

    media_by_post = {}
    for media in all_media:
        media_by_post.setdefault(media['post_id'], []).append(media)

    for post in posts:
        post['media_items'] = media_by_post.get(post['id'], [])

    return posts


def get_site_content_map():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT content_key, content_value FROM site_content')
        rows = cursor.fetchall()
    return {row['content_key']: row['content_value'] for row in rows}


def fetch_faq_items():
    """Fetch all FAQ items ordered by sort_order"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM faq_items ORDER BY sort_order ASC, id ASC')
        items = [dict(row) for row in cursor.fetchall()]
    return items


def upsert_site_content(content_key, content_value):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO site_content (content_key, content_value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(content_key)
            DO UPDATE SET content_value = excluded.content_value, updated_at = excluded.updated_at
            ''',
            (content_key, content_value, utc_now().isoformat())
        )
        conn.commit()


def delete_site_content(content_key):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM site_content WHERE content_key = ?', (content_key,))
        conn.commit()


def parse_selected_ids(param_name='selected_ids'):
    selected_ids = []

    if request.is_json:
        payload = request.get_json(silent=True) or {}
        raw_ids = payload.get(param_name) or payload.get('ids') or []
        if isinstance(raw_ids, list):
            selected_ids.extend(raw_ids)
        elif isinstance(raw_ids, str):
            selected_ids.extend(raw_ids.split(','))

    selected_ids.extend(request.form.getlist(param_name))

    fallback_csv = request.form.get('ids', '').strip()
    if fallback_csv:
        selected_ids.extend(fallback_csv.split(','))

    normalized_ids = []
    for raw_value in selected_ids:
        try:
            row_id = int(str(raw_value).strip())
            if row_id > 0:
                normalized_ids.append(row_id)
        except (TypeError, ValueError):
            continue

    return sorted(set(normalized_ids))


def build_csv_response(filename, headers, rows):
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)

    csv_content = csv_buffer.getvalue()
    return Response(
        csv_content,
        mimetype='text/csv; charset=utf-8',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )


def log_admin_action(action, target='', details=''):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO admin_activity_log (action, target, details, created_at)
                VALUES (?, ?, ?, ?)
                ''',
                (action, target, details, utc_now().isoformat())
            )
            conn.commit()
    except Exception as exc:
        app.logger.warning(f'Unable to write admin activity log: {exc}')


def get_recent_admin_activity(limit=20):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT action, target, details, created_at FROM admin_activity_log ORDER BY id DESC LIMIT ?',
            (limit,)
        )
        return cursor.fetchall()


def get_system_health_snapshot():
    db_exists = os.path.exists(DATABASE_PATH)
    db_size_bytes = os.path.getsize(DATABASE_PATH) if db_exists else 0
    uptime = utc_now() - APP_STARTED_AT
    uptime_seconds = int(max(uptime.total_seconds(), 0))
    uptime_hours = uptime_seconds // 3600
    uptime_minutes = (uptime_seconds % 3600) // 60

    return {
        'db_exists': db_exists,
        'db_size_bytes': db_size_bytes,
        'db_size_mb': round(db_size_bytes / (1024 * 1024), 3),
        'uptime_human': f'{uptime_hours}h {uptime_minutes}m',
        'telegram_configured': bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        'secret_code_configured': bool(ADMIN_SECRET_CODE),
        'started_at': APP_STARTED_AT.strftime('%Y-%m-%d %H:%M:%S UTC')
    }


def build_editable_site_file_list():
    files = list(EDITABLE_SITE_FILES)
    templates_dir = os.path.join(app.root_path, 'templates')
    if os.path.isdir(templates_dir):
        for root, _, file_names in os.walk(templates_dir):
            for file_name in file_names:
                if not file_name.endswith('.html'):
                    continue
                absolute_path = os.path.join(root, file_name)
                relative_path = os.path.relpath(absolute_path, app.root_path).replace('\\', '/')
                files.append((relative_path, f'Template: {file_name}'))

    unique_by_path = {}
    for relative_path, label in files:
        normalized = relative_path.strip().replace('\\', '/')
        if not normalized:
            continue
        unique_by_path[normalized] = {
            'path': normalized,
            'label': label
        }

    return [unique_by_path[path] for path in sorted(unique_by_path)]


def get_editable_site_file_path(relative_path):
    safe_relative = (relative_path or '').strip().replace('\\', '/')
    allowed_paths = {item['path'] for item in build_editable_site_file_list()}
    if safe_relative not in allowed_paths:
        return ''

    absolute_path = os.path.abspath(os.path.join(app.root_path, safe_relative))
    root_path = os.path.abspath(app.root_path)
    if not absolute_path.startswith(root_path):
        return ''
    return absolute_path


def build_editor_backup_prefix(relative_path):
    normalized = (relative_path or '').replace('\\', '/').strip('/')
    return re.sub(r'[^a-zA-Z0-9._-]', '_', normalized)


def parse_backup_timestamp_from_name(backup_name):
    if '__' not in backup_name:
        return backup_name
    raw_part = backup_name.split('__', 1)[1].replace('.bak', '')
    try:
        dt = datetime.strptime(raw_part, '%Y%m%d%H%M%S%f')
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except ValueError:
        return raw_part


def create_editor_backup(relative_path, file_content):
    prefix = build_editor_backup_prefix(relative_path)
    if not prefix:
        return ''

    os.makedirs(EDITOR_BACKUP_DIR, exist_ok=True)
    stamp = utc_now().strftime('%Y%m%d%H%M%S%f')
    backup_name = f'{prefix}__{stamp}.bak'
    backup_path = os.path.join(EDITOR_BACKUP_DIR, backup_name)
    with open(backup_path, 'w', encoding='utf-8') as backup_file:
        backup_file.write(file_content)

    matching = sorted(
        [
            name for name in os.listdir(EDITOR_BACKUP_DIR)
            if name.startswith(f'{prefix}__') and name.endswith('.bak')
        ],
        reverse=True
    )
    for old_name in matching[EDITOR_MAX_BACKUPS_PER_FILE:]:
        old_path = os.path.join(EDITOR_BACKUP_DIR, old_name)
        if os.path.exists(old_path):
            os.remove(old_path)

    return backup_name


def list_editor_backups(relative_path, limit=30):
    prefix = build_editor_backup_prefix(relative_path)
    if not prefix or not os.path.isdir(EDITOR_BACKUP_DIR):
        return []

    names = sorted(
        [
            name for name in os.listdir(EDITOR_BACKUP_DIR)
            if name.startswith(f'{prefix}__') and name.endswith('.bak')
        ],
        reverse=True
    )[:limit]

    return [
        {
            'name': name,
            'created_at': parse_backup_timestamp_from_name(name)
        }
        for name in names
    ]


def get_editor_backup_absolute_path(relative_path, backup_name):
    safe_name = (backup_name or '').strip()
    prefix = build_editor_backup_prefix(relative_path)
    if not prefix:
        return ''

    if '/' in safe_name or '\\' in safe_name:
        return ''
    if not safe_name.startswith(f'{prefix}__') or not safe_name.endswith('.bak'):
        return ''

    backup_path = os.path.abspath(os.path.join(EDITOR_BACKUP_DIR, safe_name))
    backup_root = os.path.abspath(EDITOR_BACKUP_DIR)
    if not backup_path.startswith(backup_root):
        return ''
    if not os.path.exists(backup_path):
        return ''
    return backup_path


@app.context_processor
def inject_asset_helper():
    site_content = get_site_content_map()

    def content_value(content_key, fallback=''):
        value = site_content.get(content_key)
        return value if value not in (None, '') else fallback

    return {
        'asset_url': get_asset_url,
        'content': content_value
    }

def send_telegram_notification(message_text):
    """Sends a message to the configured Telegram chat."""
    if not TELEGRAM_CHAT_ID or not TELEGRAM_BOT_TOKEN:
        app.logger.warning("Telegram notifications are not configured. Missing Bot Token or Chat ID.")
        return

    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    try:
        response = requests.post(
            api_url,
            json={'chat_id': TELEGRAM_CHAT_ID, 'text': message_text},
            timeout=10
        )
        response.raise_for_status()
        app.logger.info("Telegram notification sent successfully.")
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Failed to send Telegram notification: {e}")


def send_registration_lead_to_management(payload):
    if not REGISTRATION_LEADS_API_URL:
        app.logger.info('Registration lead forwarding is not configured.')
        return False

    headers = {'Content-Type': 'application/json'}
    if REGISTRATION_LEADS_API_TOKEN:
        headers['Authorization'] = f'Bearer {REGISTRATION_LEADS_API_TOKEN}'

    try:
        response = requests.post(
            REGISTRATION_LEADS_API_URL,
            json=payload,
            headers=headers,
            timeout=REGISTRATION_LEADS_API_TIMEOUT
        )
        response.raise_for_status()
        app.logger.info('Registration lead forwarded to management system.')
        return True
    except requests.exceptions.RequestException as exc:
        app.logger.error(f'Failed to forward registration lead: {exc}')
        return False

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                student_phone TEXT NOT NULL,
                dob TEXT NOT NULL,
                course TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                message TEXT NOT NULL,
                email TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS site_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_key TEXT NOT NULL UNIQUE,
                file_path TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS site_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_key TEXT NOT NULL UNIQUE,
                content_value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                target TEXT,
                details TEXT,
                created_at TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                excerpt TEXT,
                body TEXT NOT NULL,
                post_type TEXT NOT NULL DEFAULT 'news',
                event_date TEXT,
                is_published INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                media_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                caption TEXT,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(post_id) REFERENCES news_posts(id)
            )
        ''')
        cursor.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS faq_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Insert default FAQ items if table is empty
        cursor.execute('SELECT COUNT(*) FROM faq_items')
        if cursor.fetchone()[0] == 0:
            now = utc_now().isoformat()
            default_faqs = [
                ('Qaysi fanlardan repetitorlik xizmatlarini taklif qilasiz?', 'Biz keng ko\'lamli fanlardan, jumladan, Matematika, Fan, Ingliz tili va standartlashtirilgan testlarga tayyorgarlik (SAT, ACT) bo\'yicha repetitorlik xizmatlarini taklif etamiz.'),
                ('Sizning ish vaqtingiz qanday?', 'Markazimiz ish kunlari soat 9:00 dan 20:00 gacha, dam olish kunlari esa 10:00 dan 18:00 gacha ishlaydi.'),
                ('O\'quvchilarni repetitorlar bilan qanday bog\'laysiz?', 'Biz o\'quvchilarni ularning akademik ehtiyojlari, o\'rganish uslubi va shaxsiyatiga qarab repetitorlar bilan bog\'laymiz, bu esa eng yaxshi moslikni ta\'minlaydi.'),
                ('Darslar qayerda o\'tkaziladi?', 'Darslar bizning zamonaviy o\'quv markazimizda yoki o\'quvchining xohishiga ko\'ra onlayn tarzda o\'tkazilishi mumkin.'),
                ('Narxlar qanday?', 'Narxlar dastur turiga va darslar soniga qarab o\'zgaradi. Batafsil ma\'lumot olish va bepul maslahat uchun biz bilan bog\'laning.'),
            ]
            for index, (question, answer) in enumerate(default_faqs, 1):
                cursor.execute(
                    '''INSERT INTO faq_items (question, answer, sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?)''',
                    (question, answer, index, now, now)
                )
        
        conn.commit()

init_db()


@app.after_request
def add_no_cache_headers(response):
    if 'text/html' in (response.content_type or ''):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        # Bypass edge/CDN caches (Cloudflare, DigitalOcean, Vercel, etc.)
        response.headers['CDN-Cache-Control'] = 'no-store'
        response.headers['Cloudflare-CDN-Cache-Control'] = 'no-store'
        response.headers['Surrogate-Control'] = 'no-store'
        response.headers['Vary'] = '*'
        # Diagnostic: identify which instance/container served the response.
        # If two refreshes show different X-Served-By values, multiple
        # instances are running and each has its own SQLite file.
        response.headers['X-Served-By'] = os.environ.get('HOSTNAME', 'unknown')
        response.headers['X-App-Started'] = APP_STARTED_AT.isoformat()
    return response


@app.route('/favicon.ico')
def favicon():
    response = app.send_static_file('favicon.ico')
    response.headers['Cache-Control'] = 'public, max-age=604800'
    return response


@app.route('/manifest.json')
def manifest():
    response = app.send_static_file('manifest.json')
    response.headers['Cache-Control'] = 'public, max-age=604800'
    return response


@app.route('/robots.txt')
def robots_txt():
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        "Disallow: /admin\n"
        "Disallow: /admin/\n"
        "Disallow: /portal\n"
        "Disallow: /portal/\n"
        "Disallow: /students\n"
        "Disallow: /contacts_list\n"
        "\n"
        "Sitemap: https://iceberglc.com/sitemap.xml\n"
    )
    return Response(content, mimetype='text/plain')


@app.route('/sitemap.xml')
def sitemap_xml():
    from datetime import date as _date
    today = _date.today().isoformat()
    static_pages = [
        ('https://iceberglc.com/', '1.0', 'daily'),
        ('https://iceberglc.com/about', '0.8', 'monthly'),
        ('https://iceberglc.com/our_programs', '0.9', 'weekly'),
        ('https://iceberglc.com/news', '0.9', 'daily'),
        ('https://iceberglc.com/questions', '0.7', 'monthly'),
        ('https://iceberglc.com/contact', '0.8', 'monthly'),
        ('https://iceberglc.com/register', '0.8', 'monthly'),
    ]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, priority, changefreq in static_pages:
        lines.append('  <url>')
        lines.append(f'    <loc>{loc}</loc>')
        lines.append(f'    <lastmod>{today}</lastmod>')
        lines.append(f'    <changefreq>{changefreq}</changefreq>')
        lines.append(f'    <priority>{priority}</priority>')
        lines.append('  </url>')
    lines.append('</urlset>')
    return Response('\n'.join(lines), mimetype='application/xml')


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/our_programs')
def our_programs():
    return render_template('our_programs.html')


@app.route('/news')
def news():
    posts = fetch_news_posts(include_unpublished=False)
    return render_template('news.html', posts=posts)


@app.route('/questions')
def questions():
    faqs = fetch_faq_items()
    return render_template('questions.html', faqs=faqs)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    return redirect(url_for('secret_admin_login', access_slug=ADMIN_LOGIN_SLUG))


@app.route('/admin', methods=['GET'])
def admin_root():
    return redirect(url_for('secret_admin_login', access_slug=ADMIN_LOGIN_SLUG))


@app.route('/portal', methods=['GET'])
def portal_root():
    return redirect(url_for('secret_admin_login', access_slug=ADMIN_LOGIN_SLUG))


@app.route('/portal/<access_slug>', methods=['GET', 'POST'])
def secret_admin_login(access_slug):
    if access_slug != ADMIN_LOGIN_SLUG:
        return abort(404)

    error = None
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        if process_admin_login(password):
            log_admin_action('admin_login', 'session', 'Admin successfully logged in')
            return redirect(url_for('admin_dashboard'))
        else:
            error = 'Parol noto\'g\'ri. Iltimos, qayta urinib ko\'ring.'
    return render_template(
        'admin_login.html',
        error=error,
        admin_login_url=url_for('secret_admin_login', access_slug=ADMIN_LOGIN_SLUG)
    )


@app.route('/admin/secret-access', methods=['POST'])
def admin_secret_access():
    entered_code = request.form.get('secret_code', '').strip()

    if not ADMIN_SECRET_CODE:
        flash('Maxfiy kod sozlanmagan. ADMIN_SECRET_CODE ni .env faylida belgilang.', 'error')
        return redirect(url_for('contact'))

    if entered_code != ADMIN_SECRET_CODE:
        flash('Maxfiy kod noto\'g\'ri.', 'error')
        return redirect(url_for('contact'))

    flash('Maxfiy kod qabul qilindi. Maxfiy admin login sahifasi ochildi.', 'success')
    return redirect(url_for('secret_admin_login', access_slug=ADMIN_LOGIN_SLUG))


@app.route('/admin/logout')
def logout():
    if session.get('logged_in'):
        log_admin_action('admin_logout', 'session', 'Admin logged out')
    session.pop('logged_in', None)
    flash('Siz tizimdan chiqdingiz.', 'info')
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Get stats
        cursor.execute('SELECT COUNT(*) FROM students')
        total_students = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM contacts')
        total_contacts = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM news_posts')
        total_news = cursor.fetchone()[0]
        
        # Get recent students
        cursor.execute('SELECT * FROM students ORDER BY id DESC LIMIT 5')
        recent_students = cursor.fetchall()

        # Get recent contacts
        cursor.execute('SELECT * FROM contacts ORDER BY id DESC LIMIT 5')
        recent_contacts = cursor.fetchall()

    recent_activity = get_recent_admin_activity(limit=6)
    health = get_system_health_snapshot()

    stats = {
        'total_students': total_students,
        'total_contacts': total_contacts,
        'total_news': total_news
    }
    return render_template(
        'admin_dashboard.html',
        stats=stats,
        recent_students=recent_students,
        recent_contacts=recent_contacts,
        recent_activity=recent_activity,
        health=health,
        editable_file_count=len(build_editable_site_file_list())
    )


@app.route('/admin/editor', methods=['GET', 'POST'])
@login_required
def admin_editor():
    editable_files = build_editable_site_file_list()
    selected_file = request.args.get('file', '').strip()

    if request.method == 'POST':
        file_path = request.form.get('file_path', '').strip()
        editor_content = request.form.get('editor_content', '')
        absolute_path = get_editable_site_file_path(file_path)

        if not absolute_path:
            flash('Ruxsat etilmagan fayl tanlandi.', 'error')
            return redirect(url_for('admin_editor'))

        previous_content = ''
        if os.path.exists(absolute_path):
            with open(absolute_path, 'r', encoding='utf-8') as current_file:
                previous_content = current_file.read()
            create_editor_backup(file_path, previous_content)

        with open(absolute_path, 'w', encoding='utf-8') as target_file:
            target_file.write(editor_content)

        log_admin_action('site_file_update', file_path, f'Updated via admin editor ({len(editor_content)} chars)')
        flash(f'Fayl saqlandi: {file_path}', 'success')
        return redirect(url_for('admin_editor', file=file_path))

    if not selected_file and editable_files:
        selected_file = editable_files[0]['path']

    selected_absolute_path = get_editable_site_file_path(selected_file)
    selected_content = ''
    if selected_absolute_path:
        with open(selected_absolute_path, 'r', encoding='utf-8') as source_file:
            selected_content = source_file.read()

    backups = list_editor_backups(selected_file) if selected_file else []

    return render_template(
        'admin_editor.html',
        editable_files=editable_files,
        selected_file=selected_file,
        selected_content=selected_content,
        backups=backups
    )


@app.route('/admin/editor/rollback', methods=['POST'])
@login_required
def admin_editor_rollback():
    file_path = request.form.get('file_path', '').strip()
    backup_name = request.form.get('backup_name', '').strip()

    absolute_path = get_editable_site_file_path(file_path)
    if not absolute_path:
        flash('Ruxsat etilmagan fayl tanlandi.', 'error')
        return redirect(url_for('admin_editor'))

    backup_path = get_editor_backup_absolute_path(file_path, backup_name)
    if not backup_path:
        flash('Backup fayl topilmadi yoki yaroqsiz.', 'error')
        return redirect(url_for('admin_editor', file=file_path))

    if os.path.exists(absolute_path):
        with open(absolute_path, 'r', encoding='utf-8') as current_file:
            create_editor_backup(file_path, current_file.read())

    with open(backup_path, 'r', encoding='utf-8') as backup_file:
        restored_content = backup_file.read()

    with open(absolute_path, 'w', encoding='utf-8') as target_file:
        target_file.write(restored_content)

    log_admin_action('site_file_rollback', file_path, f'Rolled back from backup: {backup_name}')
    flash(f'Rollback muvaffaqiyatli bajarildi: {backup_name}', 'success')
    return redirect(url_for('admin_editor', file=file_path))


@app.route('/admin/assets', methods=['GET', 'POST'])
@login_required
def admin_assets():
    if request.method == 'POST':
        asset_key = request.form.get('asset_key', '').strip()
        custom_asset_key = request.form.get('custom_asset_key', '').strip().lower()
        image_file = request.files.get('asset_file')

        if custom_asset_key:
            if not re.match(r'^[a-z0-9_\-]{3,80}$', custom_asset_key):
                flash('Custom asset kaliti faqat a-z, 0-9, _ va - belgilaridan iborat bo`lsin (3-80 belgi).', 'error')
                return redirect(url_for('admin_assets'))
            asset_key = custom_asset_key

        if not custom_asset_key and asset_key not in ASSET_DEFAULTS:
            flash('Noto\'g\'ri asset tanlandi.', 'error')
            return redirect(url_for('admin_assets'))

        if not image_file or not image_file.filename:
            flash('Rasm faylini tanlang.', 'error')
            return redirect(url_for('admin_assets'))

        if not is_allowed_image(image_file.filename):
            flash('Faqat JPG, JPEG, PNG, WEBP yoki GIF formatlar ruxsat etiladi.', 'error')
            return redirect(url_for('admin_assets'))

        file_path = save_asset_file(image_file, asset_key)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO site_assets (asset_key, file_path, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(asset_key)
                DO UPDATE SET file_path = excluded.file_path, updated_at = excluded.updated_at
                ''',
                (asset_key, file_path, utc_now().isoformat())
            )
            conn.commit()
        log_admin_action('asset_update', asset_key, f'Asset updated with file {file_path}')

        flash('Rasm muvaffaqiyatli yangilandi.', 'success')
        return redirect(url_for('admin_assets'))

    assets = []
    for asset in ASSET_CATALOG:
        assets.append(
            {
                'key': asset['key'],
                'label': asset['label'],
                'default_url': to_public_asset_url(asset['default']),
                'current_url': get_asset_url(asset['key'], asset['default'])
            }
        )

    custom_assets = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT asset_key, file_path, updated_at
            FROM site_assets
            WHERE asset_key NOT IN ({})
            ORDER BY asset_key ASC
            '''.format(','.join('?' for _ in ASSET_DEFAULTS)),
            tuple(ASSET_DEFAULTS.keys())
        )
        rows = cursor.fetchall()
        for row in rows:
            custom_assets.append(
                {
                    'key': row['asset_key'],
                    'label': row['asset_key'],
                    'current_url': to_public_asset_url(row['file_path']),
                    'updated_at': row['updated_at']
                }
            )

    return render_template('admin_assets.html', assets=assets, custom_assets=custom_assets)


@app.route('/admin/content', methods=['GET', 'POST'])
@login_required
def admin_content():
    if request.method == 'POST':
        delete_key = request.form.get('delete_key', '').strip()
        if delete_key:
            if delete_key in CONTENT_KEYS:
                flash('Standart maydonni o`chirish mumkin emas.', 'error')
            else:
                delete_site_content(delete_key)
                log_admin_action('content_delete', delete_key, 'Custom content key deleted')
                flash('Custom maydon o`chirildi.', 'success')
            return redirect(url_for('admin_content'))

        for field in CONTENT_FIELDS:
            upsert_site_content(field['key'], request.form.get(field['key'], ''))

        custom_key = request.form.get('custom_key', '').strip()
        custom_value = request.form.get('custom_value', '')
        if custom_key:
            upsert_site_content(custom_key, custom_value)
            log_admin_action('content_custom_save', custom_key, 'Custom content key saved/updated')
            flash(f'Custom maydon saqlandi: {custom_key}', 'success')
        else:
            log_admin_action('content_bulk_save', 'site_content', 'Standard content fields updated')
            flash('Sayt kontenti muvaffaqiyatli saqlandi.', 'success')

        return redirect(url_for('admin_content'))

    current_content = get_site_content_map()
    grouped_fields = {}
    for field in CONTENT_FIELDS:
        group_name = field['group']
        grouped_fields.setdefault(group_name, [])
        grouped_fields[group_name].append(
            {
                'key': field['key'],
                'label': field['label'],
                'field_type': field['field_type'],
                'value': current_content.get(field['key'], field['default'])
            }
        )

    custom_items = []
    for key, value in sorted(current_content.items()):
        if key not in CONTENT_KEYS:
            custom_items.append({'key': key, 'value': value})

    return render_template('admin_content.html', grouped_fields=grouped_fields, custom_items=custom_items)


@app.route('/admin/news', methods=['GET', 'POST'])
@login_required
def admin_news():
    if request.method == 'POST':
        action = request.form.get('action', '').strip()

        if action == 'create_post':
            title = request.form.get('title', '').strip()
            excerpt = request.form.get('excerpt', '').strip()
            body = request.form.get('body', '').strip()
            post_type = request.form.get('post_type', 'news').strip()
            event_date = request.form.get('event_date', '').strip() or None
            is_published = 1 if request.form.get('is_published') == 'on' else 0

            if not title or len(title) < 3:
                flash('Sarlavha kamida 3 belgidan iborat bo`lsin.', 'error')
                return redirect(url_for('admin_news'))
            if not body or len(body) < 10:
                flash('Asosiy matn kamida 10 belgidan iborat bo`lsin.', 'error')
                return redirect(url_for('admin_news'))
            if post_type not in {'news', 'event'}:
                post_type = 'news'

            now = utc_now().isoformat()
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    INSERT INTO news_posts (title, excerpt, body, post_type, event_date, is_published, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (title, excerpt, body, post_type, event_date, is_published, now, now)
                )
                new_post_id = cursor.lastrowid

                media_files = request.files.getlist('media_files')
                uploaded_count = 0
                current_sort = 0
                for file_storage in media_files:
                    if not file_storage or not file_storage.filename:
                        continue
                    if not detect_news_media_type(file_storage.filename):
                        continue
                    file_path, media_type = save_news_media_file(file_storage, new_post_id)
                    current_sort += 1
                    cursor.execute(
                        'INSERT INTO news_media (post_id, media_type, file_path, caption, sort_order, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                        (new_post_id, media_type, file_path, '', current_sort, utc_now().isoformat())
                    )
                    uploaded_count += 1

                conn.commit()

            msg = 'Yangilik/Event posti yaratildi.'
            if uploaded_count:
                msg += f' {uploaded_count} ta media yuklandi.'
            log_admin_action('news_create', f'news:{new_post_id}', f'Created post: {title}')
            flash(msg, 'success')
            return redirect(url_for('admin_news'))

        if action == 'update_post':
            post_id = request.form.get('post_id', '').strip()
            title = request.form.get('title', '').strip()
            excerpt = request.form.get('excerpt', '').strip()
            body = request.form.get('body', '').strip()
            post_type = request.form.get('post_type', 'news').strip()
            event_date = request.form.get('event_date', '').strip() or None
            is_published = 1 if request.form.get('is_published') == 'on' else 0

            try:
                post_id_int = int(post_id)
            except (TypeError, ValueError):
                flash('Post ID noto`g`ri.', 'error')
                return redirect(url_for('admin_news'))

            if not title or len(title) < 3:
                flash('Sarlavha kamida 3 belgidan iborat bo`lsin.', 'error')
                return redirect(url_for('admin_news'))
            if not body or len(body) < 10:
                flash('Asosiy matn kamida 10 belgidan iborat bo`lsin.', 'error')
                return redirect(url_for('admin_news'))
            if post_type not in {'news', 'event'}:
                post_type = 'news'

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    UPDATE news_posts
                    SET title = ?, excerpt = ?, body = ?, post_type = ?, event_date = ?, is_published = ?, updated_at = ?
                    WHERE id = ?
                    ''',
                    (title, excerpt, body, post_type, event_date, is_published, utc_now().isoformat(), post_id_int)
                )
                conn.commit()

            log_admin_action('news_update', f'news:{post_id_int}', f'Updated post: {title}')
            flash('Post yangilandi.', 'success')
            return redirect(url_for('admin_news'))

        if action == 'delete_post':
            post_id = request.form.get('post_id', '').strip()
            try:
                post_id_int = int(post_id)
            except (TypeError, ValueError):
                flash('Post ID noto`g`ri.', 'error')
                return redirect(url_for('admin_news'))

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT file_path FROM news_media WHERE post_id = ?', (post_id_int,))
                media_rows = cursor.fetchall()
                for row in media_rows:
                    remove_static_file(row['file_path'])

                cursor.execute('DELETE FROM news_media WHERE post_id = ?', (post_id_int,))
                cursor.execute('DELETE FROM news_posts WHERE id = ?', (post_id_int,))
                conn.commit()

            log_admin_action('news_delete', f'news:{post_id_int}', 'Deleted post and related media')
            flash('Post o`chirildi.', 'success')
            return redirect(url_for('admin_news'))

        if action == 'upload_media':
            post_id = request.form.get('post_id', '').strip()
            media_files = request.files.getlist('media_files')
            try:
                post_id_int = int(post_id)
            except (TypeError, ValueError):
                flash('Post ID noto`g`ri.', 'error')
                return redirect(url_for('admin_news'))

            if not media_files:
                flash('Kamida bitta fayl tanlang.', 'error')
                return redirect(url_for('admin_news'))

            uploaded_count = 0
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM news_posts WHERE id = ?', (post_id_int,))
                if cursor.fetchone()[0] == 0:
                    flash('Post topilmadi.', 'error')
                    return redirect(url_for('admin_news'))

                cursor.execute('SELECT COALESCE(MAX(sort_order), 0) FROM news_media WHERE post_id = ?', (post_id_int,))
                current_sort = cursor.fetchone()[0] or 0

                for file_storage in media_files:
                    if not file_storage or not file_storage.filename:
                        continue
                    media_type = detect_news_media_type(file_storage.filename)
                    if not media_type:
                        continue

                    file_path, media_type = save_news_media_file(file_storage, post_id_int)
                    current_sort += 1
                    cursor.execute(
                        '''
                        INSERT INTO news_media (post_id, media_type, file_path, caption, sort_order, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ''',
                        (post_id_int, media_type, file_path, '', current_sort, utc_now().isoformat())
                    )
                    uploaded_count += 1

                conn.commit()

            if uploaded_count == 0:
                flash('Yaroqli media topilmadi. JPG/PNG/WEBP/GIF yoki MP4/WEBM/MOV yuklang.', 'error')
            else:
                log_admin_action('news_media_upload', f'news:{post_id_int}', f'Uploaded media count: {uploaded_count}')
                flash(f'{uploaded_count} ta media yuklandi.', 'success')
            return redirect(url_for('admin_news'))

        if action == 'delete_media':
            media_id = request.form.get('media_id', '').strip()
            try:
                media_id_int = int(media_id)
            except (TypeError, ValueError):
                flash('Media ID noto`g`ri.', 'error')
                return redirect(url_for('admin_news'))

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT post_id, file_path FROM news_media WHERE id = ?', (media_id_int,))
                row = cursor.fetchone()
                if not row:
                    flash('Media topilmadi.', 'error')
                    return redirect(url_for('admin_news'))

                remove_static_file(row['file_path'])
                cursor.execute('DELETE FROM news_media WHERE id = ?', (media_id_int,))
                conn.commit()

            log_admin_action('news_media_delete', f'news:{row["post_id"]}', f'Deleted media id: {media_id_int}')
            flash('Media o`chirildi.', 'success')
            return redirect(url_for('admin_news'))

        flash('Noma`lum amal.', 'error')
        return redirect(url_for('admin_news'))

    posts = fetch_news_posts(include_unpublished=True)
    return render_template('admin_news.html', posts=posts)

@app.route('/admin/faq', methods=['GET', 'POST'])
@login_required
def admin_faq():
    if request.method == 'POST':
        action = request.form.get('action', '').strip()

        if action == 'create_faq':
            question = request.form.get('question', '').strip()
            answer = request.form.get('answer', '').strip()

            if not question or len(question) < 5:
                flash('Savol kamida 5 belgidan iborat bo`lsin.', 'error')
                return redirect(url_for('admin_faq'))
            if not answer or len(answer) < 10:
                flash('Javob kamida 10 belgidan iborat bo`lsin.', 'error')
                return redirect(url_for('admin_faq'))

            now = utc_now().isoformat()
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COALESCE(MAX(sort_order), 0) FROM faq_items')
                next_sort = (cursor.fetchone()[0] or 0) + 1
                
                cursor.execute(
                    '''
                    INSERT INTO faq_items (question, answer, sort_order, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    (question, answer, next_sort, now, now)
                )
                conn.commit()

            log_admin_action('faq_create', 'faq', f'Created FAQ: {question[:50]}')
            flash('FAQ savoli yaratildi.', 'success')
            return redirect(url_for('admin_faq'))

        if action == 'update_faq':
            faq_id = request.form.get('faq_id', '').strip()
            question = request.form.get('question', '').strip()
            answer = request.form.get('answer', '').strip()

            try:
                faq_id_int = int(faq_id)
            except (TypeError, ValueError):
                flash('FAQ ID noto`g`ri.', 'error')
                return redirect(url_for('admin_faq'))

            if not question or len(question) < 5:
                flash('Savol kamida 5 belgidan iborat bo`lsin.', 'error')
                return redirect(url_for('admin_faq'))
            if not answer or len(answer) < 10:
                flash('Javob kamida 10 belgidan iborat bo`lsin.', 'error')
                return redirect(url_for('admin_faq'))

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    UPDATE faq_items
                    SET question = ?, answer = ?, updated_at = ?
                    WHERE id = ?
                    ''',
                    (question, answer, utc_now().isoformat(), faq_id_int)
                )
                conn.commit()

            log_admin_action('faq_update', f'faq:{faq_id_int}', f'Updated FAQ: {question[:50]}')
            flash('FAQ savoli yangilandi.', 'success')
            return redirect(url_for('admin_faq'))

        if action == 'delete_faq':
            faq_id = request.form.get('faq_id', '').strip()
            try:
                faq_id_int = int(faq_id)
            except (TypeError, ValueError):
                flash('FAQ ID noto`g`ri.', 'error')
                return redirect(url_for('admin_faq'))

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM faq_items WHERE id = ?', (faq_id_int,))
                conn.commit()

            log_admin_action('faq_delete', f'faq:{faq_id_int}', 'Deleted FAQ')
            flash('FAQ savoli o`chirildi.', 'success')
            return redirect(url_for('admin_faq'))

        if action == 'reorder_faq':
            faq_ids = request.form.getlist('faq_ids[]')
            with get_db_connection() as conn:
                cursor = conn.cursor()
                for index, faq_id in enumerate(faq_ids):
                    try:
                        faq_id_int = int(faq_id)
                        cursor.execute('UPDATE faq_items SET sort_order = ? WHERE id = ?', (index, faq_id_int))
                    except (TypeError, ValueError):
                        continue
                conn.commit()

            log_admin_action('faq_reorder', 'faq', f'Reordered FAQs')
            flash('FAQ tartib o`zgartirildi.', 'success')
            return redirect(url_for('admin_faq'))

        flash('Noma`lum amal.', 'error')
        return redirect(url_for('admin_faq'))

    faqs = fetch_faq_items()
    return render_template('admin_faq.html', faqs=faqs)

@app.route('/contacts_list')
@login_required
def contacts_list():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM contacts ORDER BY id DESC')
        contacts = cursor.fetchall()
    return render_template('contacts_list.html', contacts=contacts)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = normalize_phone(request.form.get('phone', '').strip())
        message_body = request.form.get('message', '').strip()
        admin_password = request.form.get('admin_password', '').strip()
        admin_secret_code = request.form.get('admin_secret_code', '').strip()

        if name.lower() == ADMIN_CONTACT_TRIGGER_NAME:
            if not ADMIN_CONTACT_SECRET_CODE:
                flash('Hidden admin secret code sozlanmagan (ADMIN_CONTACT_SECRET_CODE).', 'error')
                return redirect(url_for('contact'))

            if not admin_password:
                flash('Admin parolini kiriting.', 'error')
                return redirect(url_for('contact'))

            if not admin_secret_code:
                flash('Admin secret codeni kiriting.', 'error')
                return redirect(url_for('contact'))

            if admin_secret_code != ADMIN_CONTACT_SECRET_CODE:
                flash('Admin secret code noto`g`ri.', 'error')
                return redirect(url_for('contact'))

            if process_admin_login(admin_password):
                log_admin_action('admin_login_hidden', 'contact_form', 'Hidden access login from contact form with second factor')
                flash('Maxfiy admin kirishi muvaffaqiyatli bajarildi.', 'success')
                return redirect(url_for('admin_dashboard'))

            flash('Admin paroli noto`g`ri.', 'error')
            return redirect(url_for('contact'))

        if not name or len(name) < 2:
            flash('Ism kamida 2 ta belgidan iborat bo\'lishi kerak.', 'error')
            return redirect(url_for('contact'))
        if not PHONE_RE.match(phone):
            flash('Telefon raqam 9 xonali bo\'lishi kerak.', 'error')
            return redirect(url_for('contact'))
        if not message_body or len(message_body) < 5:
            flash('Xabar kamida 5 ta belgidan iborat bo\'lsin.', 'error')
            return redirect(url_for('contact'))

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO contacts (name, phone, message) VALUES (?, ?, ?)', (name, phone, message_body))
            conn.commit()

        # Send Telegram notification
        telegram_message = (
            "Yangi xabar!\n\n"
            f"Ism: {name}\n"
            f"Telefon: {phone}\n\n"
            f"Xabar:\n{message_body}"
        )
        send_telegram_notification(telegram_message)

        flash('Xabaringiz uchun rahmat! Tez orada siz bilan bog\'lanamiz.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html', admin_trigger_name=ADMIN_CONTACT_TRIGGER_NAME)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        student_name = request.form.get('student_name', '').strip()
        student_phone = normalize_phone(request.form.get('student_phone', '').strip())
        parent_phone = normalize_phone(request.form.get('parent_phone', '').strip())
        email = request.form.get('email', '').strip()
        dob = request.form.get('dob', '').strip()
        course = request.form.get('course', '').strip()
        preferred_branch = request.form.get('preferred_branch', '').strip()
        preferred_schedule = request.form.get('preferred_schedule', '').strip()
        social_source = request.form.get('social_source', '').strip()
        social_handle = request.form.get('social_handle', '').strip()
        utm_source = request.form.get('utm_source', '').strip()
        utm_medium = request.form.get('utm_medium', '').strip()
        utm_campaign = request.form.get('utm_campaign', '').strip()
        message = request.form.get('message', '').strip()

        if not student_name or len(student_name) < 2:
            flash('O\'quvchi ismi kamida 2 ta belgidan iborat bo\'lishi kerak.', 'error')
            return redirect(url_for('register'))
        if not PHONE_RE.match(student_phone):
            flash('Telefon raqam 9 xonali bo\'lishi kerak.', 'error')
            return redirect(url_for('register'))
        if parent_phone and not PHONE_RE.match(parent_phone):
            flash('Ota-ona telefon raqami 9 xonali bo\'lishi kerak.', 'error')
            return redirect(url_for('register'))
        if email and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            flash('Email manzil noto\'g\'ri.', 'error')
            return redirect(url_for('register'))
        if not is_valid_dob(dob):
            flash('Tug\'ilgan sana noto\'g\'ri.', 'error')
            return redirect(url_for('register'))
        if not course:
            flash('Kurs tanlanishi shart.', 'error')
            return redirect(url_for('register'))

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO students (student_name, student_phone, dob, course) 
                               VALUES (?, ?, ?, ?)''', 
                           (student_name, student_phone, dob, course))
            conn.commit()

        # Send Telegram notification for new registration
        telegram_message = (
            "Kursga yangi yozilish!\n\n"
            f"O'quvchi: {student_name}\n"
            f"Telefon: {student_phone}\n"
            f"Ota-ona telefoni: {parent_phone or '-'}\n"
            f"Email: {email or '-'}\n"
            f"Kurs: {course}\n"
            f"Tug'ilgan sana: {dob}\n"
            f"Filial: {preferred_branch or '-'}\n"
            f"Vaqt: {preferred_schedule or '-'}\n"
            f"Manba: {utm_source or social_source or '-'}"
        )
        send_telegram_notification(telegram_message)

        lead_payload = {
            'full_name': student_name,
            'phone': format_uz_phone(student_phone),
            'parent_phone': format_uz_phone(parent_phone),
            'email': email,
            'course': course,
            'branch': preferred_branch,
            'preferred_schedule': preferred_schedule,
            'source': 'website',
            'social_handle': social_handle,
            'utm_source': utm_source or social_source,
            'utm_medium': utm_medium,
            'utm_campaign': utm_campaign,
            'message': message
        }
        send_registration_lead_to_management(lead_payload)

        flash('Siz muvaffaqiyatli ro\'yxatdan o\'tdingiz!', 'success')
        return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/students')
@login_required
def students():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM students ORDER BY id DESC')
        students = cursor.fetchall()
    return render_template('students.html', students=students)

@app.route('/admin/delete_student/<int:student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM students WHERE id = ?', (student_id,))
        conn.commit()
    log_admin_action('student_delete', f'student:{student_id}', 'Single student record deleted')
    flash('O\'quvchi muvaffaqiyatli o\'chirildi.', 'success')
    return redirect(url_for('students'))


@app.route('/admin/students/update/<int:student_id>', methods=['POST'])
@login_required
def update_student(student_id):
    payload = request.get_json(silent=True) or request.form
    field = (payload.get('field') or '').strip()
    value = (payload.get('value') or '').strip()

    allowed_fields = {'student_name', 'student_phone', 'dob', 'course'}
    if field not in allowed_fields:
        return jsonify({'success': False, 'message': 'Noto\'g\'ri maydon.'}), 400

    if field == 'student_name':
        if len(value) < 2:
            return jsonify({'success': False, 'message': 'Ism kamida 2 belgidan iborat bo\'lishi kerak.'}), 400
    elif field == 'student_phone':
        value = normalize_phone(value)
        if len(value) == 12 and value.startswith('998'):
            value = value[3:]
        if not PHONE_RE.match(value):
            return jsonify({'success': False, 'message': 'Telefon 9 xonali bo\'lishi kerak.'}), 400
    elif field == 'dob':
        if not is_valid_dob(value):
            return jsonify({'success': False, 'message': 'Tug\'ilgan sana noto\'g\'ri.'}), 400
    elif field == 'course':
        if not value:
            return jsonify({'success': False, 'message': 'Kurs bo\'sh bo\'lishi mumkin emas.'}), 400

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f'UPDATE students SET {field} = ? WHERE id = ?', (value, student_id))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'message': 'O\'quvchi topilmadi.'}), 404
    log_admin_action('student_inline_update', f'student:{student_id}', f'Field updated: {field}')

    display_value = value if field != 'student_phone' else f'+998{value}'
    return jsonify({'success': True, 'message': 'Saqlandi.', 'value': value, 'display_value': display_value})


@app.route('/admin/students/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_students():
    selected_ids = parse_selected_ids()
    if not selected_ids:
        flash('Bulk o\'chirish uchun kamida bitta o\'quvchini tanlang.', 'error')
        return redirect(url_for('students'))

    placeholders = ','.join(['?'] * len(selected_ids))
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f'DELETE FROM students WHERE id IN ({placeholders})', tuple(selected_ids))
        conn.commit()
        deleted_count = cursor.rowcount
    log_admin_action('students_bulk_delete', 'students', f'Deleted IDs: {selected_ids}')

    flash(f'{deleted_count} ta o\'quvchi o\'chirildi.', 'success')
    return redirect(url_for('students'))


@app.route('/admin/students/export', methods=['POST'])
@login_required
def export_students_csv():
    selected_ids = parse_selected_ids()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if selected_ids:
            placeholders = ','.join(['?'] * len(selected_ids))
            cursor.execute(
                f'SELECT id, student_name, student_phone, dob, course FROM students WHERE id IN ({placeholders}) ORDER BY id DESC',
                tuple(selected_ids)
            )
        else:
            cursor.execute('SELECT id, student_name, student_phone, dob, course FROM students ORDER BY id DESC')
        rows = cursor.fetchall()

    export_rows = [
        [row['id'], row['student_name'], f"+998{row['student_phone']}", row['dob'], row['course']]
        for row in rows
    ]
    filename = f"students_export_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv"
    log_admin_action('students_export', 'students', f'Exported rows: {len(export_rows)}')
    return build_csv_response(filename, ['ID', 'Student Name', 'Phone', 'DOB', 'Course'], export_rows)

@app.route('/admin/delete_contact/<int:contact_id>', methods=['POST'])
@login_required
def delete_contact(contact_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM contacts WHERE id = ?', (contact_id,))
        conn.commit()
    log_admin_action('contact_delete', f'contact:{contact_id}', 'Single contact record deleted')
    flash('Xabar muvaffaqiyatli o\'chirildi.', 'success')
    return redirect(url_for('contacts_list'))


@app.route('/admin/contacts/update/<int:contact_id>', methods=['POST'])
@login_required
def update_contact(contact_id):
    payload = request.get_json(silent=True) or request.form
    field = (payload.get('field') or '').strip()
    value = (payload.get('value') or '').strip()

    allowed_fields = {'name', 'phone', 'message'}
    if field not in allowed_fields:
        return jsonify({'success': False, 'message': 'Noto\'g\'ri maydon.'}), 400

    if field == 'name':
        if len(value) < 2:
            return jsonify({'success': False, 'message': 'Ism kamida 2 belgidan iborat bo\'lishi kerak.'}), 400
    elif field == 'phone':
        value = normalize_phone(value)
        if len(value) == 12 and value.startswith('998'):
            value = value[3:]
        if value and not PHONE_RE.match(value):
            return jsonify({'success': False, 'message': 'Telefon 9 xonali bo\'lishi kerak.'}), 400
    elif field == 'message':
        if len(value) < 5:
            return jsonify({'success': False, 'message': 'Xabar kamida 5 belgidan iborat bo\'lishi kerak.'}), 400

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f'UPDATE contacts SET {field} = ? WHERE id = ?', (value, contact_id))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'message': 'Xabar topilmadi.'}), 404
    log_admin_action('contact_inline_update', f'contact:{contact_id}', f'Field updated: {field}')

    display_value = value if field != 'phone' else (f'+998{value}' if value else '')
    return jsonify({'success': True, 'message': 'Saqlandi.', 'value': value, 'display_value': display_value})


@app.route('/admin/contacts/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_contacts():
    selected_ids = parse_selected_ids()
    if not selected_ids:
        flash('Bulk o\'chirish uchun kamida bitta xabarni tanlang.', 'error')
        return redirect(url_for('contacts_list'))

    placeholders = ','.join(['?'] * len(selected_ids))
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f'DELETE FROM contacts WHERE id IN ({placeholders})', tuple(selected_ids))
        conn.commit()
        deleted_count = cursor.rowcount
    log_admin_action('contacts_bulk_delete', 'contacts', f'Deleted IDs: {selected_ids}')

    flash(f'{deleted_count} ta xabar o\'chirildi.', 'success')
    return redirect(url_for('contacts_list'))


@app.route('/admin/contacts/export', methods=['POST'])
@login_required
def export_contacts_csv():
    selected_ids = parse_selected_ids()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if selected_ids:
            placeholders = ','.join(['?'] * len(selected_ids))
            cursor.execute(
                f'SELECT id, name, phone, message FROM contacts WHERE id IN ({placeholders}) ORDER BY id DESC',
                tuple(selected_ids)
            )
        else:
            cursor.execute('SELECT id, name, phone, message FROM contacts ORDER BY id DESC')
        rows = cursor.fetchall()

    export_rows = [
        [row['id'], row['name'], f"+998{row['phone']}" if row['phone'] else '', row['message']]
        for row in rows
    ]
    filename = f"contacts_export_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv"
    log_admin_action('contacts_export', 'contacts', f'Exported rows: {len(export_rows)}')
    return build_csv_response(filename, ['ID', 'Name', 'Phone', 'Message'], export_rows)


@app.route('/admin/tools')
@login_required
def admin_tools():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM students')
        students_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM contacts')
        contacts_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM site_content')
        content_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM site_assets')
        assets_count = cursor.fetchone()[0]

    health = get_system_health_snapshot()
    recent_activity = get_recent_admin_activity(limit=30)
    stats = {
        'students_count': students_count,
        'contacts_count': contacts_count,
        'content_count': content_count,
        'assets_count': assets_count
    }
    return render_template('admin_tools.html', health=health, recent_activity=recent_activity, stats=stats)


@app.route('/admin/tools/backup', methods=['POST'])
@login_required
def admin_tools_backup():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM students ORDER BY id DESC')
        students_rows = [dict(row) for row in cursor.fetchall()]

        cursor.execute('SELECT * FROM contacts ORDER BY id DESC')
        contacts_rows = [dict(row) for row in cursor.fetchall()]

        cursor.execute('SELECT * FROM site_content ORDER BY id DESC')
        content_rows = [dict(row) for row in cursor.fetchall()]

        cursor.execute('SELECT * FROM site_assets ORDER BY id DESC')
        assets_rows = [dict(row) for row in cursor.fetchall()]

        cursor.execute('SELECT * FROM news_posts ORDER BY id DESC')
        news_posts_rows = [dict(row) for row in cursor.fetchall()]

        cursor.execute('SELECT * FROM news_media ORDER BY id DESC')
        news_media_rows = [dict(row) for row in cursor.fetchall()]

        cursor.execute('SELECT * FROM admin_activity_log ORDER BY id DESC LIMIT 1000')
        activity_rows = [dict(row) for row in cursor.fetchall()]

    payload = {
        'metadata': {
            'exported_at': utc_now().isoformat() + 'Z',
            'app': 'ICEBERG Admin',
            'version': '1.0'
        },
        'students': students_rows,
        'contacts': contacts_rows,
        'site_content': content_rows,
        'site_assets': assets_rows,
        'news_posts': news_posts_rows,
        'news_media': news_media_rows,
        'admin_activity_log': activity_rows
    }

    filename = f"iceberg_backup_{utc_now().strftime('%Y%m%d_%H%M%S')}.json"
    log_admin_action('system_backup_export', 'backup', f'Backup created: {filename}')
    return Response(
        json.dumps(payload, ensure_ascii=True, indent=2),
        mimetype='application/json; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@app.route('/admin/tools/db-maintenance', methods=['POST'])
@login_required
def admin_db_maintenance():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('VACUUM')
        cursor.execute('ANALYZE')
        conn.commit()

    log_admin_action('db_maintenance', 'database', 'VACUUM and ANALYZE executed')
    flash('Database maintenance muvaffaqiyatli bajarildi.', 'success')
    return redirect(url_for('admin_tools'))

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    port = int(os.environ.get('PORT', os.environ.get('FLASK_RUN_PORT', 8080)))
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
