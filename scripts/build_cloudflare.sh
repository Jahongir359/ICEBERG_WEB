#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Cloudflare Pages provides Python, but project dependencies are not installed
# unless the build explicitly requests them.
python -m pip install --disable-pip-version-check -r requirements.txt

python scripts/build_firebase.py
python scripts/check_firebase_build.py
