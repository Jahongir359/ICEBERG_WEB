# ICEBERG Google Sheets registration setup

Production flow:

`/register` → Cloudflare Pages Function → Turnstile → Apps Script web app → Google Sheet

The browser never receives the Google Sheet ID, Apps Script URL, webhook secret, or
Turnstile secret. Follow every step below; the form intentionally fails closed if a
server-side value is missing or mismatched.

## 1. Create the destination spreadsheet

1. Sign in to the Google account that should own ICEBERG registration data.
2. Create a new Google Sheet, for example **ICEBERG Website Registrations**.
3. Copy the spreadsheet ID from its URL. In
   `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`, copy only the value
   between `/d/` and `/edit`.
4. Keep the sheet private and share it only with staff who need lead access. The sheet
   does **not** need link sharing enabled.

Do not manually create columns. The included receiver creates a tab named
`Registrations` with these columns:

`ID`, `Submitted At`, `Student Name`, `Phone`, `Program ID`, `Branch ID`,
`UTM Source`, `UTM Medium`, `UTM Campaign`, `Page URL`, `Referrer`, `Status`,
`Staff Notes`.

## 2. Create and configure the Apps Script receiver

1. In the spreadsheet, select **Extensions → Apps Script**.
2. Open `Code.gs`, delete its sample content, and paste the complete contents of this
   repository's `google-apps-script/Code.gs`.
3. Save the project and give it a clear name such as **ICEBERG Registration Receiver**.
4. Generate a webhook secret locally:

   ```bash
   openssl rand -hex 32
   ```

5. In Apps Script, open **Project Settings → Script properties → Add script property**.
6. Add exactly these two properties (names are case-sensitive):

   | Property | Value |
   |---|---|
   | `SHEET_ID` | The spreadsheet ID copied in step 1 |
   | `WEBHOOK_SECRET` | The 64-character random value generated above |

7. Return to the editor, choose `setup` from the function selector, and click **Run**.
8. Approve the requested Google Sheets permissions. If Google shows an unverified-app
   warning for your own script, review that the script is yours before continuing.
9. Confirm the execution succeeds. The spreadsheet should now contain a
   `Registrations` tab with a frozen header row.

Running `setup` is safe on an existing registration sheet: it preserves existing rows
and adds any missing expected columns.

## 3. Deploy the Apps Script as a web app

1. Select **Deploy → New deployment**.
2. Next to **Select type**, choose **Web app**.
3. Set **Execute as** to **Me** (the spreadsheet owner).
4. Set **Who has access** to **Anyone**. Incoming requests are still authenticated by
   `WEBHOOK_SECRET`; users do not receive access to the spreadsheet.
5. Click **Deploy**, authorize if prompted, and copy the URL ending in `/exec`.

Do not use the `/dev` test URL. It works only for script editors and is not a production
endpoint.

Open the `/exec` URL in a private browser window. A correct deployment returns JSON
similar to:

```json
{
  "ok": true,
  "service": "ICEBERG registration receiver",
  "version": "2026-08-08.1",
  "sheet_ready": true
}
```

If `ok` or `sheet_ready` is false, do not continue until `setup` succeeds and the web
app health response is correct.

If **Anyone** is unavailable, the Google Workspace administrator is blocking anonymous
web apps. The public website cannot use that deployment until the administrator permits
it or the receiver is deployed from an account that can publish an anonymous web app.

## 4. Configure Turnstile

1. In Cloudflare, open **Turnstile** and create a widget named, for example,
   **ICEBERG Registration**.
2. Add `iceberglc.com` as an allowed hostname. Add preview hostnames only when you
   intentionally test previews; preferably use a separate preview widget.
3. Copy both generated values:
   - **Site key**: public and embedded in generated registration HTML.
   - **Secret key**: private and used only by the Pages Function.

The site key and secret key must come from the same widget. Production Turnstile keys
cannot be mixed with Cloudflare's test keys.

## 5. Configure Cloudflare Pages

This project uses `wrangler.toml` as the Cloudflare Pages configuration source of truth.
The Dashboard therefore shows plain environment variables as read-only and allows only
encrypted Secrets to be edited.

The two public values are checked into `wrangler.toml` under `[vars]`:

```toml
[vars]
PUBLIC_SITE_URL = "https://iceberglc.com"
PUBLIC_TURNSTILE_SITE_KEY = "0x4AAAAAAEGkDLLEm8ptwrlK"
```

The Turnstile site key is intentionally public. When it changes, update
`PUBLIC_TURNSTILE_SITE_KEY` in `wrangler.toml`, commit the change, and redeploy. The
static build reads this file directly so the widget key is present in generated HTML.

