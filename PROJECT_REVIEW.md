# Project review — 19 October 2026

## Rollback

The last remote merge was PR #22, `f2c236e`, containing `edf1996`.
It combined a public-site rewrite, bilingual content, security fixes, static
publishing changes, dependency pins, CI, and hosting changes across 48 files.
GitHub Actions and the Cloudflare Pages check both reported success for it.

Revert commit `fc73c90` undoes that merge using its first parent. Its tree was
verified identical to `0434428`, the main branch immediately before PR #22.
This preserves PRs #19–21, including registration caching, Sheets receiver, and
Wrangler configuration fixes. The feature branch and original commits remain
available. This review is a separate documentation addition after the revert.

The rollback affects tracked code and configuration. It does not restore a
production database, remove columns added by the reverted application, change
dashboard settings, or redeploy Google Apps Script. The old application inserts
explicit columns, so extra schema columns alone do not require deletion. Actual
production data and host configuration still need verification.

## Scope and evidence

Reviewed Flask route groups and database/file helpers, public/admin templates,
styles and browser scripts, Cloudflare registration, Apps Script, static build
and validation scripts, tests, deployment manifests, dependencies, documentation,
and Git/PR/check history. Findings below describe the restored code. This is a
repository review with isolated runtime checks, not a production security test.
No real applications or messages were sent. No unrelated fixes were applied.

## Missing or broken, by priority

| Priority | Finding and evidence | Recommended next change |
| --- | --- | --- |
| Critical if Flask is exposed with defaults | `app.py:44` supplies a known session signing key; `.env.example` also supplies known admin/secret values. In an isolated database, a cookie signed with the default key opened `/admin/dashboard` with HTTP 200. | Reapply fail-closed credentials and a random session secret in a small security-only PR; verify actual host settings. |
| High, Flask | Admin writes have no CSRF validation. An authenticated backup POST without a token returned 200; login without a token succeeded. Logout also changes state through GET. | Restore CSRF checks, POST logout, session rotation and expiry; add edge login limits. |
| High, static publishing | `scripts/build_firebase.py:92` copies all of `static/`, including any raw uploads present. Flask serves static files directly, so knowing a draft upload URL can bypass news publication status. | Publish an explicit approved-media allowlist and protect drafts. Current checkout does not establish whether production contains private uploads. |
| High, Flask | Private cache rules only cover HTML (`app.py:949`). The authenticated JSON backup returned no Cache-Control header. CSV output writes formulas unchanged (`app.py:488`); an isolated `=1+1` cell was not escaped. | Apply private/no-store headers to every private response and neutralize spreadsheet formula cells. |
| High, product behavior | Static mode returns no database news, no CMS text, default FAQs, and default assets (`fetch_news_posts`, `get_site_content_map`, `fetch_faq_items`, `get_asset_url`). Admin edits on a Flask host cannot update Cloudflare output. | Decide the source of published content and add one reviewed export/publish path, or simplify to version-controlled content. |
| Medium, registration | Two identical Flask POSTs created two student rows. `/register?success=1` can display confirmation without a stored application. Static browser fetch and upstream Cloudflare calls have no application timeout. | Restore Flask idempotency, receipt-backed confirmation, and bounded external requests. Keep the existing Apps Script deduplication. |
| Medium, Cloudflare | The handler trusts Content-Length for its size limit, accepts JSON without an object-shape guard, accepts a missing Turnstile action, and does not compare hostname (`functions/api/register.js`). | Restore actual-byte limits, shape validation, and Turnstile context checks. |
| Medium, storage and operations | Railway declares a `/data` mount but its start command does not select it; default SQLite lives in the application directory. DigitalOcean manifest enables deploy-on-push without a durable-data design. Render is the only manifest here explicitly pointing the DB to `/data`. | Choose the active backend host, verify real persistent storage, and test recovery before relying on it. Repository manifests do not prove dashboard state. |
| Medium, files and logs | File containment uses string-prefix comparisons, not resolved directory membership (`app.py:366`, `app.py:656`). Forwarding follows redirects with custom credential headers; error logging can include response bodies or token-bearing URLs (`app.py:689–797`). | Restore resolved path checks and sanitized logs; disable credential-bearing forwarding redirects. |
| Medium, backups | JSON backup omits FAQs and media file contents, limits audit records to 1,000 without metadata explaining that limit, and has no explicit consistent read transaction (`app.py:2168`). | Back up SQLite and uploads together, document retention, and exercise restoration. |
| Medium, maintenance | Runtime dependencies are unpinned. Reverting #22 removes the repository's GitHub Actions workflow and its security/browser tests. The remaining Python suite emitted unclosed SQLite connection warnings. | Restore a small CI workflow, tested dependency pins, and connection cleanup. Audit installed and deployed versions separately before making vulnerability claims. |
| Medium, admissions content | Contact defaults differ: registration config uses `+998701060404`, contact/schema/static WhatsApp defaults use `+998939461699`. Program cards advertise services that are not explicit registration choices. Verified fees, schedules, ages, durations and group sizes are absent. | Confirm one admissions contact and actual courses, then update config, copy and structured data together. |
| Medium, credibility/accessibility | Homepage hardcodes 500+ claims and animated counters beginning at zero. English relies on Google Translate. Mobile navigation, program reveals and FAQ interactions depend on JavaScript. | Obtain evidence for numerical claims, provide useful static fallbacks, and translate the pages that visitors actually need. |
| Operational, not verified | No evidence in this review establishes live Sheets receipt, staff ownership, alerting, privacy/retention procedures, backup restoration, deployed performance, or real-phone behavior. Firebase has no configured rewrite/backend for `/api/register`. | Verify one permitted end-to-end application on the active host; assign staff ownership and document failure handling. |

