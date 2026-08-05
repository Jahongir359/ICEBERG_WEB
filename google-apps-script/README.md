# Google Sheets registration receiver

1. Create a Google Sheet and copy its ID from the URL between `/d/` and `/edit`.
2. Open **Extensions > Apps Script** and replace `Code.gs` with this directory's `Code.gs`.
3. In Apps Script, open **Project Settings > Script properties** and add:
   - `SHEET_ID`: the copied spreadsheet ID
   - `WEBHOOK_SECRET`: a long random value (use at least 32 random bytes)
4. Select **Deploy > New deployment > Web app**.
5. Set **Execute as** to **Me** and access to **Anyone**.
6. Authorize the script and copy the deployment URL ending in `/exec`.
7. In Cloudflare Pages, add these encrypted secrets for both production and preview:
   - `GOOGLE_SCRIPT_URL`: the `/exec` deployment URL
   - `GOOGLE_SCRIPT_SECRET`: the same value as `WEBHOOK_SECRET`
   - `TURNSTILE_SECRET_KEY`: the secret from the Cloudflare Turnstile widget
8. Add `PUBLIC_TURNSTILE_SITE_KEY` as a plain build environment variable.
9. Redeploy the Pages project after adding the values.

Never put `GOOGLE_SCRIPT_SECRET` or `TURNSTILE_SECRET_KEY` in Git or a public build variable.
