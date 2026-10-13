# Repository code audit — 13 October 2026

The audit reviewed the Flask application and every route group, database helpers
and migrations, admin templates and browser scripts, public pages and styles,
Cloudflare registration function, Google Apps Script receiver, export/build/check
scripts, dependency declarations, and hosting/CI configuration. Existing images
and historical CSS backups are assets, not executable application code. Generated
output and third-party tooling were checked through their relevant tests rather
than treated as project source.

The audit found and fixed the issues below. This is a repository and isolated
browser audit; it is not a production penetration test or a verification of
institutional facts, host dashboards, account access, or live staff receipt.

## Findings and resolutions

| Severity | Finding | Resolution |
| --- | --- | --- |
| High | Known session/admin defaults and alternate secret-code passwords could grant administrative access. | Require a configured random session secret of at least 32 characters and a unique admin password of at least 12 characters. Reject the previous default, hash password comparisons, disable admin access when configuration is unsafe, and retire alternate code authentication. Public pages remain available. |
| High | Admin changes and login lacked CSRF protection; logout changed state via GET. | Add session CSRF tokens to all admin forms and JSON requests, validate them server-side, rotate session state after login, and make logout POST-only. Sessions have an eight-hour inactivity lifetime. |
| High | Private JSON/CSV downloads and registration responses could escape the HTML-only cache rule. | Apply no-store/private headers to all private response types, session-bearing responses, registrations, and protected news media. Add baseline Flask security headers. |
| High | Static builds copied all uploads, including unpublished or unreferenced files; Flask could directly serve unpublished news media. | Copy only snapshot-approved media into generated output, protect draft media on Flask, and exclude private tables and unsupported content keys from public export. |
| Medium | CSV cells could execute spreadsheet formulas supplied in a name or message. | Neutralize formula prefixes and leading control/whitespace variants before export; preserve ordinary text. |
| Medium | Prefix-based filesystem containment could accept sibling paths or symlinks outside the intended directory. | Resolve paths and check directory membership, restrict media deletion to uploads, and retain the editor's exact file allowlist. Add traversal/symlink regression tests. |
| Medium | Registration trusted Content-Length alone, accepted invalid JSON shapes, and only partially checked Turnstile response context. | Limit actual streamed request bytes, reject non-object JSON, bound external requests, and require the expected action and request hostname. Follow Cloudflare's [server-side validation guidance](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/). |
| Medium | Repeating a Flask submission could duplicate records and notifications; a success query parameter alone could claim receipt. | Store a unique submission UUID, deduplicate atomically, forward/notify once, and require a session marker established after storage before showing server confirmation. Static HTML does not contain a shared frozen UUID. |
| Medium | Management forwarding could follow redirects with custom credential headers, and error logs could retain response bodies or token-bearing URLs. | Disable forwarding redirects, log status/error classes instead of payloads, and keep Telegram tokens out of exception messages. |
| Medium | Hosting configuration did not consistently match durable SQLite storage. | Point Railway at `/data/database.db`; declare secure admin settings in hosting manifests; disable deploy-on-push in the checked-in DigitalOcean spec. Actual volume attachment and existing dashboard settings still require verification. |
| Low | SQLite connections remained open after request operations. | Close connections reliably while preserving commit/rollback behavior. |
| Low | Database backup omitted FAQs and could span inconsistent reads. | Include FAQs, read within one transaction, and identify the recent audit-log limit. Uploaded files require a separate backup. |
| Low | The FAQ editor crashed when Sortable failed to load; canceled admin confirmations could still disable buttons. | Guard the optional library and respect canceled submit events. Basic FAQ editing remains usable. |
| Low | Old CMS controls described fields/assets no longer used by the public templates. | Limit standard controls to active fields/assets and expose the public CSS file in the trusted admin editor. Custom template editing remains an explicitly trusted administrator capability. |
| Low | Public copy had unsupported outcomes, zero counters, mismatched enrollment choices, and only machine translation. | Replace unsupported claims, align courses with configuration, add fee/details inquiry paths, and provide 26 dedicated Uzbek/English pages with language alternates. |

## Validation

- **25 Python tests passed**, covering registration, language pairs, admin
  authentication/CSRF, private cache headers, SQL-field rejection, CSV injection,
  duplicate submissions, confirmation state, traversal, draft media, and safe
  public export/build copying.
- **16 JavaScript test cases passed** across the Cloudflare handler, Apps Script
  receiver, and Telegram draft encoding. The npm test command also passed.
  The widget uses a supported English or automatic language setting, following
  [Turnstile's supported language list](https://developers.cloudflare.com/turnstile/reference/supported-languages/).
- **Static generation and checks passed**: 26 public pages plus the 404 page,
  local references, language targets, form labels, one main/h1 per public page,
  sitemap entries, required registration configuration, and private markers.
- **Chromium checks passed** for all 26 public routes at 375px and 1280px;
  language switching and course/branch preservation; Flask and generated static
  registration; Telegram draft encoding; admin login/forms; and native menu/FAQ
  behavior with JavaScript disabled. All external message delivery was mocked.
  Homepage screenshots were visually inspected. This is viewport testing, not
  testing on physical phones.
- **Bandit completed with no untriaged findings.** Reviewed waivers are documented
  inline: the old password literal is a rejection check, and interpolated SQL is
  limited to fixed column allowlists or `?` placeholders with bound values.
  Regression tests exercise rejection of malicious column input. The scanner is
  a supplement to manual review, not proof that the application has no defects.
- **pip-audit reported no known vulnerabilities** for the final pinned runtime
  requirements. Third-party admin CDNs are not covered by that Python scan.
- **Git whitespace checks passed.** GitHub Actions now repeats the Python/Node
  tests and static checks on pull requests and main; action revisions are pinned.

## Deployment and content follow-ups

1. Set secure `SECRET_KEY` and `ADMIN_PASSWORD` on any live Flask host. Unsafe or
   missing settings disable the admin interface. The public/static site continues
   to work. Previous `ADMIN_SECRET_CODE` logins are no longer accepted.
2. Confirm persistent SQLite storage and separate media backups on the selected
   Flask host. Railway's JSON declaration is not proof that a volume is attached.
   DigitalOcean App Platform's local filesystem resets on redeployment and does
   not support persistent volumes; a durable database/media design is required
   before using this backend there. See [DigitalOcean storage documentation](https://docs.digitalocean.com/products/app-platform/how-to/store-data/).
   The manifest change does not retroactively modify a live dashboard.
3. GitHub's pre-change main check showed a successful Cloudflare Pages deployment;
   the repository also contains historical Render deployment records. Live
   secrets, storage, custom domains, and backups were not accessible in this audit.
4. Verify Cloudflare Turnstile domains/secrets, the current Apps Script deployment,
   staff access to the receiving sheet, and one permitted production submission.
   Firebase Hosting still requires a separately configured `/api/register` backend.
5. Configure persistent production rate limits and monitoring for login and public
   forms at the hosting/edge layer. Review retention/deletion and backup access.
6. Export and review actual approved CMS content before publishing it on a static
   host. Staff must supply verified fees, schedules, founding history, results,
   photographs, event reports, cooperation details, and school project updates.
7. Measure deployed Lighthouse/Core Web Vitals and test on actual phones. Local
   Chromium checks do not measure the user's network or production services.

The planned school remains clearly identified as a separate project with opening
planned for September 2027. No completed partnership, tuition, event, achievement,
or student total was fabricated during these changes.
