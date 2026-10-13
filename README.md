# ICEBERG_WEB

ICEBERG_WEB is a Flask web application for ICEBERG education center. It serves as:

- A public marketing site (about, programs, FAQ, contact)
- A student registration pipeline
- An admin dashboard for managing leads and registrations
- A Telegram notification bridge for new messages and enrollments

## Main Purpose

The primary goal is to convert website visitors into student leads, then help admins track and manage those leads from one place.

## Features

- Uzbek and English public pages: home, about, programs, results, student life,
  international cooperation, planned private school, news, admissions, FAQ,
  contact, privacy, and course inquiry
- Student registration form
- Contact inquiry drafts that open the Telegram admissions chat
- Telegram alerts for new registrations
- Admin login and protected dashboard
- Admin lists for students and contact submissions
- Delete actions for students and contacts
- Admin image manager to replace website pictures without code changes
- Admin content manager to edit site texts, links, and custom CSS without code changes

## Tech Stack

- Python + Flask
- SQLite
- Local CSS for public pages; Tailwind CSS (CDN) for the admin interface
- Gunicorn for production startup

## Quick Start

1. Clone and enter the project:

```bash
git clone <repo-url>
cd ICEBERG_WEB
```

2. Create and activate virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure environment variables:

```bash
cp .env.example .env
```

5. Run locally:

```bash
python app.py
```

Open http://127.0.0.1:8080

## Environment Variables

Set these in `.env` (or your deployment platform):

- `SECRET_KEY`: unique random session secret, at least 32 characters
- `ADMIN_PASSWORD`: unique admin password, at least 12 characters
- `ADMIN_LOGIN_SLUG`: hidden admin login path slug (example: `iceberg-portal`)
- `DATABASE_PATH`: SQLite file path (default: `database.db`)
- `TELEGRAM_BOT_TOKEN`: Telegram bot token (optional)
- `TELEGRAM_CHAT_ID`: Telegram chat ID (optional)
- `REGISTRATION_LEADS_API_URL`: optional management/ERP endpoint that receives registration leads
- `REGISTRATION_LEADS_API_TOKEN`: bearer token sent to the ERP endpoint (optional)
- `REGISTRATION_LEADS_API_TIMEOUT`: ERP request timeout in seconds (default: `8`)
- `FLASK_ENV`: set to `production` in production

If Telegram variables are missing, app still works without notifications.
If the ERP lead forwarding URL is blank, registrations are still saved locally and Telegram notifications still run.

## Registration Lead Forwarding

When `REGISTRATION_LEADS_API_URL` is configured, every successful `/register` submission is copied to the management system with a JSON `POST`.

If `REGISTRATION_LEADS_API_TOKEN` is set, the request includes:

`Authorization: Bearer <REGISTRATION_LEADS_API_TOKEN>`

Payload shape:

```json
{
  "full_name": "Student Name",
  "phone": "+998901234567",
  "source": "website",
  "submitted_at": "2026-06-05T12:00:00+00:00",
  "parent_phone": "+998991112233",
  "email": "student@example.com",
  "course": "IELTS",
  "branch": "Main branch",
  "preferred_schedule": "Evening",
  "date_of_birth": "2010-01-01",
  "social_source": "Instagram",
  "social_handle": "@student",
  "utm_source": "instagram",
  "utm_medium": "ads",
  "utm_campaign": "summer-intake",
  "message": "Interested in weekend classes"
}
```

Only `full_name`, `phone`, `source`, and `submitted_at` are always sent by the website. The other fields are optional and are omitted when blank.

The ERP endpoint should return any `2xx` response for success. If the ERP is down or returns an error, the website keeps the local registration and logs the forwarding failure.
For a Django management backend, the receiving endpoint should be an API endpoint that accepts server-to-server POSTs. If it is a normal Django form view, make it CSRF-exempt or use Django REST Framework/token authentication; otherwise Django can reject the request before saving the lead.

Production values:

```env
REGISTRATION_LEADS_API_URL=https://your-production-api.example/registration-leads/
REGISTRATION_LEADS_API_TOKEN=replace-with-shared-token
REGISTRATION_LEADS_API_TIMEOUT=8
```

On DigitalOcean App Platform, set `REGISTRATION_LEADS_API_TOKEN` as an encrypted runtime environment variable if the Django endpoint requires the shared token.

Manual test:

```bash
curl -i -X POST "https://your-production-api.example/registration-leads/" \
  -H "Authorization: Bearer YOUR_SHARED_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Test Lead","phone":"+998900000000","course":"IELTS","source":"website"}'
```

Set `ADMIN_PASSWORD` and `ADMIN_LOGIN_SLUG` in `.env`.

Admin login URL format:

`/portal/<ADMIN_LOGIN_SLUG>`

If you want to change the login password later, update `ADMIN_PASSWORD` in `.env` and restart the app.

## Deploy (Railway - Recommended)

This repository is pre-configured for Railway with:

- `Procfile`
- `railway.json`
- Gunicorn production startup

### Steps

1. Push project to GitHub.
2. In Railway, click **New Project** -> **Deploy from GitHub repo**.
3. Select this repository.
4. Add environment variables in Railway:
	- `SECRET_KEY`
	- `ADMIN_PASSWORD`
	- `ADMIN_LOGIN_SLUG`
	- `FLASK_ENV=production`
5. (Important for SQLite persistence) Add a Railway Volume and set:
	- `DATABASE_PATH=/data/database.db`
6. Deploy.

Your app will be public on a permanent Railway domain.

## Deploy (Render)

This repository includes `render.yaml` using Gunicorn.

Important: define all required environment variables in Render dashboard.

## DigitalOcean App Platform — storage prerequisites

Use the same Gunicorn start command as Render:

`gunicorn app:app --bind 0.0.0.0:$PORT`

