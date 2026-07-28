#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Cloudflare Pages provides Python, but project dependencies are not installed
# unless the build explicitly requests them.
python -m pip install --disable-pip-version-check -r requirements.txt

# Use the deployment URL for preview metadata. The custom production domain can
# still be supplied explicitly with PUBLIC_SITE_URL in the Pages environment.
if [[ -z "${PUBLIC_SITE_URL:-}" && -n "${CF_PAGES_URL:-}" ]]; then
  export PUBLIC_SITE_URL="$CF_PAGES_URL"
fi

python scripts/build_firebase.py
python scripts/check_firebase_build.py

