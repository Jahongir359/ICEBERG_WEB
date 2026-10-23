# AGENTS.md — guide for AI agents working on the iceberglc.com website

Read this first, then [`docs/plans/ICEBERG_SCHOOL_WEBSITE_PLAN.md`](docs/plans/ICEBERG_SCHOOL_WEBSITE_PLAN.md).
The plan's source of truth is the ERP repo (`College-ERP/docs/plans/`); this copy is for reference.
Before a security or backend change, also read [`PROJECT_REVIEW.md`](PROJECT_REVIEW.md) (open findings
after the PR #22 rollback).

## What this site is

The public website for two brands on one domain:

| Brand | URLs | `data-brand` | Look |
|---|---|---|---|
| **ICEBERG Learning Center** (language/exam courses, Namangan) | `iceberglc.com/`, `/about`, `/our_programs`, `/news`, `/questions`, `/contact`, `/register` | `center` | palette per plan 4.0.1 |
| **Iceberg School** (private school) — *not built yet* | `iceberglc.com/school`, `/school/about`, `/school/programs`, `/school/admissions`, `/school/admissions/thanks`, `/school/contact`, `/school/news` | `school` | maroon `#4C0909`, crest logo |

The staff/student portal is a separate app — the ERP at `app.iceberglc.com` (repo `College-ERP`).
This site only links to it (`https://app.iceberglc.com/login/?brand=school` from School pages) and
sends enquiries to it from the server.

## Active initiative

Move the site onto the shared Iceberg design system and add the School pages — plan section 10,
phases **4b → 4e**. Tick the checklist there and add a dated line to its progress notes each session.

## Stack and layout

| Item | Value |
|---|---|
| Framework / language | Flask (`app.py`, one file) + Jinja templates, SQLite; Python 3.13 |
| Hosting / deploy | **Live site: Cloudflare Pages** (project `iceberg-web`, `wrangler.toml`). The build (`scripts/build_cloudflare.sh`) runs `scripts/build_firebase.py`, which renders the Flask templates to static HTML in `public/` (git-ignored), then `scripts/check_firebase_build.py` validates it. `firebase.json`, `railway.json`, `render.yaml`, `Procfile` are older/alternative hosts for the Flask app — which one (if any) is live must be confirmed with the owner (`PROJECT_REVIEW.md`). |
| Templates / pages folder | `templates/` (`base.html` layout; public pages `index.html`, `about.html`, `our_programs.html`, `news.html`, `questions.html`, `contact.html`, `register.html`; admin pages `admin_*.html`, `students.html`, `contacts_list.html`) |
| Static files | `static/` → served at `/static/` (`static/css/style.css`, `static/js/firebase-forms.js`, `static/img/`) |
| Lead handler (`POST /api/register`) | `functions/api/register.js` (Cloudflare Pages Function): Turnstile check → Google Sheets via Apps Script (`google-apps-script/Code.gs`) → best-effort copy to the ERP when its secrets are set. The Flask `/register` route in `app.py` is the server-rendered equivalent (SQLite + Telegram + ERP). |
| Programs / branches | `config/registration.json` (published as `/registration-options.json`; each branch's `erp_branch_name` must equal the ERP branch name) |
| Secrets live in | Cloudflare Pages → Settings → Variables and Secrets (encrypted): `TURNSTILE_SECRET_KEY`, `GOOGLE_SCRIPT_URL`, `GOOGLE_SCRIPT_SECRET`, `REGISTRATION_LEADS_API_URL`, `REGISTRATION_LEADS_API_TOKEN`. Public values are `[vars]` in `wrangler.toml`. Flask hosts use env vars (`.env.example`). Never in the repo. |

## Commands

```bash
pip install -r requirements.txt                  # Flask, gunicorn, requests
python app.py                                    # local Flask site on http://127.0.0.1:8080
python -m unittest discover -s tests -v          # Flask tests
npm run test:registration                        # Pages Function + Apps Script tests (Node 22)
python scripts/build_firebase.py && python scripts/check_firebase_build.py   # static build + checks
node --check functions/api/register.js
```

All of them must pass before a commit. There is no CI workflow in this repo yet.

## Brand rules

- **Brand files are copies.** Source of truth is the ERP repo: `docs/brand/iceberg-school/tokens.json`
  (colours/font/radii for both brands) and `docs/brand/iceberg-school/web/*.png` (School logos). Here
  they will live in `/static/brand/tokens.json`, `/static/brand/tokens.css` (generated) and
  `/static/school/img/`. To change a colour, change `tokens.json` in the ERP repo first, then copy.
- Pages and components use only `var(--brand-*)` — no hex values in templates or page CSS.
- One shared base layout takes a `brand` (name, logos, nav, footer, theme-color, JSON-LD, Portal URL)
  and sets `<html data-brand="…">`. LC and School pages differ only in content and brand.
- Font: Inter on every page.
- No automatic redirects between brands; each links to the other (LC → "Iceberg School",
  School → "Part of the Iceberg family · Iceberg Learning Center").

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
- School enquiries: `form_type=school-enquiry`, mapped as in plan section 6, `source="school-website"`,
  `branch=$SCHOOL_BRANCH_NAME`. Keep Turnstile, honeypot, UTM fields and the Telegram fallback.

## Working conventions

- Small, focused changes; match the surrounding code style; don't reformat untouched files.
  PR #22 was reverted because it mixed a redesign with security and hosting changes — keep those
  in separate PRs.
- Screenshot every LC page before and after the re-skin (desktop and 390 px) and show the owner.
- Before a release, run plan section 9 (Lighthouse, Rich Results, end-to-end enquiry into the ERP).
- Commit messages: `type(scope): summary` — e.g. `feat(school): add admissions page`,
  `fix(leads): map branch codes to ERP names`, `style(brand): generate tokens.css`.
- Commit or push only when the owner asks; branch off `main` first.
- Secrets only in the hosting provider's settings; never commit real values.