The checked-in DigitalOcean spec disables deploy-on-push. App Platform local storage is ephemeral and does not provide persistent volumes; this SQLite-based backend needs a durable database/media design before use there. Applying the manifest is separate from changing existing dashboard settings. See [DigitalOcean storage documentation](https://docs.digitalocean.com/products/app-platform/how-to/store-data/).

Set these environment variables only after resolving persistence:

- `SECRET_KEY`
- `ADMIN_PASSWORD`
- `ADMIN_LOGIN_SLUG`
- `FLASK_ENV=production`
- `DATABASE_PATH` if you want the SQLite file stored outside the container default

Admin access is disabled unless both a secure `SECRET_KEY` and `ADMIN_PASSWORD` are configured. The old public default and alternate secret-code logins are rejected. Public pages continue to work when admin access is disabled.

## Deploy the public site to Firebase Hosting (Spark/free plan)

Firebase Hosting serves the public marketing pages as pre-rendered static HTML. The
Flask admin, SQLite database, Telegram integration, and server-side form processing
remain on the existing backend because Firebase Hosting does not execute Python.

The generated `public/` directory is intentionally ignored by Git. Rebuild it before
each local preview. `firebase deploy` also runs the build and validation automatically
through its predeploy hooks:

```bash
python scripts/build_firebase.py
python scripts/check_firebase_build.py
npx firebase-tools emulators:start --only hosting
npx firebase-tools deploy --only hosting --project YOUR_FIREBASE_PROJECT_ID
```

The contact form opens a pre-filled Telegram draft for the visitor to review and
send to `iceberg_qabulxona`. Configure that chat in `config/registration.json`.
The registration form
submits to a Cloudflare Pages Function, validates Turnstile server-side, and stores the
lead in Google Sheets through Apps Script. Override the public domain when needed:

```bash
PUBLIC_SITE_URL=https://www.example.com \
python scripts/build_firebase.py
```

Firebase setup:

1. Create a Firebase project and enable Hosting in the Firebase console.
2. Install or run the Firebase CLI and authenticate with `firebase login`.
3. Run the build command above.
4. Preview locally with the Hosting emulator.
5. Deploy with `firebase deploy --only hosting --project YOUR_FIREBASE_PROJECT_ID`.
6. Add `iceberglc.com` as a custom domain in Firebase Hosting, then apply the DNS
   records shown by Firebase.

`firebase.json` enables clean URLs, a custom 404 page, conservative HTML caching,
longer asset caching, and baseline browser security headers. Do not run
`firebase init hosting` over this configuration unless you intend to replace it.

## Deploy the landing page to Cloudflare Pages

Use the following Cloudflare Pages build settings:

- Framework preset: `None`
- Build command: `bash scripts/build_cloudflare.sh`
- Build output directory: `public`
- Root directory: leave blank (repository root)

The repository pins Python in `.python-version`. Keep this pin in place because
the static build imports the Flask application and therefore requires Python's
compiled SQLite module; Cloudflare's default Python 3.13 build currently omits it.

The checked-in `wrangler.toml` also declares `public` as the Pages output directory,
which prevents Cloudflare from publishing the Jinja files in `templates/` as raw
text. Do not set the output directory to the repository root or to `templates`.

The build includes a top-level `index.html`, `404.html`, and `_headers` file.
Cloudflare Pages automatically serves matching HTML files at extensionless routes,
so `/about`, `/contact`, and the other public URLs work without redirect rules.
The `_headers` file adds baseline browser security headers while leaving asset
caching to Cloudflare Pages' deployment-aware defaults.

Public Cloudflare configuration is maintained under `[vars]` in `wrangler.toml` because
that file is the Pages project's source of truth. It contains `PUBLIC_SITE_URL` and the
public `PUBLIC_TURNSTILE_SITE_KEY`. Update and deploy that file instead of trying to edit
plain variables in the Dashboard.

The static registration form saves leads to Google Sheets through a Cloudflare Pages
Function. Follow the complete setup and troubleshooting runbook in
`google-apps-script/README.md`, then configure:

- Wrangler public vars: `PUBLIC_SITE_URL` and `PUBLIC_TURNSTILE_SITE_KEY`
- Dashboard encrypted Secrets: `TURNSTILE_SECRET_KEY`, `GOOGLE_SCRIPT_URL`, and
  `GOOGLE_SCRIPT_SECRET`

The registration endpoint remains unavailable until all values are deployed. Do not
put private secret values in `wrangler.toml`.
The contact form continues to open Telegram.

### Registration programs, branches, and reception contact

Maintain registration choices only in `config/registration.json`:

- add a new object with a unique stable `id` to add a program or branch;
- change `name` to rename its user-facing label without changing stored IDs;
- set `active` to `false` to remove it from the form and server allowlist;
- update the `contact` object for the call-center and reception Telegram links.

Do not duplicate these values in templates or frontend JavaScript. Flask reads
this file directly, and the static build publishes the same file for Cloudflare's
server-side registration validation. Deploy the website after any configuration
change so the form and endpoint always use the same version.

Preview deployments automatically use Cloudflare's `CF_PAGES_URL`. To test or
deploy from the command line:

```bash
bash scripts/build_cloudflare.sh
npx wrangler pages dev public
npx wrangler pages deploy public
```

## Admin Image Management

After admin login, open **Rasmlarni Boshqarish** from the admin sidebar.

- Upload a new image for any listed slot.
- Allowed formats: JPG, JPEG, PNG, WEBP, GIF.
- Updated image is applied automatically on relevant pages.

Covered assets include:

- Logos (public and admin pages)
- Home hero and method image
- About hero and team photos
- Contact hero image
- Programs hero and all course card photos

## Admin Content Management

After admin login, open **Sayt Kontenti** from the admin sidebar.

- Edit core UI texts (header, footer, homepage, about, contact, register, FAQ).
- Update contact links (email, phone, map URL) and social links.
- Add custom CSS from admin (`custom_css`) to change visual styling globally.
- Add custom content keys for future template usage.

## Security Notes

- Do not commit real bot tokens, chat IDs, admin passwords, or secret keys.
- Keep `.env` out of git (already ignored).
- Use a strong `ADMIN_PASSWORD` and `SECRET_KEY` in production.

## Public content and languages

Public pages have dedicated Uzbek and English URLs: `/` and `/en`, with matching
paths such as `/international` and `/en/international`. Copy for the informational
pages lives in `public_content.py`; course and branch choices live in
`config/registration.json`. Contact inquiries open the configured Telegram
admissions chat with a draft. The visitor must review and send it in Telegram.
Registration still uses Flask when served dynamically, or `/api/register` on
Cloudflare Pages. Firebase requires a separately configured registration backend;
this repository's Firebase Hosting configuration alone does not provide one.

No student totals, score claims, tuition amounts, agreements, or campus photographs
have been invented. The private school is labeled as a separate planned project,
with opening planned for September 2027. Staff should confirm this date and all
institutional facts before publishing.

To publish verified course details, add `details.uz` and `details.en` objects to the
relevant program in `config/registration.json`. Supported text fields are
`age_level`, `duration_schedule`, `class_teacher`, `methods`, and `tuition`.
Missing values show an admissions inquiry prompt. Include lesson length and weekly
frequency in `duration_schedule`, and payment periods/materials costs in `tuition`.

### Publish CMS content on a static host

Static builds read `config/public_content.json`. To export reviewed public records
from the Flask CMS, run on the machine containing its database and uploaded media:

```bash
python scripts/export_public_content.py --database /path/to/database.db
```

The export includes only published news, public FAQs, approved asset references,
and the supported public text keys (`hero_main_title`, `hero_main_subtitle`,
`contact_email`). It copies referenced local media into `static/published/`.
Applications, contacts, credentials, unknown content keys, and unpublished news
are excluded. Review the exported copy and media permissions, transfer the snapshot
and `static/published/` to the website checkout, then rebuild and deploy. Edits in
Flask do not automatically trigger a static deployment.

The static build excludes raw `static/uploads/` and unreferenced exported media.
Only snapshot-referenced media is copied into generated output. Do not use a
complete admin database backup as a public content source.

```bash
python -m unittest discover -s tests -p 'test_*.py'
npm run test:registration
python scripts/build_firebase.py
python scripts/check_firebase_build.py
```

The build checker validates pages, local links, language alternates, basic form
labels, document landmarks, sitemap coverage, and private markers. It does not
replace browser/mobile testing, Lighthouse measurements, or production receipt
verification.

## Audit and release checks

See `CODE_AUDIT.md` for the repository review, fixes, validation, and deployment
follow-ups. Admin forms and JSON mutations require a session CSRF token; logout
is POST-only. Only `ADMIN_PASSWORD` authenticates an admin. Sessions expire after
eight hours, and private pages, registrations, CSV exports, and database backups
are never publicly cacheable. The JSON database backup includes FAQs; uploaded
media must be backed up separately.

Flask registrations carry a per-form UUID. Repeating a UUID preserves one database
record and avoids repeated forwarding/notifications. A success URL alone does not
produce a confirmation. Static registration uses a per-browser submission UUID
and the existing Apps Script deduplication. Both endpoints enforce request limits;
Cloudflare also checks Turnstile action and hostname.

For the optional isolated browser/security tools:

```bash
python -m pip install -r requirements-dev.txt
python -m playwright install --with-deps chromium
python scripts/check_browser.py
python -m bandit -r app.py public_content.py scripts add_column.py
python -m pip_audit -r requirements.txt
```

The browser script uses a temporary test database and disables external delivery.
GitHub Actions runs the Python tests, Node tests, static build, and build checker
on pull requests and pushes to main. The action revisions are pinned. Production
rate limiting, persistent storage/backups, account ownership, and live message
receipt remain hosting checks.
