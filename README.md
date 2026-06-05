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
- `REGISTRATION_LEADS_API_URL`: management/ERP endpoint that receives registration leads (defaults to `https://app.iceberglc.com/public/registration-leads/`)
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
REGISTRATION_LEADS_API_URL=https://app.iceberglc.com/public/registration-leads/
REGISTRATION_LEADS_API_TOKEN=replace-with-shared-token
REGISTRATION_LEADS_API_TIMEOUT=8
```

On DigitalOcean App Platform, set `REGISTRATION_LEADS_API_TOKEN` as an encrypted runtime environment variable if the Django endpoint requires the shared token.

Manual test:

```bash
curl -i -X POST "https://app.iceberglc.com/public/registration-leads/" \
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
