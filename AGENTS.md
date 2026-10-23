# AGENTS.md — guide for AI agents working on the iceberglc.com website

Read this first, then [`docs/plans/ICEBERG_SCHOOL_WEBSITE_PLAN.md`](docs/plans/ICEBERG_SCHOOL_WEBSITE_PLAN.md).
This repo owns the website: its plan, design tokens, logos copies, pages and lead handler. The ERP
(`College-ERP`) only receives leads and hosts the portal.
Before a security or backend change, also read [`PROJECT_REVIEW.md`](PROJECT_REVIEW.md) (open findings
after the PR #22 rollback).

## What this site is

**iceberglc.com is the Iceberg School website** (private school, grades 1–11, maroon crest), with the
former Learning Center as its **Iceberg Courses** section (owner decision 2026-10-23, plan section 0).
The whole site uses `<html data-brand="school">`.

| URL | Template (`templates/site/`) |
|---|---|
| `/` | `home.html` |
| `/about`, `/programs` | `about.html`, `programs.html` |
| `/admissions`, `/admissions/thanks` | `admissions.html` (School enquiry form), `thanks.html` |
| `/courses`, `/register` | `courses.html` (ICEBERG o'quv markazi), `register.html` (course registration) |
| `/news`, `/contact` | `news.html`, `contact.html` |
| `/our_programs`, `/questions` | 301 → `/courses`, `/courses#savollar` (Flask routes + generated `_redirects`) |

Shared pieces: `site/base.html` (header, mobile menu, dock, footer, JSON-LD), `site/_macros.html`
(`icon()`, `fact()`), `_stages.html`, `_cta.html`, `_news_card.html`. Styles: `static/css/site.css`;
script: `static/js/site.js`; forms: `static/js/firebase-forms.js`. `templates/base.html` with
`style.css`/`tailwind.css` now only serves the Flask admin login.

The staff/student portal is a separate app — the ERP at `app.iceberglc.com` (repo `College-ERP`).
This site only links to it (`https://app.iceberglc.com/login/?brand=school`) and sends enquiries to
it from the server.

## Active initiative

Plan section 10, phases **4c → 4e**: owner fills `config/school.json`, reviews copy, then launch
checks (section 9) and deploy. Tick the checklist there and add a dated line to its progress notes.

## Stack and layout

| Item | Value |
|---|---|
| Framework / language | Flask (`app.py`, one file) + Jinja templates, SQLite; Python 3.13 |
| Hosting / deploy | **Live site: Cloudflare Pages** (project `iceberg-web`, `wrangler.toml`). The build (`scripts/build_cloudflare.sh`) runs `scripts/build_firebase.py`, which renders the Flask templates to static HTML in `public/` (git-ignored), then `scripts/check_firebase_build.py` validates it. `firebase.json`, `railway.json`, `render.yaml`, `Procfile` are older/alternative hosts for the Flask app — which one (if any) is live must be confirmed with the owner (`PROJECT_REVIEW.md`). |
| Templates / pages folder | `templates/` (`base.html` layout; public pages `index.html`, `about.html`, `our_programs.html`, `news.html`, `questions.html`, `contact.html`, `register.html`; admin pages `admin_*.html`, `students.html`, `contacts_list.html`) |
| Static files | `static/` → served at `/static/` (`static/css/style.css`, `static/js/firebase-forms.js`, `static/img/`) |
| Lead handler (`POST /api/register`) | `functions/api/register.js` (Cloudflare Pages Function): Turnstile check → Google Sheets via Apps Script (`google-apps-script/Code.gs`) → best-effort copy to the ERP when its secrets are set. The Flask `/register` route in `app.py` is the server-rendered equivalent (SQLite + Telegram + ERP). |
| Programs / branches | `config/registration.json` (published as `/registration-options.json`; each branch's `erp_branch_name` must equal the ERP branch name) |
| School facts | `config/school.json` — phone, address, hours, year, tuition, links. Empty = visible `[placeholder]`, left out of JSON-LD |
| Secrets live in | Cloudflare Pages → Settings → Variables and Secrets (encrypted): `TURNSTILE_SECRET_KEY`, `GOOGLE_SCRIPT_URL`, `GOOGLE_SCRIPT_SECRET`, `REGISTRATION_LEADS_API_URL`, `REGISTRATION_LEADS_API_TOKEN`; optional variable `SCHOOL_BRANCH_NAME`. Public values are `[vars]` in `wrangler.toml`. Flask hosts use env vars (`.env.example`). Never in the repo. |

## Commands

```bash
pip install -r requirements.txt                  # Flask, gunicorn, requests
python app.py                                    # local Flask site on http://127.0.0.1:8080
python -m unittest discover -s tests -v          # Flask tests
npm run test:registration                        # Pages Function + Apps Script tests (Node 22)
python scripts/build_firebase.py && python scripts/check_firebase_build.py   # static build + checks
node --check functions/api/register.js
npm install && npm run build:css                 # after changing Tailwind classes in templates/JS
python scripts/build_brand_tokens.py             # after editing static/brand/tokens.json
```

`static/css/tailwind.css` and `static/brand/tokens.css` are generated but committed, because the
Cloudflare build runs Python only. Rebuild and commit them with the change that needs them.

All of them must pass before a commit. There is no CI workflow in this repo yet.

## Brand rules

- **This repo owns the website's design.** `static/brand/tokens.json` (colours, fonts, radii) is the
  source for `tokens.css`; `static/school/img/` holds the School logos and photos. The core maroon/teal
  brand colours and the logo originals are shared with the ERP (`College-ERP/docs/brand/iceberg-school/`)
  — if a core colour or logo changes, update both repos. Gold/cream/paper and Fraunces are website-only.
- Pages and components use only `var(--brand-*)` (or `rgb(var(--brand-*-rgb) / a)`, or Tailwind
  `brand-*` classes) — no new hex values in templates or page CSS.
- `templates/site/base.html` is the one public layout; new pages extend it and reuse `.card`, `.btn`,
  `.sec`, `.page-hero`, `.form-card`, `.faq` from `site.css` rather than adding page CSS.
- Fonts: Fraunces (warm serif, `--brand-font-display`) for headings, Inter (`--brand-font`) for body,
  buttons, labels and kickers. Colours: maroon + gold on cream/paper (`--brand-gold*`, `--brand-cream`,
  `--brand-paper`); gold as text only in its `-ink` shade on light grounds.
- Motion: `.rv` reveal on scroll, `[data-split]` word rise, card lift with gold rule, marquee, page
  view transitions — all off under `prefers-reduced-motion`.
- Test every change at 390 px first (no horizontal scroll, dock not covering content), then desktop.

## Content rules

- Uzbek first; Russian and English as real pages with `hreflang` (plan 4.0 step 4). No new string
  ships without its Uzbek text.
- **Never invent facts** — grades, prices, numbers, results, addresses, phones. Use a visible
  `[PLACEHOLDER]` until the owner supplies them.
- Every page: unique `<title>` and description, one `<h1>`, canonical on `https://iceberglc.com/…`,
  OG/Twitter tags, the right JSON-LD (School pages: `School`, plan section 5). Public URLs go in
  `sitemap.xml`; don't loosen `robots.txt`.
- Existing LC URLs never change; if a page must move, add a 301. `/register` and `/api/register`
  keep working throughout.

## Lead form → ERP

- Browser posts only to this site's `/api/register`. Only the server handler calls the ERP
  (`POST https://app.iceberglc.com/public/registration-leads/`, `Authorization: Bearer
  $REGISTRATION_LEADS_API_TOKEN`). Never call the ERP or expose the token from browser JavaScript.
- Google Sheets stays the primary store; the ERP copy is best-effort and must never fail an
  application that Sheets stored.
- Branch codes from the LC form (`main`, `gayrat`) are mapped to the **exact ERP branch names**
  through `erp_branch_name` in `config/registration.json`; `unknown` → empty. Until those names are
  filled in, the code is sent and only ERP super admins see the leads.
- School enquiries (`/admissions`): `form_type=school-enquiry`, Sheets `program=grade-N`,
  `branch=school`; ERP `source="school-website"`, `program="Grade N"`, `branch=$SCHOOL_BRANCH_NAME`
  (default "Iceberg School"). Keep Turnstile, honeypot, consent and UTM fields.

## Working conventions

- Small, focused changes; match the surrounding code style; don't reformat untouched files.
  PR #22 was reverted because it mixed a redesign with security and hosting changes — keep those
  in separate PRs.
- Screenshot changed pages at 390 px and desktop and show the owner.
- Before a release, run plan section 9 (Lighthouse, Rich Results, end-to-end enquiry into the ERP).
- Commit messages: `type(scope): summary` — e.g. `feat(school): add admissions page`,
  `fix(leads): map branch codes to ERP names`, `style(brand): generate tokens.css`.
- Commit or push only when the owner asks; branch off `main` first.
- Secrets only in the hosting provider's settings; never commit real values.
