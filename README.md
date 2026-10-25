# ICEBERG_WEB — iceberglc.com

The public website of **Iceberg School** (Iceberg Maktabi), a private school for grades 1–11 in
Uychi, Uzbekistan, with **Iceberg Courses** (ICEBERG o'quv markazi: IELTS, CEFR, SAT, Korean,
Chinese and subject courses) as a section of the same site. In Uzbek, Russian and English;
mobile first; maroon + gold brand.

The staff/student portal is a separate app, the ERP at `app.iceberglc.com`
([Jahongir359/College-ERP](https://github.com/Jahongir359/College-ERP)). This site links to it and
sends enquiries to it from the server.

Guides: [`AGENTS.md`](AGENTS.md) (how the repo works, rules) ·
[`docs/plans/ICEBERG_SCHOOL_WEBSITE_PLAN.md`](docs/plans/ICEBERG_SCHOOL_WEBSITE_PLAN.md) (plan and
checklist) · [`PROJECT_REVIEW.md`](PROJECT_REVIEW.md) (open findings).

## Pages

Each page exists in Uzbek, Russian (`/ru/…`) and English (`/en/…`).

| URL | What |
|---|---|
| `/` | Home: school poster, crest pillars, grade stages, parent app, courses band, news |
| `/about`, `/programs` | The school, leadership and team, campus photos; stages 1–4 / 5–9 / 10–11 and subjects |
| `/admissions` | Steps, School enquiry form, fees, FAQ (`/admissions/thanks` after sending) |
| `/courses`, `/register` | Iceberg Courses and course registration |
| `/news`, `/contact` | News (from `config/news.json`) and contacts with map links |
| `/hamkorlik` (`/ru/partners`, `/en/partners`) | Partnerships |
| `/ilova` | "Coming soon" page for the portal and app (noindex) |

## How it works

```
templates/site/*.html ─┐
config/*.json ─────────┼─ app.py (Flask + Jinja) ── scripts/build_static.py ── public/ ── Cloudflare Pages
translations/*.json ───┘                                                                        │
                       forms (static/js/forms.js) ── POST /api/register (functions/api/register.js)
                                                     ├─ Turnstile check
                                                     ├─ Google Sheets via Apps Script (primary store)
                                                     └─ best effort: ERP lead + Telegram message
```

- **Live site:** Cloudflare Pages (project `iceberg-web`, `wrangler.toml`). Pushing to `main`
  deploys; every pull request gets a preview build. The build runs `scripts/build_cloudflare.sh`:
  `build_static.py` renders all pages to `public/`, `check_static_build.py` checks links, forms,
  sitemap, redirects and headers.
- **Content:** school facts in `config/school.json`, news in `config/news.json`, course FAQ in
  `config/faq.json`, programs and branches in `config/registration.json`. Text is Uzbek; its
  Russian and English are in `translations/ru.json` and `translations/en.json`.
- **Design:** `static/css/site.css` on brand tokens `static/brand/tokens.json` → `tokens.css`;
  motion in `static/js/site.js`.

| Path | What |
|---|---|
| `app.py` | Page routes, translations (`_()`), sitemap, robots, old-URL redirects |
| `templates/site/` | Page templates and shared pieces (`base.html`, `_macros.html`, `_*.html`) |
| `config/`, `translations/` | Content and its translations |
| `static/` | CSS, JS, brand tokens, images, icons |
| `functions/api/register.js` | The form handler (Cloudflare Pages Function) |
| `google-apps-script/` | The Google Sheets receiver and its setup guide |
| `scripts/` | Static build and checks, brand token generator |
| `cloudflare/_headers` | Security headers for every response |
| `tests/` | Python page tests, Node form-handler tests |

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py                     # preview on http://127.0.0.1:8080
```

The forms need the Pages Function: `python scripts/build_static.py`, copy `.dev.vars.example` to
`.dev.vars` and fill it in, then `npx wrangler pages dev public`.

Checks (all must pass before a commit; GitHub Actions runs them on every pull request too):

```bash
python -m unittest discover -s tests -v
npm run test:registration         # Node 22: Pages Function + Apps Script tests
python scripts/build_static.py && python scripts/check_static_build.py
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
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | secret | Detailed message for each request to the support chat |
| `SCHOOL_BRANCH_NAME` | variable (optional) | ERP branch name for School enquiries; default "Iceberg School" |

Each branch in `config/registration.json` has an `erp_branch_name`; set it to the exact ERP branch
name so branch admins see their leads.