## What is overdone

1. **Release scope.** PR #22 mixed a complete visual/content rewrite with security,
   credential requirements and hosting behavior. A successful test run cannot
   establish approval of a redesign or readiness of host credentials. Split these
   into independently reviewable changes.
2. **Hosting choices.** Cloudflare, Firebase, Render, Railway, DigitalOcean and a
   Procfile all coexist. Contact delivery differs between Flask (database and bot)
   and static output (WhatsApp). Keep one production path and one clear local
   development path; archive unused recipes after confirming they are unused.
3. **Admin access tricks.** Hidden contact-form login, secret-access endpoint,
   configurable portal URL and interchangeable secret/password values add moving
   parts. One authenticated admin login is easier to maintain and secure. Two
   fields using the same default secret do not provide independent factors.
4. **Editable surface.** The CMS edits text, media, FAQs and news, but also allows
   editing application templates/CSS with a custom backup system. That is more
   power and maintenance than normal content updates need, especially when the
   production static build ignores CMS data. Prefer Git for code and limited CMS
   fields for staff.
5. **Frontend delivery.** Runtime Tailwind, a large local stylesheet, page-specific
   inline CSS/JS, Google Translate, icon/font CDNs and stock-photo requests are
   layered together. Compile required styles and keep shared interactions in one
   place; preserve the existing design while simplifying delivery.
6. **Content expansion in #22.** The change grew seven public pages to 26 localized
   routes, including results, student life, cooperation and a school project,
   despite outstanding staff facts. Prioritize accurate courses, contacts and a
   working application flow before expanding the sitemap.

Security checks, registration validation, server-side Turnstile verification,
Sheets deduplication and tests are justified. They should be recovered separately
from the reverted redesign.

## Verification performed

- Before rollback: all 25 Python tests passed, all three Node test files passed,
  and the 26-page static build and validator passed.
- After rollback: all seven remaining Python tests and both Node test files
  passed. The seven-page static build plus 404 and its validator passed.
- All seven public Flask routes and nine authenticated admin/list pages returned
  HTTP 200 against an isolated temporary database. All templates parsed.
- Isolated probes reproduced default-key session forgery, tokenless login/backup,
  missing backup cache headers/FAQs, unescaped CSV formulas, and duplicate Flask
  registrations. All external delivery was mocked during registration probes.
- `git diff 0434428 fc73c90 --exit-code` and whitespace checks passed.
- No fresh browser, accessibility scanner, dependency vulnerability scan, live
  delivery test, or host-dashboard inspection was performed in this review.

## Recommended sequence

1. Complete and verify the requested rollback deployment.
2. Recover only the security and data-protection fixes, with focused tests.
3. Confirm the active host, admissions contacts and live receipt/storage/backups.
4. Unify content publishing and remove unused hosting/login/editor complexity.
5. Make small content and usability changes within the restored design, each
   backed by confirmed staff information and browser checks.
