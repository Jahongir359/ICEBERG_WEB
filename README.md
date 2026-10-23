# ICEBERG_WEB — iceberglc.com

The public website of **Iceberg School** (Iceberg Maktabi), a private school for grades 1–11 in
Uzbekistan, with **Iceberg Courses** (ICEBERG o'quv markazi: IELTS, CEFR, SAT and subject courses)
as a section of the same site. Uzbek first, mobile first, maroon + gold brand.

The staff/student portal is a separate app, the ERP at `app.iceberglc.com`
([Jahongir359/College-ERP](https://github.com/Jahongir359/College-ERP)). This site links to it and
sends enquiries to it from the server.

Guides: [`AGENTS.md`](AGENTS.md) (how the repo works, rules) ·
[`docs/plans/ICEBERG_SCHOOL_WEBSITE_PLAN.md`](docs/plans/ICEBERG_SCHOOL_WEBSITE_PLAN.md) (plan and
checklist) · [`PROJECT_REVIEW.md`](PROJECT_REVIEW.md) (open security/operations findings).

## Pages

| URL | What |
|---|---|
| `/` | Home: school poster hero, crest pillars, grade stages, parent app, team, courses band |
| `/about`, `/programs` | The school, the leader's welcome, values; grade stages 1–4 / 5–9 / 10–11 |
| `/admissions` | Steps, School enquiry form, tuition, FAQ (`/admissions/thanks` after sending) |
| `/courses`, `/register` | Iceberg Courses and course registration |
| `/news`, `/contact` | News (from the Flask admin) and contacts |
| `/our_programs`, `/questions` | Permanent redirects to `/courses` (old Learning Center URLs) |

## How it runs

- **Code:** Flask (`app.py`) with Jinja templates in `templates/site/`; styles `static/css/site.css`;
  brand tokens `static/brand/tokens.json` → `tokens.css`.
- **Live site:** Cloudflare Pages (project `iceberg-web`, `wrangler.toml`). The build
  (`scripts/build_cloudflare.sh`) renders the Flask pages to static HTML in `public/`
  (`scripts/build_firebase.py` — the name is historical) and validates them
  (`scripts/check_firebase_build.py`). Pushing to `main` deploys production.
- **Forms:** both forms post to `/api/register`, a Cloudflare Pages Function
  (`functions/api/register.js`): Turnstile check → Google Sheets through Apps Script
  (`google-apps-script/`) → a best-effort copy to the ERP's Registration leads.
- **Flask admin** (news, FAQ, contacts, leads in SQLite) runs only where `app.py` is hosted with
  Gunicorn (`Procfile`, `railway.json`, `render.yaml`, `.do/`). Confirm which host, if any, is live
  before changing those files.

## School facts

`config/school.json` holds the school's phone, address, hours, academic year, tuition, links and
the leader's name, role and message. Empty values show on the site as a dashed `[placeholder]`
and are left out of search data. Course programs and branches are in `config/registration.json`.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # then set SECRET_KEY and ADMIN_PASSWORD
python app.py                     # http://127.0.0.1:8080
```

Checks (all must pass before a commit):

```bash
python -m unittest discover -s tests -v
npm run test:registration         # Node 22: Pages Function + Apps Script tests
python scripts/build_firebase.py && python scripts/check_firebase_build.py
python scripts/build_brand_tokens.py --check
```

## Configuration

Cloudflare Pages → Settings → Variables and Secrets (never commit real values):

| Name | Kind | Purpose |
|---|---|---|
| `PUBLIC_SITE_URL`, `PUBLIC_TURNSTILE_SITE_KEY` | `[vars]` in `wrangler.toml` | Canonical URL, Turnstile widget |
| `TURNSTILE_SECRET_KEY` | secret | Server-side Turnstile check |
| `GOOGLE_SCRIPT_URL`, `GOOGLE_SCRIPT_SECRET` | secret | Apps Script receiver (see `google-apps-script/README.md`) |
| `REGISTRATION_LEADS_API_URL`, `REGISTRATION_LEADS_API_TOKEN` | secret | ERP copy: `https://app.iceberglc.com/public/registration-leads/` and the ERP's lead token |
| `SCHOOL_BRANCH_NAME` | variable (optional) | ERP branch name for School enquiries; default "Iceberg School" |

Each branch in `config/registration.json` has an `erp_branch_name`; set it to the exact ERP branch
name so branch admins see their leads.

The Flask app reads `.env` (see `.env.example`): `SECRET_KEY`, `ADMIN_PASSWORD`, `ADMIN_LOGIN_SLUG`
(admin login at `/portal/<slug>`), `DATABASE_PATH`, `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`,
`REGISTRATION_LEADS_API_URL`/`_TOKEN`, `SCHOOL_BRANCH_NAME`.
