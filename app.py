from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response, abort
import requests
import os
import re
import hashlib
import csv
import io
import json
import secrets
import hmac
import uuid
from pathlib import Path
from datetime import UTC, date, datetime, timedelta
from functools import wraps
from contextlib import contextmanager
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from public_content import NAVIGATION, PAGES, COURSE_COPY


STATIC_BUILD_MODE = os.environ.get('ICEBERG_STATIC_BUILD') == '1'
PUBLIC_CONTENT_PATH = os.path.join(os.path.dirname(__file__), 'config', 'public_content.json')
with open(PUBLIC_CONTENT_PATH, encoding='utf-8') as public_content_file:
    PUBLIC_CONTENT = json.load(public_content_file)
try:
    import sqlite3
except ModuleNotFoundError:
    if not STATIC_BUILD_MODE:
        raise
    sqlite3 = None


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
configured_secret = os.environ.get('SECRET_KEY', '').strip()
SECURE_SESSION_CONFIGURED = len(configured_secret) >= 32 and configured_secret not in {'dev-only-secret-change-me', 'iceberg-admin'}
app.secret_key = configured_secret if SECURE_SESSION_CONFIGURED else secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    MAX_CONTENT_LENGTH=32 * 1024 * 1024,
    MAX_FORM_MEMORY_SIZE=1024 * 1024,
)
if os.environ.get('FLASK_ENV') == 'production':
    app.config['SESSION_COOKIE_SECURE'] = True

# Telegram Bot configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
DEFAULT_REGISTRATION_LEADS_API_URL = ''
REGISTRATION_LEADS_API_URL = os.environ.get(
    'REGISTRATION_LEADS_API_URL',
    DEFAULT_REGISTRATION_LEADS_API_URL
).strip()
REGISTRATION_LEADS_API_TOKEN = os.environ.get('REGISTRATION_LEADS_API_TOKEN', '').strip()
REGISTRATION_LEADS_API_TIMEOUT = float(os.environ.get('REGISTRATION_LEADS_API_TIMEOUT', '8'))

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '').strip()
# reject the old public default
ADMIN_ENABLED = SECURE_SESSION_CONFIGURED and len(ADMIN_PASSWORD) >= 12 and ADMIN_PASSWORD != 'iceberg-admin'  # nosec B105
ADMIN_PASSWORD_HASH = generate_password_hash(ADMIN_PASSWORD) if ADMIN_ENABLED else ''


def build_admin_login_slug():
    configured_slug = re.sub(r'[^a-zA-Z0-9_-]', '', os.environ.get('ADMIN_LOGIN_SLUG', '').strip())
    if configured_slug:
        return configured_slug

    return 'iceberg-portal'


ADMIN_LOGIN_SLUG = build_admin_login_slug()
DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(app.root_path, 'database.db'))
REGISTRATION_CONFIG_PATH = os.path.join(app.root_path, 'config', 'registration.json')
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
ALLOWED_NEWS_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
ALLOWED_NEWS_VIDEO_EXTENSIONS = {'.mp4', '.webm', '.mov', '.m4v'}

ASSET_CATALOG = [
    {'key': 'site_logo', 'label': 'Asosiy logo', 'default': 'img/logo.png'},
    {'key': 'about_team_1', 'label': 'Azizbek Nasriddinov rasmi', 'default': 'img/azizbek.png'},
    {'key': 'about_team_2', 'label': 'Maqsudbek Mirzayev rasmi', 'default': 'img/maqsudbek.png'},
    {'key': 'about_team_3', 'label': 'Islomjon Ergashboyev rasmi', 'default': 'img/islomjon.png'},
]
ASSET_DEFAULTS = {asset['key']: asset['default'] for asset in ASSET_CATALOG}
EDITABLE_SITE_FILES = [
    ('static/css/style.css', 'Global CSS styles'),
    ('static/css/public.css', 'Public page CSS styles')
]
EDITOR_BACKUP_DIR = os.path.join(app.root_path, 'backups', 'site_editor')
EDITOR_MAX_BACKUPS_PER_FILE = max(int(os.environ.get('EDITOR_MAX_BACKUPS_PER_FILE', '20')), 1)

