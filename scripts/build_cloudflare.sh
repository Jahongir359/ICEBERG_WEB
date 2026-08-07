#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Cloudflare Pages provides Python, but project dependencies are not installed
# unless the build explicitly requests them.
python -m pip install --disable-pip-version-check -r requirements.txt

# Canonicals default to the production domain in build_firebase.py. Preview
# deployment URLs must never become canonical URLs.

python scripts/build_firebase.py
python scripts/check_firebase_build.py
