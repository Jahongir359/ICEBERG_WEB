# ICEBERG_WEB

ICEBERG_WEB is a Flask web application for ICEBERG education center. It serves as:

- A public marketing site (about, programs, FAQ, contact)
- A student registration pipeline
- An admin dashboard for managing leads and registrations
- A Telegram notification bridge for new messages and enrollments

## Main Purpose

The primary goal is to convert website visitors into student leads, then help admins track and manage those leads from one place.

## Features

- Public pages: home, about, programs, FAQ, contact
- Student registration form
- Contact form with database storage
- Telegram alerts for new registrations and messages
- Admin login and protected dashboard
- Admin lists for students and contact submissions
- Delete actions for students and contacts
- Admin image manager to replace website pictures without code changes
- Admin content manager to edit site texts, links, and custom CSS without code changes

## Tech Stack

- Python + Flask
- SQLite
- Tailwind CSS (CDN)
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

- `SECRET_KEY`: Flask secret key for sessions (required in production)
- `ADMIN_PASSWORD`: Admin login password
- `ADMIN_SECRET_CODE`: optional extra secret value used by internal admin access checks
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
	- `ADMIN_SECRET_CODE`
	- `ADMIN_LOGIN_SLUG`
	- `FLASK_ENV=production`
5. (Important for SQLite persistence) Add a Railway Volume and set:
	- `DATABASE_PATH=/data/database.db`
6. Deploy.

Your app will be public on a permanent Railway domain.

## Deploy (Render)

This repository includes `render.yaml` using Gunicorn.

Important: define all required environment variables in Render dashboard.

## Deploy (DigitalOcean App Platform)

Use the same Gunicorn start command as Render:

`gunicorn app:app --bind 0.0.0.0:$PORT`

Set these environment variables in DigitalOcean:

- `SECRET_KEY`
- `ADMIN_PASSWORD`
- `ADMIN_SECRET_CODE`
- `ADMIN_LOGIN_SLUG`
- `FLASK_ENV=production`
- `DATABASE_PATH` if you want the SQLite file stored outside the container default

If those admin variables are omitted, the app falls back to `iceberg-admin` and `iceberg-portal` so the hidden login path stays consistent across deployments.

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

The static contact form opens a pre-filled WhatsApp message. The registration form
submits to a Cloudflare Pages Function, validates Turnstile server-side, and stores the
lead in Google Sheets through Apps Script. Override the public domain or contact-form
WhatsApp number during the build when needed:

```bash
PUBLIC_SITE_URL=https://www.example.com \
PUBLIC_WHATSAPP_NUMBER=998901234567 \
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

For the production deployment, add this environment variable in
**Workers & Pages → your project → Settings → Environment variables**:

```text
PUBLIC_SITE_URL=https://iceberglc.com
```

The static registration form saves leads to Google Sheets through a Cloudflare Pages
Function. Follow the complete setup and troubleshooting runbook in
`google-apps-script/README.md`, then configure:

- Build variable: `PUBLIC_TURNSTILE_SITE_KEY`
- Encrypted secrets: `TURNSTILE_SECRET_KEY`, `GOOGLE_SCRIPT_URL`, and
  `GOOGLE_SCRIPT_SECRET`

The registration endpoint will remain unavailable until all four values are set.
`TURNSTILE_SITE_KEY` is also accepted as a backwards-compatible build-variable
name, but `PUBLIC_TURNSTILE_SITE_KEY` remains the documented default.
The contact form continues to open WhatsApp.

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