CONTENT_FIELDS = [
    {'key': 'hero_main_title', 'label': 'Bosh sahifa sarlavhasi (UZ)', 'group': 'Home', 'default': 'Kelajagingizni ICEBERG bilan quring', 'field_type': 'text'},
    {'key': 'hero_main_subtitle', 'label': 'Bosh sahifa matni (UZ)', 'group': 'Home', 'default': 'Ingliz tili, imtihon tayyorgarligi va akademik fanlar. Amaliy mashg‘ulotlar va individual yordam bilan o‘zingizga mos kursni tanlang.', 'field_type': 'textarea'},
    {'key': 'contact_email', 'label': 'Aloqa email', 'group': 'Contact', 'default': 'iceberg.edu.center@gmail.com', 'field_type': 'text'},
]

CONTENT_KEYS = {field['key'] for field in CONTENT_FIELDS}

PHONE_RE = re.compile(r'^[0-9]{9}$')


def load_registration_config():
    with open(REGISTRATION_CONFIG_PATH, 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)
    config['programs'] = [item for item in config.get('programs', []) if item.get('active')]
    config['branches'] = [item for item in config.get('branches', []) if item.get('active')]
    for group_name in ('programs', 'branches'):
        ids = [item.get('id', '') for item in config[group_name]]
        if len(ids) != len(set(ids)) or any(not re.fullmatch(r'[a-z0-9-]+', item_id) for item_id in ids):
            raise RuntimeError(f'Invalid or duplicate active registration {group_name} ID')
    return config


REGISTRATION_CONFIG = load_registration_config()
REGISTRATION_PROGRAMS = {item['id']: item for item in REGISTRATION_CONFIG['programs']}
REGISTRATION_BRANCHES = {item['id']: item for item in REGISTRATION_CONFIG['branches']}


def utc_now():
    return datetime.now(UTC).replace(tzinfo=None)


APP_STARTED_AT = utc_now()


@contextmanager
def get_db_connection():
    if sqlite3 is None:
        raise RuntimeError('SQLite is unavailable during the static Firebase build')
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False, timeout=30)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA cache_size=-64000')  # 64 MB page cache
        conn.execute('PRAGMA temp_store=MEMORY')
        conn.execute('PRAGMA foreign_keys=ON')
        with conn:
            yield conn
    finally:
        conn.close()


def normalize_phone(raw_phone):
    digits = re.sub(r'[^0-9]', '', raw_phone or '')
    if len(digits) == 12 and digits.startswith('998'):
        return digits[3:]
    return digits


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
        if not ADMIN_ENABLED:
            abort(503, description='Admin access requires a secure SECRET_KEY and ADMIN_PASSWORD.')
        if not session.get('logged_in'):
            flash('Avval admin tizimiga kiring.', 'error')
            return redirect(url_for('secret_admin_login', access_slug=ADMIN_LOGIN_SLUG))
        return view(*args, **kwargs)
    return wrapped_view


def process_admin_login(password):
    candidate = (password or '').strip()
    if ADMIN_ENABLED and candidate and check_password_hash(ADMIN_PASSWORD_HASH, candidate):
        session.clear()
        session['logged_in'] = True
        session.permanent = True
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
    if STATIC_BUILD_MODE:
        return to_public_asset_url(PUBLIC_CONTENT.get('assets', {}).get(asset_key) or fallback or ASSET_DEFAULTS.get(asset_key, ''))
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
    static_root = (Path(app.root_path) / 'static').resolve()
    absolute_path = (static_root / relative_path.replace('\\', '/')).resolve()
    if not absolute_path.is_relative_to(static_root / 'uploads'):
        return
    if absolute_path.is_file():
        absolute_path.unlink()


def fetch_news_posts(include_unpublished=False):
    if STATIC_BUILD_MODE:
        return PUBLIC_CONTENT.get('news', [])
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
    if STATIC_BUILD_MODE:
        return PUBLIC_CONTENT.get('content', {})
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT content_key, content_value FROM site_content')
        rows = cursor.fetchall()
    return {row['content_key']: row['content_value'] for row in rows}


def fetch_faq_items():
    """Fetch all FAQ items ordered by sort_order"""
    if STATIC_BUILD_MODE:
        if PUBLIC_CONTENT.get('faqs'):
            return PUBLIC_CONTENT['faqs']
        return [
            {
                'question': question,
                'answer': answer,
                'sort_order': index,
            }
            for index, (question, answer) in enumerate(DEFAULT_FAQS, 1)
        ]
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
        if not isinstance(payload, dict):
            abort(400)
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

    if len(set(normalized_ids)) > 500:
        abort(400, description='Select at most 500 records per operation.')
    return sorted(set(normalized_ids))


