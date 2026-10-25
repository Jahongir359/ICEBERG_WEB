# Project review

Last updated 2026-10-26, after the code audit. The original review (19 October 2026, after the PR #22
rollback) is in Git history; this page keeps only what still applies.

## Resolved

| Earlier finding | How it was resolved |
| --- | --- |
| Flask admin: default session key and admin secrets, no CSRF, private responses cached, CSV formula injection, string-prefix path checks, uncontrolled template/CSS editor, incomplete JSON backups | The admin panel, its SQLite database, uploads and backups were removed (2026-10-26, owner decision). `app.py` only renders public pages; no secrets, sessions or writes remain. |
| Static build copied raw uploads; admin news never reached the static site | No uploads exist. Content is version-controlled: `config/news.json`, `config/faq.json`, `config/school.json`. |
| Six hosting recipes (Cloudflare, Firebase, Render, Railway, DigitalOcean, Procfile) | Cloudflare Pages is the only host; the other recipes were removed. |
| Duplicate Flask registration path (SQLite, idempotency gaps, `?success=1` confirmation) | Both forms post only to the Pages Function `/api/register`; Apps Script deduplicates by submission ID. |
| Contact defaults disagreed; numerical claims without evidence; English via Google Translate | One set of facts in `config/`; only owner-confirmed figures are shown; real Russian and English pages replace Google Translate. |
| Campaign (UTM) fields were always empty on the static site | `static/js/forms.js` reads them from the page address. |

## Open

| Priority | Finding | Next step |
| --- | --- | --- |
| Medium | `functions/api/register.js` trusts `Content-Length` for its size limit, accepts any JSON value as the body, accepts a missing Turnstile action and does not compare the Turnstile hostname. | Measure the real body size, require a JSON object, require `action === "register"` and the site hostname. |
| Medium | No CI workflow: checks run only locally and in the Cloudflare build. | Add a small GitHub Actions job running the Python and Node tests and the static build check. |
| Operational | Not verified end to end in production: Sheets receipt, Telegram message (needs `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`), ERP copy (ERP offline). | Send one test enquiry after each is configured; plan section 9. |
| Content | The course FAQ (`config/faq.json`) is old Learning Center text (mentions ACT, online lessons, hours). | Owner to confirm or correct. |
