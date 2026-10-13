# Iceberg website upgrade checklist

Updated 13 October 2026. Changes are implemented in the workspace; they have not
been deployed. Institutional facts that were not supplied are requested through
admissions rather than fabricated.

## Implemented

- [x] Replace zero counters and unsupported student/IELTS/admission claims with useful educational information.
- [x] Explain the center, location, courses, admissions, and cooperation on the homepage.
- [x] Align advertised enrollment choices with the six configured programs.
- [x] Add course detail fields and fee inquiry links that preserve the selected program.
- [x] Use the configured central admissions number consistently and identify the G'ayrat branch separately.
- [x] Add dedicated Uzbek and English pages with language links, `lang`, and hreflang.
- [x] Create International Cooperation with proposed activities clearly distinguished from signed partnerships.
- [x] Create the separate private-school project page, with September 2027 clearly marked as planned.
- [x] Add admissions, results, student life, and privacy pages.
- [x] Keep existing teacher photographs and roles; link visitors to admissions for qualifications.
- [x] Replace contact inquiries with Telegram drafts in both Flask and static builds; visitors review and send in Telegram.
- [x] Keep course registration on its existing Flask/Cloudflare pipeline, with localized forms and errors.
- [x] Add a request timeout, preserve retry identifiers, and offer phone/Telegram alternatives.
- [x] Make navigation and FAQs usable without JavaScript; add skip links, visible focus, and reduced-motion support.
- [x] Remove Google Translate and runtime Tailwind CDN from public pages.
- [x] Add public CMS export for static news, text, FAQs, and approved media.
- [x] Exclude private tables, unpublished news, raw uploads, and unreferenced media from static publishing.
- [x] Extend the sitemap, static generator, and build checks for all 26 public pages.
- [x] Close SQLite connections when request operations finish.
- [x] Audit admin authentication, CSRF, private caching, CSV exports, media access, request bounds, and repeat submissions; add regression tests.
- [x] Test the site in Chromium at phone and desktop sizes, including dynamic/static registration and admin forms.
- [x] Pin runtime dependencies and add GitHub Actions checks. See [CODE_AUDIT.md](CODE_AUDIT.md).

## Staff facts and content still needed

- [ ] Verify current enrollment versus lifetime students taught, with reporting dates and evidence.
- [ ] Supply founding history and a timeline of educational activities.
- [ ] Confirm course ages/entry levels, duration, schedules, lesson length, group sizes, instructors, fees, and payment terms. The pages currently offer clear inquiry prompts.
- [ ] Verify phone numbers, Telegram accounts, email ownership, exact campus addresses, and opening hours.
- [ ] Supply verified teacher qualifications and teaching experience.
- [ ] Provide permitted original campus photographs, student projects, and dated student results.
- [ ] Publish genuine event reports using the CMS export workflow; no example events were created.
- [ ] Confirm any signed institutional partnerships and the cooperation contact email.
- [ ] Confirm the private-school project status and planned September 2027 opening.
- [ ] Review Uzbek/English copy and the privacy notice against actual operations, including retention and deletion handling.

## Release checks

- [ ] Confirm whether production uses Flask, Cloudflare Pages, or Firebase. Firebase currently needs separate backend routing for `/api/register`.
- [ ] Export existing approved CMS content from the actual database, review media permissions, and rebuild.
- [ ] Test keyboard navigation, menu operation, form errors, zoom, and layouts on real browsers and phones.
- [ ] Configure secure admin credentials, durable storage/backups, and production rate limits on the active host.
- [ ] Measure Lighthouse/PageSpeed performance and Core Web Vitals on the deployed site.
- [ ] Verify a permitted course application reaches responsible staff in production.
- [ ] Verify the Telegram admissions account can receive messages and drafts work in the target Telegram clients.
- [ ] Deploy the reviewed changes.

Automated checks cover bilingual routes, registration, Telegram draft encoding,
public export privacy, static assets, local links, form labels, landmarks,
hreflang targets, and sitemap coverage. These do not establish production delivery,
real-phone usability, or institutional accuracy.

## Later

- [ ] Add confirmed scholarships, public event calendar, and downloadable brochures.
- [ ] Expand school management features only when operational requirements are defined.