def build_csv_response(filename, headers, rows):
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([safe_csv_cell(value) for value in row])

    csv_content = csv_buffer.getvalue()
    return Response(
        csv_content,
        mimetype='text/csv; charset=utf-8',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )


def safe_csv_cell(value):
    if isinstance(value, str) and (value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n'))):
        return "'" + value
    return value


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
        'registration_leads_configured': bool(REGISTRATION_LEADS_API_URL),
        'secret_code_configured': ADMIN_ENABLED,
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

    absolute_path = (Path(app.root_path) / safe_relative).resolve()
    if not absolute_path.is_relative_to(Path(app.root_path).resolve()):
        return ''
    return str(absolute_path)


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

    backup_path = (Path(EDITOR_BACKUP_DIR) / safe_name).resolve()
    if not backup_path.is_relative_to(Path(EDITOR_BACKUP_DIR).resolve()):
        return ''
    if not os.path.exists(backup_path):
        return ''
    return str(backup_path)


@app.context_processor
def inject_asset_helper():
    site_content = get_site_content_map()

    def content_value(content_key, fallback=''):
        value = site_content.get(content_key)
        return value if value not in (None, '') else fallback

    language = 'en' if request.path == '/en' or request.path.startswith('/en/') else 'uz'
    uz_path = (request.path[3:] or '/') if language == 'en' else request.path
    en_path = '/en' if uz_path == '/' else '/en' + uz_path
    email = content_value('contact_email', 'iceberg.edu.center@gmail.com')
    titles = {
        '/': ('ICEBERG — Namangandagi o‘quv markazi', 'ICEBERG — Education in Namangan, Uzbekistan'),
        '/our_programs': ('Dasturlar', 'Programs'), '/news': ('Yangiliklar va tadbirlar', 'News & events'),
        '/contact': ('Aloqa va filiallar', 'Contact & campus information'),
        '/register': ('Kurs uchun ariza', 'Course inquiry'),
    }
    return {
        'asset_url': get_asset_url,
        'content': content_value,
        'registration': REGISTRATION_CONFIG,
        'site_language': language,
        'uz_path': uz_path,
        'en_path': en_path,
        'local_url': lambda path: ('/en' if path == '/' else '/en' + path) if language == 'en' else path,
        'navigation': NAVIGATION,
        'contact_email': email,
        'current_year': utc_now().year,
        'page_title': titles.get(uz_path, ('ICEBERG', 'ICEBERG'))[1 if language == 'en' else 0],
        'page_description': ('ICEBERG courses, admissions, and educational activities in Namangan region, Uzbekistan.'
                             if language == 'en' else 'ICEBERG kurslari, qabul va ta’lim faoliyati. Namangan viloyati, O‘zbekiston.'),
        'course_copy': COURSE_COPY,
        'csrf_token': csrf_token,
        'institution_schema': {
            '@context': 'https://schema.org', '@type': 'EducationalOrganization',
            'name': 'ICEBERG Study Center', 'url': 'https://iceberglc.com',
            'telephone': REGISTRATION_CONFIG['contact']['call_center_phone'],
            'email': email,
            'address': {'@type': 'PostalAddress', 'addressRegion': 'Namangan', 'addressCountry': 'UZ'},
        },
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
        app.logger.error('Telegram notification failed: %s', type(e).__name__)


def build_management_lead_payload(payload):
    management_payload = dict(payload)
    field_aliases = {
        'student_name': payload.get('full_name', ''),
        'student_phone': payload.get('phone', ''),
        'created_at': payload.get('submitted_at', ''),
        'dob': payload.get('date_of_birth', ''),
        'preferred_branch': payload.get('branch', '')
    }
    management_payload.update({key: value for key, value in field_aliases.items() if value})
    return management_payload


def log_management_forwarding_failure(response=None, error=None):
    if response is not None:
        return f'HTTP {response.status_code}'
    return type(error).__name__ if error else 'Unknown forwarding error'


def post_registration_lead(payload, headers):
    response = requests.post(
        REGISTRATION_LEADS_API_URL,
        json=payload,
        headers=headers,
        timeout=REGISTRATION_LEADS_API_TIMEOUT,
        allow_redirects=False,
    )
    if 200 <= response.status_code < 300:
        return response

    if response.status_code in {400, 415, 422}:
        app.logger.warning(
            'Management lead JSON POST failed; retrying as form data. Response: %s',
            log_management_forwarding_failure(response=response)
        )
        form_headers = {key: value for key, value in headers.items() if key.lower() != 'content-type'}
        return requests.post(
            REGISTRATION_LEADS_API_URL,
            data=payload,
            headers=form_headers,
            timeout=REGISTRATION_LEADS_API_TIMEOUT,
            allow_redirects=False,
        )

    return response


def send_registration_lead_to_management(payload):
    if not REGISTRATION_LEADS_API_URL:
        app.logger.info('Registration lead forwarding is not configured.')
        log_admin_action(
            'registration_forwarding_skipped',
            payload.get('full_name', 'registration'),
            'REGISTRATION_LEADS_API_URL is not configured'
        )
        return False

    management_payload = build_management_lead_payload(payload)
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    if REGISTRATION_LEADS_API_TOKEN:
        headers['Authorization'] = f'Bearer {REGISTRATION_LEADS_API_TOKEN}'
        headers['X-Registration-Token'] = REGISTRATION_LEADS_API_TOKEN
        headers['X-API-Key'] = REGISTRATION_LEADS_API_TOKEN

    try:
        response = post_registration_lead(management_payload, headers)
        if 300 <= response.status_code < 400:
            raise requests.RequestException('Management redirects are not accepted.')
        response.raise_for_status()
        app.logger.info('Registration lead forwarded to management system.')
        log_admin_action(
            'registration_forwarding_success',
            payload.get('full_name', 'registration'),
            f'Sent to {REGISTRATION_LEADS_API_URL}'
        )
        return True
    except requests.exceptions.RequestException as exc:
        failure_detail = log_management_forwarding_failure(
            response=getattr(exc, 'response', None),
            error=exc
        )
        app.logger.error('Failed to forward registration lead: %s', failure_detail)
        log_admin_action(
            'registration_forwarding_failed',
            payload.get('full_name', 'registration'),
            failure_detail
        )
        return False


def ensure_table_columns(cursor, table_name, column_definitions):
    cursor.execute(f'PRAGMA table_info({table_name})')
    existing_columns = {row[1] for row in cursor.fetchall()}
    for column_name, column_sql in column_definitions.items():
        if column_name not in existing_columns:
            cursor.execute(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}')

DEFAULT_FAQS = [
    ('Qaysi kurslar bor?', 'IELTS, ingliz tili, SAT, matematika, kimyo va biologiya. Kursning filialdagi mavjudligini qabul jamoasi bilan tasdiqlang.'),
    ('Narx va jadvalni qanday bilaman?', 'Yosh va daraja talabi, kurs davomiyligi, guruh hajmi, jadval va to‘lov shartlarini qabul jamoasidan so‘rang.'),
    ('Markazga qanday tashrif buyuraman?', 'Filialning aniq manzili va ish vaqtini oldindan qabul jamoasi bilan kelishing.'),
    ('Ariza joyni band qiladimi?', 'Ariza — bog‘lanish so‘rovi. Kurs mavjudligi va qabul shartlari jamoa bilan alohida tasdiqlanadi.'),
    ('Xususiy maktab ochilganmi?', 'Maktab alohida loyiha bo‘lib, ochilish 2027-yil sentabrga rejalashtirilgan. Bu amaldagi o‘quv markazidan alohida.'),
]


def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                student_phone TEXT NOT NULL,
                parent_phone TEXT,
                email TEXT,
                dob TEXT NOT NULL,
                course TEXT NOT NULL,
                preferred_branch TEXT,
                preferred_schedule TEXT,
                social_source TEXT,
                social_handle TEXT,
                utm_source TEXT,
                utm_medium TEXT,
                utm_campaign TEXT,
                message TEXT,
                forwarded_to_management INTEGER NOT NULL DEFAULT 0,
                created_at TEXT
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
        ensure_table_columns(
            cursor,
            'students',
            {
                'parent_phone': 'TEXT',
                'email': 'TEXT',
                'preferred_branch': 'TEXT',
                'preferred_schedule': 'TEXT',
                'social_source': 'TEXT',
                'social_handle': 'TEXT',
                'utm_source': 'TEXT',
                'utm_medium': 'TEXT',
                'utm_campaign': 'TEXT',
                'message': 'TEXT',
                'forwarded_to_management': 'INTEGER NOT NULL DEFAULT 0',
                'created_at': 'TEXT',
                'submission_id': 'TEXT',
            }
        )
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS students_submission_id ON students(submission_id)')
        ensure_table_columns(cursor, 'contacts', {'email': 'TEXT'})
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
            for index, (question, answer) in enumerate(DEFAULT_FAQS, 1):
                cursor.execute(
                    '''INSERT INTO faq_items (question, answer, sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?)''',
                    (question, answer, index, now, now)
                )
        
        conn.commit()

if not STATIC_BUILD_MODE:
    init_db()


# Private/dynamic HTML that must never be cached (admin panels and live data
# views). Scoped tightly so public marketing pages stay cacheable for crawlers.
NO_CACHE_PREFIXES = ('/admin', '/portal', '/students', '/contacts_list')


def csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_urlsafe(32)
    return session['_csrf_token']


@app.before_request
def protect_admin_requests():
    private = request.path.startswith(NO_CACHE_PREFIXES)
    if private and request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        provided = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token', '')
        expected = session.get('_csrf_token', '')
        if not expected or not provided or not hmac.compare_digest(expected, provided):
            abort(400, description='Invalid CSRF token. Reload the page and try again.')
    if request.path in {'/register', '/en/register'} and request.content_length and request.content_length > 16384:
        abort(413)


@app.before_request
def protect_unpublished_uploads():
    prefix = '/static/uploads/news/'
    if request.path.startswith(prefix) and not STATIC_BUILD_MODE and not (ADMIN_ENABLED and session.get('logged_in')):
        relative = request.path[len('/static/'):]
        with get_db_connection() as conn:
            published = conn.execute('''SELECT 1 FROM news_media m JOIN news_posts p ON p.id = m.post_id
                                        WHERE m.file_path = ? AND p.is_published = 1''', (relative,)).fetchone()
        if not published:
            abort(404)


@app.after_request
def add_cache_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    private = (request.path.startswith(NO_CACHE_PREFIXES)
               or request.path in {'/register', '/en/register'}
               or bool(session) or 'Set-Cookie' in response.headers
               or request.path.startswith('/static/uploads/news/'))
    if private or 'text/html' in (response.content_type or ''):
        if private:
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            # Bypass edge/CDN caches (Cloudflare, DigitalOcean, Vercel, etc.)
            response.headers['CDN-Cache-Control'] = 'no-store'
            response.headers['Cloudflare-CDN-Cache-Control'] = 'no-store'
            response.headers['Surrogate-Control'] = 'no-store'
        else:
            # Public pages: short cache + revalidate. Good for crawl efficiency
            # while keeping CMS edits visible within ~1 minute. Note: no Vary:*
            # (discouraged, hurts crawling). Lower max-age if edits must appear
            # faster; raise it to reduce load.
            response.headers['Cache-Control'] = 'public, max-age=60, must-revalidate'
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

    def _template_mtime(template_name):
        # Real "last modified" signal = when the page's template last changed
        # (i.e. the last deploy that touched it), not the current date.
        try:
            path = os.path.join(app.root_path, 'templates', template_name)
            return _date.fromtimestamp(os.path.getmtime(path)).isoformat()
        except OSError:
            return today

    # (loc, priority, changefreq, source template)
    static_pages = [
        ('https://iceberglc.com/', '1.0', 'daily', 'index.html'),
        ('https://iceberglc.com/about', '0.8', 'monthly', 'information.html'),
        ('https://iceberglc.com/our_programs', '0.9', 'weekly', 'our_programs.html'),
        ('https://iceberglc.com/news', '0.9', 'daily', 'news.html'),
        ('https://iceberglc.com/questions', '0.7', 'monthly', 'questions.html'),
        ('https://iceberglc.com/contact', '0.8', 'monthly', 'contact.html'),
        ('https://iceberglc.com/register', '0.8', 'monthly', 'register.html'),
    ]
    for slug in ('international', 'private-school', 'admissions', 'privacy', 'results', 'student-life'):
        static_pages.append((f'https://iceberglc.com/{slug}', '0.7', 'monthly', 'information.html'))
    for path, _, _ in NAVIGATION:
        english_path = '/en' if path == '/' else '/en' + path
        static_pages.append(('https://iceberglc.com' + english_path, '0.7', 'monthly', 'information.html'))
    static_pages.append(('https://iceberglc.com/en/register', '0.8', 'monthly', 'register_en.html'))
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, priority, changefreq, template_name in static_pages:
        lastmod = _template_mtime(template_name)
        lines.append('  <url>')
        lines.append(f'    <loc>{loc}</loc>')
        lines.append(f'    <lastmod>{lastmod}</lastmod>')
        lines.append(f'    <changefreq>{changefreq}</changefreq>')
        lines.append(f'    <priority>{priority}</priority>')
        lines.append('  </url>')
    lines.append('</urlset>')
    return Response('\n'.join(lines), mimetype='application/xml')


@app.route('/en')
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return information_page('about')

@app.route('/en/our_programs')
@app.route('/our_programs')
def our_programs():
    return render_template('our_programs.html')


@app.route('/en/news')
@app.route('/news')
def news():
    posts = fetch_news_posts(include_unpublished=False)
    return render_template('news.html', posts=posts)


@app.route('/questions')
def questions():
    faqs = fetch_faq_items()
    return render_template('questions.html', faqs=faqs)


@app.route('/<slug>')
@app.route('/en/<slug>')
def information_page(slug):
    if slug not in PAGES:
        abort(404)
    language = 'en' if request.path.startswith('/en/') else 'uz'
    title, description, sections = PAGES[slug][language]
    return render_template('information.html', slug=slug, page_title=title,
                           page_description=description, sections=sections)

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
    if not ADMIN_ENABLED:
        abort(503, description='Admin access requires a secure SECRET_KEY and ADMIN_PASSWORD.')

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
    abort(410)


@app.route('/admin/logout', methods=['POST'])
def logout():
    if session.get('logged_in'):
        log_admin_action('admin_logout', 'session', 'Admin logged out')
    session.clear()
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
        placeholders = ','.join('?' for _ in ASSET_DEFAULTS)
        # Only '?' placeholders are interpolated; all key values are bound separately.
        query = f'SELECT asset_key, file_path, updated_at FROM site_assets WHERE asset_key NOT IN ({placeholders}) ORDER BY asset_key ASC'  # nosec B608
        cursor.execute(query, tuple(ASSET_DEFAULTS.keys()))
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

@app.route('/en/contact')
@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/en/register', methods=['GET', 'POST'])
@app.route('/register', methods=['GET', 'POST'])
def register():
    registration_template = 'register_en.html' if request.path.startswith('/en/') else 'register.html'
    form_data = {}
    errors = {}
    submission_id = request.form.get('submission_id', '') if request.method == 'POST' else ''
    if submission_id:
        try:
            submission_id = str(uuid.UUID(submission_id))
        except (ValueError, AttributeError):
            abort(400)
    else:
        submission_id = '' if STATIC_BUILD_MODE else str(uuid.uuid4())
    if request.method == 'POST':
        if request.form.get('website', ''):
            abort(400)
        student_name = re.sub(
            r'[\x00-\x1f\x7f]',
            '',
            request.form.get('student_name', '').strip(),
        )[:100]
        student_phone = normalize_phone(request.form.get('student_phone', '').strip())
        course = request.form.get('course', '').strip()
        preferred_branch = request.form.get('preferred_branch', '').strip()
        utm_source = request.form.get('utm_source', '').strip()[:100]
        utm_medium = request.form.get('utm_medium', '').strip()[:100]
        utm_campaign = request.form.get('utm_campaign', '').strip()[:150]
        form_data = {
            'student_name': student_name,
            'student_phone': student_phone,
            'course': course,
            'preferred_branch': preferred_branch,
        }

        if not student_name or len(student_name) < 2:
            errors['student_name'] = 'Ism va familiyangizni kiriting.'
        if not PHONE_RE.match(student_phone):
            errors['student_phone'] = 'Telefon raqamingizni tekshiring.'
        if course not in REGISTRATION_PROGRAMS:
            errors['course'] = 'Dastur tanlang.'
        if preferred_branch not in REGISTRATION_BRANCHES:
            errors['preferred_branch'] = 'Filial tanlang.'

        if errors:
            if registration_template == 'register_en.html':
                translations = {'student_name': 'Enter your full name.', 'student_phone': 'Check your phone number.', 'course': 'Choose a program.', 'preferred_branch': 'Choose a branch.'}
                errors = {key: translations[key] for key in errors}
            return render_template(
                registration_template,
                registration=REGISTRATION_CONFIG,
                form_data=form_data,
                errors=errors,
                success=False,
                submission_id=submission_id,
            ), 422

        created_at = utc_now().isoformat()
        lead_payload = {
            'full_name': student_name,
            'phone': format_uz_phone(student_phone),
            'course': course,
            'branch': preferred_branch,
            'source': 'website',
            'submitted_at': created_at
        }
        optional_lead_fields = {
            'utm_source': utm_source,
            'utm_medium': utm_medium,
            'utm_campaign': utm_campaign,
        }
        lead_payload.update({key: value for key, value in optional_lead_fields.items() if value})

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO students (
                    student_name, student_phone, parent_phone, email, dob, course,
                    preferred_branch, preferred_schedule, social_source, social_handle,
                    utm_source, utm_medium, utm_campaign, message,
                    forwarded_to_management, created_at, submission_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(submission_id) DO NOTHING
                ''',
                (
                    student_name, student_phone, '', '', '', course,
                    preferred_branch, '', '', '',
                    utm_source, utm_medium, utm_campaign, '',
                    0, created_at, submission_id,
                )
            )
            student_id = cursor.lastrowid
            inserted = cursor.rowcount != 0
            conn.commit()

        success_path = '/en/register' if registration_template == 'register_en.html' else '/register'
        if not inserted:
            session['_registration_success'] = True
            return redirect(success_path + '?success=1')

        forwarded_to_management = 1 if send_registration_lead_to_management(lead_payload) else 0
        if forwarded_to_management:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE students SET forwarded_to_management = ? WHERE id = ?',
                    (forwarded_to_management, student_id)
                )
                conn.commit()

        telegram_lines = [
            "Kursga yangi yozilish!",
            "",
            f"O'quvchi: {student_name}",
            f"Telefon: {format_uz_phone(student_phone)}"
        ]
        optional_telegram_lines = [
            ("Dastur", REGISTRATION_PROGRAMS[course]['name']),
            ("Filial", REGISTRATION_BRANCHES[preferred_branch]['name']),
            ("Manba", utm_source)
        ]
        telegram_lines.extend(f"{label}: {value}" for label, value in optional_telegram_lines if value)
        telegram_message = "\n".join(telegram_lines)
        send_telegram_notification(telegram_message)

        session['_registration_success'] = True
        return redirect(success_path + '?success=1')
    requested_program = request.args.get('program', '').strip()
    requested_branch = request.args.get('branch', '').strip()
    return render_template(
        registration_template,
        registration=REGISTRATION_CONFIG,
        form_data={
            'course': requested_program if requested_program in REGISTRATION_PROGRAMS else '',
            'preferred_branch': requested_branch if requested_branch in REGISTRATION_BRANCHES else '',
        },
        errors={},
        success=session.pop('_registration_success', False) and request.args.get('success') == '1',
        submission_id=submission_id,
    )

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
    payload = request.get_json(silent=True) if request.is_json else request.form
    if payload is None or not hasattr(payload, 'get'):
        abort(400)
    field = payload.get('field', '')
    value = payload.get('value', '')
    if not isinstance(field, str) or not isinstance(value, str) or len(value) > 3000:
        abort(400)
    field, value = field.strip(), value.strip()

    allowed_fields = {
        'student_name',
        'student_phone',
        'parent_phone',
        'email',
        'dob',
        'course',
        'preferred_branch',
        'preferred_schedule',
        'social_source',
        'social_handle',
        'utm_source',
        'utm_medium',
        'utm_campaign',
        'message'
    }
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
    elif field == 'parent_phone':
        value = normalize_phone(value)
        if len(value) == 12 and value.startswith('998'):
            value = value[3:]
        if value and not PHONE_RE.match(value):
            return jsonify({'success': False, 'message': 'Ota-ona telefoni 9 xonali bo\'lishi kerak.'}), 400
    elif field == 'email':
        if value and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', value):
            return jsonify({'success': False, 'message': 'Email manzil noto\'g\'ri.'}), 400
    elif field == 'dob':
        if value and not is_valid_dob(value):
            return jsonify({'success': False, 'message': 'Tug\'ilgan sana noto\'g\'ri.'}), 400
    elif field == 'preferred_branch':
        if value and value not in REGISTRATION_BRANCHES:
            return jsonify({'success': False, 'message': 'Filial noto‘g‘ri.'}), 400
    elif field == 'course':
        if value not in REGISTRATION_PROGRAMS:
            return jsonify({'success': False, 'message': 'Kurs bo\'sh bo\'lishi mumkin emas.'}), 400

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # field is checked against the fixed allowlist
        cursor.execute(f'UPDATE students SET {field} = ? WHERE id = ?', (value, student_id))  # nosec B608
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'message': 'O\'quvchi topilmadi.'}), 404
    log_admin_action('student_inline_update', f'student:{student_id}', f'Field updated: {field}')

    if field in {'student_phone', 'parent_phone'}:
        display_value = f'+998{value}' if value else ''
    else:
        display_value = value
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
        # placeholders contain only '?' and values are bound
        cursor.execute(f'DELETE FROM students WHERE id IN ({placeholders})', tuple(selected_ids))  # nosec B608
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
            # placeholders contain only '?' and values are bound
            cursor.execute(f'SELECT * FROM students WHERE id IN ({placeholders}) ORDER BY id DESC', tuple(selected_ids))  # nosec B608
        else:
            cursor.execute('SELECT * FROM students ORDER BY id DESC')
        rows = cursor.fetchall()

    export_rows = [
        [
            row['id'],
            row['student_name'],
            f"+998{row['student_phone']}" if row['student_phone'] else '',
            f"+998{row['parent_phone']}" if row['parent_phone'] else '',
            row['email'] or '',
            row['dob'],
            row['course'],
            row['preferred_branch'] or '',
            row['preferred_schedule'] or '',
            row['social_source'] or '',
            row['social_handle'] or '',
            row['utm_source'] or '',
            row['utm_medium'] or '',
            row['utm_campaign'] or '',
            row['message'] or '',
            'yes' if row['forwarded_to_management'] else 'no',
            row['created_at'] or ''
        ]
        for row in rows
    ]
    filename = f"students_export_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv"
    log_admin_action('students_export', 'students', f'Exported rows: {len(export_rows)}')
    return build_csv_response(
        filename,
        [
            'ID',
            'Student Name',
            'Student Phone',
            'Parent Phone',
            'Email',
            'DOB',
            'Course',
            'Preferred Branch',
            'Preferred Schedule',
            'Social Source',
            'Social Handle',
            'UTM Source',
            'UTM Medium',
            'UTM Campaign',
            'Message',
            'Forwarded To Management',
            'Created At'
        ],
        export_rows
    )

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
    payload = request.get_json(silent=True) if request.is_json else request.form
    if payload is None or not hasattr(payload, 'get'):
        abort(400)
    field = payload.get('field', '')
    value = payload.get('value', '')
    if not isinstance(field, str) or not isinstance(value, str) or len(value) > 3000:
        abort(400)
    field, value = field.strip(), value.strip()

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
        # field is checked against the fixed allowlist
        cursor.execute(f'UPDATE contacts SET {field} = ? WHERE id = ?', (value, contact_id))  # nosec B608
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
        # placeholders contain only '?' and values are bound
        cursor.execute(f'DELETE FROM contacts WHERE id IN ({placeholders})', tuple(selected_ids))  # nosec B608
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
                # placeholders contain only '?' and values are bound
                f'SELECT id, name, phone, message FROM contacts WHERE id IN ({placeholders}) ORDER BY id DESC',  # nosec B608
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
        conn.execute('BEGIN')
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

        cursor.execute('SELECT * FROM faq_items ORDER BY sort_order, id')
        faq_rows = [dict(row) for row in cursor.fetchall()]

        cursor.execute('SELECT * FROM admin_activity_log ORDER BY id DESC LIMIT 1000')
        activity_rows = [dict(row) for row in cursor.fetchall()]

    payload = {
        'metadata': {
            'exported_at': utc_now().isoformat() + 'Z',
            'app': 'ICEBERG Admin',
            'version': '1.1',
            'audit_log_limit': 1000,
        },
        'students': students_rows,
        'contacts': contacts_rows,
        'site_content': content_rows,
        'site_assets': assets_rows,
        'news_posts': news_posts_rows,
        'news_media': news_media_rows,
        'faq_items': faq_rows,
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
    app.run(debug=debug_mode, host=os.environ.get('FLASK_RUN_HOST', '127.0.0.1'), port=port)