Open **Workers & Pages → ICEBERG Pages project → Settings → Variables and Secrets** and
add only these encrypted **Production Secrets**:

| Name | Exact value |
|---|---|
| `TURNSTILE_SECRET_KEY` | Secret key matching the public Turnstile site key |
| `GOOGLE_SCRIPT_URL` | Apps Script deployment URL ending in `/exec` |
| `GOOGLE_SCRIPT_SECRET` | Exactly the same value as Apps Script `WEBHOOK_SECRET` |

Important checks:

- Do not add quotes, spaces, or a trailing newline to any value.
- `GOOGLE_SCRIPT_SECRET` and `WEBHOOK_SECRET` must match character-for-character.
- The Apps Script URL must begin with `https://script.google.com/macros/s/` and end
  with `/exec`.
- Never put `GOOGLE_SCRIPT_SECRET` or `TURNSTILE_SECRET_KEY` in `wrangler.toml`, Git,
  frontend JavaScript, or generated HTML.
- Add equivalent Secrets under **Preview** only if preview registrations should work.
  Prefer a different test sheet, webhook secret, and Turnstile widget for previews.

After saving the Secrets, create a fresh production deployment. A redeploy is required
for both the Function bindings and the public Turnstile key in generated HTML.

## 6. Verify production end to end

1. Open `https://iceberglc.com/register` in a private browser window.
2. Confirm the Turnstile widget loads without a domain error.
3. Submit a clearly labeled test lead, for example `ICEBERG SETUP TEST`.
4. Confirm the page displays `Arizangiz qabul qilindi!`.
5. Open the spreadsheet and confirm exactly one new row appears with:
   - a unique `ID`;
   - the current `Submitted At` timestamp;
   - normalized phone such as `+998901234567`;
   - stable `Program ID` such as `ielts`;
   - stable `Branch ID` such as `main`, `gayrat`, or `unknown`.
6. Delete the test row manually after verification if it is not needed.

Do not treat a visible Turnstile checkmark as proof that Sheets is configured. Turnstile
only verifies the visitor; success is shown only after Apps Script confirms the row was
saved.

## Updating the receiver later

Saving `Code.gs` does not update the live `/exec` version.

1. Save the edited code.
2. Run `setup` once if columns or setup logic changed.
3. Select **Deploy → Manage deployments**.
4. Edit the active web-app deployment.
5. Select **New version**, then click **Deploy**.
6. Reopen the `/exec` URL and verify the reported version.

Editing the existing deployment normally preserves its `/exec` URL. If a new deployment
produces a different URL, update `GOOGLE_SCRIPT_URL` in Cloudflare and redeploy Pages.

## Troubleshooting

### `Ro'yxatdan o'tish xizmati hali sozlanmagan.`

`GOOGLE_SCRIPT_URL` or `GOOGLE_SCRIPT_SECRET` is missing/invalid in the Cloudflare
Production environment. Confirm the URL is the `/exec` URL and redeploy.

### `Xavfsizlik tekshiruvidan qayta o'ting.`

The Turnstile token was missing, expired, already used, issued for another hostname, or
validated with a non-matching secret. Confirm the site/secret key pair and allowed
hostname, refresh the page, then submit once.

### `Arizani saqlab bo'lmadi.`

Turnstile succeeded, but Apps Script did not confirm storage. Check in this order:

1. Open `GOOGLE_SCRIPT_URL` directly and require `ok:true` and `sheet_ready:true`.
2. Confirm it reports receiver version `2026-08-08.1` or newer.
3. Compare Apps Script `WEBHOOK_SECRET` with Cloudflare `GOOGLE_SCRIPT_SECRET`.
4. In Apps Script, open **Executions** and inspect the newest `doPost` failure.
5. In Cloudflare, open the Pages deployment's Function logs and search for the
   `reference` value returned by the website.
6. Confirm the deploying Google account still owns or can edit the spreadsheet.
7. Run `setup`, publish a **New version**, and redeploy Cloudflare Pages.

### The submission succeeds but no row appears

Verify that you are viewing the spreadsheet identified by `SHEET_ID` and the tab named
`Registrations`. Do not point production and preview at the same sheet unintentionally.

## Secret rotation

To rotate the webhook secret without exposing it:

1. Generate a new secret.
2. Update Apps Script `WEBHOOK_SECRET`.
3. Update Cloudflare `GOOGLE_SCRIPT_SECRET` immediately afterward.
4. Redeploy Pages and submit one test lead.

There may be a short failure window between steps 2 and 3, so perform rotation during a
low-traffic period. Rotate the Turnstile secret separately from the Turnstile dashboard
and update `TURNSTILE_SECRET_KEY` in Cloudflare.
