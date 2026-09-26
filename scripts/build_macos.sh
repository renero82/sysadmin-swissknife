#!/usr/bin/env bash
# Local build of "Sysadmin Swissknife.app" (for testing before a release).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv-build
source .venv-build/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt pyinstaller pillow pytest
python -m pytest -q tests
pyinstaller --noconfirm sysadmin_swissknife.spec
"dist/Sysadmin Swissknife.app/Contents/MacOS/Sysadmin Swissknife" --selftest
echo
echo "Done: dist/Sysadmin Swissknife.app"
echo "Open it with:  open \"dist/Sysadmin Swissknife.app\""
